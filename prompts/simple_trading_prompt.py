"""
简化版交易提示词 - 参考AI-Trader的成功经验
让AI更自由地思考和决策，用中文沟通
"""

def get_simple_buy_prompt(
    trade_date: str,
    cash: float,
    total_assets: float,
    candidates: list,
    holdings: dict,
    model_name: str = "AI",
    index_data: dict = None,
    recent_news: str = "",
    initial_capital: float = 10000
) -> str:
    """
    极简买入提示词 - 中文版
    
    核心理念：
    1. 明确角色和目标
    2. 提供必要信息
    3. 最小化限制，让AI自主决策
    """
    
    # 计算收益率
    profit_pct = ((total_assets - initial_capital) / initial_capital) * 100
    
    # 候选股票信息（精简版）
    candidates_info = []
    for stock in candidates[:20]:  # 显示前20只
        candidates_info.append(
            f"{stock['code']} {stock['name']}: "
            f"价格{stock.get('price', 0):.2f}元, "
            f"PE{stock.get('pe', 0):.1f}, "
            f"换手{stock.get('turnover', 0):.2f}%"
        )
    candidates_text = "\n".join(candidates_info)
    
    # 持仓信息（精简版）
    holdings_info = []
    for code, info in holdings.items():
        profit = info.get('profit_pct', 0)
        holdings_info.append(
            f"{code} {info.get('name', '')}: {info.get('amount', 0)}股, "
            f"成本{info.get('cost', 0):.2f}元, "
            f"{'+' if profit >= 0 else ''}{profit:.1f}%"
        )
    holdings_text = "\n".join(holdings_info) if holdings_info else "暂无持仓"
    
    # 大盘信息（如果有）
    index_info = ""
    if index_data:
        sh_change = index_data.get('sh_change', 0)
        index_info = f"\n大盘走势: 上证{'+' if sh_change >= 0 else ''}{sh_change:.2f}%"
    
    # 计算建议投资金额（根据初始资金动态调整）
    min_invest = int(initial_capital * 0.1)  # 10%
    max_invest = int(initial_capital * 0.3)  # 30%
    
    prompt = f"""你是一名专业股票交易员（{model_name}），正在管理一个{initial_capital/10000:.0f}万元的A股投资组合。

今天是 {trade_date}

【账户状态】
可用资金: {cash:.0f}元
总资产: {total_assets:.0f}元  
累计收益: {profit_pct:+.1f}%{index_info}

【当前持仓】
{holdings_text}

【今日候选股票】（系统已筛选的优质标的）
{candidates_text}

【你的任务】
分析候选股票，决定是否买入。

【决策建议】
- 思考每只股票的潜力和风险
- 考虑当前的资金状况和持仓情况
- 你可以买入1-3只股票，也可以选择观望
- **重要**：单只股票投资金额建议在{min_invest}-{max_invest}元之间
- **注意**：根据股价计算合理的股数，例如股价10元就买{int(min_invest/10)}-{int(max_invest/10)}股

【输出格式】
如果决定买入，请返回JSON数组（suggested_amount是股数）：
[
    {{
        "stock_code": "000001.SZ",
        "suggested_amount": 200,
        "reason": "我的分析（用中文，第一人称）",
        "confidence": 0.75
    }}
]

**示例**：如果股价是20元，投资4000元，就买200股（200股×20元=4000元）

如果今天不买入，返回空数组: []

请开始你的分析和决策。
"""
    return prompt


def get_simple_sell_prompt(
    trade_date: str,
    cash: float,
    total_assets: float,
    holdings: dict,
    model_name: str = "AI",
    index_data: dict = None,
    recent_news: str = "",
    initial_capital: float = 10000
) -> str:
    """
    极简卖出提示词 - 中文版
    """
    
    profit_pct = ((total_assets - initial_capital) / initial_capital) * 100
    
    holdings_info = []
    must_sell_stocks = []  # 必须卖出的股票
    should_sell_stocks = []  # 建议卖出的股票
    
    for code, info in holdings.items():
        profit = info.get('profit_pct', 0)
        hold_days = info.get('hold_days', 0)
        
        # 标记必须/建议卖出的股票
        signal = ""
        if profit >= 15:
            signal = " 🔴【必须止盈】"
            must_sell_stocks.append(f"{code}（盈利{profit:.1f}%）")
        elif profit >= 12:
            signal = " 🟠【建议止盈】"
            should_sell_stocks.append(f"{code}（盈利{profit:.1f}%）")
        elif profit <= -5:
            signal = " 🔴【必须止损】"
            must_sell_stocks.append(f"{code}（亏损{abs(profit):.1f}%）")
        elif profit <= -3:
            signal = " 🟠【建议止损】"
            should_sell_stocks.append(f"{code}（亏损{abs(profit):.1f}%）")
        elif hold_days >= 10 and -3 < profit < 5:
            signal = " 🟡【建议换股】"
            should_sell_stocks.append(f"{code}（持有{hold_days}天，表现平平）")
        
        holdings_info.append(
            f"{code} {info.get('name', '')}: "
            f"{info.get('amount', 0)}股, "
            f"成本{info.get('cost', 0):.2f}元, "
            f"现价{info.get('current_price', 0):.2f}元, "
            f"{'盈利' if profit >= 0 else '亏损'}{abs(profit):.1f}%, "
            f"持有{hold_days}天{signal}"
        )
    
    holdings_text = "\n".join(holdings_info)
    
    # 生成强制卖出提示
    force_sell_alert = ""
    if must_sell_stocks:
        force_sell_alert = f"\n\n⚠️ 【强制卖出警告】\n以下股票已触发止盈/止损线，必须卖出：\n" + "\n".join(f"- {s}" for s in must_sell_stocks)
    
    suggestion_alert = ""
    if should_sell_stocks:
        suggestion_alert = f"\n\n💡 【卖出建议】\n以下股票建议卖出：\n" + "\n".join(f"- {s}" for s in should_sell_stocks)
    
    # 大盘信息
    index_info = ""
    if index_data:
        sh_change = index_data.get('sh_change', 0)
        index_info = f"\n大盘走势: 上证{'+' if sh_change >= 0 else ''}{sh_change:.2f}%"
    
    # 现金预警
    cash_alert = ""
    if cash < 1000:
        cash_alert = f"\n\n⚠️ 【现金预警】当前可用资金仅{cash:.0f}元，已低于安全线！建议卖出部分盈利股票补充现金。"
    
    prompt = f"""你是一名专业股票交易员（{model_name}），正在管理一个{initial_capital/10000:.0f}万元的A股投资组合。

今天是 {trade_date}

【账户状态】
可用资金: {cash:.0f}元
总资产: {total_assets:.0f}元
累计收益: {profit_pct:+.1f}%{index_info}

【当前持仓】（请注意每只股票的完整代码）
{holdings_text}{force_sell_alert}{suggestion_alert}{cash_alert}

【你的任务】
分析当前持仓，严格执行止盈止损纪律。

【⚠️ 强制执行规则】
1. 🔴 盈利≥15%：必须全部卖出止盈（锁定利润）
2. 🔴 亏损≥5%：必须全部卖出止损（避免更大损失）
3. 🟠 盈利12-15%：强烈建议卖出至少一半
4. 🟠 亏损3-5%：强烈建议止损
5. 🟡 持有≥10天且收益<5%：考虑换股

【决策原则】
- 纪律第一：严格执行止盈止损，不能有侥幸心理
- 保护本金：小亏就跑，避免深套
- 落袋为安：盈利到手才算赚，不要幻想更高涨幅
- 现金为王：保持足够现金才能抓住新机会
- 避免"贪婪"和"恐惧"：理性决策，不受情绪影响

【输出格式】
如果决定卖出，请返回JSON数组：
[
    {{
        "stock_code": "000001.SZ",
        "amount": 200,
        "reason": "触发15%止盈线，严格执行纪律卖出"
    }}
]

如果继续持有，返回空数组: []

请开始你的分析和决策。记住：执行纪律比预测涨跌更重要！
"""
    return prompt
