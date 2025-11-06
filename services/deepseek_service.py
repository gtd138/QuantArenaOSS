"""DeepSeek AI服务"""
import json
import time
from typing import Dict, Any, Optional, List
from openai import OpenAI


class DeepSeekService:
    """DeepSeek AI服务（单例模式）"""
    _instance = None
    
    def __new__(cls, api_key: str = '', api_base: str = '', model: str = 'deepseek-chat'):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, api_key: str = '', api_base: str = '', model: str = 'deepseek-chat'):
        if api_key and not hasattr(self, '_initialized'):
            self.client = OpenAI(
                api_key=api_key,
                base_url=api_base,
                timeout=60.0,  # 设置60秒超时
                max_retries=3  # 最多重试3次
            )
            self.model = model
            self._initialized = True
    
    def analyze_stock(self, stock_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析股票并给出交易建议
        
        Args:
            stock_data: 股票数据，包括：
                - code: 股票代码
                - name: 股票名称
                - price: 当前价格
                - history: 历史数据（最近N天的收盘价、成交量等）
                - indicators: 技术指标
                
        Returns:
            Dict包含：
                - action: 'buy' | 'sell' | 'hold'
                - confidence: 置信度 (0-1)
                - reason: 决策理由
                - suggested_amount: 建议数量（股）
        """
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                prompt = self._build_analysis_prompt(stock_data)
                
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "你是一个专业的股票分析师和交易顾问。请基于提供的数据进行理性分析，给出具体的交易建议。"
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.7,
                    max_tokens=1000
                )
            
                result = self._parse_analysis_result(response.choices[0].message.content)
                
                # 提取推理过程（如果有）
                if hasattr(response.choices[0].message, 'reasoning_content'):
                    result['reasoning'] = response.choices[0].message.reasoning_content
                
                return result
                
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"AI分析失败（第{attempt+1}次尝试）: {e}，{retry_delay}秒后重试...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # 指数退避
                else:
                    print(f"AI分析失败（已重试{max_retries}次）: {e}")
                    return {
                        'action': 'hold',
                        'confidence': 0.0,
                        'reason': f'分析失败: {str(e)}',
                        'suggested_amount': 0
                    }
    
    def select_stocks(self, candidates: List[Dict[str, Any]], max_select: int = 5) -> List[str]:
        """
        从候选股票中选择最优股票
        
        Args:
            candidates: 候选股票列表
            max_select: 最多选择数量
            
        Returns:
            List[str]: 选中的股票代码列表
        """
        try:
            prompt = self._build_selection_prompt(candidates, max_select)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个专业的选股专家。请从候选股票中选出最有潜力的股票，并说明理由。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.8,
                max_tokens=1500
            )
            
            result = self._parse_selection_result(response.choices[0].message.content)
            return result
            
        except Exception as e:
            print(f"选股分析失败: {e}")
            return []
    
    def _build_analysis_prompt(self, stock_data: Dict[str, Any]) -> str:
        """构建分析提示词"""
        prompt = f"""
请分析以下股票并给出交易建议：

**基本信息**
- 代码: {stock_data.get('code', 'N/A')}
- 名称: {stock_data.get('name', 'N/A')}
- 当前价格: {stock_data.get('price', 0):.2f} 元
- 行业: {stock_data.get('industry', 'N/A')}

**历史数据（最近5天）**
"""
        
        history = stock_data.get('history', [])
        if history:
            for day in history[:5]:
                prompt += f"- {day.get('date', 'N/A')}: 收盘 {day.get('close', 0):.2f}, "
                prompt += f"涨跌幅 {day.get('pct_chg', 0):+.2f}%, "
                prompt += f"成交量 {day.get('vol', 0):.0f}手\n"
        
        prompt += f"""
**技术指标**
- 5日均价: {stock_data.get('ma5', 0):.2f}
- 10日均价: {stock_data.get('ma10', 0):.2f}
- 资金流入: {stock_data.get('money_flow', 0):.2f} 万元

**当前持仓**
- 可用资金: {stock_data.get('available_cash', 0):.2f} 元
- 持仓数量: {stock_data.get('holding', 0)} 股

请根据以上信息，给出交易建议。请以JSON格式回复：
{{
    "action": "buy/sell/hold",
    "confidence": 0.0-1.0,
    "reason": "决策理由",
    "suggested_amount": 数量（股，必须是100的整数倍）
}}
"""
        return prompt
    
    def _build_selection_prompt(self, candidates: List[Dict[str, Any]], max_select: int) -> str:
        """构建选股提示词"""
        prompt = f"请从以下 {len(candidates)} 只候选股票中选出最有潜力的 {max_select} 只：\n\n"
        
        for i, stock in enumerate(candidates[:20], 1):  # 最多展示20只
            prompt += f"{i}. {stock.get('code', 'N/A')} {stock.get('name', 'N/A')}\n"
            prompt += f"   价格: {stock.get('price', 0):.2f} 元, "
            prompt += f"涨跌幅: {stock.get('pct_chg', 0):+.2f}%, "
            prompt += f"行业: {stock.get('industry', 'N/A')}\n"
        
        prompt += f"\n请选出 {max_select} 只股票，并以JSON列表格式返回股票代码：\n"
        prompt += '["代码1", "代码2", ...]\n'
        
        return prompt
    
    def _parse_analysis_result(self, content: str) -> Dict[str, Any]:
        """解析分析结果"""
        try:
            # 尝试提取JSON
            import re
            json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                
                # 验证必需字段
                if 'action' not in result:
                    result['action'] = 'hold'
                if 'confidence' not in result:
                    result['confidence'] = 0.5
                if 'reason' not in result:
                    result['reason'] = content
                if 'suggested_amount' not in result:
                    result['suggested_amount'] = 0
                
                # 确保数量是100的整数倍
                result['suggested_amount'] = int(result['suggested_amount'] / 100) * 100
                
                return result
            else:
                # 无法解析JSON，返回默认值
                return {
                    'action': 'hold',
                    'confidence': 0.5,
                    'reason': content,
                    'suggested_amount': 0
                }
                
        except Exception as e:
            print(f"解析分析结果失败: {e}")
            return {
                'action': 'hold',
                'confidence': 0.0,
                'reason': '解析失败',
                'suggested_amount': 0
            }
    
    def _parse_selection_result(self, content: str) -> List[str]:
        """解析选股结果"""
        try:
            import re
            # 尝试提取JSON数组
            json_match = re.search(r'\[([^\]]+)\]', content)
            if json_match:
                result = json.loads(json_match.group())
                return [str(code).strip() for code in result]
            else:
                # 尝试提取股票代码（格式如 000001.SZ）
                codes = re.findall(r'\d{6}\.[A-Z]{2}', content)
                return codes[:10]  # 最多返回10只
                
        except Exception as e:
            print(f"解析选股结果失败: {e}")
            return []
