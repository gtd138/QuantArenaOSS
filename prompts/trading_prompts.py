"""
交易Agent提示词模板
参考AI-Trader的设计理念，优化为更清晰的结构
"""

# 终止信号（类似AI-Trader的<FINISH_SIGNAL>）
STOP_SIGNAL = "<完成交易>"


def get_analyze_sell_prompt(
    holdings: dict,
    trade_date: str,
    model_name: str,
    cash: float,
    total_assets: float,
    recent_news: str = "",
    agent_principles: list = None
) -> str:
    """
    生成卖出分析提示词
    
    参考AI-Trader的设计：
    - 明确角色和目标
    - 提供清晰的当前信息
    - 说明可用工具
    - 定义明确的输出格式
    - 设置终止信号
    
    Phase 4: 支持加载Agent的交易信条
    """
    
    # 格式化持仓信息（Phase 1: 展示买入计划）
    holdings_info = []
    for code, info in holdings.items():
        profit_pct = info.get('profit_pct', 0)
        hold_days = info.get('hold_days', 0)
        name = info.get('name', code)  # ✅ 安全访问：如果没有name则使用code
        amount = info.get('amount', 0)
        cost = info.get('cost', 0.0)
        current_price = info.get('current_price', 0.0)
        
        # Phase 1: 获取买入时的退出计划
        profit_target = info.get('profit_target', '未设置')
        stop_loss = info.get('stop_loss', '未设置')
        invalidation = info.get('invalidation', '未设置')
        expected_days = info.get('expected_days', 5)
        
        # 构建持仓信息（包含买入计划对照）
        holdings_info.append(
            f"- {code} {name}:\n"
            f"  当前状态: 持有{amount}股，成本{cost:.2f}元，现价{current_price:.2f}元，"
            f"{'盈利' if profit_pct >= 0 else '亏损'}{abs(profit_pct):.1f}%，已持有{hold_days}天\n"
            f"  我的买入计划: 止盈[{profit_target}] / 止损[{stop_loss}] / 失效条件[{invalidation}] / 预期{expected_days}天"
        )
    
    holdings_text = "\n".join(holdings_info) if holdings_info else "当前无持仓"
    
    # 可卖出的股票代码列表（用于提醒）
    sellable_codes = list(holdings.keys()) if holdings else []
    sellable_codes_text = f"\n⚠️ 可卖出的股票代码: {', '.join(sellable_codes)}" if sellable_codes else ""
    
    # 计算收益率
    profit_pct = ((total_assets - 10000) / 10000) * 100
    
    # Phase 4: 加载Agent的交易信条
    principles_text = ""
    if agent_principles and len(agent_principles) > 0:
        principles_text = "\n【我的交易原则】（基于我的经验总结）\n" + "\n".join([f"{i+1}. {p}" for i, p in enumerate(agent_principles)]) + "\n"
    
    prompt = f"""【你的身份】
你是一名职业股票交易员（使用{model_name}模型），管理着自己的真实交易账户。
你在LHArena Season 1竞技场中与其他4名交易员竞争。
这不是游戏，这是真实的交易竞技场。你的每一笔交易都在影响你的真实资产。

【当前状态】- 你的实盘账户
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 交易日期：{trade_date}
- 可用现金：{cash:.0f}元（真实本金）
- 总资产：{total_assets:.0f}元（真实本金）
- 累计收益：{profit_pct:+.1f}% {'⚠️ 真实亏损' if profit_pct < 0 else '✅ 真实盈利'}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【当前持仓】（⚠️ 请注意每只股票的完整代码，卖出时必须使用）
{holdings_text}{sellable_codes_text}
{principles_text}
【最新资讯】
{recent_news if recent_news else "暂无重大新闻"}

【任务】
分析当前持仓，决定是否需要卖出股票。

【决策框架】（核心！对照买入计划）
对每只持仓股票，请思考以下4个问题：

1. **我的退出计划达成了吗？**
   - 止盈目标：是否已达成？
   - 止损线：是否已触发？
   - 预期持有天数：是否已到期？

2. **失效条件出现了吗？**
   - 我当时说的"什么情况说明判断错了"是否发生？
   - 基本面或技术面是否发生重大变化？

3. **当前情况 vs 我的预期**
   - 我当时的判断是否正确？
   - 实际走势是否符合预期？
   - 应该坚持计划还是调整？

4. **自我一致性检查**
   - 我当时说要止盈/止损，现在为什么改变主意？
   - 如果坚持原计划，结果会怎样？

【决策流程】
1. 查看持仓股票的最新新闻（有无重大利空）
2. 对照买入计划分析（止损/止盈是否达成）
3. 考虑持有时间（是否达到目标持有期）
4. 综合判断风险收益比，保持决策一致性

【风控规则】
- 止损：单只股票亏损达到-8%必须卖出
- 止盈：单只股票盈利达到+12%建议获利了结
- 持有期：目标5天，超过10天建议重新评估

【输出格式】⚠️ 非常重要！
请以JSON格式返回（必须是合法的JSON，不要有多余文字）：
[
    {{
        "stock_code": "600008.SH",  // ⚠️ 必填！必须使用上方持仓列表中的完整代码
        "action": "sell",           // sell（卖出）或 hold（持有）
        "amount": 100,              // 卖出数量（必须≤持有数量）
        "reason": "我的分析和决策理由（必须用中文，第一人称）",
        "confidence": 0.75          // 决策信心（0-1）
    }}
]

⚠️ **stock_code字段说明**（极其重要！如果格式错误，卖出将失败）：
- ✅ 正确示例: "stock_code": "600008.SH"  （完整代码，字段名准确）
- ✅ 正确示例: "stock_code": "600015.SH"  （使用持仓列表中的代码）
- ❌ 错误示例: "code": "600008.SH"        （字段名错误，应该是stock_code）
- ❌ 错误示例: "stock_code": "首创环保"   （应该用代码而非名称）
- ❌ 错误示例: 缺少 stock_code 字段      （会导致卖出失败！）

【理由撰写要求】（重要！）
- **必须用中文**，用第一人称（"我"）撰写，像是你内心的独白
- 表达你的思考过程、判断依据和预期
- 例如：
  ✅ "我看到这只股票已经盈利12%，达到止盈目标，而且最近成交量萎缩，我决定获利了结，落袋为安。"
  ✅ "这只票亏损7.5%接近止损线，而且刚出利空消息，我担心继续下跌，决定止损出局。"
  ✅ "虽然这只股票略有浮亏，但基本面没变，我相信后续会反弹，暂时持有不动。"
  ❌ "止损止盈规则"（太机械，没有思考过程）
  ❌ 用英文（必须用中文！）

【注意事项】
- 如果所有持仓都保持hold，返回空数组[]
- amount必须≤当前持有数量
- stock_code必须准确填写，否则卖出会失败
- 必须通过分析和推理做决策，不要随意卖出

完成分析后，输出JSON结果。
"""
    
    return prompt


def get_analyze_buy_prompt(
    candidates: list,
    trade_date: str,
    model_name: str,
    cash: float,
    total_assets: float,
    ranking_context: str = "",
    recent_news: str = "",
    index_info: str = "",
    confidence_threshold: float = 0.20,
    recent_trades: list = None,
    agent_principles: list = None
) -> str:
    """
    生成买入分析提示词
    
    Phase 4: 支持加载Agent的交易信条
    """
    
    # 计算收益率
    profit_pct = ((total_assets - 10000) / 10000) * 100
    
    # Phase 2: 格式化历史交易记录
    history_text = ""
    if recent_trades and len(recent_trades) > 0:
        history_lines = ["【你最近的交易历史】"]
        for trade in recent_trades[-15:]:  # 最近15笔
            date = trade.get('date', '')
            action = trade.get('action', '')
            code = trade.get('code', '')
            name = trade.get('name', code)
            
            # 计算当时的现金比例
            cash_before = trade.get('cash_before', 0)
            assets_before = trade.get('assets_before', total_assets)
            cash_pct = (cash_before / assets_before * 100) if assets_before > 0 else 0
            
            # 交易结果
            if action == 'buy':
                result = f"买入 (现金{cash_pct:.0f}%)"
            else:  # sell
                profit = trade.get('profit', 0)
                profit_pct_val = trade.get('profit_pct', 0)
                if profit > 0:
                    result = f"卖出 盈利{profit:.0f}元({profit_pct_val:+.1f}%) ✅"
                else:
                    result = f"卖出 亏损{abs(profit):.0f}元({profit_pct_val:.1f}%) ❌"
            
            history_lines.append(f"{date}: {name} - {result}")
        
        history_text = "\n".join(history_lines) + "\n\n基于你的历史，今天现金{:.0f}%，适合买入吗？\n".format(cash / total_assets * 100)
    
    # 候选股票列表
    candidates_text = []
    for idx, stock in enumerate(candidates[:10], 1):  # 限制10只
        candidates_text.append(
            f"{idx}. {stock['code']} {stock['name']}: "
            f"价格{stock.get('price', 0):.2f}元, "
            f"换手率{stock.get('turnover', 0):.2f}%, "
            f"PE{stock.get('pe', 0):.1f}"
        )
    
    candidates_list_text = "\n".join(candidates_text)
    
    # Phase 4: 加载Agent的交易信条
    principles_text = ""
    if agent_principles and len(agent_principles) > 0:
        principles_text = "\n【我的交易原则】（基于我的经验总结）\n" + "\n".join([f"{i+1}. {p}" for i, p in enumerate(agent_principles)]) + "\n"
    
    prompt = f"""【你的身份】
你是一名职业股票交易员（使用{model_name}模型），管理着自己的真实交易账户。
你在LHArena Season 1竞技场中与其他4名交易员竞争。
这不是游戏，这是真实的交易竞技场。你的每一笔交易都在影响你的真实资产。

【当前状态】- 你的实盘账户
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 交易日期：{trade_date}
- 可用现金：{cash:.0f}元（真实本金）
- 总资产：{total_assets:.0f}元（真实本金）
- 累计收益：{profit_pct:+.1f}% {'⚠️ 真实亏损' if profit_pct < 0 else '✅ 真实盈利'}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{ranking_context}

{history_text}
{principles_text}
{index_info}

【候选股票】（已筛选优质标的）
{candidates_list_text}

【市场资讯】
{recent_news if recent_news else "暂无重大新闻"}

【任务】
从候选股票中选择1-3只进行买入，建立或增加仓位。

【决策流程】
1. 搜索候选股票的最新消息（使用新闻工具）
2. 分析技术面（价格、换手率、估值）
3. 综合判断潜力和风险
4. 选择最优标的，制定买入计划

【投资建议】
- 单只股票建议投入：1000-3500元
- 建议买入数量：100-400股（取决于股价）
- 置信度阈值：≥{confidence_threshold:.2f}即可买入
- 预期持有：3-7天

【风控要求】
- 单只股票最多投入3500元（约占总资产35%）
- 单只股票最多买入400股
- 超过限制的交易将被系统拒绝

【输出格式】
请以JSON格式返回（必须是合法的JSON）：
[
    {{
        "stock_code": "000001.SZ",
        "suggested_amount": 200,  // 建议买入数量（100-400股）
        "reason": "我的分析和买入理由（必须用中文，第一人称）",
        "confidence": 0.75,       // 决策信心（0-1，≥{confidence_threshold:.2f}才会执行）
        "expected_days": 5,       // 预期持有天数
        "exit_plan": {{
            "profit_target": "+8%或放量突破",  // 止盈目标（价格、涨幅、形态）
            "stop_loss": "-5%或跌破均线",      // 止损条件（不能说"永不止损"）
            "invalidation": "出现利空或板块大跌"  // 失效条件（什么情况说明判断错了）
        }}
    }}
]

【退出计划必填】（核心要求！）
每次买入必须回答3个问题：
1. **什么时候止盈？**（价格、涨幅、形态、时间）
   - 例如："+8%"、"突破10元"、"放量突破前高"、"3天内+5%"
   
2. **什么时候止损？**（不能说"永不止损"）
   - 例如："-5%"、"跌破9元"、"跌破5日均线"、"连续3天下跌"
   
3. **什么情况说明判断错了？**（利空、技术破位）
   - 例如："出现重大利空"、"板块整体大跌"、"成交量持续萎缩"

**为什么必须填写退出计划？**
- ✅ 买入时就思考退出，避免"买了就忘"
- ✅ 建立决策闭环，提高纪律性
- ✅ 卖出时可以对照当初的计划，保持自我一致性

【理由撰写要求】（重要！）
- **必须用中文**，用第一人称（"我"）撰写，像是你内心的独白
- 表达你的思考过程、信心和预期
- 例如：
  ✅ "我看好这只股票的短期走势，换手率7.5%显示资金活跃，PE仅30倍处于合理区间，我有75%的信心能在3-5天内获利5%以上。"
  ✅ "这个标的技术面不错，今日放量上涨，我准备建仓200股，预期3天内能有不错的收益。"
  ✅ "虽然市场整体不太好，但这只票逆势上涨，说明有资金关注。我决定小仓位试探性买入100股。"
  ❌ "PE低换手率适中"（太机械，没有人格）
  ❌ 用英文（必须用中文！）

【重要提示】
- 如果现金不足或无合适标的，返回空数组[]
- suggested_amount必须是100的整数倍
- 每只股票的投入不要超过3500元
- 通过深入分析做决策，而不是随意选择

完成分析后，输出JSON结果。
"""
    
    return prompt


def get_reflection_prompt(
    trade_history: list,
    daily_assets: list,
    current_strategy: dict,
    agent_principles: list = None
) -> str:
    """
    生成反思提示词
    
    Phase 3: 用问题引导代替命令
    Phase 4: 增加Agent自主学习和经验总结
    """
    
    # 计算统计数据
    total_trades = len(trade_history)
    buy_trades = [t for t in trade_history if t['action'] == 'buy']
    sell_trades = [t for t in trade_history if t['action'] == 'sell']
    
    # 计算胜率
    profitable_sells = [t for t in sell_trades if t.get('profit', 0) > 0]
    win_rate = (len(profitable_sells) / len(sell_trades) * 100) if sell_trades else 0
    
    # 计算成功和失败交易的平均持有天数
    success_hold_days = []
    failure_hold_days = []
    for trade in sell_trades:
        hold_days = trade.get('hold_days', 0)
        if trade.get('profit', 0) > 0:
            success_hold_days.append(hold_days)
        else:
            failure_hold_days.append(hold_days)
    
    avg_success_days = sum(success_hold_days) / len(success_hold_days) if success_hold_days else 0
    avg_failure_days = sum(failure_hold_days) / len(failure_hold_days) if failure_hold_days else 0
    
    # 分析现金比例与交易结果的关系
    cash_analysis = ""
    if buy_trades:
        # 安全计算现金比例，避免None值
        high_cash_trades = [
            t for t in buy_trades 
            if t.get('cash_before') and t.get('assets_before') 
            and t.get('cash_before', 0) / t.get('assets_before', 10000) > 0.3
        ]
        low_cash_trades = [
            t for t in buy_trades 
            if t.get('cash_before') and t.get('assets_before')
            and t.get('cash_before', 0) / t.get('assets_before', 10000) < 0.2
        ]
        cash_analysis = f"\n- 高现金比例(>30%)交易：{len(high_cash_trades)}次\n- 低现金比例(<20%)交易：{len(low_cash_trades)}次"
    
    # 最近10笔交易（详细）
    recent_trades_text = []
    for trade in trade_history[-10:]:
        profit = trade.get('profit', 0)
        action_desc = "买入" if trade['action'] == 'buy' else "卖出"
        if trade['action'] == 'sell':
            recent_trades_text.append(
                f"- {trade['date']} {action_desc} {trade.get('name', trade.get('code', '未知'))} "
                f"{'盈利' if profit > 0 else '亏损'}{abs(profit):.0f}元 (持有{trade.get('hold_days', 0)}天)"
            )
        else:
            cash_pct = (trade.get('cash_before', 0) / trade.get('assets_before', 10000) * 100) if trade.get('assets_before', 0) > 0 else 0
            recent_trades_text.append(
                f"- {trade['date']} {action_desc} {trade.get('name', trade.get('code', '未知'))} "
                f"(当时现金{cash_pct:.0f}%)"
            )
    
    recent_trades = "\n".join(recent_trades_text) if recent_trades_text else "暂无交易记录"
    
    # 资产曲线
    initial_assets = daily_assets[0]['total_assets'] if daily_assets else 10000
    current_assets = daily_assets[-1]['total_assets'] if daily_assets else 10000
    total_return = ((current_assets - initial_assets) / initial_assets) * 100
    
    # Phase 4: 加载Agent之前的交易信条
    principles_text = ""
    if agent_principles and len(agent_principles) > 0:
        principles_text = "\n【我之前总结的交易原则】\n" + "\n".join([f"- {p}" for p in agent_principles]) + "\n"
    
    prompt = f"""【你的身份】
你是一名职业股票交易员，管理着自己的真实交易账户。
你在LHArena Season 1竞技场中与其他4名交易员竞争。
这不是游戏，这是真实的交易竞技场。

💰 【真实损益统计】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
初始本金: ￥10,000.00
当前资产: ￥{current_assets:.2f}
累计收益: {total_return:+.2f}% {'⚠️ 真实亏损' if total_return < 0 else '✅ 真实盈利'}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{f'⚠️ 你已经亏损了￥{abs(current_assets - initial_assets):.2f}，这些钱永远回不来了。' if total_return < -10 else ''}

【交易统计】
- 总交易次数：{total_trades}次 (买入{len(buy_trades)}次，卖出{len(sell_trades)}次)
- 胜率：{win_rate:.1f}%
- 成功交易平均持有：{avg_success_days:.1f}天
- 失败交易平均持有：{avg_failure_days:.1f}天{cash_analysis}

【最近交易记录】
{recent_trades}
{principles_text}
【深度反思】（Phase 3: 用问题引导思考）
请基于数据回答以下问题：

**1. 现金管理**
Q: 你当前现金比例是多少？对灵活性有什么影响？
Q: 数据显示你在高现金vs低现金时的交易表现有何不同？
Q: 什么样的现金比例对你来说是健康的？

**2. 持有时间**
Q: 数据显示你成功交易平均{avg_success_days:.0f}天，失败交易{avg_failure_days:.0f}天，说明了什么？
Q: 你是否应该更快止盈或更快止损？

**3. 决策习惯**
Q: 你是否过于激进买入，但卖出时过于保守？
Q: 你在什么情况下决策更准确？什么情况下容易失误？
Q: 你是否遵守了自己当初制定的退出计划？

**4. 自我认知**
Q: 你最擅长什么类型的交易？（短线/中线，低估值/成长股）
Q: 你的盲点在哪里？什么类型的股票你总是判断失误？

【Agent自主学习】（Phase 4: 总结经验并制定调整计划）

基于你的交易数据和反思，请总结：

**我的优势**：
- 哪些判断是对的？哪些操作效果好？
- 我擅长什么类型的股票/市场环境？

**我的问题**：
- 哪些判断失误了？哪些操作需要改进？
- 我的盲点在哪里？

**我的调整计划**（重要！自己决定）：
- 我需要更关注什么？
- 我需要改变什么决策习惯？
- 我的风险偏好需要调整吗？
- 我应该形成什么样的"交易原则"？

【输出格式】
请以JSON格式返回：
{{
    "cash_reflection": "关于现金管理的思考",
    "timing_reflection": "关于持有时间的思考",
    "decision_reflection": "关于决策习惯的思考",
    "self_awareness": "关于自我认知的总结",
    
    "my_strengths": ["我的优势1", "我的优势2"],
    "my_weaknesses": ["我的问题1", "我的问题2"],
    
    "trading_principles": [
        "我的交易原则1（例如：我更擅长短线交易，不要贪恋长期持有）",
        "我的交易原则2（例如：我需要保持至少30%现金，否则心态会失衡）",
        "我的交易原则3（例如：我应该相信第一直觉，不要反复纠结）"
    ],
    
    "adjustment_plan": {{
        "what_to_focus": "我需要更关注什么",
        "what_to_change": "我需要改变什么决策习惯",
        "risk_preference": "我的风险偏好调整（更激进/更保守/保持不变）"
    }}
}}

**注意**：
- 这是你的自我学习，没有"正确答案"
- 基于数据总结，不要空谈
- 你的"交易原则"将在后续决策中被加载，影响你的判断
- 勇于探索，允许试错
"""
    
    return prompt


def get_simple_action_prompt(
    task: str,
    context: str
) -> str:
    """
    简单任务提示词模板
    
    Args:
        task: 任务描述
        context: 上下文信息
    """
    
    prompt = f"""你是一个A股量化交易助手。

【任务】
{task}

【上下文】
{context}

【要求】
- 思考并给出合理的建议
- 以JSON格式返回结果
- 理由必须用中文表达

请完成任务。
"""
    
    return prompt

