#!/usr/bin/env python3
"""
A股趋势分析系统 - 主程序入口
"""
import sys
import logging
import argparse

from src.analyzer import StockAnalyzer, SimplifiedAnalyzer
from src.report_generator import ReportGenerator
from src.config import get_china_now, is_trading_day

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='A股趋势分析系统')
    parser.add_argument(
        '--mode', 
        choices=['full', 'quick'], 
        default='quick',
        help='运行模式: full=完整分析, quick=快速分析'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='强制运行（忽略交易日检查）'
    )
    parser.add_argument(
        '--clean',
        action='store_true',
        help='清理30天前的历史数据'
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 50)
    logger.info("A股趋势分析系统启动")
    logger.info(f"当前时间: {get_china_now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"运行模式: {args.mode}")
    logger.info("=" * 50)
    
    # 检查是否为交易日
    if not args.force and not is_trading_day():
        logger.info("今天不是交易日，跳过更新")
        return 0
    
    try:
        # 选择分析器
        if args.mode == 'full':
            logger.info("使用完整分析模式...")
            analyzer = StockAnalyzer()
            result = analyzer.analyze_period_ranking()
        else:
            logger.info("使用快速分析模式...")
            analyzer = SimplifiedAnalyzer()
            result = analyzer.quick_analyze()
        
        if not result or not result.get('periods'):
            logger.error("分析结果为空")
            return 1
        
        # 生成报告
        logger.info("生成报告...")
        generator = ReportGenerator()
        success = generator.generate_report(result)
        
        # 可选：清理旧数据
        if args.clean:
            logger.info("清理旧历史数据...")
            generator.clean_old_history(keep_days=30)
        
        if success:
            logger.info("=" * 50)
            logger.info("✅ 分析完成!")
            logger.info(f"更新时间: {result.get('update_time')}")
            logger.info("=" * 50)
            return 0
        else:
            logger.error("报告生成失败")
            return 1
            
    except Exception as e:
        logger.error(f"运行出错: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())