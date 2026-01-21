"""
报告生成模块 - 负责生成JSON数据文件供前端使用
"""
import json
from pathlib import Path
from typing import Dict
import logging

from .config import DOCS_DATA_DIR, ANALYSIS_DIR, get_china_now

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ReportGenerator:
    """报告生成器 - 生成前端所需的JSON数据文件"""
    
    def __init__(self):
        self._ensure_dirs()
    
    def _ensure_dirs(self):
        """确保必要的目录存在"""
        DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)
        ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    
    def generate_report(self, analysis_result: Dict) -> bool:
        """
        生成报告（JSON数据文件）
        
        Args:
            analysis_result: 分析结果字典
            
        Returns:
            是否成功
        """
        try:
            # 1. 保存为前端使用的最新数据
            self._save_latest_data(analysis_result)
            
            # 2. 保存历史存档
            self._save_history_data(analysis_result)
            
            logger.info("✅ 报告生成完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ 生成报告失败: {e}")
            return False
    
    def _save_latest_data(self, data: Dict):
        """
        保存最新数据为JSON文件（供前端读取）
        文件路径: docs/data/latest.json
        """
        latest_path = DOCS_DATA_DIR / "latest.json"
        
        with open(latest_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"📄 最新数据已保存: {latest_path}")
    
    def _save_history_data(self, data: Dict):
        """
        保存历史数据存档
        文件路径: 
          - docs/data/data_YYYY-MM-DD.json (供前端历史查询)
          - data/analysis/analysis_YYYY-MM-DD.json (本地存档)
        """
        date_str = data.get('analysis_date', get_china_now().strftime('%Y-%m-%d'))
        
        # 保存到 docs/data 目录（前端可访问）
        frontend_history_path = DOCS_DATA_DIR / f"data_{date_str}.json"
        with open(frontend_history_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # 保存到 data/analysis 目录（本地存档）
        local_history_path = ANALYSIS_DIR / f"analysis_{date_str}.json"
        with open(local_history_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"📚 历史数据已保存: {date_str}")
    
    def clean_old_history(self, keep_days: int = 30):
        """
        清理旧的历史数据（可选）
        
        Args:
            keep_days: 保留最近多少天的数据
        """
        import os
        from datetime import datetime, timedelta
        
        cutoff_date = get_china_now() - timedelta(days=keep_days)
        
        # 清理 docs/data 目录
        for file_path in DOCS_DATA_DIR.glob("data_*.json"):
            try:
                # 从文件名提取日期
                date_str = file_path.stem.replace("data_", "")
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                
                if file_date.date() < cutoff_date.date():
                    file_path.unlink()
                    logger.info(f"🗑️ 已删除旧文件: {file_path.name}")
                    
            except (ValueError, OSError) as e:
                logger.warning(f"清理文件失败 {file_path}: {e}")
        
        # 清理 data/analysis 目录
        for file_path in ANALYSIS_DIR.glob("analysis_*.json"):
            try:
                date_str = file_path.stem.replace("analysis_", "")
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                
                if file_date.date() < cutoff_date.date():
                    file_path.unlink()
                    logger.info(f"🗑️ 已删除旧文件: {file_path.name}")
                    
            except (ValueError, OSError) as e:
                logger.warning(f"清理文件失败 {file_path}: {e}")


def get_available_history_dates() -> list:
    """
    获取可用的历史数据日期列表
    
    Returns:
        日期字符串列表，按日期降序排列
    """
    dates = []
    
    for file_path in DOCS_DATA_DIR.glob("data_*.json"):
        try:
            date_str = file_path.stem.replace("data_", "")
            dates.append(date_str)
        except:
            continue
    
    # 按日期降序排列
    dates.sort(reverse=True)
    
    return dates