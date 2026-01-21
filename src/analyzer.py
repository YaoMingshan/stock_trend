"""
数据分析模块 - 负责计算涨跌排行和趋势分析
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import json
import logging
import akshare as ak
import time

from .config import (
    ANALYSIS_PERIODS,
    TOP_N,
    ANALYSIS_DIR,
    get_china_now,
    EXCLUDE_ST,
    MIN_PRICE
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StockAnalyzer:
    """股票分析器"""
    
    def __init__(self):
        self.analysis_date = get_china_now().strftime('%Y-%m-%d')
    
    def analyze_period_ranking(self) -> Dict:
        """
        分析各周期涨跌排行
        
        Returns:
            {
                "update_time": "2024-01-15 15:30:00",
                "periods": {
                    "5d": {"gainers": [...], "losers": [...]},
                    "10d": {"gainers": [...], "losers": [...]},
                    "20d": {"gainers": [...], "losers": [...]}
                }
            }
        """
        logger.info("开始分析涨跌排行...")
        
        result = {
            "update_time": get_china_now().strftime('%Y-%m-%d %H:%M:%S'),
            "analysis_date": self.analysis_date,
            "periods": {}
        }
        
        # 获取实时行情作为基础数据
        try:
            realtime_df = ak.stock_zh_a_spot_em()
            realtime_df = self._preprocess_realtime_data(realtime_df)
        except Exception as e:
            logger.error(f"获取实时行情失败: {e}")
            return result
        
        # 分析各个周期
        for period in ANALYSIS_PERIODS:
            logger.info(f"分析 {period} 日涨跌排行...")
            period_result = self._analyze_single_period(realtime_df, period)
            result["periods"][f"{period}d"] = period_result
        
        # 添加市场概况
        result["market_overview"] = self._get_market_overview(realtime_df)
        
        # 保存分析结果
        self._save_analysis_result(result)
        
        return result
    
    def _preprocess_realtime_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """预处理实时数据"""
        # 重命名列
        column_mapping = {
            '代码': 'symbol',
            '名称': 'name',
            '最新价': 'price',
            '涨跌幅': 'pct_change',
            '涨跌额': 'change_amount',
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
            '流通市值': 'float_market_cap',
            '涨速': 'change_speed',
            '5分钟涨跌': 'change_5min',
            '60日涨跌幅': 'change_60d',
            '年初至今涨跌幅': 'change_ytd'
        }
        
        df = df.rename(columns=column_mapping)
        
        # 过滤无效数据
        df = df[df['price'].notna() & (df['price'] > 0)]
        
        # 过滤ST
        if EXCLUDE_ST:
            df = df[~df['name'].str.contains('ST|退|\*', na=False, regex=True)]
        
        # 过滤低价股
        df = df[df['price'] >= MIN_PRICE]
        
        # 过滤停牌
        df = df[df['volume'] > 0]
        
        # 过滤涨跌停（新股等）
        df = df[(df['pct_change'] > -11) & (df['pct_change'] < 11)]
        
        logger.info(f"预处理后剩余 {len(df)} 只股票")
        
        return df
    
    def _analyze_single_period(
        self, 
        base_df: pd.DataFrame, 
        period: int
    ) -> Dict:
        """分析单个周期的涨跌排行"""
        
        result = {
            "period_days": period,
            "gainers": [],
            "losers": [],
            "statistics": {}
        }
        
        # 获取历史数据计算区间涨跌幅
        stock_changes = []
        
        symbols = base_df['symbol'].tolist()
        total = len(symbols)
        
        logger.info(f"开始计算 {total} 只股票的 {period} 日涨跌幅...")
        
        for idx, symbol in enumerate(symbols):
            if idx % 200 == 0 and idx > 0:
                logger.info(f"进度: {idx}/{total}")
            
            try:
                # 获取历史数据
                hist_df = ak.stock_zh_a_hist(
                    symbol=symbol,
                    period="daily",
                    start_date=(get_china_now() - timedelta(days=period + 10)).strftime('%Y%m%d'),
                    end_date=get_china_now().strftime('%Y%m%d'),
                    adjust="qfq"
                )
                
                if hist_df is None or len(hist_df) < period:
                    continue
                
                # 计算区间涨跌幅
                closes = hist_df['收盘'].values
                if len(closes) >= period + 1:
                    start_price = closes[-(period + 1)]
                    end_price = closes[-1]
                    period_change = (end_price - start_price) / start_price * 100
                    
                    stock_info = base_df[base_df['symbol'] == symbol].iloc[0]
                    
                    stock_changes.append({
                        'symbol': symbol,
                        'name': stock_info['name'],
                        'price': float(stock_info['price']),
                        'period_change': round(period_change, 2),
                        'today_change': float(stock_info['pct_change']),
                        'turnover': float(stock_info['turnover']) if pd.notna(stock_info['turnover']) else 0,
                        'market_cap': float(stock_info['market_cap']) / 100000000 if pd.notna(stock_info['market_cap']) else 0  # 转为亿
                    })
                    
            except Exception as e:
                continue
            
            # 控制请求频率
            time.sleep(0.02)
        
        if not stock_changes:
            return result
        
        # 转换为DataFrame进行排序
        changes_df = pd.DataFrame(stock_changes)
        
        # 获取涨幅TOP10
        top_gainers = changes_df.nlargest(TOP_N, 'period_change')
        result['gainers'] = top_gainers.to_dict('records')
        
        # 获取跌幅TOP10
        top_losers = changes_df.nsmallest(TOP_N, 'period_change')
        result['losers'] = top_losers.to_dict('records')
        
        # 统计信息
        result['statistics'] = {
            'total_stocks': len(changes_df),
            'avg_change': round(changes_df['period_change'].mean(), 2),
            'median_change': round(changes_df['period_change'].median(), 2),
            'up_count': int((changes_df['period_change'] > 0).sum()),
            'down_count': int((changes_df['period_change'] < 0).sum()),
            'up_ratio': round((changes_df['period_change'] > 0).sum() / len(changes_df) * 100, 2)
        }
        
        return result
    
    def _get_market_overview(self, df: pd.DataFrame) -> Dict:
        """获取市场概况"""
        return {
            'total_stocks': len(df),
            'up_stocks': int((df['pct_change'] > 0).sum()),
            'down_stocks': int((df['pct_change'] < 0).sum()),
            'flat_stocks': int((df['pct_change'] == 0).sum()),
            'limit_up': int((df['pct_change'] >= 9.9).sum()),
            'limit_down': int((df['pct_change'] <= -9.9).sum()),
            'avg_change': round(df['pct_change'].mean(), 2),
            'total_amount': round(df['amount'].sum() / 100000000, 2)  # 亿元
        }
    
    def _save_analysis_result(self, result: Dict):
        """保存分析结果"""
        # 保存到analysis目录
        filename = f"analysis_{self.analysis_date}.json"
        filepath = ANALYSIS_DIR / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        logger.info(f"分析结果已保存到: {filepath}")


class SimplifiedAnalyzer:
    """简化版分析器 - 减少API调用，提高效率"""
    
    def __init__(self):
        self.analysis_date = get_china_now().strftime('%Y-%m-%d')
    
    def quick_analyze(self) -> Dict:
        """
        快速分析 - 使用更少的API调用
        主要使用市场排行接口
        """
        logger.info("开始快速分析...")
        
        result = {
            "update_time": get_china_now().strftime('%Y-%m-%d %H:%M:%S'),
            "analysis_date": self.analysis_date,
            "periods": {},
            "market_overview": {}
        }
        
        try:
            # 获取实时行情
            df = ak.stock_zh_a_spot_em()
            df = self._filter_stocks(df)
            
            # 获取市场概况
            result["market_overview"] = self._calc_market_overview(df)
            
            # 对于不同周期，我们采样计算
            for period in ANALYSIS_PERIODS:
                logger.info(f"快速分析 {period} 日数据...")
                result["periods"][f"{period}d"] = self._quick_period_analysis(df, period)
                
        except Exception as e:
            logger.error(f"快速分析失败: {e}")
        
        return result
    
    def _filter_stocks(self, df: pd.DataFrame) -> pd.DataFrame:
        """过滤股票"""
        df = df[df['最新价'].notna() & (df['最新价'] > 1)]
        df = df[~df['名称'].str.contains('ST|退', na=False)]
        df = df[df['成交量'] > 0]
        df = df[(df['涨跌幅'] > -11) & (df['涨跌幅'] < 11)]
        return df
    
    def _calc_market_overview(self, df: pd.DataFrame) -> Dict:
        """计算市场概况"""
        return {
            'total_stocks': len(df),
            'up_stocks': int((df['涨跌幅'] > 0).sum()),
            'down_stocks': int((df['涨跌幅'] < 0).sum()),
            'limit_up': int((df['涨跌幅'] >= 9.9).sum()),
            'limit_down': int((df['涨跌幅'] <= -9.9).sum()),
            'avg_change': round(df['涨跌幅'].mean(), 2),
            'total_amount': round(df['成交额'].sum() / 100000000, 2)
        }
    
    def _quick_period_analysis(self, base_df: pd.DataFrame, period: int) -> Dict:
        """
        快速周期分析
        采样200只股票进行分析
        """
        # 随机采样以减少API调用
        sample_size = min(300, len(base_df))
        sample_df = base_df.sample(n=sample_size, random_state=42)
        
        stock_changes = []
        
        for _, row in sample_df.iterrows():
            symbol = row['代码']
            try:
                hist = ak.stock_zh_a_hist(
                    symbol=symbol,
                    period="daily",
                    start_date=(get_china_now() - timedelta(days=period + 10)).strftime('%Y%m%d'),
                    end_date=get_china_now().strftime('%Y%m%d'),
                    adjust="qfq"
                )
                
                if hist is None or len(hist) < period:
                    continue
                
                closes = hist['收盘'].values
                if len(closes) >= period + 1:
                    change = (closes[-1] - closes[-(period+1)]) / closes[-(period+1)] * 100
                    
                    stock_changes.append({
                        'symbol': symbol,
                        'name': row['名称'],
                        'price': float(row['最新价']),
                        'period_change': round(change, 2),
                        'today_change': float(row['涨跌幅']),
                        'market_cap': round(float(row['总市值']) / 100000000, 2) if pd.notna(row['总市值']) else 0
                    })
                    
            except:
                continue
            
            time.sleep(0.03)
        
        if not stock_changes:
            return {'gainers': [], 'losers': [], 'statistics': {}}
        
        changes_df = pd.DataFrame(stock_changes)
        
        return {
            'gainers': changes_df.nlargest(TOP_N, 'period_change').to_dict('records'),
            'losers': changes_df.nsmallest(TOP_N, 'period_change').to_dict('records'),
            'statistics': {
                'sample_size': len(changes_df),
                'avg_change': round(changes_df['period_change'].mean(), 2),
                'up_ratio': round((changes_df['period_change'] > 0).sum() / len(changes_df) * 100, 2)
            }
        }