---
name: office-word
description: 管理文档格式规范并路由有强格式要求的子技能，子技能包括：简历写作与优化、专利撰写/审查/答复/布局、签证文件填写与生成、公文写作（诉讼通知/法律公告/会议告示）。统一管理文档排版规范（页面/字体/章节/图表/公式）与 .docx/.pdf 文件的解析及生成脚本。触发条件：用户提到 Word/Office 文档、上传了 .docx/.doc/.pdf 文件并希望产出同类型文件、提到简历/专利/签证文件/起诉状/公告/会议通知/公文，或需要控制文档输出格式。
---

# 文档格式与交付管理

本 Skill 聚焦于文档产物的格式规范与交付流程，同时管理有强格式要求的子技能（简历、专利、签证文件）。

## 路由规则（1 跳直达：命中后一次性读完该行全部文件）

根据用户意图匹配体裁，**执行前 MUST 用 Read 一次性读完该行列出的全部文件**（子技能工作流 + 它的全部 references 叶子），不要只读 SKILL 再逐步发现，避免漏读叶子约束。

| 体裁信号 | 执行前 MUST Read（按顺序，全部） |
|---|---|
| 简历、CV、求职材料；改简历、优化简历、填模板 | `resume-writing/SKILL_resume-writing.md` ＋ `resume-writing/references/构建简历.md`、`优化简历.md`、`格式检查.md`、`简历辅导.md` |
| 专利、权利要求书、说明书、技术交底书、审查意见（OA）、专利布局、FTO | `patent-writing/SKILL_patent-writing.md` ＋ `patent-writing/references/drafting-workflow.md`、`patent-strategy.md`、`review-checklist.md`、`oa-response.md` |
| 签证文件、签证表格、邀请函、在职证明、行程单、官方表格填写 | `visa-doc-filler/SKILL_visa-doc-filler.md` ＋ `visa-doc-filler/references/common-visa-docs.md`、`field-mappings.md` |
| 起诉状、答辩状、传票、法院通知、减资公告、清算公告、会议通知、会议纪要、公文 | `official-document/SKILL_official-document.md` ＋ `official-document/references/litigation-templates.md` |

排版/版式风格对所有体裁通用，见 [`office-word-layout.md`](office-word-layout.md)。

> **脚本位置（重要）**：所有 Python 脚本统一在**本 skill 根目录的 `scripts/`**，命令一律从 skill 根执行，如 `uv run scripts/docx_edit.py ...`。子技能内不再单独放脚本。

若未命中上述体裁，则按下方通用格式与交付规范处理文档需求。

## 1. 产物交付规则

- 用户无法直接看到思考过程和工具调用中产生的产物，所有需要给用户查看的非 canvas 产物，必须使用 **NotifyHuman** 工具推送。
- 使用本地文件创建工具（如 `LocalCreateFile`）生成文件后，**必须**调用 NotifyHuman 将文件路径或内容传递给用户。
- **例外**：当产物通过 `CanvasCreateFile` 创建时，**禁止**再调用 NotifyHuman——CanvasCreateFile 创建的内容将根据 canvas_id 自动展示给用户。
- NotifyHuman 仅用于交付虚拟机中的文件路径和非 CanvasCreateFile 工具返回的产物链接。

## 2. 排版与版式风格

排版规范（A4/字体/边距/标题层级/图表编号）与版式质量（避免重叠溢出、配色、可读性、图文一致）统一见 [`office-word-layout.md`](office-word-layout.md)。用户给了模板时以模板为准。

## 3. 交付验收（强制）

在最终输出前做一次"覆盖检查"：

- **计划不丢失**：过程中承诺/规划过的分析维度必须在最终产物出现
- **交付物可打开**：交付的文件必须能被目标应用打开；不得只给大纲或伪装格式
- **交互可用**：若交付网页/交互报告，必须逐个点击验证关键交互可用
- **来源必输出**：最终产物必须包含"引用与来源"小节（如适用）
- **核心数据必标注来源**：摘要、关键结论、图表/表格的关键数字必须就地带来源编号

## 4. 富媒体与版式质量（强制）

已并入 [`office-word-layout.md`](office-word-layout.md) 第二节，交付含可视化/排版时按其执行。

## 5. 文档操作脚本

### 5.1 docx_edit.py — Word 解包/打包/替换

```bash
# 解包：将 .docx 解压为可编辑的 XML 目录
uv run scripts/docx_edit.py unpack 模板.docx unpacked/

# 打包：将编辑后的 XML 目录重新打包为 .docx
uv run scripts/docx_edit.py pack unpacked/ 输出.docx

# 替换：直接在 .docx 中做文本替换（保留原格式）
uv run scripts/docx_edit.py replace 原文件.docx 输出.docx replacements.json
```

replacements.json 格式：
```json
{
  "replacements": [
    {"find": "{{占位符}}", "replace": "替换内容"}
  ],
  "track_changes": false,
  "author": "assistant"
}
```

### 5.2 extract_docx.py — Word 文本提取

```bash
# 提取为可读文本（Markdown 风格标记结构）
uv run scripts/extract_docx.py resume.docx

# 提取为 JSON 结构化数据
uv run scripts/extract_docx.py resume.docx --format structured

# 指定引擎：auto（默认）、python-docx、xml
uv run scripts/extract_docx.py resume.docx --engine xml
```

### 5.3 extract_pdf.py — PDF 文本提取

```bash
# 提取 PDF 文本（支持多栏检测和表格提取）
uv run scripts/extract_pdf.py resume.pdf

# 输出为结构化 JSON
uv run scripts/extract_pdf.py resume.pdf --format structured
```

### 5.4 extract_text.py — 多格式文本提取

```bash
# 支持 .docx / .doc / .pdf / .txt / .md / .html
uv run scripts/extract_text.py 文件.docx
uv run scripts/extract_text.py 文件.pdf -o output.txt
```

### 5.5 create_docx.py — 从 JSON 生成 .docx

```bash
# 从 content.json 生成标准排版的 .docx（专利格式）
uv run scripts/create_docx.py content.json output.docx
```

## 6. 参考文档（需要时读取）

- 编辑已有 .docx 的 XML 操作指南：`references/docx-editing-guide.md`
- 使用 docx-js 从零创建 .docx 的指南：`references/docx-creation-guide.md`

## 7. 交付物类型锁定

- 用户要 `ppt/pptx` 就必须交付可打开的 `pptx` 文件
- 用户要网页就必须交付可打开的 `html`（而不是 markdown 伪装网页）
- 用户要 Word 就交付 `docx` 或明确可导出的格式
- 功能清单锁定：若用户要求可折叠/展开、可切换、可筛选等交互能力，必须列入交付清单并在最终产物里逐项验收；做不到时提前说明限制与替代方案

## 子技能目录（在本 skill 中的实际位置）

```
lark-doc/
├── SKILL.md                                 # 顶层入口（飞书 + Office 路由）
├── scripts/                                 # 全部 Python 脚本（从 skill 根执行）
│   ├── create_docx.py  docx_edit.py  extract_docx.py  extract_pdf.py  extract_text.py
└── references/office-word/                  # 本模块（Office 全部内容）
    ├── SKILL_office-word.md                 # 本文件（Office 控制面 + 体裁路由）
    ├── office-word-layout.md                # Word 排版与版式风格（所有体裁通用）
    ├── references/                           # Word 机制指南
    │   ├── docx-creation-guide.md           # docx-js 从零创建机制
    │   └── docx-editing-guide.md            # 解包改 XML 回包机制
    ├── resume-writing/                       # 简历：SKILL_*.md + references/
    ├── patent-writing/                       # 专利：SKILL_*.md + references/
    ├── visa-doc-filler/                      # 签证：SKILL_*.md + references/
    └── official-document/                    # 公文：SKILL_*.md + references/
```

> 注：脚本已统一上提到 skill 根 `scripts/`；子技能内的脚本调用一律写作 `uv run scripts/xxx.py` 并从 skill 根执行。
