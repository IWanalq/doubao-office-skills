---
name: lark-doc
description: "飞书云文档 + 本地 Office Word 一体化文档技能。【飞书/Doubao 文档】当用户给出 feishu.cn 或 doubao.com 的 /docx/、/wiki/ URL 或 token，或要求创建/打开/读取/总结/整理/改写/翻译/审阅/编辑云文档、追加替换删除移动内容、调整排版、插入或下载图片/附件/素材/画板时使用（命令走 lark-cli docs --api-version v2，默认 DocxXML，也支持 Markdown；文档内嵌电子表格/多维表格/画板/同步块时先用本 skill 提取 token 再下钻）。【本地 Office】当用户上传 .docx/.doc/.pdf 并希望产出同类文件，或提到 Word 文档、简历/CV、专利/权利要求书/审查意见、签证文件/表格填写、起诉状/公告/会议通知/公文 等强格式文书时，路由到 office-word 模块用脚本解析与生成 .docx/.pdf。路由依据是输入载体（飞书 token vs 本地文件）和文书类型，而非域名。"
metadata:
  requires:
    bins: ["lark-cli"]
  cliHelp: "lark-cli docs --api-version v2 --help; lark-cli docs +create --api-version v2 --help; lark-cli docs +fetch --api-version v2 --help; lark-cli docs +update --api-version v2 --help"
---

# 文档技能（飞书云文档 + 本地 Office Word）

本 skill 一个入口、两套执行引擎：**飞书引擎**（lark-cli 操作云文档）与 **Office 引擎**（脚本解析/生成本地 .docx/.pdf）。先按下表路由，再进入对应引擎执行。

## 路由 — 先判目标载体，再执行

| 输入信号 | 去哪 |
|---|---|
| 本地 `.docx/.doc/.pdf` 文件；要产出 Word/PDF 文件；简历/CV、专利/权利要求书/技术交底书/审查意见(OA)、签证文件/表格填写、起诉状/答辩状/公告/会议通知/公文 等强格式文书 | **必读 [`references/office-word/SKILL_office-word.md`](references/office-word/SKILL_office-word.md) 并完全按它执行**（脚本统一在本 skill 根 `scripts/`，命令从 skill 根执行：`uv run scripts/xxx.py`） |
| feishu.cn / doubao.com 的 `/docx/`、`/wiki/` URL 或 token；创建/读取/改写/排版飞书云文档 | 按下方 **飞书 docs (v2)** 流程执行 |

未命中本地 Office 信号的，一律走飞书 docs (v2)。

---

# docs (v2) — 飞书引擎

> **⚠️ API 版本：本 skill 使用 v2 API。所有 `docs +create --api-version v2`、`docs +fetch --api-version v2`、`docs +update --api-version v2` 命令必须携带 `--api-version v2`。**

```bash
# 常用示例
lark-cli docs +fetch  --api-version v2 --doc "文档URL或token"
lark-cli docs +create --api-version v2 --content '<title>标题</title><p>内容</p>'
lark-cli docs +update --api-version v2 --doc "文档URL或token" --command append --content '<p>内容</p>'
```

## 前置条件 — 执行操作前必读

**CRITICAL — 执行对应操作前，MUST 先用 Read 工具读取以下文件：**
1. **认证**：运行环境已配置好 `lark-cli` 认证，直接使用 `lark-cli docs` 命令即可——无需查找任何额外的认证 skill 或目录；**不要因为找不到某个外部目录就判定"skill 路径有误"或中止后续步骤。下面第 2、3 条中 `references/` 下的文件才是必读，且一定存在。**
2. **读取文档（`docs +fetch --api-version v2`）** → 必读 [`lark-doc-fetch.md`](references/lark-doc-fetch.md)（`--scope` / `--detail` 选择、局部读取策略、`<fragment>` / `<excerpt>` 输出结构）
3. **创建或编辑文档内容** → 必读 [`lark-doc-xml.md`](references/lark-doc-xml.md)（XML 语法规则，仅当用户明确要求 Markdown 时改读 [`lark-doc-md.md`](references/lark-doc-md.md)）**和 [`lark-doc-style.md`](references/style/lark-doc-style.md)（排版风格 + 富 block 红线 + 丰富度/列表一致性自检——无论是否 spawn 子 Agent，主 Agent 都必须读）**；从零创建时加读 [`lark-doc-create-workflow.md`](references/style/lark-doc-create-workflow.md)；编辑已有文档时加读 [`lark-doc-update-workflow.md`](references/style/lark-doc-update-workflow.md)

**未读完以上文件就执行相应操作会导致参数选择错误、格式错误或样式不达标。**

> **格式选择规则（全局）：**
> - **创建 / 导入场景**（`docs +create`，或 `docs +update --command append/overwrite` 的整段写入）：XML 和 Markdown 都可以。用户提供 `.md` 本地文件、或明确说"导入 Markdown"时，直接用 Markdown；否则默认 XML（可用 callout、grid、checkbox 等富 block）。
> - **精准编辑场景**（`docs +update` 的 `str_replace` / `block_insert_after` / `block_replace` / `block_delete` / `block_move_after` 等局部精修指令）：优先使用 XML（`--doc-format xml`，即默认值）。XML 能稳定表达 block 结构和样式，局部精修更可控；不要因为 Markdown 更简单就自行切换。

## 快速决策
- 用户需要“某个 block 的直达链接 / 锚点链接”时：返回 `文档基础 URL#block_id`。如果当前只有文档 URL 没有 block_id，先用 `docs +fetch --detail with-ids` 拿到目标 block 的 id
- 例：
  - 已知文档 URL = `https://xxx.feishu.cn/docx/doxcn123`
  - 已知 block_id = `blkcn456`
  - 应返回 `https://xxx.feishu.cn/docx/doxcn123#blkcn456`
- 用户需要在文档内**创建、复制或移动**资源块（画板、电子表格、多维表格等）时，必须先读取 [`lark-doc-xml.md`](references/lark-doc-xml.md) 的「三、资源块」章节
- 写文档时，重要信息（核心流程、架构、对比、风险、路线图、关键指标、因果关系）优先规划为画板，不要只用文字或表格承载
- 新增画板必须隔离到 SubAgent：简单图由 SubAgent 直接插入 `<whiteboard type="svg">完整 SVG</whiteboard>`，不读 `lark-whiteboard`；复杂图才由主 Agent 先建 `<whiteboard type="blank"></whiteboard>`，再启动 SubAgent 读取 `lark-whiteboard` 写入
- 用户说"看一下文档里的图片/附件/素材""预览素材" → 用 `lark-cli docs +media-preview`
- 用户明确说"下载素材" → 用 `lark-cli docs +media-download`
- 如果目标是画板/whiteboard/画板缩略图 → 只能用 `lark-cli docs +media-download --type whiteboard`（不要用 `+media-preview`）
- 拿到 spreadsheet URL/token 后 → 切到 `lark-sheets` 做对象内部操作
- 用户说"给文档加评论""查看评论""回复评论""给评论加/删除表情 reaction" → 切到 `lark-drive` 处理
- 文档内容中出现嵌入的 `<sheet>`、`<bitable>` 或 `<cite file-type="sheets|bitable">` 标签时 → **必须主动提取 token 并切到对应技能下钻读取内部数据**，不能只呈现标签本身

| 标签 / 属性 | 提取字段 | 切到技能 |
|-|-|-|
| `<sheet token="..." sheet-id="...">` | `token` -> spreadsheet_token, `sheet-id` | [`lark-sheets`](../lark-sheets/SKILL.md) |
| `<bitable token="..." table-id="...">` | `token` -> app_token, `table-id` | [`lark-base`](../lark-base/SKILL.md) |
| `<cite type="doc" file-type="sheets" token="..." sheet-id="...">` | 同 `<sheet>` | [`lark-sheets`](../lark-sheets/SKILL.md) |
| `<cite type="doc" file-type="bitable" token="..." table-id="...">` | 同 `<bitable>` | [`lark-base`](../lark-base/SKILL.md) |
| `<synced_reference src-token="..." src-block-id="...">` | `src-token` -> doc_token, `src-block-id` -> block_id | 用 `docs +fetch --api-version v2` 读取 src-token 文档，定位 block |

## Shortcuts（推荐优先使用）

Shortcut 是对常用操作的高级封装（`lark-cli docs +<verb> [flags]`）。有 Shortcut 的操作优先使用。

| Shortcut | 说明 |
|----------|------|
| [`+create`](references/lark-doc-create.md) | Create a Lark document (XML / Markdown) |
| [`+fetch`](references/lark-doc-fetch.md) | Fetch Lark document content (XML / Markdown) |
| [`+update`](references/lark-doc-update.md) | Update a Lark document (str_replace / block_insert_after / block_replace / ...) |
| [`+media-insert`](references/lark-doc-media-insert.md) | Insert a local image or file at the end of a Lark document (4-step orchestration + auto-rollback). Prefer `--from-clipboard` when the image is already on the system clipboard (screenshots, copy from Feishu/browser); use `--file` only for on-disk sources. |
| [`+media-download`](references/lark-doc-media-download.md) | Download document media or whiteboard thumbnail (auto-detects extension) |
| [`+media-preview`](references/lark-doc-media-preview.md) | Preview document media file (auto-detects extension) |
| [`+whiteboard-update`](../lark-whiteboard/references/lark-whiteboard-update.md) | Alias of `whiteboard +update`. Update an existing whiteboard with DSL, Mermaid or PlantUML. Prefer `whiteboard +update`; refer to lark-whiteboard skill for details. |
