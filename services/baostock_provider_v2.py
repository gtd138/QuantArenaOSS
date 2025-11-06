"""
BaostockProvider V2 - 线程安全版本
解决多线程login/logout冲突问题
"""
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import baostock as bs
from services.akshare_news_service import get_news_service


class BaostockProviderV2:
    """
    Baostock数据提供者 V2 - 线程安全版本
    
    改进：
    1. 使用线程本地存储（thread-local storage）
    2. 每个线程独立login/logout
    3. 避免跨线程连接冲突
    """
    
    def __init__(self, retry: int = 2, retry_delay: float = 0.5, query_timeout: float = 300.0):
        """
        初始化
        
        Args:
            retry: 重试次数（减少到2次，加快失败）
            retry_delay: 重试延迟（减少到0.5秒，加快重试）
            query_timeout: 单次查询超时时间（秒）（增加到300秒，给baostock足够响应时间）
        """
        self._retry = retry
        self._retry_delay = retry_delay
        self._query_timeout = query_timeout
        
        # 线程本地存储（每个线程独立的login状态）
        self._thread_local = threading.local()
        
        # 全局锁（保护缓存）
        self._cache_lock = threading.Lock()
        
        # 正在进行的查询（避免重复查询同一数据）
        self._pending_queries: Dict[Tuple, threading.Event] = {}
        self._pending_queries_lock = threading.Lock()
        
        # 缓存（线程安全）
        self._daily_cache: Dict[Tuple[str, str], Dict[str, float]] = {}
        self._trade_dates_cache: Dict[Tuple[str, str], List[str]] = {}
        self._basic_info_cache: Dict[str, Dict[str, str]] = {}
        self._all_stock_cache: Dict[str, List[str]] = {}
        self._candidates_cache: Dict[Tuple[str, float, int], List[Dict[str, float]]] = {}
        self._index_cache: Dict[Tuple[str, str], Dict[str, float]] = {}
        self._stock_whitelist: List[str] = []
        self._delisted_or_st: Dict[str, bool] = {}
        self._hot_candidate_cache: Dict[str, Dict[str, Any]] = {}
        self._preloaded_daily_dates: Dict[str, str] = {}
        self._preload_lock = threading.Lock()
        self._candidate_pool_by_date: Dict[str, Dict[str, Any]] = {}
        try:
            self._news_service = get_news_service()
        except Exception as news_err:
            print(f"⚠️ 无法初始化新闻服务: {news_err}", flush=True)
            self._news_service = None

        # 主线程初始化：预加载基本信息
        self._main_thread_login()
        self._load_basic_info()
        self._main_thread_logout()
    
    def _main_thread_login(self):
        """主线程登录（用于初始化）"""
        lg = bs.login()
        if lg.error_code != "0":
            raise RuntimeError(f"Baostock login failed: {lg.error_msg}")
    
    def _main_thread_logout(self):
        """主线程登出"""
        bs.logout()
    
    def _ensure_thread_login(self) -> None:
        """
        确保当前线程已登录
        
        每个线程第一次使用时自动login
        使用线程本地存储避免冲突
        """
        # 检查当前线程是否已登录
        if not hasattr(self._thread_local, 'logged_in'):
            self._thread_local.logged_in = False
        
        if self._thread_local.logged_in:
            return
        
        # 当前线程登录
        lg = bs.login()
        if lg.error_code != "0":
            raise RuntimeError(f"Baostock thread login failed: {lg.error_msg}")
        
        self._thread_local.logged_in = True
        
        # 注册线程退出时自动logout
        def cleanup():
            if hasattr(self._thread_local, 'logged_in') and self._thread_local.logged_in:
                try:
                    bs.logout()
                    self._thread_local.logged_in = False
                except:
                    pass
        
        # 注意：Python的threading不支持直接注册cleanup，需要手动管理
        # 这里简化处理，依赖进程结束时自动清理
    
    @staticmethod
    def _to_baostock_code(ts_code: str) -> str:
        """将TS代码转为Baostock格式"""
        code, market = ts_code.split('.')
        market = market.lower()
        if market == 'sh':
            return f"sh.{code}"
        if market == 'sz':
            return f"sz.{code}"
        raise ValueError(f"Unsupported market: {ts_code}")
    
    @staticmethod
    def _to_ts_code(bs_code: str) -> str:
        """将Baostock代码转为TS格式"""
        market, code = bs_code.split('.')
        market = market.upper()
        return f"{code}.{market}"
    
    @staticmethod
    def _format_date(date_str: str) -> str:
        """格式化日期为YYYY-MM-DD"""
        if '-' in date_str:
            return date_str
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    
    @staticmethod
    def _normalize_float(value: str) -> float:
        """规范化浮点数"""
        if value in (None, '', 'None'):
            return 0.0
        try:
            return float(value)
        except ValueError:
            return 0.0
    
    def _load_basic_info(self) -> None:
        """加载股票基本信息"""
        if self._basic_info_cache:
            return
        
        print("📋 加载股票基本信息...")
        
        try:
            rs = bs.query_stock_basic()
            total_count = 0
            st_count = 0
            delisted_count = 0
            whitelist: List[str] = []
            
            while rs.error_code == '0' and rs.next():
                data = rs.get_row_data()
                if not data:
                    continue
                bs_code = data[0]
                ts_code = self._to_ts_code(bs_code)
                name = data[1]
                ipo_date = data[2] if len(data) > 2 else ''
                out_date = data[3] if len(data) > 3 else ''
                stock_type = data[4] if len(data) > 4 else ''
                status = data[5] if len(data) > 5 else '1'
                name_upper = name.upper() if name else ''
                is_st = 'ST' in name_upper
                is_listed = status in ('1', '上市') and not out_date
                is_delisted = not is_listed
                
                info = {
                    'code': ts_code,
                    'name': name,
                    'industry': data[2] if len(data) > 2 else '',
                    'area': data[3] if len(data) > 3 else '',
                    'ipo_date': ipo_date,
                    'out_date': out_date,
                    'type': stock_type,
                    'status': status,
                    'is_st': is_st,
                    'is_listed': is_listed,
                }
                self._basic_info_cache[ts_code] = info
                self._delisted_or_st[ts_code] = is_st or is_delisted
                total_count += 1
                if is_st:
                    st_count += 1
                if is_delisted:
                    delisted_count += 1
                
                # 🔥 只有真正的股票才加入白名单（排除指数）
                # 股票代码规则：60/68/900（上交所）、00/001/002/003/30/200（深交所）
                code_number = ts_code.split('.')[0]
                is_stock = (
                    code_number.startswith('60') or code_number.startswith('68') or code_number.startswith('900') or  # 上交所
                    code_number.startswith('000') or code_number.startswith('001') or code_number.startswith('002') or 
                    code_number.startswith('003') or code_number.startswith('30') or code_number.startswith('200')  # 深交所
                ) and stock_type in ('1', '股票')  # stock_type=1 表示股票
                
                if not is_st and not is_delisted and is_stock:
                    whitelist.append(ts_code)
            
            self._stock_whitelist = whitelist
            self._all_stock_cache['all'] = list(self._basic_info_cache.keys())
            print(
                f"  ✅ 已加载 {total_count} 只股票基本信息，白名单 {len(self._stock_whitelist)} 只"
                f"（ST {st_count}，退市 {delisted_count}）"
            )
            
        except Exception as e:
            print(f"  ⚠️ 加载失败: {e}")
    
    def _query_with_retry(self, func):
        """
        带重试的查询（带超时保护）
        
        注意：不使用全局锁，允许并发查询
        """
        # 确保当前线程已登录
        self._ensure_thread_login()
        
        last_error = None
        for attempt in range(self._retry):
            try:
                # 使用线程池执行函数，设置超时
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(func)
                    try:
                        return future.result(timeout=self._query_timeout)
                    except FutureTimeoutError as timeout_exc:
                        # 超时：跳过此次查询
                        if attempt == 0:  # 只打印一次
                            print(f"  ⚠️ 查询超时（{self._query_timeout}秒），尝试 {attempt+1}/{self._retry}", flush=True)
                        last_error = timeout_exc
                        time.sleep(self._retry_delay * (attempt + 1))
                        continue
            except (UnicodeDecodeError, UnicodeError) as exc:
                # 编码错误：可能是baostock返回的数据编码问题
                # 打印警告但继续重试
                if attempt == 0:  # 只打印一次，避免刷屏
                    print(f"  ⚠️ 编码错误（尝试 {attempt+1}/{self._retry}）: {exc}", flush=True)
                last_error = exc
                # 编码错误时延迟稍长一点
                time.sleep(self._retry_delay * (attempt + 2))
            except Exception as exc:
                last_error = exc
                time.sleep(self._retry_delay * (attempt + 1))
        
        # 如果是编码错误，不抛出异常，而是返回None让调用者处理
        if isinstance(last_error, (UnicodeDecodeError, UnicodeError)):
            print(f"  ⚠️ 编码错误，重试{self._retry}次后仍失败，跳过此次查询", flush=True)
            return None
        
        # 如果是超时错误，返回None
        if isinstance(last_error, (FutureTimeoutError, TimeoutError)):
            print(f"  ⚠️ 查询超时，重试{self._retry}次后仍失败，跳过此次查询", flush=True)
            return None
        
        raise RuntimeError(f"Baostock request failed after {self._retry} retries: {last_error}")
    
    def get_trade_dates(self, start_date: str, end_date: str) -> List[str]:
        """
        获取交易日列表
        
        Args:
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            
        Returns:
            ['20250102', '20250103', ...]
        """
        # 检查缓存（线程安全）
        key = (start_date, end_date)
        with self._cache_lock:
            if key in self._trade_dates_cache:
                return self._trade_dates_cache[key]
        
        start_fmt = self._format_date(start_date)
        end_fmt = self._format_date(end_date)
        
        def _fetch():
            rs = bs.query_trade_dates(start_date=start_fmt, end_date=end_fmt)
            dates: List[str] = []
            while rs.error_code == '0' and rs.next():
                row = rs.get_row_data()
                if row[1] == '1':  # is_trading_day
                    dates.append(row[0].replace('-', ''))
            return dates
        
        dates = self._query_with_retry(_fetch)
        
        # 缓存（线程安全）
        with self._cache_lock:
            self._trade_dates_cache[key] = dates
        
        return dates
    
    def get_daily_price(self, ts_code: str, trade_date: str) -> Optional[Dict[str, float]]:
        """
        获取单只股票单日价格
        
        Args:
            ts_code: 股票代码 000001.SZ
            trade_date: 交易日期 YYYYMMDD
            
        Returns:
            价格数据字典
        """
        # 检查缓存（线程安全）
        key = (ts_code, trade_date)
        with self._cache_lock:
            if key in self._daily_cache:
                return self._daily_cache[key]
        
        # ✅ 优化：避免重复查询 - 检查是否有其他线程正在查询同一数据
        event = None
        is_my_query = False  # 标记是否是本线程创建的查询
        with self._pending_queries_lock:
            if key in self._pending_queries:
                # 有其他线程正在查询，等待它完成
                event = self._pending_queries[key]
                is_my_query = False
            else:
                # 创建新的事件，标记开始查询
                event = threading.Event()
                self._pending_queries[key] = event
                is_my_query = True
        
        # 如果是其他线程的查询，等待它完成
        if event and not is_my_query and not event.is_set():
            # 等待其他线程完成查询（最多等待30秒，避免死锁）
            if event.wait(timeout=30.0):
                # 查询完成，再次检查缓存
                with self._cache_lock:
                    if key in self._daily_cache:
                        with self._pending_queries_lock:
                            if key in self._pending_queries:
                                del self._pending_queries[key]
                        return self._daily_cache[key]
            else:
                # 等待超时，可能是查询线程出现问题，清理并自己执行查询
                with self._pending_queries_lock:
                    if key in self._pending_queries:
                        del self._pending_queries[key]
                event = None
                is_my_query = True
        
        # 获取数据（如果是自己的查询或等待超时）
        try:
            bs_code = self._to_baostock_code(ts_code)
            date_fmt = self._format_date(trade_date)
            
            def _fetch():
                rs = bs.query_history_k_data_plus(
                    bs_code,
                    "date,code,open,high,low,close,preclose,volume,amount,turn,pctChg,peTTM",
                    start_date=date_fmt,
                    end_date=date_fmt,
                    frequency="d",
                    adjustflag="3",  # 不复权
                )
                rows = []
                while rs.error_code == '0' and rs.next():
                    rows.append(rs.get_row_data())
                return rows
            
            rows = self._query_with_retry(_fetch)
            
            # 处理编码错误返回None的情况
            if rows is None:
                # 通知等待的线程
                if event:
                    with self._pending_queries_lock:
                        if key in self._pending_queries:
                            del self._pending_queries[key]
                    event.set()
                return None
            
            if not rows:
                if event:
                    with self._pending_queries_lock:
                        if key in self._pending_queries:
                            del self._pending_queries[key]
                    event.set()
                return None
            
            row = rows[0]
            result = {
                'trade_date': row[0].replace('-', ''),
                'code': ts_code,
                'open': self._normalize_float(row[2]),
                'high': self._normalize_float(row[3]),
                'low': self._normalize_float(row[4]),
                'close': self._normalize_float(row[5]),
                'preclose': self._normalize_float(row[6]),
                'volume': self._normalize_float(row[7]),
                'amount': self._normalize_float(row[8]),
                'turnover_rate': self._normalize_float(row[9]),
                'pct_chg': self._normalize_float(row[10]),
                'pe_ttm': self._normalize_float(row[11]),
            }
            
            # 缓存（线程安全）
            with self._cache_lock:
                self._daily_cache[key] = result
            
            # ✅ 通知等待的线程查询完成
            if event:
                with self._pending_queries_lock:
                    if key in self._pending_queries:
                        del self._pending_queries[key]
                event.set()
            
            return result
            
        except Exception as e:
            # 发生异常时也要通知等待的线程
            if event:
                with self._pending_queries_lock:
                    if key in self._pending_queries:
                        del self._pending_queries[key]
                event.set()
            return None
    
    def get_stock_basic_info(self, ts_code: str) -> Dict[str, str]:
        """
        获取股票基本信息
        
        Args:
            ts_code: 股票代码
            
        Returns:
            {'code': '000001.SZ', 'name': '平安银行', 'industry': '', 'area': ''}
        """
        with self._cache_lock:
            info = self._basic_info_cache.get(ts_code)
            if info:
                return info

        # 未命中缓存时，返回基本占位数据
        return {
            'code': ts_code,
            'name': ts_code,
            'industry': '',
            'area': ''
        }

    def preload_daily_data(self, trade_date: str, batch_size: int = 200) -> None:
        """预热指定交易日的行情和候选缓存。"""
        with self._preload_lock:
            status = self._preloaded_daily_dates.get(trade_date)
            if status == 'done':
                return
            if status == 'in_progress':
                print(f"⚠️ 预热已在进行中: {trade_date}", flush=True)
                return
            self._preloaded_daily_dates[trade_date] = 'in_progress'

        start_time = time.time()
        print(f"🚀 开始预热 {trade_date}，批次大小 {batch_size}", flush=True)

        hot_codes: List[str] = []
        hot_sectors: List[Dict[str, Any]] = []
        if self._news_service:
            try:
                hot_codes = self._news_service.get_hot_stock_codes(trade_date, limit=batch_size)
            except Exception as err:
                print(f"⚠️ 获取热点股票失败({trade_date}): {err}", flush=True)
            try:
                hot_sectors = self._news_service.get_hot_sectors(trade_date, limit=20)
            except Exception as err:
                print(f"⚠️ 获取热门板块失败({trade_date}): {err}", flush=True)

        with self._cache_lock:
            whitelist = list(self._stock_whitelist)

        if not whitelist:
            print("⚠️ 白名单为空，跳过预热", flush=True)
            with self._preload_lock:
                self._preloaded_daily_dates.pop(trade_date, None)
            return

        # 组合候选：优先热点，其次白名单剩余
        ordered_codes: List[str] = []
        seen: set[str] = set()
        for code in hot_codes:
            if code in whitelist and code not in seen:
                ordered_codes.append(code)
                seen.add(code)
            elif code not in seen:
                ordered_codes.append(code)
                seen.add(code)

        for code in whitelist:
            if code not in seen:
                ordered_codes.append(code)
                seen.add(code)

        preloaded: List[Dict[str, Any]] = []
        skipped = 0
        errors = 0

        for ts_code in ordered_codes:
            if len(preloaded) >= batch_size:
                break

            if self._delisted_or_st.get(ts_code):
                skipped += 1
                continue

            try:
                info = self.get_stock_basic_info(ts_code)
                daily = self.get_daily_price(ts_code, trade_date)
            except Exception as err:
                errors += 1
                print(f"⚠️ 预热获取失败 {trade_date} {ts_code}: {err}", flush=True)
                continue

            if not daily:
                errors += 1
                print(f"⚠️ 预热无行情 {trade_date} {ts_code}: daily=None", flush=True)
                continue

            price = daily.get('close', 0)
            volume = daily.get('volume', 0)
            if price <= 0 or volume <= 0:
                skipped += 1
                print(
                    f"⚠️ 预热过滤 {trade_date} {ts_code}: price={price}, volume={volume}",
                    flush=True
                )
                continue

            preloaded.append({
                'code': ts_code,
                'name': info.get('name', ts_code),
                'close': price,
                'pct_chg': daily.get('pct_chg', 0),
                'industry': info.get('industry', ''),
                'pe_ttm': daily.get('pe_ttm', 0),
                'turnover_rate': daily.get('turnover_rate', 0),
            })

        with self._cache_lock:
            self._candidate_pool_by_date[trade_date] = {
                'candidates': preloaded,
                'hot_codes': hot_codes,
                'hot_sectors': hot_sectors,
                'generated_at': datetime.now().isoformat(),
                'source': 'preload'
            }

        duration = time.time() - start_time
        print(
            f"✅ 预热完成 {trade_date}: {len(preloaded)} 只，热点 {len(hot_codes)}，跳过 {skipped}，错误 {errors}，耗时 {duration:.1f}s",
            flush=True
        )

        with self._preload_lock:
            self._preloaded_daily_dates[trade_date] = 'done'

    def get_candidate_pool(self, trade_date: str) -> Dict[str, Any]:
        """返回指定交易日的候选池（如果不存在则尝试即时预热）。"""
        with self._cache_lock:
            pool = self._candidate_pool_by_date.get(trade_date)
            if pool:
                return pool

        print(f"⚠️ {trade_date} 候选池缓存缺失，尝试即时预热", flush=True)
        try:
            self.preload_daily_data(trade_date)
        except Exception as exc:
            print(f"❌ 即时预热失败 ({trade_date}): {exc}", flush=True)
            with self._preload_lock:
                # 允许后续重试
                if self._preloaded_daily_dates.get(trade_date) != 'done':
                    self._preloaded_daily_dates.pop(trade_date, None)
            return {'candidates': [], 'hot_codes': [], 'hot_sectors': [], 'source': 'fallback'}

        with self._cache_lock:
            return self._candidate_pool_by_date.get(
                trade_date,
                {'candidates': [], 'hot_codes': [], 'hot_sectors': [], 'source': 'fallback'}
            )

    def get_candidates(self, trade_date: str, max_price: float, limit: int) -> List[Dict[str, float]]:
        """获取候选股票列表，优先使用预热缓存。"""
        pool = self.get_candidate_pool(trade_date)
        candidates = pool.get('candidates', [])
        filtered = []
        
        if candidates:
            print(f"🔍 [{trade_date}] 开始过滤: 候选={len(candidates)}只, max_price={max_price}", flush=True)
            # 打印前5只股票的价格
            for i, c in enumerate(candidates[:5]):
                print(f"   样本{i+1}: {c.get('code')} price={c.get('close', 0)}", flush=True)
            
            filtered = [
                c for c in candidates
                if c.get('close', 0) > 0 and c.get('close', 0) <= max_price
            ]
            
            print(f"✅ [{trade_date}] 过滤结果: {len(filtered)}只符合条件", flush=True)
            
            if filtered:
                # 热点优先
                hot_codes = set(pool.get('hot_codes', []))
                ordered = [c for c in filtered if c.get('code') in hot_codes]
                ordered.extend(c for c in filtered if c.get('code') not in hot_codes)
                return ordered[:limit]

        print(
            f"⚠️ {trade_date} 缓存候选池为空或过滤后为空，触发退化遍历"
            f" (候选={len(candidates)}, 过滤后={len(filtered)})",
            flush=True
        )

        # 退化逻辑：回到旧的遍历方式，但遵循白名单与热点
        with self._cache_lock:
            fallback_codes = list(self._stock_whitelist)

        result: List[Dict[str, float]] = []
        skipped_count = 0
        error_count = 0
        hot_codes_set = set(pool.get('hot_codes', []))

        for ts_code in fallback_codes:
            try:
                info = self.get_stock_basic_info(ts_code)
                if self._delisted_or_st.get(ts_code):
                    skipped_count += 1
                    continue

                daily = self.get_daily_price(ts_code, trade_date)
                if not daily:
                    error_count += 1
                    continue

                price = daily.get('close', 0)
                if price <= 0 or price > max_price:
                    continue

                # 长期停牌（无成交量）直接跳过
                if daily.get('volume', 0) <= 0:
                    skipped_count += 1
                    continue

                result.append({
                    'code': ts_code,
                    'name': info.get('name', ts_code),
                    'close': price,
                    'pct_chg': daily.get('pct_chg', 0),
                    'industry': info.get('industry', ''),
                    'pe_ttm': daily.get('pe_ttm', 0),
                    'turnover_rate': daily.get('turnover_rate', 0),
                    'is_hot': ts_code in hot_codes_set
                })

                if len(result) >= limit:
                    break
            except Exception:
                error_count += 1
                continue

        if error_count or skipped_count:
            print(
                f"  📊 退化候选筛选: 找到{len(result)}只，跳过{skipped_count}，错误{error_count}",
                flush=True
            )
        else:
            print(f"  ✅ 退化模式完成，共 {len(result)} 只候选", flush=True)

        return result

    def get_latest_price(self, ts_code: str) -> Optional[Dict[str, float]]:
        """获取最新价格"""
        today = datetime.now().strftime('%Y%m%d')
        return self.get_daily_price(ts_code, today)
    
    def get_index_data(self, trade_date: str) -> Dict[str, Dict[str, float]]:
        """
        获取主要指数数据
        
        Args:
            trade_date: 交易日期 YYYYMMDD
            
        Returns:
            {
                'sh_index': {上证指数数据},
                'sz_index': {深证成指数据},
                'hs300': {沪深300数据},
                'cyb_index': {创业板指数据}
            }
        """
        # 清理过期缓存
        if len(self._index_cache) > 200:
            self.clean_expired_index_cache(current_trade_date=trade_date, months=6)
        
        # 指数代码
        indices = {
            'sh_index': 'sh.000001',  # 上证指数
            'sz_index': 'sz.399001',  # 深证成指
            'hs300': 'sh.000300',     # 沪深300
            'cyb_index': 'sz.399006'  # 创业板指
        }
        
        result = {}
        for name, code in indices.items():
            index_data = self._get_index_daily(code, trade_date)
            if index_data:
                result[name] = index_data
        
        return result
    
    def _get_index_daily(self, index_code: str, trade_date: str) -> Optional[Dict[str, float]]:
        """
        获取单个指数某日数据
        
        Args:
            index_code: 指数代码 sh.000001
            trade_date: 交易日期 YYYYMMDD
            
        Returns:
            指数数据字典
        """
        # 检查缓存
        key = (index_code, trade_date)
        with self._cache_lock:
            if key in self._index_cache:
                return self._index_cache[key]
        
        try:
            date_fmt = self._format_date(trade_date)
            
            def _fetch():
                rs = bs.query_history_k_data_plus(
                    index_code,
                    "date,code,open,high,low,close,preclose,volume,amount,pctChg",
                    start_date=date_fmt,
                    end_date=date_fmt,
                    frequency="d",
                    adjustflag="3"
                )
                rows = []
                while rs.error_code == '0' and rs.next():
                    rows.append(rs.get_row_data())
                return rows
            
            rows = self._query_with_retry(_fetch)
            
            # 处理编码错误返回None的情况
            if rows is None:
                return None
            
            if not rows:
                return None
            
            row = rows[0]
            result = {
                'code': index_code,
                'close': self._normalize_float(row[5]),
                'open': self._normalize_float(row[2]),
                'high': self._normalize_float(row[3]),
                'low': self._normalize_float(row[4]),
                'preclose': self._normalize_float(row[6]),
                'volume': self._normalize_float(row[7]),
                'amount': self._normalize_float(row[8]),
                'pct_chg': self._normalize_float(row[9]),
                'trade_date': trade_date
            }
            
            # 缓存
            with self._cache_lock:
                self._index_cache[key] = result
            
            return result
            
        except Exception as e:
            return None
    
    def preload_index_data(self, start_date: str, end_date: str) -> bool:
        """
        预加载指数数据
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            是否成功
        """
        print("📈 预加载指数数据（前后各一周）...")
        
        try:
            # 扩展日期范围
            start_dt = datetime.strptime(start_date, '%Y%m%d') - timedelta(days=7)
            end_dt = datetime.strptime(end_date, '%Y%m%d') + timedelta(days=7)
            
            extended_start = start_dt.strftime('%Y%m%d')
            extended_end = end_dt.strftime('%Y%m%d')
            
            print(f"   日期范围: {extended_start[:4]}-{extended_start[4:6]}-{extended_start[6:8]} ~ {extended_end[:4]}-{extended_end[4:6]}-{extended_end[6:8]}")
            
            # 获取交易日
            trade_dates = self.get_trade_dates(extended_start, extended_end)
            
            # 指数列表
            indices = {
                '上证指数': 'sh.000001',
                '深证成指': 'sz.399001',
                '沪深300': 'sh.000300',
                '创业板指': 'sz.399006'
            }
            
            # 批量获取
            for name, code in indices.items():
                count = 0
                for trade_date in trade_dates:
                    data = self._get_index_daily(code, trade_date)
                    if data:
                        count += 1
                
                print(f"   - {name}: {count} 条")
            
            total_cached = len(self._index_cache)
            print(f"✅ 指数数据已加载到内存: {total_cached} 条记录")
            return True
            
        except Exception as e:
            print(f"⚠️ 指数数据预加载失败: {e}")
            return False
    
    def clean_expired_index_cache(self, current_trade_date: str, months: int = 6):
        """清理过期缓存"""
        try:
            current_dt = datetime.strptime(current_trade_date, '%Y%m%d')
            cutoff_dt = current_dt - timedelta(days=months * 30)
            cutoff_date = cutoff_dt.strftime('%Y%m%d')
            
            with self._cache_lock:
                expired_keys = [
                    k for k in self._index_cache.keys()
                    if k[1] < cutoff_date
                ]
                
                for key in expired_keys:
                    del self._index_cache[key]
                
                if expired_keys:
                    print(f"🗑️ 已清理 {len(expired_keys)} 条过期指数缓存")
                    
        except Exception as e:
            print(f"⚠️ 清理缓存失败: {e}")
    
    def __del__(self):
        """析构函数：清理线程本地资源"""
        # 尝试登出当前线程
        try:
            if hasattr(self._thread_local, 'logged_in') and self._thread_local.logged_in:
                bs.logout()
        except:
            pass


# 单例模式
_provider_v2_instance = None

def get_baostock_provider_v2() -> BaostockProviderV2:
    """获取BaostockProvider V2单例"""
    global _provider_v2_instance
    if _provider_v2_instance is None:
        _provider_v2_instance = BaostockProviderV2()
    return _provider_v2_instance

