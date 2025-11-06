"""反思服务 - 让AI从经验中学习和改进"""
from typing import Dict, List, Any, Optional
from services.deepseek_service import DeepSeekService
import json


class ReflectionService:
    """
    反思服务 - Agent的自我学习和改进能力
    
    功能：
    1. 每日反思：分析当天决策的对错
    2. 经验总结：从成功/失败中提取模式
    3. 策略调整：根据表现动态优化
    4. 记忆管理：积累和检索经验
    """
    
    def __init__(self, ai_service: DeepSeekService):
        """
        初始化反思服务
        
        Args:
            ai_service: DeepSeek AI服务
        """
        self.ai = ai_service
        
        # 经验记忆库
        self.memory = {
            'successful_patterns': [],  # 成功模式
            'failed_patterns': [],      # 失败模式
            'insights': [],             # 洞察
            'strategy_adjustments': []  # 策略调整历史
        }
        
        # 性能追踪
        self.performance_history = []
    
    def daily_reflection(self, day_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        每日反思 - 分析当天的决策和结果
        
        Args:
            day_data: {
                'date': '20240115',
                'trades': [...],  # 当天的交易
                'decisions': [...],  # AI做的决策
                'results': {...},  # 当天的结果
                'holdings': {...}  # 持仓状态
            }
            
        Returns:
            Dict: 反思结果
        """
        if not day_data.get('trades'):
            # 没有交易，不反思
            return {'has_reflection': False}
        
        prompt = f"""
你是一个自我反思的AI交易员。请回顾今天的交易，深入分析决策的对错。

**今天的日期**: {day_data['date']}

**今天的交易**:
{json.dumps(day_data.get('trades', []), ensure_ascii=False, indent=2)}

**今天的决策逻辑**:
{json.dumps(day_data.get('decisions', []), ensure_ascii=False, indent=2)}

**今天的结果**:
- 总资产: {day_data.get('results', {}).get('total_assets', 0):.2f}元
- 现金: {day_data.get('results', {}).get('cash', 0):.2f}元
- 持仓数: {day_data.get('results', {}).get('holdings_count', 0)}只
- 今日收益: {day_data.get('results', {}).get('daily_profit', 0):.2f}元

**反思任务**:
1. 分析每笔交易的决策是否正确
2. 如果盈利，总结成功的原因（不要归功于运气）
3. 如果亏损，深挖失败的根本原因
4. 提取可复用的经验教训
5. 给出具体的改进建议

请以JSON格式返回：
{{
  "overall_assessment": "今日整体评价",
  "successful_decisions": [
    {{
      "decision": "具体决策",
      "reason": "为什么成功",
      "pattern": "可复用的模式"
    }}
  ],
  "failed_decisions": [
    {{
      "decision": "具体决策",
      "reason": "为什么失败",
      "lesson": "吸取的教训"
    }}
  ],
  "insights": ["洞察1", "洞察2"],
  "adjustments": ["建议调整1", "建议调整2"]
}}
"""
        
        try:
            response = self.ai.client.chat.completions.create(
                model=self.ai.model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个善于自我反思和学习的AI交易员。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content
            
            # 解析反思结果
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                reflection = json.loads(json_match.group())
                
                # 更新记忆库
                self._update_memory(reflection)
                
                reflection['has_reflection'] = True
                reflection['date'] = day_data['date']
                
                return reflection
            else:
                return {'has_reflection': False, 'raw': content}
                
        except Exception as e:
            print(f"❌ 每日反思失败: {e}")
            return {'has_reflection': False, 'error': str(e)}
    
    def weekly_summary(self, week_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        周度总结 - 提取一周的经验模式
        
        Args:
            week_data: 一周的交易数据
            
        Returns:
            Dict: 周度总结
        """
        if not week_data:
            return {'has_summary': False}
        
        # 统计本周表现
        total_trades = sum(len(d.get('trades', [])) for d in week_data)
        profitable_days = len([d for d in week_data if d.get('results', {}).get('daily_profit', 0) > 0])
        
        prompt = f"""
你是一个自我学习的AI交易员。请总结这一周的交易经验。

**本周概况**:
- 交易天数: {len(week_data)}天
- 交易次数: {total_trades}次
- 盈利天数: {profitable_days}天

**每日反思摘要**:
{json.dumps([{
    'date': d['date'],
    'trades_count': len(d.get('trades', [])),
    'profit': d.get('results', {}).get('daily_profit', 0)
} for d in week_data], ensure_ascii=False, indent=2)}

**任务**:
1. 找出本周成功的交易模式
2. 找出本周失败的交易模式
3. 总结关键洞察
4. 给出下周的策略建议

返回JSON格式：
{{
  "successful_patterns": ["模式1", "模式2"],
  "failed_patterns": ["模式1", "模式2"],
  "key_insights": ["洞察1", "洞察2"],
  "next_week_strategy": "下周策略建议"
}}
"""
        
        try:
            response = self.ai.client.chat.completions.create(
                model=self.ai.model,
                messages=[
                    {"role": "system", "content": "你是善于总结经验的AI交易员。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1500
            )
            
            content = response.choices[0].message.content
            
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                summary = json.loads(json_match.group())
                summary['has_summary'] = True
                
                # 更新记忆
                if summary.get('successful_patterns'):
                    self.memory['successful_patterns'].extend(summary['successful_patterns'])
                if summary.get('failed_patterns'):
                    self.memory['failed_patterns'].extend(summary['failed_patterns'])
                
                return summary
            else:
                return {'has_summary': False}
                
        except Exception as e:
            print(f"❌ 周度总结失败: {e}")
            return {'has_summary': False, 'error': str(e)}
    
    def suggest_strategy_adjustment(self, performance: Dict[str, Any]) -> Dict[str, Any]:
        """
        策略调整建议 - 根据表现动态优化
        
        Args:
            performance: {
                'win_rate': 0.45,
                'total_return': -5.2,
                'recent_trades': [...],
                'current_params': {...}
            }
            
        Returns:
            Dict: 调整建议
        """
        prompt = f"""
你是一个自我优化的AI交易员。根据近期表现，给出策略调整建议。

**近期表现**:
- 胜率: {performance.get('win_rate', 0)*100:.1f}%
- 总收益率: {performance.get('total_return', 0):.2f}%
- 最大回撤: {performance.get('max_drawdown', 0):.2f}%
- 交易次数: {performance.get('trade_count', 0)}次

**当前策略参数**:
{json.dumps(performance.get('current_params', {}), ensure_ascii=False, indent=2)}

**已知的成功模式**:
{json.dumps(self.memory['successful_patterns'][-5:], ensure_ascii=False)}

**已知的失败模式**:
{json.dumps(self.memory['failed_patterns'][-5:], ensure_ascii=False)}

**任务**:
如果表现不佳（胜率<50%或收益<0），给出具体调整建议：
1. 应该调整哪些参数？
2. 应该避免什么行为？
3. 应该强化什么策略？

返回JSON格式：
{{
  "should_adjust": true/false,
  "reason": "调整理由",
  "suggested_changes": {{
    "ai_confidence_threshold": 新值或null,
    "max_holdings": 新值或null,
    "focus_on": ["关注点1", "关注点2"],
    "avoid": ["避免1", "避免2"]
  }},
  "expected_improvement": "预期改进效果"
}}
"""
        
        try:
            response = self.ai.client.chat.completions.create(
                model=self.ai.model,
                messages=[
                    {"role": "system", "content": "你是善于自我优化的AI交易员。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1500
            )
            
            content = response.choices[0].message.content
            
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                adjustment = json.loads(json_match.group())
                
                # 记录调整历史
                if adjustment.get('should_adjust'):
                    self.memory['strategy_adjustments'].append({
                        'timestamp': performance.get('date', 'unknown'),
                        'adjustment': adjustment
                    })
                
                return adjustment
            else:
                return {'should_adjust': False}
                
        except Exception as e:
            print(f"❌ 策略调整建议失败: {e}")
            return {'should_adjust': False, 'error': str(e)}
    
    def query_experience(self, context: Dict[str, Any]) -> List[str]:
        """
        查询相关经验 - 在做决策前回忆类似情况
        
        Args:
            context: {
                'stock_code': '601600.SH',
                'situation': '价格下跌5%，资金流出'
            }
            
        Returns:
            List[str]: 相关经验
        """
        relevant_experiences = []
        
        # 简单的关键词匹配（未来可用向量检索）
        query_text = json.dumps(context, ensure_ascii=False).lower()
        
        # 搜索成功模式
        for pattern in self.memory['successful_patterns']:
            if any(keyword in query_text for keyword in ['下跌', '流出', '回调']):
                if any(keyword in pattern.lower() for keyword in ['下跌', '回调', '抄底']):
                    relevant_experiences.append(f"✅ 成功经验: {pattern}")
        
        # 搜索失败模式
        for pattern in self.memory['failed_patterns']:
            if any(keyword in query_text for keyword in ['下跌', '流出']):
                if any(keyword in pattern.lower() for keyword in ['下跌', '抄底', '追跌']):
                    relevant_experiences.append(f"❌ 失败教训: {pattern}")
        
        return relevant_experiences[:3]  # 返回最多3条
    
    def _update_memory(self, reflection: Dict[str, Any]):
        """更新记忆库"""
        self.deepseek = DeepSeekService(
            api_key=config['deepseek']['api_key'],
            api_base=config['deepseek']['api_base'],
            model=config['deepseek']['model']
        )
        # 添加成功模式
        for success in reflection.get('successful_decisions', []):
            if 'pattern' in success:
                self.memory['successful_patterns'].append(success['pattern'])
        
        # 添加失败教训
        for failure in reflection.get('failed_decisions', []):
            if 'lesson' in failure:
                self.memory['failed_patterns'].append(failure['lesson'])
        
        # 添加洞察
        insights = reflection.get('insights', [])
        if insights:
            self.memory['insights'].extend(insights)
        
        # 限制记忆大小（保留最近100条）
        for key in ['successful_patterns', 'failed_patterns', 'insights']:
            if len(self.memory[key]) > 100:
                self.memory[key] = self.memory[key][-100:]
    
    def get_memory_summary(self) -> Dict[str, Any]:
        """获取记忆摘要"""
        return {
            'successful_patterns_count': len(self.memory['successful_patterns']),
            'failed_patterns_count': len(self.memory['failed_patterns']),
            'insights_count': len(self.memory['insights']),
            'adjustments_count': len(self.memory['strategy_adjustments']),
            'recent_successful_patterns': self.memory['successful_patterns'][-5:],
            'recent_failed_patterns': self.memory['failed_patterns'][-5:],
            'recent_insights': self.memory['insights'][-5:]
        }
