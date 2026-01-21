"""
配置模块 - 集中管理所有配置项
"""
from pathlib import Path
from datetime import datetime
import pytz

# 路径配置
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DAILY_DATA_DIR = DATA_DIR / "daily"
ANALYSIS_DIR = DATA_DIR / "analysis"
DOCS_DIR = BASE_DIR / "docs"
DOCS_DATA_DIR = DOCS_DIR / "data"

# 确保目录存在
for dir_path in [DAILY_DATA_DIR, ANALYSIS_DIR, DOCS_DATA_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# 分析配置
ANALYSIS_PERIODS = [5, 10, 20]  # 分析周期（天）
TOP_N = 50  # 排行榜数量

# 时区配置
CHINA_TZ = pytz.timezone('Asia/Shanghai')

# 股票过滤配置
EXCLUDE_ST = True  # 排除ST股票
EXCLUDE_NEW_STOCKS_DAYS = 60  # 排除上市不足60天的新股
MIN_PRICE = 1.0  # 最低价格过滤
MIN_MARKET_CAP = 10  # 最小市值（亿元）

def get_china_now():
    """获取当前中国时间"""
    return datetime.now(CHINA_TZ)

def is_trading_day():
    """简单判断是否为交易日（周一到周五）"""
    now = get_china_now()
    return now.weekday() < 5