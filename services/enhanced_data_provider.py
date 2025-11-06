"""
增强数据提供者
整合基本面、技术面等多维度分析
"""
from services.fundamental_analyzer import FundamentalAnalyzer
from services.technical_analyzer import TechnicalAnalyzer
from typing import Dict, Optional, List
import time

class EnhancedDataProvider:
    """
    增强数据提供者
    整合多个分析模块，提供全面的股票分析
    """
    
    def __init__(self):
        self.fundamental = FundamentalAnalyzer()
        self.technical = TechnicalAnalyzer()
        self.cache = {}
        self.cache_ttl = 300  # 5分钟缓存
    
    def get_stock_analysis(self, code: str, modules: List[str] = None) -> Dict:
        """
        获取股票多维度分析
        
        Args:
            code: 股票代码
            modules: 需要的模块列表 ['fundamental', 'technical'] 或 None (全部)
            
        Returns:
            分析结果字典
        """
        if modules is None:
            modules = ['fundamental', 'technical']
        
        result = {}
        
        # 基本面分析
        if 'fundamental' in modules:
            fundamental_data = self.fundamental.analyze(code)
            if fundamental_data:
                result['fundamental'] = fundamental_data
        
        # 技术面分析
        if 'technical' in modules:
            technical_data = self.technical.analyze(code)
            if technical_data:
                result['technical'] = technical_data
        
        # 生成综合摘要
        result['summary'] = self._generate_综合摘要(code, result)
        
        return result
    
    def get_analysis_summary(self, code: str) -> str:
        """
        获取综合分析摘要（自然语言）
        供Agent Prompt使用
        
        Args:
            code: 股票代码
            
        Returns:
            自然语言摘要
        """
        try:
            # 检查缓存
            cache_key = f"summary_{code}"
            if cache_key in self.cache:
                cache_time, cached_result = self.cache[cache_key]
                if time.time() - cache_time < self.cache_ttl:
                    return cached_result
            
            # 获取分析
            analysis = self.get_stock_analysis(code)
            
            # 生成摘要
            summary_parts = []
            has_data = False
            
            # 基本面部分
            if 'fundamental' in analysis:
                fundamental_summary = self.fundamental.get_analysis_summary(code)
                if "获取失败" not in fundamental_summary:
                    summary_parts.append(fundamental_summary)
                    has_data = True
            
            # 技术面部分
            if 'technical' in analysis:
                technical_summary = self.technical.get_analysis_summary(code)
                if "获取失败" not in technical_summary:
                    summary_parts.append(technical_summary)
                    has_data = True
            
            # 如果没有任何数据
            if not has_data:
                return f"⚠️ {code} 详细数据暂时不可用（网络问题），建议参考基础指标"
            
            # 综合判断
            综合判断 = self._generate_买入建议(analysis)
            summary_parts.append(f"\n【综合判断】{综合判断}")
            
            result = "\n\n".join(summary_parts)
            
            # 缓存结果
            self.cache[cache_key] = (time.time(), result)
            
            return result
            
        except Exception as e:
            # 降级返回简化信息
            return f"⚠️ {code} 详细数据暂时不可用（网络问题），建议参考基础指标"
    
    def _generate_综合摘要(self, code: str, analysis: Dict) -> str:
        """生成综合摘要"""
        parts = []
        
        if 'fundamental' in analysis:
            score = analysis['fundamental']['overall_score']
            parts.append(f"基本面{score}分")
        
        if 'technical' in analysis:
            summary = analysis['technical']['summary']
            parts.append(f"技术面: {summary}")
        
        return " | ".join(parts) if parts else "数据不足"
    
    def _generate_买入建议(self, analysis: Dict) -> str:
        """生成买入建议"""
        signals = []
        
        # 基本面评分
        fundamental_score = 0
        if 'fundamental' in analysis:
            fundamental_score = analysis['fundamental']['overall_score']
            if fundamental_score >= 70:
                signals.append("基本面优秀")
            elif fundamental_score >= 50:
                signals.append("基本面良好")
        
        # 技术面评分
        technical_score = 0
        if 'technical' in analysis:
            tech = analysis['technical']
            
            # 趋势
            if tech['trend']['direction'] == 'up':
                technical_score += 30
                signals.append("上升趋势")
            elif tech['trend']['direction'] == 'down':
                technical_score -= 20
                signals.append("下跌趋势")
            
            # MACD
            if tech['indicators']['macd']['signal'] == 'golden_cross':
                technical_score += 20
                signals.append("MACD金叉")
            elif tech['indicators']['macd']['signal'] == 'death_cross':
                technical_score -= 20
            
            # RSI
            if tech['indicators']['rsi']['status'] == 'oversold':
                technical_score += 10
                signals.append("RSI超卖")
            elif tech['indicators']['rsi']['status'] == 'overbought':
                technical_score -= 10
            
            # 量价
            if tech['volume']['price_volume'] == 'rising_with_volume':
                technical_score += 20
                signals.append("放量上涨")
            elif tech['volume']['price_volume'] == 'falling_with_volume':
                technical_score -= 20
        
        # 综合判断
        total_score = (fundamental_score * 0.4 + technical_score * 0.6)
        
        if total_score >= 60 and len(signals) >= 2:
            recommendation = f"✓ 买入信号较强 ({'+'.join(signals)})"
        elif total_score >= 40:
            recommendation = f"⚠️ 观望为主 ({', '.join(signals) if signals else '信号不明显'})"
        else:
            recommendation = "✗ 不建议买入"
        
        return recommendation
    
    def batch_analyze(self, codes: List[str]) -> Dict[str, str]:
        """
        批量分析多只股票（用于候选股票列表）
        
        Args:
            codes: 股票代码列表
            
        Returns:
            {code: summary} 字典
        """
        results = {}
        
        for code in codes:
            try:
                summary = self.get_analysis_summary(code)
                results[code] = summary
            except Exception as e:
                print(f"⚠️ 分析{code}失败: {e}")
                results[code] = "⚠️ 分析失败"
        
        return results
