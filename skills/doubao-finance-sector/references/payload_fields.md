# payload 字段全集与报错速查

> 长参考文件：默认先读 `references/payload_contract.md`。只有 payload 报错看不懂、需要字段全集、或维护渲染合同时，再读本文。第二阶段流程、hydrate 顺序和准出命令以 `payload_contract.md` 为准；硬校验以 `scripts/render_dashboard.py` 为准；HTML 文本必须从第一阶段正文原句搬运，不压缩、不改写。

## 1. 顶层字段

必填字段见 `payload_contract.md`。完整字段按用途分为：

| 字段 | 用途 | 备注 |
|---|---|---|
| `sector` / `market` / `timestamp` | 顶栏与文件名 | `timestamp` 是行情截止时点，不用盘中价充当收盘价 |
| `index_caliber` | 目标概念板块 | 名称 + 代码，全篇唯一口径 |
| `selected_stocks` | 10 只代表股名称 | 与第一阶段 facts 一致 |
| `data_mode` | 板块数据完整状态 | 固定 `full`；板块指标必须来自目标板块自身 |
| `composite_score` / `info_score` / `market_score` | 热度分 | 1-5 分；综合分公式见 `scoring_and_divergence.md` |
| `headline` / `summary` | Hero 核心判断 | `headline` 来自 chat 开篇 `标题：` 后的一句话核心判断；`summary` 来自标题后的解释段，不重复热度分数 |
| `key_chips` | Hero 四张小卡 | 固定 4 张，见下 |
| `divergence` | 双轨背离卡 | `type` 可省，脚本按分数判定 |
| `answer` | 直接回答 | 映射第一阶段 `## 直接回答` 的“问题 / 结论 / 下一步” |
| `section_summaries` | 模块1-5本段结论 | 映射各模块 `**本段结论：**`，键：`heat` / `catalysts` / `divergence` / `watch` / `risks` |
| `dimensions` | 模块1四维度 | 映射模块1四维表，价格涨跌、成交量能、代表股表现、估值位置 |
| `catalysts` | 模块2时间线 | 映射模块2催化，精选 3-5 条，最多 6 条 |
| `stocks` / `divergence_groups` | 模块3热力图与四组 | 股票与组员由 facts 覆盖；解释文字从 chat 原句搬运 |
| `watch_signals` | 模块4信号 | 映射模块4信号，3-4 条，最多 4 条 |
| `risks` | 模块5风险 | 映射模块5风险，可观察、可证伪 |
| `sources` | 模块6来源 | 渲染公开来源与数据终端；有 `url` 的可点击，无 `url` 的作为数据终端展示 |
| `numeric_facts` | 数字事实表 | 与第一阶段 facts 同源，用于复算与绑定 |
| `gaps` / `claim_to_source` | 内部留痕 | 不渲染到 HTML |

## 2. key_chips

必须恰好 4 张，每张有 `metric_key`、`value`、`source.lane`、建议有 `fact` / `value_num`。

固定必有：

- `close_point`：目标概念板块指数 / 板块行情的当日收盘点位。
- `pe_ttm`：10 只代表股中市值最大那只的股票 PE(TTM)，label 写成 `<股票名> PE(TTM)`。

另外两张必须二选一成对出现：

- 当日组：`daily_change` + `turnover_amount`
- 近7日组：`change_7d` + `turnover_7d`

6 个候选指标口径：

| metric_key | 口径 |
|---|---|
| `close_point` | 目标概念板块指数 / 板块行情当日收盘点位 |
| `daily_change` | 目标概念板块指数 / 板块行情当日涨跌幅 |
| `change_7d` | 目标概念板块指数 / 板块行情近7个交易日涨跌幅 |
| `turnover_amount` | 目标概念板块全成分 / 官方板块口径当日成交额 |
| `turnover_7d` | 目标概念板块全成分 / 官方板块口径近7个交易日日均成交额 |
| `pe_ttm` | 10 只代表股中市值最大那只的股票 PE(TTM) |

除 `pe_ttm` 外，核心小卡都是目标板块口径，不得用 10 股样本合计 / 均值替代。目标板块字段不可得时，回到第一阶段补取；不能输出替代值。

所有小卡行情数字都必须 `source.lane:"seed_finance_search"`。近7日涨跌幅口径：当天为 T / Day 0，`change_7d = T日收盘(d7_close_t) / T-7交易日收盘(d7_close_base) - 1`；近7个交易日日均成交额为 T-6 至 T 的 7 个交易日成交额均值，即 `turnover_7d = avg(d7_turnovers)`。

## 3. dimensions

固定 4 个，顺序不可变：

1. 价格涨跌
2. 成交量能
3. 代表股表现
4. 估值位置

每项字段：

```json
{
  "name": "成交量能",
  "track": "行情",
  "value": "关键数值",
  "state": "确认",
  "read": "2-3句解读",
  "source": { "lane": "seed_finance_search", "as_of": "YYYY-MM-DD" }
}
```

硬约束：

- 4 个维度都属于行情轨，`source.lane` 固定 `seed_finance_search`。
- 代表股表现只分析选定的 10 只。
- 估值位置只按 10 只代表股 PE(TTM) 的中位数 / 区间 / 分布分析，不写板块 PE。
- `value` 从模块1表格“数值”列逐字搬运，不压缩成单个裸数字；口径见 `chat_contract.md` 模块1。
- `read` 从模块1对应卡片解读搬运，不压缩、不改写。
- 若 `value` 含 PE / PB / PS，必须带 TTM / 静态 / 动态 / LYR / 滚动等口径词。

## 4. catalysts

模块2只放最终解释本轮涨跌的核心催化，精选 3-5 条，最多 6 条。

```json
{
  "date": "6月12日",
  "tone": "利好",
  "category": "政策",
  "source_name": "新华社",
  "title": "事件标题",
  "fact": "只概括该来源原文事实",
  "url": "https://...",
  "why": "风险说明 / 影响机制（HTML 不显示“为什么重要”字段名）",
  "verify": "后续验证",
  "freshness_reason": "可选；超过14天仍使用时填",
  "source": { "lane": "general_search", "tier": 1, "level": "一手" }
}
```

规则：

- `date` 是事件发生日，不晚于 `timestamp`。
- `source_name` 只填来源名，`url` 必须能打开。
- 只许一级 / 二级来源；聚合承载页若机构署名，最高标二级；个人 / 自媒体 / 无法确认机构作者不得入选。
- `fact` 只依据该条来源原文，不混入其它数据或推断。
- 超过行情截止日前 14 个自然日的旧催化，只有政策 / 官方 / 公告 / 财报 / 数据类仍在兑现时可保留，并填 `freshness_reason`。

来源分级争议看 `data_rules.md`，不要在本文重复判断。

## 5. stocks 与 divergence_groups

第二阶段不要手工重填 10 股行情、近7日复算、`role/select_reason` 或四组分组。

流程：

```bash
python3 scripts/hydrate_payload_from_facts.py work/<板块>_facts.json work/<板块>_payload.json
```

该脚本会从第一阶段 facts 覆盖：

- `stocks`
- `divergence_groups`
- `_facts_hydration.stocks_sha256`

渲染门只检查水合指纹是否一致。若 10 股完整性、近7日复算、四组分组或代表股理由有错，回第一阶段修 facts 后重新水合，不在 payload 里手工补。

## 6. watch_signals

模块4信号建议 4 条，允许 3 条，最多 4 条。字段：

```json
{
  "signal": "板块能否连续 2 日放量并站上前高",
  "watch": "能否连续两个交易日放量并保持主力净流入",
  "improve": "若延续，主结论如何升级",
  "worsen": "若恶化，主结论如何降级或失效",
  "event_date": "2026-06-17"
}
```

规则：

- `signal` / `watch` / `improve` / `worsen` 必填。
- 有具体未来日期时填 `event_date`，且必须晚于 `timestamp`。
- 持续型信号不填 `event_date`，文本里也不要写具体日历日期。
- 禁止“信息热度+1 / 行情热度-1”等内部评分语言。

模块4写法看 `chat_contract.md`。

## 7. risks

每条风险字段：

```json
{
  "title": "风险名",
  "trigger": "触发条件",
  "why": "影响 / 传导链",
  "invalidate": "什么出现会推翻当前结论"
}
```

字段名以渲染脚本为准：序号旁标题取 `title`，说明段取 `why`，不要写成 `risk` / `impact`。风险必须可观察、可证伪，不写空泛风险。

## 8. sources

```json
{
  "category": "公开信息",
  "name": "新华社",
  "title": "新闻标题",
  "date": "2026-06-12",
  "url": "https://...",
  "used_for": "模块2 催化"
}
```

模块6渲染公开来源与数据终端。带 `url` 的来源展示“查看原文”；无 `url` 的行情终端 / 数据终端展示为“数据终端”。来源按日期倒序渲染。

## 9. numeric_facts

`numeric_facts` 是 payload 中展示数字的事实边界，与第一阶段 facts 同源。市场数字必须 `lane:"seed_finance_search"`、`tier:1`、有 `source_name`，可复算项带原始分量。

常用字段：

```json
{
  "id": "idx_daily_change",
  "metric": "板块当日涨跌幅",
  "value": 1.8,
  "unit": "%",
  "period": "2026-06-18",
  "as_of": "2026-06-18",
  "kind": "change",
  "tier": 1,
  "lane": "seed_finance_search",
  "source_name": "同花顺数据库",
  "prev_close": 1020,
  "last_close": 1038.36,
  "change_pct": 1.8
}
```

复算类型：

| `kind` | 分量字段 | 复算 |
|---|---|---|
| `change` | `prev_close` / `last_close` / `change_pct` | `(last/prev - 1) * 100` |
| `retracement` | `range_high` / `range_low` / `range_pct` | `(low/high - 1) * 100` |
| `rebound` | `from_low` / `rebound_to` / `rebound_pct` | `(to/low - 1) * 100` |
| `ratio` | `numerator` / `denominator` / `value` / `as_pct` | `num/den` 或 `num/den*100` |

展示项可用 `fact:"id"` + `value_num` 绑定，校验门会检查展示值与登记值一致。

## 10. 报错速查

| 报错关键词 | 常见原因 | 处理 |
|---|---|---|
| `key_chips` | 不够 4 张、缺 `metric_key`、当日组/近7日组混搭、误填板块 PE | 按第2节重排；PE 只取最大市值代表股股票 PE(TTM) |
| `dimensions` | 不是固定四维、顺序错、lane 错、估值缺口径 | 按第3节修；估值只写 10 股 PE(TTM) |
| `catalysts` | 缺 `source_name` / `url`、来源为三级、日期晚于截止日 | 换一级/二级来源；周末未交易新闻改入模块4背景 |
| `stocks_sha256` / `hydrate` | 未水合或水合后手改 `stocks` / `divergence_groups` | 重新运行 `hydrate_payload_from_facts.py` |
| `watch_signals` | 字段空、超过4条、日期不晚于截止日、具体日期缺 `event_date` | 合并同类信号；预定型补 `event_date`；持续型去硬日期 |
| `numeric_facts` / `复算` | 展示值与分量算不一致、`value_num` 与事实打架 | 修原始分量或登记值，别只改展示文字 |
| `source.lane` | 行情数字误用 `general_search` | 市场/估值/成交/资金/个股财务数字改回 `seed_finance_search` |
| `data_mode` | 不是 `full` | 改回 `full`；板块指标回到第一阶段补取目标板块自身数据 |

调试可临时用 `--warn-only`，但交付路径必须通过 `render_dashboard.py --check-only`，不得把 warn-only 产物说成已通过硬校验。
