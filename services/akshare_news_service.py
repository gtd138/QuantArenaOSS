"""
AkShare新闻服务 - 获取A股市场新闻和资讯
免费使用，无需API Key
"""
import akshare as ak
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from http import HTTPStatus
import pandas as pd
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import time


class AkShareNewsService:
    """
    AkShare新闻服务
    
    功能：
    1. 获取个股新闻公告
    2. 获取市场热点新闻
    3. 获取行业新闻
    4. 新闻时间过滤（防前瞻）
    """
    
    def __init__(self, query_timeout: float = 15.0):
        """
        初始化AkShare新闻服务
        
        Args:
            query_timeout: 单次查询超时时间（秒），默认15秒
        """
        self.cache = {}  # 简单缓存避免重复请求
        self._cache_lock = threading.Lock()  # 保护缓存
        self._query_timeout = query_timeout  # 查询超时时间
        self._pending_queries: Dict[str, threading.Event] = {}  # 正在进行的查询
        self._pending_queries_lock = threading.Lock()  # 保护待查询字典
        self._hot_stock_cache: Dict[Tuple[str, int], List[str]] = {}
        self._hot_sector_cache: Dict[Tuple[str, int], List[Dict[str, Any]]] = {}
    
    def get_stock_news(
        self, 
        stock_code: str, 
        trade_date: str,
        max_news: int = 5
    ) -> List[Dict[str, Any]]:
        """
        获取个股新闻
        
        Args:
            stock_code: 股票代码（如：000001.SZ）
            trade_date: 交易日期（如：20250101）
            max_news: 最多返回新闻数量
            
        Returns:
            [
                {
                    "title": "标题",
                    "content": "内容摘要",
                    "publish_time": "发布时间",
                    "url": "链接"
                }
            ]
        """
        try:
            # 转换股票代码格式（去掉.SZ/.SH后缀）
            symbol = stock_code.split('.')[0]
            
            # 缓存key
            cache_key = f"stock_{symbol}_{trade_date}"
            
            # ✅ 线程安全：检查缓存
            with self._cache_lock:
                if cache_key in self.cache:
                    return self.cache[cache_key]
            
            # ✅ 优化：避免重复查询 - 检查是否有其他线程正在查询同一数据
            event = None
            is_my_query = False  # 标记是否是本线程创建的查询
            with self._pending_queries_lock:
                if cache_key in self._pending_queries:
                    # 有其他线程正在查询，等待它完成
                    event = self._pending_queries[cache_key]
                    is_my_query = False
                else:
                    # 创建新的事件，标记开始查询
                    event = threading.Event()
                    self._pending_queries[cache_key] = event
                    is_my_query = True
            
            # 如果是其他线程的查询，等待它完成
            if event and not is_my_query and not event.is_set():
                # 等待其他线程完成查询（最多等待20秒）
                if event.wait(timeout=20.0):
                    # 查询完成，再次检查缓存
                    with self._cache_lock:
                        if cache_key in self.cache:
                            with self._pending_queries_lock:
                                if cache_key in self._pending_queries:
                                    del self._pending_queries[cache_key]
                            return self.cache[cache_key]
                else:
                    # 等待超时，可能是查询线程出现问题，清理并自己执行查询
                    with self._pending_queries_lock:
                        if cache_key in self._pending_queries:
                            del self._pending_queries[cache_key]
                    event = None
                    is_my_query = True
            
            # ✅ 使用线程池执行查询，设置超时（如果是自己的查询或等待超时）
            def _fetch():
                return ak.stock_news_em(symbol=symbol)
            
            news_df = None
            try:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(_fetch)
                    news_df = future.result(timeout=self._query_timeout)
            except FutureTimeoutError:
                print(f"⚠️ 获取股票新闻超时 ({stock_code}): {self._query_timeout}秒", flush=True)
                # 通知等待的线程
                if event:
                    with self._pending_queries_lock:
                        if cache_key in self._pending_queries:
                            del self._pending_queries[cache_key]
                    event.set()
                return []
            
            if news_df is None or news_df.empty:
                return []
            
            # 转换日期格式
            trade_date_obj = datetime.strptime(trade_date, '%Y%m%d')
            
            # 过滤新闻（只保留trade_date之前的新闻）
            news_list = []
            
            # ✅ 兼容不同的列名格式（AkShare可能返回中文或英文列名）
            # 尝试查找列名
            title_col = None
            content_col = None
            time_col = None
            url_col = None
            source_col = None
            
            for col in news_df.columns:
                col_str = str(col)
                if '标题' in col_str or 'title' in col_str.lower():
                    title_col = col
                if '内容' in col_str or 'content' in col_str.lower():
                    content_col = col
                if '时间' in col_str or 'date' in col_str.lower():
                    time_col = col
                if '链接' in col_str or 'url' in col_str.lower():
                    url_col = col
                if '来源' in col_str or 'source' in col_str.lower():
                    source_col = col
            
            for _, row in news_df.iterrows():
                try:
                    # 获取发布时间（兼容不同列名）
                    publish_time = ''
                    if time_col:
                        publish_time = str(row[time_col]) if time_col in row.index else ''
                    else:
                        # 尝试多个可能的列名
                        for col_name in ['发布时间', '时间', 'date']:
                            if col_name in news_df.columns:
                                publish_time = str(row[col_name])
                                break
                    
                    # 如果获取不到时间，尝试继续（有些新闻可能没有时间字段）
                    news_date = None
                    if publish_time:
                        try:
                            # 尝试解析时间格式（可能是"2025-01-15 10:30:00"或其他格式）
                            if len(publish_time) >= 10:
                                news_date = datetime.strptime(publish_time[:10], '%Y-%m-%d')
                            elif len(publish_time) == 8 and publish_time.isdigit():
                                # YYYYMMDD格式
                                news_date = datetime.strptime(publish_time, '%Y%m%d')
                        except:
                            pass
                    
                    # ✅ 防前瞻 + 日期范围限制：只保留交易日期前7天内的新闻
                    if news_date:
                        news_date_obj = news_date.date()
                        trade_date_only = trade_date_obj.date()
                        
                        # 1. 防前瞻：跳过未来新闻
                        if news_date_obj > trade_date_only:
                            continue
                        
                        # 2. 日期范围限制：只保留交易日期前7天内的新闻（确保新闻相关性）
                        days_diff = (trade_date_only - news_date_obj).days
                        if days_diff > 7:
                            continue  # 新闻太旧，跳过
                    
                    # 获取标题和内容
                    title = ''
                    if title_col:
                        title = str(row[title_col]) if title_col in row.index else ''
                    else:
                        for col_name in ['新闻标题', '标题', 'title']:
                            if col_name in news_df.columns:
                                title = str(row[col_name])
                                break
                    
                    content = ''
                    if content_col:
                        content = str(row[content_col]) if content_col in row.index else ''
                    else:
                        for col_name in ['新闻内容', '内容', 'content']:
                            if col_name in news_df.columns:
                                content = str(row[col_name])
                                break
                    
                    url = ''
                    if url_col:
                        url = str(row[url_col]) if url_col in row.index else ''
                    else:
                        for col_name in ['新闻链接', '链接', 'url']:
                            if col_name in news_df.columns:
                                url = str(row[col_name])
                                break
                    
                    source = '东方财富'
                    if source_col:
                        source = str(row[source_col]) if source_col in row.index else '东方财富'
                    
                    # 只有标题不为空才添加
                    if title:
                        news_list.append({
                            'title': title,
                            'content': content[:200] if content else '',  # 限制内容长度
                            'publish_time': publish_time,
                            'url': url,
                            'source': source
                        })
                    
                    if len(news_list) >= max_news:
                        break
                        
                except Exception as e:
                    continue
            
            # ✅ 线程安全：缓存结果
            with self._cache_lock:
                self.cache[cache_key] = news_list
            
            # ✅ 通知等待的线程查询完成
            if event:
                with self._pending_queries_lock:
                    if cache_key in self._pending_queries:
                        del self._pending_queries[cache_key]
                event.set()
            
            return news_list
            
        except Exception as e:
            print(f"⚠️ 获取股票新闻失败 ({stock_code}): {e}", flush=True)
            # 通知等待的线程
            cache_key = f"stock_{stock_code.split('.')[0]}_{trade_date}"
            with self._pending_queries_lock:
                if cache_key in self._pending_queries:
                    event = self._pending_queries[cache_key]
                    del self._pending_queries[cache_key]
                    event.set()
            return []
    
    def get_market_hot_news(
        self, 
        trade_date: str,
        max_news: int = 10
    ) -> List[Dict[str, Any]]:
        """
        获取市场热点新闻
        
        Args:
            trade_date: 交易日期
            max_news: 最多返回新闻数量
            
        Returns:
            新闻列表
        """
        try:
            # 缓存key
            cache_key = f"market_hot_{trade_date}"
            
            # ✅ 线程安全：检查缓存
            with self._cache_lock:
                if cache_key in self.cache:
                    return self.cache[cache_key]
            
            # ✅ 优化：避免重复查询 - 检查是否有其他线程正在查询同一数据
            event = None
            is_my_query = False  # 标记是否是本线程创建的查询
            with self._pending_queries_lock:
                if cache_key in self._pending_queries:
                    # 有其他线程正在查询，等待它完成
                    event = self._pending_queries[cache_key]
                    is_my_query = False
                else:
                    # 创建新的事件，标记开始查询
                    event = threading.Event()
                    self._pending_queries[cache_key] = event
                    is_my_query = True
            
            # 如果是其他线程的查询，等待它完成
            if event and not is_my_query and not event.is_set():
                # 等待其他线程完成查询（最多等待20秒）
                if event.wait(timeout=20.0):
                    # 查询完成，再次检查缓存
                    with self._cache_lock:
                        if cache_key in self.cache:
                            with self._pending_queries_lock:
                                if cache_key in self._pending_queries:
                                    del self._pending_queries[cache_key]
                            return self.cache[cache_key]
                else:
                    # 等待超时，可能是查询线程出现问题，清理并自己执行查询
                    with self._pending_queries_lock:
                        if cache_key in self._pending_queries:
                            del self._pending_queries[cache_key]
                    event = None
                    is_my_query = True
            
            # ✅ 使用线程池执行查询，设置超时（如果是自己的查询或等待超时）
            def _fetch():
                try:
                    result = ak.news_cctv()  # CCTV财经新闻
                    # 如果是generator，转换为DataFrame
                    if hasattr(result, '__iter__') and not isinstance(result, pd.DataFrame):
                        return pd.DataFrame(list(result))
                    else:
                        return result
                except Exception as e1:
                    try:
                        result = ak.news_economic_baidu()  # 百度财经新闻
                        # 如果是generator，转换为DataFrame
                        if hasattr(result, '__iter__') and not isinstance(result, pd.DataFrame):
                            return pd.DataFrame(list(result))
                        else:
                            return result
                    except Exception as e2:
                        raise Exception(f"CCTV: {e1}, Baidu: {e2}")
            
            news_df = None
            try:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(_fetch)
                    news_df = future.result(timeout=self._query_timeout)
            except FutureTimeoutError:
                print(f"⚠️ 获取市场热点超时: {self._query_timeout}秒", flush=True)
                # 通知等待的线程
                if event:
                    with self._pending_queries_lock:
                        if cache_key in self._pending_queries:
                            del self._pending_queries[cache_key]
                    event.set()
                return []
            except Exception as e:
                print(f"⚠️ 获取市场热点失败: {e}", flush=True)
                # 通知等待的线程
                if event:
                    with self._pending_queries_lock:
                        if cache_key in self._pending_queries:
                            del self._pending_queries[cache_key]
                    event.set()
                return []
            
            if news_df is None or news_df.empty:
                return []
            
            # 转换日期格式（用于防前瞻过滤）
            trade_date_obj = datetime.strptime(trade_date, '%Y%m%d')
            
            # 转换为列表，并过滤未来新闻（防前瞻）
            news_list = []
            
            # ✅ 兼容不同的列名格式（CCTV返回英文列名，其他可能返回中文列名）
            # 尝试多种可能的列名
            title_col = None
            date_col = None
            content_col = None
            
            for col in news_df.columns:
                col_lower = str(col).lower()
                if 'title' in col_lower or '标题' in str(col) or 'title' in str(col):
                    title_col = col
                if 'date' in col_lower or '时间' in str(col) or '日期' in str(col):
                    date_col = col
                if 'content' in col_lower or '内容' in str(col):
                    content_col = col
            
            # 如果没有找到，尝试默认列名
            if title_col is None and 'title' in news_df.columns:
                title_col = 'title'
            if date_col is None and 'date' in news_df.columns:
                date_col = 'date'
            if content_col is None and 'content' in news_df.columns:
                content_col = 'content'
            
            # ✅ 两阶段过滤：先尝试严格过滤（7天内），如果结果为空则放宽到30天
            strict_max_days = 7
            relaxed_max_days = 30
            
            # 第一阶段：收集所有有效新闻（带日期信息）
            all_news_with_date = []
            for idx, row in news_df.iterrows():
                # 获取标题和内容（兼容不同列名）
                title = ''
                if title_col:
                    title = str(row.get(title_col, '') if hasattr(row, 'get') else row[title_col] if title_col in row.index else '')
                else:
                    # 尝试直接访问
                    for col in ['title', '标题', '新闻标题']:
                        if col in news_df.columns:
                            title = str(row[col])
                            break
                
                if not title:  # 跳过无标题的新闻
                    continue
                
                content = ''
                if content_col:
                    content = str(row.get(content_col, '') if hasattr(row, 'get') else row[content_col] if content_col in row.index else '')
                else:
                    for col in ['content', '内容', '新闻内容']:
                        if col in news_df.columns:
                            content = str(row[col])
                            break
                
                # 尝试解析新闻发布时间
                publish_time_str = ''
                if date_col:
                    publish_time_str = str(row.get(date_col, '') if hasattr(row, 'get') else row[date_col] if date_col in row.index else '')
                else:
                    # 尝试多种可能的日期列名
                    for col in ['date', '发布时间', '时间', '日期']:
                        if col in news_df.columns:
                            publish_time_str = str(row[col])
                            break
                
                # 尝试解析日期（兼容多种格式）
                news_date = None
                days_diff = None
                if publish_time_str:
                    try:
                        # CCTV返回的是YYYYMMDD格式
                        if len(publish_time_str) == 8 and publish_time_str.isdigit():
                            news_date = datetime.strptime(publish_time_str, '%Y%m%d')
                        elif len(publish_time_str) >= 10:
                            # 尝试解析 "YYYY-MM-DD" 或 "YYYY-MM-DD HH:MM:SS"
                            news_date_str = publish_time_str[:10]
                            news_date = datetime.strptime(news_date_str, '%Y-%m-%d')
                        
                        if news_date:
                            news_date_obj = news_date.date()
                            trade_date_only = trade_date_obj.date()
                            
                            # 防前瞻：跳过未来新闻
                            if news_date_obj > trade_date_only:
                                continue
                            
                            # 计算日期差
                            days_diff = (trade_date_only - news_date_obj).days
                    except:
                        # 日期解析失败，跳过
                        continue
                
                # 保存新闻信息（包括日期差）
                all_news_with_date.append({
                    'title': title,
                    'content': content[:200] if content else '',
                    'publish_time': publish_time_str,
                    'url': '',
                    'source': '东方财富',
                    'days_diff': days_diff if days_diff is not None else 999  # 无日期信息视为很旧
                })
            
            # 第二阶段：优先选择7天内的新闻，如果不够则放宽到30天
            # 先按日期差排序（最近的在前）
            all_news_with_date.sort(key=lambda x: x['days_diff'] if x['days_diff'] != 999 else 999)
            
            # 尝试严格过滤（7天内）
            for news_item in all_news_with_date:
                if len(news_list) >= max_news:
                    break
                if news_item['days_diff'] <= strict_max_days:
                    # 移除days_diff字段（不返回给调用者）
                    news_item.pop('days_diff')
                    news_list.append(news_item)
            
            # 如果严格过滤后结果太少，放宽到30天
            if len(news_list) < max_news:
                for news_item in all_news_with_date:
                    if len(news_list) >= max_news:
                        break
                    if news_item['days_diff'] <= relaxed_max_days:
                        # 跳过已经添加的
                        if 'days_diff' in news_item:
                            news_item.pop('days_diff')
                            news_list.append(news_item)
            
            # ✅ 线程安全：缓存结果
            with self._cache_lock:
                self.cache[cache_key] = news_list
            
            # ✅ 通知等待的线程查询完成
            if event:
                with self._pending_queries_lock:
                    if cache_key in self._pending_queries:
                        del self._pending_queries[cache_key]
                event.set()
            
            return news_list
            
        except Exception as e:
            print(f"⚠️ 获取市场热点失败: {e}", flush=True)
            return []
    
    def get_stock_announcements(
        self, 
        stock_code: str,
        trade_date: str,
        max_announcements: int = 3
    ) -> List[Dict[str, Any]]:
        """
        获取个股公告
        
        Args:
            stock_code: 股票代码
            trade_date: 交易日期
            max_announcements: 最多返回公告数量
            
        Returns:
            公告列表
        """
        try:
            # 转换股票代码
            symbol = stock_code.split('.')[0]
            
            # 缓存key
            cache_key = f"announcement_{symbol}_{trade_date}"
            if cache_key in self.cache:
                return self.cache[cache_key]
            
            # 获取沪深A股公告
            # 注意：AkShare的公告接口可能需要日期参数
            announcements_df = ak.stock_notice_report(symbol=symbol)
            
            if announcements_df is None or announcements_df.empty:
                return []
            
            # 转换日期
            trade_date_obj = datetime.strptime(trade_date, '%Y%m%d')
            
            # 过滤公告
            announcement_list = []
            for _, row in announcements_df.iterrows():
                try:
                    # 解析公告日期
                    notice_date_str = row.get('公告日期', '')
                    if not notice_date_str:
                        continue
                    
                    notice_date = datetime.strptime(notice_date_str[:10], '%Y-%m-%d')
                    
                    # 防前瞻：只保留交易日期当天及之前的公告（避免使用未来信息）
                    if notice_date.date() > trade_date_obj.date():
                        continue
                    
                    announcement_list.append({
                        'title': row.get('公告标题', ''),
                        'type': row.get('公告类型', ''),
                        'publish_time': notice_date_str,
                        'url': row.get('公告链接', '')
                    })
                    
                    if len(announcement_list) >= max_announcements:
                        break
                        
                except Exception as e:
                    continue
            
            # 缓存
            self.cache[cache_key] = announcement_list
            
            return announcement_list
            
        except Exception as e:
            print(f"⚠️ 获取股票公告失败 ({stock_code}): {e}")
            return []
    
    def format_news_for_prompt(
        self, 
        news_list: List[Dict[str, Any]]
    ) -> str:
        """
        格式化新闻为提示词文本
        
        Args:
            news_list: 新闻列表
            
        Returns:
            格式化后的文本
        """
        if not news_list:
            return "暂无相关新闻"
        
        formatted = []
        for idx, news in enumerate(news_list, 1):
            formatted.append(
                f"{idx}. 【{news['publish_time'][:10]}】{news['title']}\n"
                f"   {news['content'][:100]}..."
            )
        
        return "\n".join(formatted)

    # ===================== 新增热点相关工具 =====================
    def _convert_to_ts_code(self, raw_code: str) -> Optional[str]:
        """将常见的6位代码转换为TS格式。"""
        if not raw_code:
            return None
        code = raw_code.strip()
        if len(code) != 6 or not code.isdigit():
            return None
        if code.startswith(('6', '9')):
            return f"{code}.SH"
        if code.startswith(('0', '3')):
            return f"{code}.SZ"
        if code.startswith('8'):
            # 北交所代码
            return f"{code}.BJ"
        return None

    def get_hot_stock_codes(self, trade_date: str, limit: int = 200) -> List[str]:
        """获取热点股票TS代码列表，并进行缓存。"""
        cache_key = (trade_date, limit)
        with self._cache_lock:
            cached = self._hot_stock_cache.get(cache_key)
            if cached is not None:
                return cached

        def _fetch_hot_rank():
            try:
                return ak.stock_hot_rank_em()
            except Exception as e:
                print(f"⚠️ 获取热门股票榜失败: {e}", flush=True)
                return None

        df = _fetch_hot_rank()

        if isinstance(df, HTTPStatus):
            print(f"⚠️ 热点股票接口返回HTTP状态: {df}", flush=True)
            df = None

        if df is not None and not isinstance(df, pd.DataFrame):
            try:
                df = pd.DataFrame(df)
            except Exception as conv_err:
                print(f"⚠️ 无法解析热点股票数据: {conv_err}", flush=True)
                df = None

        if df is None or df.empty:
            with self._cache_lock:
                self._hot_stock_cache[cache_key] = []
            return []

        hot_codes: List[str] = []
        # 兼容不同列名（中文/英文）
        code_columns = ['代码', 'code', '股票代码']
        for _, row in df.iterrows():
            raw_code = ''
            for col in code_columns:
                if col in df.columns:
                    raw_code = str(row.get(col, '')).strip()
                    if raw_code:
                        break
            ts_code = self._convert_to_ts_code(raw_code)
            if ts_code:
                hot_codes.append(ts_code)
            if len(hot_codes) >= limit:
                break

        with self._cache_lock:
            self._hot_stock_cache[cache_key] = hot_codes

        print(f"🔥 获取到 {len(hot_codes)} 只热门股票（{trade_date}）", flush=True)
        return hot_codes

    def get_hot_sectors(self, trade_date: str, limit: int = 20) -> List[Dict[str, Any]]:
        """获取热门板块信息，供提示词参考。"""
        cache_key = (trade_date, limit)
        with self._cache_lock:
            cached = self._hot_sector_cache.get(cache_key)
            if cached is not None:
                return cached

        def _fetch_board_rank() -> Optional[pd.DataFrame]:
            # 先尝试行业资金流，再尝试概念热点
            try:
                return ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流")
            except Exception as first_err:
                try:
                    return ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="概念资金流")
                except Exception as second_err:
                    print(f"⚠️ 获取热门板块失败: {first_err}; {second_err}", flush=True)
                    return None

        df = _fetch_board_rank()

        if isinstance(df, HTTPStatus):
            print(f"⚠️ 热门板块接口返回HTTP状态: {df}", flush=True)
            df = None

        if df is not None and not isinstance(df, pd.DataFrame):
            try:
                df = pd.DataFrame(df)
            except Exception as conv_err:
                print(f"⚠️ 无法解析热门板块数据: {conv_err}", flush=True)
                df = None

        if df is None or df.empty:
            with self._cache_lock:
                self._hot_sector_cache[cache_key] = []
            return []

        name_columns = ['名称', '板块名称', '行业名称', 'name']
        change_columns = ['涨跌幅', '涨跌幅(%)', '涨幅', 'change']

        sectors: List[Dict[str, Any]] = []
        for _, row in df.iterrows():
            sector_name = ''
            for col in name_columns:
                if col in df.columns:
                    sector_name = str(row.get(col, '')).strip()
                    if sector_name:
                        break
            if not sector_name:
                continue

            change_pct: Optional[float] = None
            for col in change_columns:
                if col in df.columns:
                    try:
                        change_pct = float(str(row.get(col, '0')).replace('%', '').strip())
                        break
                    except ValueError:
                        continue

            sectors.append({
                'name': sector_name,
                'change_pct': change_pct
            })

            if len(sectors) >= limit:
                break

        with self._cache_lock:
            self._hot_sector_cache[cache_key] = sectors

        print(f"🔥 获取到 {len(sectors)} 个热门板块（{trade_date}）", flush=True)
        return sectors


# 单例模式
_news_service_instance = None

def get_news_service() -> AkShareNewsService:
    """获取新闻服务单例"""
    global _news_service_instance
    if _news_service_instance is None:
        _news_service_instance = AkShareNewsService()
    return _news_service_instance

