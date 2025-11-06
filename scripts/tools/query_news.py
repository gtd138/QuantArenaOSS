"""
新闻查询工具
快速查询指定股票或市场的新闻
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services.akshare_news_service import get_news_service
from datetime import datetime
import argparse


def query_stock_news(stock_code: str, trade_date: str = None, max_news: int = 10):
    """查询个股新闻"""
    if not trade_date:
        trade_date = datetime.now().strftime('%Y%m%d')
    
    print(f"\n📰 查询 {stock_code} 的新闻（截至 {trade_date}）\n")
    print("=" * 80)
    
    news_service = get_news_service()
    news_list = news_service.get_stock_news(stock_code, trade_date, max_news)
    
    if not news_list:
        print("⚠️ 暂无新闻数据")
        return
    
    print(f"✅ 共找到 {len(news_list)} 条新闻\n")
    
    for idx, news in enumerate(news_list, 1):
        print(f"\n【新闻 {idx}】")
        print(f"标题: {news['title']}")
        print(f"时间: {news['publish_time']}")
        print(f"来源: {news['source']}")
        if news.get('content'):
            print(f"内容: {news['content'][:200]}...")
        if news.get('url'):
            print(f"链接: {news['url']}")
        print("-" * 80)


def query_market_news(trade_date: str = None, max_news: int = 10):
    """查询市场热点"""
    if not trade_date:
        trade_date = datetime.now().strftime('%Y%m%d')
    
    print(f"\n🔥 市场热点新闻（截至 {trade_date}）\n")
    print("=" * 80)
    
    news_service = get_news_service()
    news_list = news_service.get_market_hot_news(trade_date, max_news)
    
    if not news_list:
        print("⚠️ 暂无热点新闻")
        return
    
    print(f"✅ 共找到 {len(news_list)} 条热点\n")
    
    for idx, news in enumerate(news_list, 1):
        print(f"\n【热点 {idx}】")
        print(f"标题: {news['title']}")
        if news.get('publish_time'):
            print(f"时间: {news['publish_time']}")
        if news.get('content'):
            print(f"内容: {news['content'][:200]}...")
        print("-" * 80)


def main():
    parser = argparse.ArgumentParser(description='A股新闻查询工具')
    parser.add_argument('--stock', '-s', type=str, help='股票代码（如：000001.SZ）')
    parser.add_argument('--market', '-m', action='store_true', help='查询市场热点')
    parser.add_argument('--date', '-d', type=str, help='日期（格式：20250115，默认今天）')
    parser.add_argument('--max', type=int, default=10, help='最大新闻数量（默认10）')
    
    args = parser.parse_args()
    
    if args.stock:
        query_stock_news(args.stock, args.date, args.max)
    elif args.market:
        query_market_news(args.date, args.max)
    else:
        print("用法示例：")
        print("  python query_news.py --stock 000001.SZ")
        print("  python query_news.py --market")
        print("  python query_news.py --stock 600036.SH --date 20250101 --max 5")
        print("\n参数说明：")
        print("  --stock, -s  : 股票代码（如：000001.SZ, 600036.SH）")
        print("  --market, -m : 查询市场热点")
        print("  --date, -d   : 日期（格式：YYYYMMDD，默认今天）")
        print("  --max        : 最大新闻数量（默认10）")


if __name__ == "__main__":
    main()

