# 分析模式路由

当前 skill 只有一个 HTML 模板,但内部按 `meta.analysis_mode` 选择分析镜头。缺省时根据 `meta.question_type` 推断。任何模式都不输出目标价、不输出仓位、不输出买卖建议。

## 路由边界

先判断用户是否关注**市场整体影响**。只有市场整体、宏观/政策/新闻/风险事件、跨资产联动、资金风险偏好和市场情绪问题才进入本 Skill。单只股票、具体板块涨跌、行业长期观点、公司基本面、财报/业绩数字应转相邻 Skill,不要为了填充 `analysis_mode` 硬做简报。

## 模式总表

| analysis_mode | 何时使用 | 借鉴来源 | 前台重点 | 必须避免 |
|---|---|---|---|---|
| market_event | 全市场涨跌归因、市场热点、新闻/风险事件、大盘事件、市场级海外映射 | economic-impact-report | 事件 -> 变化 -> 传导 -> 事实 -> 验证 | 写成新闻列表;把个股/板块异动当市场整体问题 |
| policy_macro | 政策、宏观、利率、汇率、商品、地缘冲击 | economic-impact-report | 政策/冲击 -> 变量 -> 行业/环节 -> 市场反应 | 宏观空谈 |
| dated_catalyst | 有明确会议、公告、数据、财报、监管节点 | catalyst-calendar | 日期/窗口 -> 信心 -> 验证项 -> 证伪项 | 把软窗口写成确定日期 |
| earnings_event | 财报季、业绩风险已经进入市场级语境;纯财报/业绩数据问题应转「财报与业绩分析」 | earnings-preview / earnings-deep-dive | 只讨论财报季/业绩风险对市场预期、风格和风险偏好的影响 | 复述单家公司收入利润;替代财报分析 Skill |
| theme_watch | 市场级交易主线、主题作为全市场风险偏好或资金线索时使用 | idea-generation / thesis-tracker | 主线 -> 证据强弱 -> 验证/证伪 -> 后续追问 | 把行业长期观点、板块热度或受益股名单写成本 Skill |

## 默认推断

| question_type | 默认 analysis_mode |
|---|---|
| market | market_event;市场级主题/主线用 `analysis_mode=theme_watch` |
| policy | policy_macro |
| event | market_event |
| update | market_event |

`single_stock` / `sector` / `company` / `watchlist` 不再是本 Skill 的可输出 `question_type`。若用户实际问题落在个股涨跌、板块/行业涨跌热度、行业长期观点、公司基本面或纯财报业绩数字,应按「路由边界」转相邻 Skill;若是市场级主题观察,使用 `question_type=market` + `analysis_mode=theme_watch`。

## 字段落点

- `insight.one_sentence`: 一句话判断,不是标题复述。
- `insight.what_changed`: 相比预期或上一阶段的新变化。
- `insight.consensus_vs_delta`: 共识和预期差,没有机构观点时写市场可能分歧。
- `visuals.impact_chain`: 横向传导链,必须从事件走向市场变量或行业环节。
- `visuals.impact_facts`: 对应传导链节点标题下的正文,优先引用官方、媒体、机构来源。
- `interpretation[]`: 渲染为「各方有哪些值得关注的观点？」,每条必须回指 `refs`。
- `verification.confirm` / `verification.invalidate`: 必填,渲染为「验证 / 证伪信号」,后续用来确认或推翻主线,不能写成泛泛关注。`confirm_signals` / `invalidate_signals` 只作为洞见摘要,不能替代结构化 verification。
