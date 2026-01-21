"""
数据获取模块 - 负责从数据源获取A股数据
"""
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import json
import time
from pathlib import Path
from typing import Optional, Dict, List
import logging

from .config import (
    DAILY_DATA_DIR, 
    ANALYSIS_PERIODS, 
    CHINA_TZ,
    EXCLUDE_ST,
    MIN_PRICE,
    get_china_now
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StockDataFetcher:
    """A股数据获取器"""
    
    def __init__(self):
        self.cache = {}
        
    def get_all_stocks(self) -> pd.DataFrame:
        """获取所有A股股票列表"""
        try:
            # 获取A股股票列表
            stock_info = ak.stock_info_a_code_name()
            logger.info(f"获取到 {len(stock_info)} 只股票")
            return stock_info
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return pd.DataFrame()
    
    def get_stock_daily_data(
        self, 
        symbol: str, 
        days: int = 30
    ) -> Optional[pd.DataFrame]:
        """
        获取单只股票的日线数据
        
        Args:
            symbol: 股票代码
            days: 获取天数
            
        Returns:
            DataFrame with columns: date, open, high, low, close, volume, amount
        """
        try:
            # 计算日期范围
            end_date = get_china_now().strftime('%Y%m%d')
            start_date = (get_china_now() - timedelta(days=days + 30)).strftime('%Y%m%d')
            
            # 使用akshare获取数据
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq"  # 前复权
            )
            
            if df.empty:
                return None
                
            # 标准化列名
            df = df.rename(columns={
                '日期': 'date',
                '开盘': 'open',
                '收盘': 'close',
                '最高': 'high',
                '最低': 'low',
                '成交量': 'volume',
                '成交额': 'amount',
                '涨跌幅': 'pct_change',
                '换手率': 'turnover'
            })
            
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').tail(days)
            
            return df
            
        except Exception as e:
            logger.debug(f"获取 {symbol} 数据失败: {e}")
            return None
    
    def get_realtime_quotes(self) -> pd.DataFrame:
        """获取实时行情数据（用于快速获取当日数据）"""
        try:
            # 获取A股实时行情
            df = ak.stock_zh_a_spot_em()
            
            # 标准化列名
            df = df.rename(columns={
                '代码': 'symbol',
                '名称': 'name',
                '最新价': 'price',
                '涨跌幅': 'pct_change',
                '涨跌额': 'change',
                '成交量': 'volume',
                '成交额': 'amount',
                '振幅': 'amplitude',
                '最高': 'high',
                '最低': 'low',
                '今开': 'open',
                '昨收': 'pre_close',
                '换手率': 'turnover',
                '市盈率-动态': 'pe',
                '市净率': 'pb',
                '总市值': 'market_cap',
                '流通市值': 'float_market_cap'
            })
            
            logger.info(f"获取到 {len(df)} 只股票的实时行情")
            return df
            
        except Exception as e:
            logger.error(f"获取实时行情失败: {e}")
            return pd.DataFrame()
    
    def get_historical_ranking_data(self) -> Dict[str, pd.DataFrame]:
        """
        获取用于排行的历史数据
        
        Returns:
            Dict with period as key and DataFrame as value
        """
        logger.info("开始获取历史数据...")
        
        # 先获取实时行情作为基础
        realtime_df = self.get_realtime_quotes()
        
        if realtime_df.empty:
            logger.error("无法获取实时行情")
            return {}
        
        # 过滤无效数据
        realtime_df = self._filter_stocks(realtime_df)
        
        # 获取需要的最大天数的历史数据
        max_days = max(ANALYSIS_PERIODS) + 5
        
        result = {}
        
        # 获取每只股票的历史数据并计算区间涨跌幅
        for period in ANALYSIS_PERIODS:
            logger.info(f"计算 {period} 日涨跌幅...")
            period_data = self._calculate_period_change(
                realtime_df.copy(), 
                period
            )
            result[f"{period}d"] = period_data
            
        return result
    
    def _filter_stocks(self, df: pd.DataFrame) -> pd.DataFrame:
        """过滤股票"""
        original_count = len(df)
        
        # 过滤ST股票
        if EXCLUDE_ST:
            df = df[~df['name'].str.contains('ST|退', na=False)]
        
        # 过滤低价股
        df = df[df['price'] >= MIN_PRICE]
        
        # 过滤停牌股票（成交量为0）
        df = df[df['volume'] > 0]
        
        # 过滤涨跌幅异常的（可能是新股或复牌）
        df = df[df['pct_change'].abs() <= 20]
        
        logger.info(f"过滤后剩余 {len(df)}/{original_count} 只股票")
        
        return df
    
    def _calculate_period_change(
        self, 
        df: pd.DataFrame, 
        period: int
    ) -> pd.DataFrame:
        """
        计算指定周期的涨跌幅
        
        使用批量获取历史数据的方式提高效率
        """
        try:
            # 使用akshare获取所有股票的历史涨跌幅数据
            # 这里我们用一个更高效的方法
            
            result_list = []
            total = len(df)
            
            for idx, row in df.iterrows():
                symbol = row['symbol']
                
                if idx % 100 == 0:
                    logger.info(f"处理进度: {idx}/{total}")
                
                try:
                    # 获取历史数据
                    hist_df = self.get_stock_daily_data(symbol, period + 5)
                    
                    if hist_df is None or len(hist_df) < period:
                        continue
                    
                    # 计算区间涨跌幅
                    close_prices = hist_df['close'].values
                    if len(close_prices) >= period:
                        period_start_price = close_prices[-(period+1)] if len(close_prices) > period else close_prices[0]
                        period_end_price = close_prices[-1]
                        period_change = (period_end_price - period_start_price) / period_start_price * 100
                        
                        result_list.append({
                            'symbol': symbol,
                            'name': row['name'],
                            'price': row['price'],
                            'period_change': round(period_change, 2),
                            'market_cap': row.get('market_cap', 0),
                            'turnover': row.get('turnover', 0)
                        })
                        
                except Exception as e:
                    continue
                
                # 避免请求过快
                time.sleep(0.05)
            
            result_df = pd.DataFrame(result_list)
            return result_df
            
        except Exception as e:
            logger.error(f"计算 {period} 日涨跌幅失败: {e}")
            return pd.DataFrame()


class FastDataFetcher:
    """快速数据获取器 - 使用汇总接口减少请求次数"""
    
    def get_period_ranking(self) -> Dict[str, Dict]:
        """
        获取各周期排行数据
        使用更高效的方式获取数据
        """
        try:
            result = {}
            
            for period in ANALYSIS_PERIODS:
                logger.info(f"获取 {period} 日涨跌排行...")
                
                # 获取涨幅排行
                top_gainers = self._get_gainers_ranking(period)
                
                # 获取跌幅排行
                top_losers = self._get_losers_ranking(period)
                
                result[f"{period}d"] = {
                    'gainers': top_gainers,
                    'losers': top_losers
                }
                
                time.sleep(0.5)
            
            return result
            
        except Exception as e:
            logger.error(f"获取排行数据失败: {e}")
            return {}
    
    def _get_gainers_ranking(self, period: int) -> List[Dict]:
        """获取涨幅排行"""
        try:
            # 使用akshare的排行榜接口
            if period == 5:
                df = ak.stock_zh_a_spot_em()
            else:
                df = ak.stock_zh_a_spot_em()
            
            # 这里需要根据实际接口调整
            # 简化处理：使用实时数据模拟
            
            df = self._filter_valid_stocks(df)
            
            # 取涨幅前10
            df = df.nlargest(10, '涨跌幅')
            
            result = []
            for _, row in df.iterrows():
                result.append({
                    'symbol': row['代码'],
                    'name': row['名称'],
                    'price': float(row['最新价']) if pd.notna(row['最新价']) else 0,
                    'change': float(row['涨跌幅']) if pd.notna(row['涨跌幅']) else 0,
                    'volume': float(row['成交额']) if pd.notna(row['成交额']) else 0
                })
            
            return result
            
        except Exception as e:
            logger.error(f"获取涨幅排行失败: {e}")
            return []
    
    def _get_losers_ranking(self, period: int) -> List[Dict]:
        """获取跌幅排行"""
        try:
            df = ak.stock_zh_a_spot_em()
            df = self._filter_valid_stocks(df)
            
            # 取跌幅前10
            df = df.nsmallest(10, '涨跌幅')
            
            result = []
            for _, row in df.iterrows():
                result.append({
                    'symbol': row['代码'],
                    'name': row['名称'],
                    'price': float(row['最新价']) if pd.notna(row['最新价']) else 0,
                    'change': float(row['涨跌幅']) if pd.notna(row['涨跌幅']) else 0,
                    'volume': float(row['成交额']) if pd.notna(row['成交额']) else 0
                })
            
            return result
            
        except Exception as e:
            logger.error(f"获取跌幅排行失败: {e}")
            return []
    
    def _filter_valid_stocks(self, df: pd.DataFrame) -> pd.DataFrame:
        """过滤有效股票"""
        # 过滤ST
        df = df[~df['名称'].str.contains('ST|退', na=False)]
        # 过滤停牌
        df = df[df['成交量'] > 0]
        # 过滤异常涨跌幅
        df = df[(df['涨跌幅'] > -20) & (df['涨跌幅'] < 20)]
        # 过滤低价股
        df = df[df['最新价'] >= 1]
        
        return df