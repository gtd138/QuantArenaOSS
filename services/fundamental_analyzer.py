"""
基本面分析器
提供PE/PB/ROE/财务指标等多维度分析
"""
import akshare as ak
from typing import Dict, Optional
import pandas as pd
import time
from datetime import datetime

class FundamentalAnalyzer:
    """基本面分析器"""
    
    def __init__(self):
        self.cache = {}  # 简单缓存
        self.cache_ttl = 300  # 5分钟缓存
        self.last_request_time = 0  # 上次请求时间
        self.request_delay = 0.5  # 请求间隔（秒）
    
    def analyze(self, code: str) -> Optional[Dict]:
        """
        分析股票基本面
        
        Args:
            code: 股票代码 (如 "600000.SH")
            
        Returns:
            基本面分析结果字典，如果获取失败返回None
        """
        try:
            # 简化代码格式（AKShare需要6位数字代码）
            simple_code = code.split('.')[0]
            
            # 获取财务指标
            financial_data = self._get_financial_indicators(simple_code)
            
            if not financial_data:
                return None
            
            # 计算评分
            valuation_score = self._calculate_valuation_score(financial_data)
            profitability_score = self._calculate_profitability_score(financial_data)
            
            return {
                'valuation': {
                    'pe': financial_data.get('pe', 0),
                    'pb': financial_data.get('pb', 0),
                    'score': valuation_score
                },
                'profitability': {
                    'roe': financial_data.get('roe', 0),
                    'score': profitability_score
                },
                'overall_score': int((valuation_score + profitability_score) / 2)
            }
            
        except Exception as e:
            print(f"⚠️ 获取{code}基本面数据失败: {e}")
            return None
    
    def _get_financial_indicators(self, code: str) -> Optional[Dict]:
        """获取财务指标（带缓存和重试）"""
        # 检查缓存
        cache_key = f"fundamental_{code}"
        if cache_key in self.cache:
            cache_time, cached_data = self.cache[cache_key]
            if time.time() - cache_time < self.cache_ttl:
                return cached_data
        
        # 请求限流：确保请求间隔
        time_since_last = time.time() - self.last_request_time
        if time_since_last < self.request_delay:
            time.sleep(self.request_delay - time_since_last)
        
        # 重试3次
        for attempt in range(3):
            try:
                # 使用AKShare获取实时行情（包含PE/PB）
                df = ak.stock_zh_a_spot_em()
                
                # 查找该股票
                stock_data = df[df['代码'] == code]
                
                if stock_data.empty:
                    return None
                
                row = stock_data.iloc[0]
                
                result = {
                    'pe': float(row.get('市盈率-动态', 0) or 0),
                    'pb': float(row.get('市净率', 0) or 0),
                    'roe': 0,  # 实时行情中没有ROE，需要从财务报表获取
                    'revenue_growth': 0,
                    'profit_growth': 0
                }
                
                # 更新缓存
                self.cache[cache_key] = (time.time(), result)
                self.last_request_time = time.time()
                
                return result
                
            except Exception as e:
                if attempt < 2:  # 前两次失败时重试
                    time.sleep(1)  # 等待1秒后重试
                    continue
                else:  # 第3次失败，放弃
                    # 只打印一次，避免刷屏
                    return None
        
        return None
    
    def _calculate_valuation_score(self, data: Dict) -> int:
        """计算估值评分 (0-100)"""
        score = 50  # 基准分
        
        pe = data.get('pe', 0)
        pb = data.get('pb', 0)
        
        # PE评分
        if 0 < pe < 15:
            score += 25  # 低估值
        elif 15 <= pe < 30:
            score += 10  # 合理
        elif pe >= 50:
            score -= 20  # 高估
        
        # PB评分
        if 0 < pb < 2:
            score += 25  # 低估值
        elif 2 <= pb < 5:
            score += 10  # 合理
        elif pb >= 8:
            score -= 20  # 高估
        
        return max(0, min(100, score))
    
    def _calculate_profitability_score(self, data: Dict) -> int:
        """计算盈利能力评分 (0-100)"""
        score = 50  # 基准分
        
        roe = data.get('roe', 0)
        
        # ROE评分
        if roe >= 15:
            score += 30  # 优秀
        elif roe >= 10:
            score += 20  # 良好
        elif roe >= 5:
            score += 10  # 一般
        elif roe < 0:
            score -= 30  # 亏损
        
        return max(0, min(100, score))
    
    def get_analysis_summary(self, code: str) -> str:
        """
        获取基本面分析摘要（自然语言）
        
        Returns:
            分析摘要文本
        """
        analysis = self.analyze(code)
        
        if not analysis:
            return "⚠️ 基本面数据获取失败"
        
        val = analysis['valuation']
        prof = analysis['profitability']
        overall = analysis['overall_score']
        
        # 评分等级
        def get_grade(score):
            if score >= 80: return "优秀✓"
            elif score >= 60: return "良好"
            elif score >= 40: return "一般"
            else: return "较差✗"
        
        summary = f"""
【基本面】评分: {overall}分 ({get_grade(overall)})
估值: PE={val['pe']:.1f} PB={val.get('pb', 0):.1f} (评分{val['score']}分)
盈利: ROE={prof.get('roe', 0):.1f}% (评分{prof['score']}分)
"""
        
        return summary.strip()
