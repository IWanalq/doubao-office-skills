# Doubao 外部模型交付契约

用于豆包、Coze、Canvas、浏览器插件等外部模型承载场景。默认模式是 `json_for_dialog`:模型只输出完整 `briefing.json`,外部程序用 `render_dialog_brief.py` 生成对话框正文。只有用户明确要求或确认生成 HTML 时,才进入 `json_for_html`:仍然只输出同一份 `briefing.json`,再由外部程序构建 HTML。

核心原则:豆包等外部模型是**结构化数据填写器**,不是 Markdown 报告作者、网页生成器或最终排版器。外层对话框输出必须由 `render_dialog_brief.py` 从 `briefing.json` 渲染,不要让模型自由写 Markdown。对话正文和 HTML 必须同源于 `briefing.json`,这样章节顺序、事实颗粒度、影响链、分歧和验证信号才不会漂移。

## 模式一:json_for_dialog

用于普通问答、分享对话和不需要文件的场景。模型不直接写 Markdown 正文,只输出纯 JSON 对象,且必须是完整 `briefing.json`;外部程序随后渲染对话正文。

### 输入

外部编排器应给模型:

- `user_question`: 用户原始问题。
- `as_of`: 外部系统确认的当前时间。
- `market_calendar`: 外部系统确认的交易日、休市状态和数据口径;模型不要自行猜测交易日。
- `sources.json`: 已去重的结构化来源列表,每条包含 `id/title/source/url/published_at/type/level/snippet`。
- `references/briefing-schema.json` 的必要字段说明。
- `references/dialog-delivery.md` 完整正文:这是对话框输出的唯一 Markdown 契约;不要只给摘要,不要给 HTML 模板。

### 输出

- 只输出纯 JSON 对象,不要 Markdown 代码块。
- 必须填写 `dialog_brief`、`insight`、`reading_budget`、`section_summaries`、`highlight`、`visuals.summary_cards`、`visuals.impact_chain`、`news_items`、`interpretation`、`verification`、`source_check`、`references` 和 `meta.disclaimer_id=standard_v2_full_risk_notice`。
- `dialog_brief.verdict` 直接回答用户问题;`executive_summary` 讲清事实变化、市场含义、限制条件和分歧;`key_points` 使用固定对象键 `fact_change / market_meaning / disagreement / verification`,每项只填 `{text, refs}`;`watch_signals` 写成可跟踪信号;不要手写 `risk_boundary`,交付入口会按固定免责声明补齐。
- `reading_budget.thirty_second` 是 HTML「核心观点」正文,要补充事实依据、市场含义、限制条件或主要分歧,不要一句话结束。
- `section_summaries.impact/viewpoints/verification` 是历史字段名,前台渲染为「关键洞见」。分别写给「上述信息如何影响市场？」「各方有哪些值得关注的观点？」「哪些信号会验证/证伪核心观点？」标题下。不要写栏目摘要;必须写二阶判断,例如预期差、传导断点、限制条件、最小验证信号或会迫使判断下修的条件。
- 不要自然语言总结、章节标题、Markdown 表格、工具过程或“需要我生成 HTML 吗”等前台话术;这些都由渲染脚本生成。

## 模式二:json_for_html

只在用户明确要求 HTML、网页、可点击简报、导出文件,或已经回答需要 HTML 展开版时使用。此模式下同样只输出纯 JSON 对象,且必须是完整 `briefing.json`:

- 不要 Markdown 代码块。
- 不要解释文字。
- 不要自然语言总结。
- 不要 schema 以外的临时字段。
- 不要把 `sources.json` 原样包一层返回。
- 必须填写 `dialog_brief`;对话框回复也从这份 JSON 生成,不能只填 HTML 相关字段。

### 禁止

- 不要运行代码。
- 不要读取本地文件。
- 不要自行搜索网页。
- 不要生成 HTML。
- 不要复制或改写 HTML 模板。
- 不要使用 CanvasCreateFile、HTML 编辑器或富文本画布。
- 不要检查 `node_modules`、`jsdom` 或执行 `npm install`。
- 不要使用 `--allow-csr` 或交付 CSR 半成品。
- 不要输出工具过程、调试记录、文件编辑记录、CoT 或修复步骤。
- 不要使用 `--no-audit`、`--allow-warnings` 或任何绕过校验的参数。
- 不要自行解释校验错误或连续自我修复;外部编排器最多 2 次把错误清单发回模型修 JSON。

### 填写规则

- `references[]` 只能来自 `sources.json`,必须保留真实 URL、发布时间、来源类型和等级。
- `news_items[].ref`、`interpretation[].refs`、`visuals.impact_facts[].refs`、`verification.*[].refs` 只能引用已存在的 `references[].id`。
- 内容字段按 `references/briefing-schema.json` 的写作说明填写,但运行时不会因为字段文案表述方式打回。不要为了纯文案润色自我修复。
- 校验失败只修结构、引用、来源或交付契约错误;不要把短文案、长文案或没有命中特定表达当成阻断问题。
- 宏观政策、央行、通胀、利率预期题优先使用 Fed/ECB/CME/BLS/BEA/EIA/财政部/交易所等 official 或 A 级来源;媒体只做背景或市场反应。
- 遇到来源冲突,写入 `conflicts`;不要自行拼接事实。
- 遇到信息不足,写入 `coverage_gaps`;不要硬编。
- 遇到非交易日或“今天”类问题,使用外部输入的交易日和数据口径;不要根据搜索结果自行改日期。
- 不要把 HTML 的 7 段叙事链改写成自拟报告目录。最终对话顶层栏目必须按 `references/dialog-delivery.md` 输出。`news_items` 只承载「有哪些关键增量信息？」,`insight` 只承载「这些信息为什么重要？」,`section_summaries` 只承载后段栏目的关键洞见,`visuals.impact_chain/impact_facts` 只承载「上述信息如何影响市场？」的链条和节点正文,`interpretation` 只承载「各方有哪些值得关注的观点？」,`verification` 只承载「哪些信号会验证/证伪核心观点？」。

## 外部交付

`json_for_dialog` 模式下,外部程序把模型输出保存为 `briefing.json` 后执行:

```bash
python3 scripts/render_dialog_brief.py <briefing.json> <reply.txt>
python3 scripts/verify_delivery_text.py <reply.txt>
```

用户要求或确认生成 HTML 时,外部模型仍只按本 Skill 格式要求准备完整 `briefing.json`,不得自行生成或修改 HTML。本地或非豆包编排器需要验证 HTML 时,模型输出保存为 `model-output.json` 后执行:

```bash
python3 scripts/run_external_delivery.py <model-output.json> <out.html> --reply-text <reply.txt> --briefing-json <briefing.json>
```

`run_external_delivery.py` 会负责纯 JSON 检查、规范化固定角色键、补齐固定风险边界、严格构建、HTML 契约校验、`render_dialog_brief.py` 深度对话框回复生成和 `verify_delivery_text.py` 前台文本校验。失败时不交付本地 HTML。
成品 HTML 交付时,先使用 `FileBatchUpload` 工具拿到公网链接作为附件,再将附件带给 `app_builder_agent` 工具进行交付,要求**严格按照 HTML 源文件**进行渲染输出,不做任何代码变更。
如果校验失败,编排器只把机器可读错误清单中的 `blocking_issues[]` 交给模型修正。修复依据只包括 `path/message`;模型只能修改对应 `path` 和必要引用,不能因为一个字段失败而全局删改、扩写或重排整份 JSON。不要把纯文案润色当成校验修复。`advisory_issues` 不阻断交付,不得发回模型触发修复循环。超过 2 次仍失败,必须停止交付,向用户返回错误清单和未生成 HTML 的状态。
