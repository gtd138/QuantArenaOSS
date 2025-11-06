"""策略优化服务 - 使用DeepSeek动态调整交易策略"""
import json
from typing import Dict, Any, List
from services.deepseek_service import DeepSeekService


class StrategyOptimizer:
    """策略优化器 - 根据回测结果自动优化交易参数"""
    
    def __init__(self, ai_service: DeepSeekService, config: Dict[str, Any]):
        """
        初始化策略优化器
        
        Args:
            ai_service: DeepSeek AI服务
            config: 当前配置
        """
        self.ai = ai_service
        self.config = config
        self.optimization_history = []  # 优化历史
        
    def optimize_strategy(self, backtest_result: Dict[str, Any], 
                         current_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据回测结果优化策略参数
        
        Args:
            backtest_result: 回测结果统计
            current_params: 当前交易参数
            
        Returns:
            Dict: 优化后的参数建议
        """
        # 构建优化提示词
        prompt = self._build_optimization_prompt(backtest_result, current_params)
        
        try:
            response = self.ai.client.chat.completions.create(
                model=self.ai.model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个专业的量化交易策略优化专家。请基于回测结果分析策略表现，并给出参数优化建议。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,  # 降低温度，让建议更保守
                max_tokens=1500
            )
            
            result = self._parse_optimization_result(response.choices[0].message.content)
            
            # 记录优化历史
            self.optimization_history.append({
                'backtest_result': backtest_result,
                'old_params': current_params.copy(),
                'new_params': result.get('suggested_params', {}),
                'reason': result.get('reason', '')
            })
            
            return result
            
        except Exception as e:
            print(f"策略优化失败: {e}")
            return {
                'should_optimize': False,
                'suggested_params': current_params,
                'reason': f'优化失败: {str(e)}'
            }
    
    def _build_optimization_prompt(self, backtest_result: Dict[str, Any], 
                                   current_params: Dict[str, Any]) -> str:
        """构建优化提示词"""
        prompt = f"""
请分析以下量化交易回测结果，并给出策略参数优化建议：

**回测表现**
- 总收益率: {backtest_result.get('total_return', 0):.2f}%
- 最大回撤: {backtest_result.get('max_drawdown', 0):.2f}%
- 交易次数: {backtest_result.get('trade_count', 0)}
- 胜率: {backtest_result.get('win_rate', 0):.2f}%
- 买入次数: {backtest_result.get('buy_count', 0)}
- 卖出次数: {backtest_result.get('sell_count', 0)}

**当前策略参数**
- 止损比例: {current_params.get('stop_loss_pct', 0)*100:.1f}%
- 止盈比例: {current_params.get('stop_profit_pct', 0)*100:.1f}%
- 最大持仓: {current_params.get('max_holdings', 5)}只
- AI置信度阈值: {current_params.get('ai_confidence_threshold', 0.5)}
- 每次分析股票数: {current_params.get('analyze_stock_count', 5)}只
- 单只最大仓位: {current_params.get('max_position_pct', 0)*100:.1f}%

**分析要求**
1. 评估当前策略的优缺点
2. 如果收益率 < 0%，建议调整策略参数
3. 如果最大回撤 > 20%，需要降低风险
4. 如果交易次数过少（< 10次），建议放宽条件
5. 如果胜率 < 40%，需要提高AI置信度阈值
6. 给出具体的参数调整建议

请以JSON格式回复：
{{
    "should_optimize": true/false,
    "analysis": "策略分析",
    "suggested_params": {{
        "stop_loss_pct": 新值,
        "stop_profit_pct": 新值,
        "max_holdings": 新值,
        "ai_confidence_threshold": 新值,
        "analyze_stock_count": 新值,
        "max_position_pct": 新值
    }},
    "reason": "调整理由",
    "expected_improvement": "预期改进"
}}
"""
        return prompt
    
    def _parse_optimization_result(self, content: str) -> Dict[str, Any]:
        """解析优化结果"""
        try:
            import re
            # 提取JSON
            json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
            if json_match:
                # 处理多层嵌套的JSON
                json_str = content[content.find('{'):content.rfind('}')+1]
                result = json.loads(json_str)
                
                # 验证必需字段
                if 'should_optimize' not in result:
                    result['should_optimize'] = False
                if 'suggested_params' not in result:
                    result['suggested_params'] = {}
                if 'reason' not in result:
                    result['reason'] = '无明确建议'
                
                return result
            else:
                return {
                    'should_optimize': False,
                    'suggested_params': {},
                    'reason': '无法解析AI回复',
                    'analysis': content
                }
                
        except Exception as e:
            print(f"解析优化结果失败: {e}")
            return {
                'should_optimize': False,
                'suggested_params': {},
                'reason': f'解析失败: {str(e)}',
                'raw_content': content
            }
    
    def get_optimization_summary(self) -> str:
        """获取优化历史摘要"""
        if not self.optimization_history:
            return "暂无优化历史"
        
        summary = f"优化历史（共{len(self.optimization_history)}次）：\n"
        for i, opt in enumerate(self.optimization_history, 1):
            summary += f"\n第{i}次优化：\n"
            summary += f"  收益率: {opt['backtest_result'].get('total_return', 0):.2f}%\n"
            summary += f"  调整理由: {opt['reason'][:100]}\n"
        
        return summary
