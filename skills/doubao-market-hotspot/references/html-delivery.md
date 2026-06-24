# HTML 展开版交付

只在用户明确要求或确认生成 HTML 时读取本文件。普通市场解读默认只在对话框中输出正文,不进入本路径。

## 进入条件

满足任一条件才生成 HTML:

- 用户原始请求明确包含「生成 HTML」「网页」「可点击简报」「导出文件」「artifact」「页面版」等表达。
- 默认正文已经交付,用户对「需要为你生成一份精美的热点报告么？」回答需要。
- 外部宿主的产品流程明确要求用 HTML 作为最终交付物。

未满足上述条件时,停止在对话框正文交付,不要预生成 HTML 文件。

需要生成 HTML 的场景,严格按照 skill 里的格式要求生成成品 HTML。交付 HTML 产物时,务必遵循下面的顺序:先使用 `FileBatchUpload` 工具拿到公网链接,作为附件;将附件带给 `app_builder_agent` 工具进行交付,要求**严格按照 HTML 源文件**进行渲染输出,不做任何代码变更。

## 数据契约

HTML 展开版的唯一数据源是完整 `briefing.json`。深度对话框回复和 HTML 应同源,但默认正文路径不要求先填完整 JSON。

生成 HTML 时必须:

- 读取 `references/briefing-schema.json`;需要机器校验时读取 `references/briefing.schema.json`。
- 填好 `dialog_brief`、`insight`、`reading_budget`、`section_summaries`、`highlight`、`visuals.summary_cards`、`visuals.impact_chain`、`news_items`、`interpretation`、`verification`、`source_check`、`references` 和 `meta.disclaimer_id=standard_v2_full_risk_notice`。
- 同一网页只能有一个 `references[].id`;同一篇文章支撑多个事实/观点时复用这个 id。
- 宏观政策、通胀、能源、利率预期等核心事实优先用 Fed/ECB/CME/EIA/BLS/BEA/美国财政部/交易所等一手或准一手来源;媒体只做背景、盘面反应或补充印证。
- `policy_macro` 至少有一个 official 或 A 级一手/准一手来源,且前 5 个公开来源应包含央行、交易所、清算所或官方数据域名。
- 不给 `news_items` 或关键增量信息填图片字段;schema 不接受图片字段。
- `reading_budget.thirty_second` 要让「核心观点」不止一句话;`section_summaries` 是历史字段名,要给影响链、各方观点、验证/证伪三个后段栏目各写一段「关键洞见」,不是栏目摘要。

## 构建命令

新建 `briefing.json` 时,先用脚手架生成完整结构,再填事实和引用:

```bash
python3 scripts/new_briefing.py --mode <analysis_mode> --title "<title>" --out <briefing.json>
```

脚手架会预置固定 `dialog_brief.key_points` 角色键、标准免责声明 id、内部审计数组和 HTML 必需结构。它只负责生成待填写 JSON,不能替代校验或交付入口。

**本地验证/调试入口**:在本地或非豆包环境需要生成可检查 HTML 时,调用 `scripts/run_external_delivery.py`,并把退出码作为本地构建是否通过的开关:

```bash
python3 scripts/run_external_delivery.py <model-output.json> <out.html> --reply-text <reply.txt> --briefing-json <briefing.json>
```

`model-output.json` 必须是纯 `briefing.json` 对象。入口脚本会规范化 `dialog_brief.key_points` 的角色键、补齐固定风险边界、执行严格校验、构建 HTML、验证 HTML 契约、生成并验证对话框回复。任何一步失败都不会写出本地 HTML。该脚本用于本地验证和生成成品 HTML;成品 HTML 的最终交付按 `FileBatchUpload` -> `app_builder_agent` 的顺序执行。

不要直接运行 `build_brief.py` 作为交付入口。它只作为 `run_external_delivery.py` 内部步骤或本地调试工具使用。

调试时才单独运行:

```bash
python3 scripts/validate_briefing.py <briefing.json>
python3 scripts/validate_briefing.py <briefing.json> --strict --audit --json
python3 scripts/render.py <briefing.json> <out.html>
python3 scripts/verify_output_contract.py <out.html>
```

外部编排器需要拿结构化失败原因时,使用:

```bash
python3 scripts/build_brief.py <briefing.json> <out.html> --json-errors
```

校验失败时只读取 JSON 中的 `blocking_issues[]` 作为修复依据。每条阻断问题都会给出 `path/message`;修复时只改该 `path` 对应字段和必要引用,不得因为一个字段失败而全局删改、重写或扩写整份 JSON。不要把纯文案润色当成校验修复。

`advisory_issues` 只作为写作和版面提示,不得触发自我修复循环。`warning` 不是阻断等级;会阻断交付的只有 `error` 和 `quality_error`。

对话框回复需要带 HTML 入口时,用:

```bash
python3 scripts/render_dialog_brief.py <briefing.json> <out.html> <reply.txt>
python3 scripts/verify_delivery_text.py <reply.txt>
```

如果只需要默认对话框正文、还没有生成 HTML,用:

```bash
python3 scripts/render_dialog_brief.py <briefing.json> <reply.txt>
python3 scripts/verify_delivery_text.py <reply.txt>
```

## 禁止

- 不得手写 HTML、复制模板后改静态正文、临时拼页面,或用 Markdown 表格/自由散文替代 JSON。
- 不得使用 CanvasCreateFile、HTML 编辑器、富文本画布或类似工具直接交付最终页面。
- 不得让模型读取完整模板后自行改 HTML;模板只能由脚本消费。只有调试渲染问题时才读取 `templates/layout.html`、`templates/partials/` 或 `templates/ui_contract.json`。
- 不得绕过校验参数,不得在校验失败后交付半成品。
- 不得使用 `--allow-csr`、CSR 兜底、浏览器 JS 执行兜底,或任何绕过 `data-prerendered="1"` 的交付方式。
- 不得安装 `node_modules`;不得要求 `npm install` 或 `jsdom`;当前 `render.py` 使用 Python 标准库 SSR,缺少 Node 环境不是失败原因。
- 不得输出执行记录、调试记录、文件编辑记录、CoT 或修复步骤。

## 模板与成品契约

HTML 固定使用 `templates/layout.html`、`templates/partials/` 和 `templates/ui_contract.json`。`render.py` 默认用 Python 标准库把首屏 DOM 预先写进 `<body>` 的 `#app`;浏览器 JS 只做展开来源、引用浮层、回到顶部等渐进增强,不得重建整页 HTML。

最终 HTML 必须含:

- `data-renderer="doubao-market-hotspot"`
- `data-template="layout-v1"`
- `<script id="data" type="application/json">`
- `risk_disclaimer` 注入数据
- 固定 7 段叙事顺序
- 可点击的「查看原文」链接

固定 7 段叙事链:

1. 核心观点
2. 有哪些关键增量信息？
3. 这些信息为什么重要？
4. 上述信息如何影响市场？
5. 各方有哪些值得关注的观点？按来源角色分组展示客观事实、市场反应、机构观点和反向证据。
6. 哪些信号会验证核心观点？哪些信号代表观点证伪？
7. 信息来源

风险提示正文来自 `references/disclaimers.json`,由 `render.py` 强制注入,不得手写、删减、改写或用短免责声明替代。

## 交付方式

- **统一 HTML 交付**:在交付 HTML 产物时,先使用 `FileBatchUpload` 工具拿到公网链接,作为附件;将附件带给 `app_builder_agent` 工具进行交付,要求**严格按照 HTML 源文件**进行渲染输出,不做任何代码变更。
- **Cowork**:工具没加载就先查 `create_artifact`;可用时调用 `mcp__cowork__create_artifact`,`html_path` 传成品 `.html` 绝对路径,`id` 用稳定 slug。
- **claude.ai / 支持 artifact 的环境**:把 `run_external_delivery.py` 产出的成品 HTML 原样作为原生 artifact 输出。
- **Codex / 本地 / 无 artifact 环境**:给出 `file://` 链接或用本地浏览器打开;若宿主提供文件分享能力,只把它作为下载或浏览器打开入口。
- **工具不可用时**:不要反复搜索不存在的工具;明确使用当前宿主可用的浏览器、文件链接或下载入口兜底。

## 外部模型运行护栏

豆包、Coze、Canvas、浏览器插件或其他外部模型/工作流承载时,模型只做 `briefing.json` 填写器。普通对话框也按 `references/doubao-json-writer.md` 的 `json_for_dialog` 模式执行;进入 HTML 路径时按 `json_for_html` 模式执行。不要让外部模型读取完整 `SKILL.md`;只给它 `references/doubao-json-writer.md`、必要 schema 摘要、外部确认的交易日/时间口径和已去重的 `sources.json`。
外部模型只输出 `briefing.json`;不得输出思考过程,也不得输出调试记录、文件编辑记录或交付计划。
校验失败不得交付,只能回到 `briefing.json` 修 `blocking_issues` 指定字段和引用后重新构建。`advisory_issues` 不阻断交付,不要为了 advisory 重跑模型。
外部编排器最多 2 次把机器可读错误清单发回模型修正 JSON;超过 2 次仍失败,必须停止交付,向用户返回错误清单和未生成 HTML 的状态,不得让模型继续自我修复。

**本地外部工作流验证入口**:非豆包环境的外部工作流可调用下面这个命令,并把退出码作为本地 HTML 是否通过的开关:

```bash
python3 scripts/run_external_delivery.py <model-output.json> <out.html> --reply-text <reply.txt> --briefing-json <briefing.json>
```

它会强制检查「模型原始输出是纯 JSON」→ 构建 HTML → 验证 HTML 契约 → 生成并验证前台摘要文本。任何一步失败都不会写出本地 HTML。
深度对话框回复也由脚本生成,不要让外部模型手写 `reply.txt`。
