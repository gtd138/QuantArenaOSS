"""日期工具类"""
from datetime import datetime, timedelta
from typing import List


class DateUtils:
    """日期工具类"""
    
    @staticmethod
    def format_date(date_str: str, input_fmt: str = '%Y%m%d', output_fmt: str = '%Y-%m-%d') -> str:
        """
        格式化日期
        
        Args:
            date_str: 日期字符串
            input_fmt: 输入格式
            output_fmt: 输出格式
            
        Returns:
            str: 格式化后的日期
        """
        try:
            date_obj = datetime.strptime(date_str, input_fmt)
            return date_obj.strftime(output_fmt)
        except:
            return date_str
    
    @staticmethod
    def get_date_range(start_date: str, end_date: str, fmt: str = '%Y%m%d') -> List[str]:
        """
        获取日期区间内的所有日期
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            fmt: 日期格式
            
        Returns:
            List[str]: 日期列表
        """
        try:
            start = datetime.strptime(start_date, fmt)
            end = datetime.strptime(end_date, fmt)
            
            dates = []
            current = start
            while current <= end:
                dates.append(current.strftime(fmt))
                current += timedelta(days=1)
            
            return dates
        except:
            return []
    
    @staticmethod
    def add_days(date_str: str, days: int, fmt: str = '%Y%m%d') -> str:
        """
        日期加减
        
        Args:
            date_str: 日期字符串
            days: 天数（正数为加，负数为减）
            fmt: 日期格式
            
        Returns:
            str: 新日期
        """
        try:
            date_obj = datetime.strptime(date_str, fmt)
            new_date = date_obj + timedelta(days=days)
            return new_date.strftime(fmt)
        except:
            return date_str
    
    @staticmethod
    def is_valid_date(date_str: str, fmt: str = '%Y%m%d') -> bool:
        """
        检查日期是否有效
        
        Args:
            date_str: 日期字符串
            fmt: 日期格式
            
        Returns:
            bool: 是否有效
        """
        try:
            datetime.strptime(date_str, fmt)
            return True
        except:
            return False
    
    @staticmethod
    def get_today(fmt: str = '%Y%m%d') -> str:
        """
        获取今天的日期
        
        Args:
            fmt: 日期格式
            
        Returns:
            str: 今天的日期
        """
        return datetime.now().strftime(fmt)
    
    @staticmethod
    def compare_dates(date1: str, date2: str, fmt: str = '%Y%m%d') -> int:
        """
        比较两个日期
        
        Args:
            date1: 日期1
            date2: 日期2
            fmt: 日期格式
            
        Returns:
            int: date1 > date2 返回1, date1 == date2 返回0, date1 < date2 返回-1
        """
        try:
            d1 = datetime.strptime(date1, fmt)
            d2 = datetime.strptime(date2, fmt)
            
            if d1 > d2:
                return 1
            elif d1 == d2:
                return 0
            else:
                return -1
        except:
            return 0
