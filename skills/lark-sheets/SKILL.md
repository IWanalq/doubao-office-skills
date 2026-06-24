---
name: lark-sheets
version: 3.0.0
description: "表格全场景处理：覆盖本地 Excel/CSV 与在线表格（含 doubao.com 的 /sheets/ 链接）的创建、读写、分析、计算、建模、文本语义处理、可视化、图表/透视表、表格美化等所有表格任务。用户上传 Excel/CSV、或给出feishu/doubao.com 表格链接（/sheets/ URL/token）作为附件时使用；用户口述数据要整理成表时使用；用户要求计算、统计、建模、预测、分类、挖掘、可视化、透视、美化、公式计算时使用。一切与 excel 相关的任务必须加载本技能。本技能不负责获取外部信息，如需补充数据须先通过其他途径获得。"
metadata:
  requires:
    bins: ["lark-cli", "python3"]
  cliHelp: "lark-cli sheets --help"
---

# 表格全场景处理技能（lark-sheets）

本技能统一处理两类表格，**一套场景方法论、两套执行引擎**：

| 引擎 | 适用对象 | 工具 |
| --- | --- | --- |
| **Excel 引擎** | 本地 `.xlsx` / `.xls` / `.csv` 文件 | Python（pandas / openpyxl）+ `scripts/` 下脚本 |
| **飞书引擎** | 飞书在线表格、doubao.com 的 `/sheets/` 链接 | `lark-cli sheets`（详见「三」） |

两套引擎通过 `lark-cli drive +import` 打通：本地 Excel 可一键导入为飞书在线表格。

---

## 0、开工前：先定「输入来源」与「产物载体」

任何表格任务，先回答两个问题：数据从哪来（输入）、产物以什么形式交付（载体）。这决定走哪套引擎。

### 0.1 识别输入来源

| 输入信号 | 来源判定 | 走哪套引擎 |
| --- | --- | --- |
| 用户上传 `.xlsx` / `.xls` / `.csv` 文件 | 本地 Excel/CSV | Excel 引擎；需飞书产物见 0.2 |
| 用户给出飞书 / doubao 的 `/sheets/` 链接或 token | 飞书在线表格 | 飞书引擎（「三」） |
| 用户口述 / 粘贴数据，无文件 | 待结构化 | 先结构化，再按产物载体（0.2）选引擎 |
| 无数据 | 信息不足 | 向用户询问，或先用其它工具获取数据 |

> ⚠️ **doubao.com 的 `/sheets/` 链接也走飞书引擎**：路由依据是 URL 路径模式（`/sheets/`）和 token，而不是域名。不要因为域名不是飞书就回退到 WebFetch。

### 0.2 表格产物载体决策与导入（默认飞书在线表格）

> **核心策略，优先级高于其它交付说明。**

- **默认载体 = 飞书在线表格**。当用户需要一个表格产物时（哪怕用户说“做个 Excel”“整理成表格”“给我个表”），**默认产出飞书在线表格**，方便在线预览、协作和编辑。
- **唯一的例外（产出本地文件）**：用户**直接明确禁止**使用飞书表格
- 上述例外之外，一律以飞书在线表格交付。

**`.xlsx` → 飞书表格导入（`lark-cli drive +import`）**：当需要把本地 Excel 变成飞书在线表格时，用 Python 生成 `.xlsx` 后调用 `lark-cli drive +import` 导入：

```bash
# 导入本地 Excel 为飞书电子表格
lark-cli drive +import --file "<本地.xlsx相对路径>" --type sheet --name "<在线表格名称>"
```

参数：

| 参数 | 必填 | 说明 |
|------|------|------|
| `--file` | 是 | 本地文件相对路径，如 `.xlsx` / `.xls` / `.csv` |
| `--type` | 是 | 目标文档类型；本技能固定用 `sheet` |
| `--folder-token` | 否 | 目标文件夹 token；不传则导入到云空间根目录 |
| `--name` | 否 | 导入后的在线文档名称；不传默认用本地文件名去扩展名 |

要点：
- 导入成功后，把飞书在线表格链接提供给用户。
- 仅产出无格式 `.csv` 且用户明确只要本地文件时，直接生成即可，无需导入。

### 0.3 三条实现路径

根据「输入来源 × 产物载体」选择路径：

| 场景 | 实现路径 |
| --- | --- |
| 默认飞书产物，从零创建 / 口述数据整理 | 直接用飞书引擎（`lark-cli sheets`，见「三」）构建；或先用 Python 生成 `.xlsx` 再按 0.2 导入飞书 |
| 默认飞书产物，但输入是本地 Excel | 用 Excel 引擎（Python）处理 `.xlsx`，再按 0.2 用 `lark-cli drive +import` 导入飞书，交付在线链接 |
| 默认飞书产物，输入已是飞书表格 | 全程用飞书引擎（「三」）就地操作 |
| 用户明确禁止飞书表格） | 用 Excel 引擎（Python）产出本地文件，按「四」的质量规范交付，**不导入飞书** |

> **何时优先用 Python vs 直接用 lark-cli**：涉及复杂数据清洗、批量计算、多表 merge、统计建模等“重数据加工”时，用 Python 处理更顺手，处理完再导入飞书；若只是在已有飞书表格上读写、套公式、美化、加图表/透视表/条件格式，直接用飞书引擎更短更稳。

---

## 一、场景识别与分派

识别场景后，**读取对应 reference 文件**，按其指导执行。下表的 reference 已按「飞书引擎（lark-sheets-*）」与「Excel 引擎 / 引擎无关方法学（guide-* / ref-* / template-*）」标注；具体走哪套引擎由 0.2 的产物载体与输入来源决定。

### 场景分派表

| 场景 | 典型信号词 / 意图 | 引擎 & 读取的 reference |
|------|----------------|-----------------|
| **表格创建与整理** | “做个表”、“整理成表格/Excel”、“生成报表”、“做个模板”、“整理一下格式” | 默认飞书：「三」+ `references/lark-sheets-core-operations.md` / `lark-sheets-write-cells.md` / `lark-sheets-visual-standards.md`；若产物为 `.xlsx`：`references/ref-xlsx-workflow.md`（含行高/列宽/截断默认规则） |
| **文本语义处理** | “提炼要点”、“归类”、“贴标签”、“标准化文本”、“语义抽取”、“分类观点”、“汇总文字” | `references/guide-semantic-analysis.md`（方法学引擎无关；Excel 用 Python，飞书用 lark-cli 读写） |
| **数据洞察 / 数值计算 / 量化建模 / 数据挖掘** | “分析一下/有什么发现/给出洞察”、“计算/统计/求和/公式”、“建模/预测/排名打分/优化”、“挖掘/聚类/关联/找规律” | 按「二、通用执行流程」执行；表格读写按载体选引擎（飞书=「三」，Excel=「四」+ `references/ref-xlsx-workflow.md`）；分析报告输出模板见 `references/template-report.md` |
| **数据透视表** | “透视表/数据透视表/pivot”、“交叉分析/多维汇总”、“按 X 统计 Y 并对比”、“分组对比” | 飞书原生：`references/lark-sheets-pivot-table.md`（Excel 输入先按 0.2 导入飞书，再 `+pivot-create` 建原生透视表，交付在线链接） |
| **公式迁移 / 飞书公式生成** | “把 Excel 公式改写成飞书公式”、“ARRAYFORMULA”、“数组函数”、“INDEX/OFFSET/MAP/LAMBDA” | 飞书：`references/lark-sheets-formula-translation.md` |
| **财务 / 金融建模与报表**（叠加层） | “财务模型”、“估值/DCF/LBO/Comps”、“三张报表/IS/BS/CFS”、“财务预测”、“预算/Variance”、“Sensitivity/情景分析”、“投行/PE/Equity Research/FP&A/咨询场景” | 默认飞书：`references/lark-sheets-financial-modeling-standards.md`（金融操作+视觉规范，叠加于上述场景之上）；若产物为 `.xlsx`：「四」通用规范 + 该文件的财务逻辑/视觉原则 |


> **多场景叠加**：若任务横跨多个场景，按主诉求选主场景，次要场景的相关说明也可参考对应 reference 文件。
>
> **财务/金融为叠加层**：「财务/金融建模与报表」不是独立场景，而是一层**视觉与操作规范叠加**。当数据属于财务/估值/报表性质时，先按主场景（洞察/计算/建模/创建等）执行，再叠加金融规范（飞书载体看 `lark-sheets-financial-modeling-standards.md`），其优先级高于通用视觉规范。

---

## 二、通用执行流程

以下流程适用于所有场景，引擎无关；具体的读写命令由对应引擎章节（「三」飞书 / 「四」Excel）提供。

### 2.0 基本原则

1. **修改范围以完成目标为准**：默认允许为完成任务在必要范围内修改现有表格（值、公式、样式、合并、列宽/行高等），但不要引入与任务无关的破坏性改动（如删除明细、改变数据口径、重命名/删除 sheet）。若用户明确要求“除指定位置外其他任何单元格都不能动”，则严格按其约束执行。
2. **输出落点按用户诉求**：用户要求“直接在原表改/覆盖原文件”则就地修改；用户要求“保留原表/需要留底”则复制 sheet 或另存新文件/新表格，保证原 sheet 不变。
3. **公式优先原则**：凡是需要计算，优先写公式到最终交付的表格对应单元格，保持动态计算能力。
   - Excel 引擎：写 Excel 公式（如 `ws['C2'] = '=A2+B2'`），不要在 Python 中算好数值再写入。
   - 飞书引擎：写飞书公式；Excel 公式到飞书公式的迁移规则见 `references/lark-sheets-formula-translation.md`。
   - **例外**（允许直接写静态值）：从外部抓取的数据、永不变化的常量、用公式会产生循环引用。

### 2.1 判断数据来源（对应 0.1）

按 0.1 判断来源后进入 2.2：上传 Excel/CSV → 走 Excel 引擎预检；飞书 / doubao 链接 → 走飞书引擎预检；口述/粘贴数据 → 先结构化并按 0.2 选载体，需进一步分析再进入 2.2；信息不足 → 先向用户确认或先用其它工具取数。

### 2.2 数据结构和内容的预先检查

拿到数据后，**先检查结构再动手处理**：

1. **运行结构预检**了解数据概况（预检只为了解数据，具体执行仍需读取完整内容）：
   - **Excel 文件**：`python scripts/inspect_workbook.py <文件路径>`
   - **CSV 文件**：用 `pd.read_csv(..., nrows=15)` 预览，注意编码（优先尝试 utf-8-sig、gbk、gb18030）
   - **飞书表格**：先 `lark-cli sheets +workbook-info` 拿子表清单与元数据，再 `+cells-get` / `+csv-get` 预览数据与结构（合并/行高列宽见 `+sheet-info`）。详见 `references/lark-sheets-read-data.md`、`references/lark-sheets-core-operations.md`。
2. **评估数据规模**，决定执行策略：
   - **小数据**（行数 ≤ 1000，文件 ≤ 5MB）：一次性加载处理
   - **大数据**（行数 > 1000 或文件 > 5MB）：分批策略（分 sheet / 分行批处理 / 流式读取 / 列裁剪）
   - **多 sheet 文件**：逐个 sheet 单独执行完整的「预检 → 处理 → 输出」流程
3. **识别合并单元格**：合并单元格的值仅存储在左上角；提取类任务需 `ffill` 填充；写公式/做合并时只允许在左上角单元格写值/公式。Excel 见 `references/ref-xlsx-workflow.md`，飞书见 `references/lark-sheets-sheet-structure.md`。
4. **识别“表头不清晰”并做字段理解**：若出现无表头/空表头列/多行表头/前几行是标题说明：
   - Excel 用 `scripts/preview_excel_rows.py` 对可疑 sheet 预览更多行（如前 30 行），结合数据形态判断真正表头行
   - 对空表头列，观察该列前 20 个非空值的类型与模式，推断临时列名（如 `未命名_金额`、`未命名_日期`）
   - 后续映射与计算优先用“列坐标/列字母 + 行号范围”锁定字段来源，避免引用错列
5. **识别“特殊行/特殊单元格”并特殊处理**：出现“合计/总计/小计/汇总/累计”等与明细口径不同的行时，做聚合/统计/建模前从明细中排除这些汇总行，避免重复统计（`inspect_workbook.py` 的 `special_rows` 可辅助定位）。

### 2.3 字段语义对齐

动手前，确认用户的指标/概念与数据中字段如何对应。用户说的“收入”是哪一列？“完成率”怎么算？避免“答非所问”。

### 2.4 按场景执行

读取场景分派表（「一」）中对应的 reference 文件，按其工作流程执行任务。

### 2.5 交付

- **改动策略匹配诉求**：默认可在必要范围内修改；若用户要求“只改指定位置/保留原表”，则通过新建 sheet/复制 sheet/另存等方式实现
- **公式在交付表**：计算结果用公式写在最终交付的表格位置，不在临时表/中间 sheet 计算后回填数值
- **载体按 0.2**：默认交付飞书在线表格链接；用户明确要本地文件时交付 `.xlsx` / `.csv`
- **结论优先于过程**：最终交付聚焦用户需要的结论和建议，过滤中间过程
- **格式专业**：图表须有中文标题/坐标轴/图例；新建表格的行高/列宽须自适应（Excel 见「四」，飞书见 `references/lark-sheets-visual-standards.md`）
- **不主动做外部搜索补全**：信息不足时先向用户确认

### 2.6 信息合理性校验（生成/推断信息时必做）

当任务需要“生成信息/补全缺失值/把口述信息整理成表/输出结论建议/构造示例数据”时，交付前必须做合理性校验：

1. **单位合理**：液体优先体积（ml/L），非液体优先质量（g/kg）；货币/数量/百分比/温度单位一致；表头写清单位（如 `Revenue (¥)`、`Weight (g)`）。
2. **取值范围**：时间/时长/数量一般不为负；百分比一般在 `[0,1]` 或 `[0%,100%]`，异常值判断是否格式混淆并统一。
3. **日期时间一致**：结束时间不得早于开始时间；跨天需显式说明或拆分。

---

## 三、飞书表格操作引擎（lark-cli）

### 术语约定

下列词在本 skill 各文档中可能交替出现，但**指同一对象**；解析用户口语时按此映射：

| 标准用语 | 同义 / 口语（均指同一对象） | 说明 |
| --- | --- | --- |
| 工作表（sheet） | 子表、tab、标签页 | spreadsheet 内的单张表；`sheet_id` 是其稳定标识 |
| 电子表格（spreadsheet） | 工作簿、表格 | 顶层容器；由 `--url` 或 `--spreadsheet-token` 定位 |
| reference_id | id | **表内对象**的稳定标识，即各对象主键 flag 接受的值（见下表）。⚠️ 与 `lark-sheets-float-image` 的 `--image-uri`（图片上传句柄）不是一回事，后者不属于 reference_id |

每类对象用各自的主键 flag 定位（命名不统一，按此表对照，不要凭直觉拼）：

| 对象 | 主键 flag | 对象 | 主键 flag |
| --- | --- | --- | --- |
| 工作表 sheet | `--sheet-id` | 条件格式规则 | `--rule-id` |
| 图表 chart | `--chart-id` | 筛选视图 | `--view-id` |
| 透视表 pivot | `--pivot-table-id` | 迷你图（按组） | `--group-id` |
| 浮动图片 | `--float-image-id` | | |

### 场景 → 命令速查（拿不准命令名先查这里，别按直觉拼）

把高频意图映射到**真实存在**的 shortcut / flag。agent 常从 Excel / Google Sheets / 飞书 OpenAPI 误迁移命令名或 flag，先对照本表，避免一次必然失败的试错。完整 shortcut 见各工具参考。

| 你要做的事 | ✅ 正确写法 | ❌ 不存在（会被 cobra 拒） |
| --- | --- | --- |
| 读数据（纯值 / CSV） | `+csv-get`（范围用 `--range`） | — |
| 读值 + 公式 / 样式 / 批注 | `+cells-get --include value,formula,style,comment,data_validation` | `--with-styles`、`--with-merges`、`--include-merged-cells` |
| 写纯值（整块 CSV 平铺） | `+csv-put`（定位用 `--start-cell`，单个左上角锚点格；也接受 `--range` 别名，区间自动取左上角） | — |
| 写值 / 公式 / 样式 | `+cells-set`（定位用 `--range`） | — |
| 查找单元格 | `+cells-search`（关键字用 `--find`） | `+cells-find`、`+find`、`--query` |
| 查找并替换 | `+cells-replace` | — |
| 看子表结构（合并 / 行高列宽 / 冻结 / 隐藏） | `+sheet-info` | `+sheet-get`、`+structure-get`、`+sheet-structure-get` |
| 看工作簿 / 子表清单 | `+workbook-info` | — |
| 导出 xlsx / 单表 csv | `+workbook-export` | — |
| 清除内容 / 格式 | `+cells-clear`（范围维度用 `--scope`，取值 content / formats / all） | `--type` |
| 批量清除多区域 | `+cells-batch-clear`（`--scope`） | `--target` |
| 调整列宽 / 行高 | `+cols-resize` / `+rows-resize`（行、列是两个独立命令） | `--dimension`（无此 flag） |
| 分组汇总 / 透视 | `+pivot-create`（默认不传落点 flag → 自动新建子表，零覆盖） | 用 SUMIF / 本地脚本拼一张假透视表 |

> ⚠️ **定位 flag**：`+cells-get` / `+cells-set` / `+csv-get` 用 `--range`；`+csv-put` 规范用 `--start-cell`（单个左上角锚点格），也接受 `--range` 别名（区间自动取左上角），二者择一即可。
> ⚠️ **读取附加信息**一律走 `+cells-get --include …`，**没有** `--with-styles` 这类 flag；**看合并单元格**用 `+sheet-info` 的 `merged_cells`，不要在 `+cells-get` 里找 merge flag。

### References

本引擎的 reference 分两组：先读**通用方法与规范**（横切所有飞书任务的工作流、铁律、样式、公式规则，不含具体 shortcut）；再按操作对象进入**工具参考**查具体 shortcut 与调用细节。编辑类任务务必先过一遍通用方法与规范，其中的铁律对所有工具参考一律生效。

#### 通用方法与规范（先读，横切所有飞书任务，不含具体 shortcut）

| Reference | 描述 |
| --- | --- |
| [飞书表格核心操作：分析、编辑与可视化](references/lark-sheets-core-operations.md) | 飞书表格核心操作工作流。当用户需要对已有的飞书表格进行查看、分析、编辑或可视化时使用。适用场景：数据查询与统计、公式计算、表格美化、创建图表/透视表、筛选排序、批量修改数据、调整表格结构等。即使用户没有明确说“飞书表格”，只要操作对象是已有的在线表格，都应触发此工作流。不适用于本地 Excel 文件操作。 |
| [飞书表格样式与配色规范](references/lark-sheets-visual-standards.md) | 飞书表格样式与配色规范：表头/数据区/汇总行的颜色、字号、对齐、边框等取值标准，以及新增汇总行、追加行列继承原表风格、已有区域美化等典型场景的决策流程与样式要点。工具调用参数细节请参考对应的 lark-sheets-write-cells / lark-sheets-range-operations / lark-sheets-batch-update。条件格式（高亮、标红、数据条、色阶）请使用 lark-sheets-conditional-format。仅针对飞书表格，不适用于本地 Excel 文件。 |
| [飞书表格公式生成规则](references/lark-sheets-formula-translation.md) | Excel 公式到飞书表格公式的迁移与生成规则。核心目标不是保留 Excel 原语法，而是按飞书表格可执行规则重写公式，并在结果上尽量对齐 Excel。当用户要求把 Excel 公式改写成飞书表格公式，或需要生成飞书公式（尤其涉及 ARRAYFORMULA、原生数组函数、INDEX/OFFSET、MAP/LAMBDA、日期差、多层范围结果与二次展开）时使用。仅针对飞书在线表格，不适用于本地 Excel 文件执行。 |
| [飞书表格金融/财务建模规范](references/lark-sheets-financial-modeling-standards.md) | 飞书在线表格中的金融、财务、估值与经营分析规范：DCF / LBO / Comps / Precedent、三张财务报表、预算与 Variance、Sensitivity / Scenario、资本结构、Unit Economics、Market Sizing、FP&A 与投研/投行/PE/咨询模型。覆盖科目标准分类、三表勾稽、颜色编码、数字格式、单位、年份横向布局、假设/计算/输出分层与多 sheet 拆分、Sensitivity 专用视觉规范等。作为「财务/金融」场景的视觉与操作规范叠加层，优先级高于通用视觉规范。仅针对飞书表格。 |

#### 按对象的工具参考（含 shortcut）

| Reference | 描述 |
| --- | --- |
| [Lark Sheet Workbook](references/lark-sheets-workbook.md) | 管理飞书表格的工作簿结构（子表列表及元数据）。当用户提到“看看这个表格有什么”、“表格结构”、“有哪些 sheet”、“新建一个 sheet”、“删除这个工作表”、“重命名”、“复制一份”、“移动到前面”时使用。仅针对飞书表格。 |
| [Lark Sheet Sheet Structure](references/lark-sheets-sheet-structure.md) | 管理飞书表格的子表结构与布局。适用场景：查看行高、列宽、隐藏行列、合并单元格等布局信息，以及“插入一行”、“删除这列”、“隐藏行”、“冻结表头”、行列分组（大纲折叠/展开）等操作。行列大纲仅在用户明确提到“行分组”、“列分组”、“大纲”、“outline”时才触发，“按XXX分组”等数据分组场景请使用 lark-sheets-pivot-table。如需在表尾追加数据，应先通过此 skill 插入行，再通过 lark-sheets-write-cells 写入。仅针对飞书表格。 |
| [Lark Sheet Read Data](references/lark-sheets-read-data.md) | 读取飞书表格中的单元格数据。当用户需要“看看数据”、“分析数据”、“统计/汇总”时使用；也适用于需要查看公式、样式、批注等详细信息的场景。仅针对飞书表格。 |
| [Lark Sheet Search & Replace](references/lark-sheets-search-replace.md) | 在飞书表格中搜索和替换文本，支持限定范围、大小写匹配、精确匹配、正则表达式。当用户需要“查找”、“搜索”、“定位”某个值，或“替换”、“批量修改文本”、“把 A 改成 B”时使用。不要用于理解表格结构（应读取数据）、不要用于数据分析（应读取数据后计算）、不要把用户操作动作中的关键词（如“汇总金额”“统计数量”）当作搜索词。仅针对飞书表格。 |
| [Lark Sheet Write Cells](references/lark-sheets-write-cells.md) | 向飞书表格的指定区域批量写入值、公式、样式、批注或单元格图片。适用场景：填写数据、设置公式、修改格式、添加批注、嵌入单元格图片（如需操作浮动图片，请使用 lark-sheets-float-image）；若只需把一块 CSV 纯值批量铺到表格上（不带公式/样式），直接使用 `+csv-put` 更短更快。追加数据需先通过 lark-sheets-sheet-structure 插入行列。仅针对飞书表格。 |
| [Lark Sheet Range Operations](references/lark-sheets-range-operations.md) | 对飞书表格中指定区域执行结构性操作（不涉及写入单元格数据值）。适用场景：清除内容或格式（“清空”、“删除内容”、“去掉格式”）、合并/取消合并单元格、调整行高列宽（“加宽列”、“自适应列宽”）、移动/复制/填充/排序数据（“移动数据”、“复制到”、“自动填充”、“按某列排序”）。写入单元格数据请使用 lark-sheets-write-cells。仅针对飞书表格。 |
| [Lark Sheet Batch Update](references/lark-sheets-batch-update.md) | 将多个飞书表格写入操作合并为一次批量执行，按顺序依次完成。适合需要连续执行多个写入操作的场景（如先修改结构再写入数据）。仅针对飞书表格。 |
| [Lark Sheet Chart](references/lark-sheets-chart.md) | 管理飞书表格中的图表（柱形图、折线图、饼图、条形图、面积图、散点图、组合图、雷达图等）。当用户需要创建图表、修改图表样式或数据源、查看已有图表配置、删除图表时使用。也适用于用户提到“数据可视化”、“画个图”、“趋势分析”、“对比图”、“占比分析”、“做个图表”等数据可视化相关场景。仅针对飞书表格。 |
| [Lark Sheet Pivot Table](references/lark-sheets-pivot-table.md) | 管理飞书表格中的数据透视表。当用户需要创建透视表、修改透视表的行列字段/聚合方式/筛选条件、查看已有透视表配置、删除透视表时使用。也适用于用户提到“分组汇总”、“交叉分析”、“按XXX统计”、“按字段分组”、“再分下组”、“多维分析”、“数据透视”等场景。仅针对飞书表格。 |
| [Lark Sheet Conditional Format](references/lark-sheets-conditional-format.md) | 管理飞书表格中的条件格式规则（重复值高亮、单元格值比较、数据条、色阶、排名、自定义公式等）。当用户需要创建条件格式、修改已有规则的范围或样式、查看当前条件格式配置、删除规则时使用。也适用于用户提到“高亮”、“标红”、“颜色标记”、“数据条”、“色阶”、“条件样式”等场景。仅针对飞书表格。 |
| [Lark Sheet Filter](references/lark-sheets-filter.md) | 管理飞书表格中的筛选器（filter）。当用户需要筛选数据（按文本/数值/颜色/日期条件过滤行）、查看已有筛选配置、修改或删除筛选器时使用。也适用于“只看”、“筛选出”、“仅保留符合条件的”等场景。仅针对飞书表格。 |
| [Lark Sheet Filter View](references/lark-sheets-filter-view.md) | 管理飞书表格中的筛选视图（filter view）。当用户需要“建一个 XX 视图”、“保存这个筛选状态”、“切换不同筛选”、维护一个 sheet 上多份独立筛选配置时使用。视图与筛选器（filter）相互独立，可在同一 sheet 共存；视图的隐藏行仅在用户进入该视图时本地生效，不影响其他协作者。仅针对飞书表格。 |
| [Lark Sheet Sparkline](references/lark-sheets-sparkline.md) | 管理飞书表格中的迷你图（折线迷你图、柱形迷你图、胜负迷你图）。当用户需要在单元格内嵌入小型图表来展示数据趋势时使用。也适用于“趋势线”、“单元格内图表”、“迷你图”等场景。注意：不等同于被禁用的 SPARKLINE() 公式函数。仅针对飞书表格。 |
| [Lark Sheet Float Image](references/lark-sheets-float-image.md) | 管理飞书表格中的浮动图片。当用户需要在表格中插入浮动图片、调整图片位置和大小、查看已有浮动图片、删除图片时使用。也适用于“插入图片”、“添加 logo”、“放一张图”等场景。注意：如果用户需要将图片嵌入到某个单元格内部（单元格图片），请阅读 lark-sheets-write-cells。仅针对飞书表格。 |

### 公共 flag 速查

各 reference 的每个 shortcut 标题下用一行徽章标注该 shortcut 支持的公共 / 系统 flag，例如：

- `_公共四件套 · 系统：--dry-run_` — URL/token + sheet 定位（两组各**必给一个**，详见下方「公共 flag」），加 `--dry-run`
- `_公共：URL/token（无 sheet 定位） · 系统：--yes、--dry-run_` — 只接 URL/token，常见于 `+batch-update` 等不强制 sheet 定位的 shortcut

徽章里只列名字。type / 必填 / 描述都在本段统一声明：

#### 公共 flag（定位资源）

**公共四件套** = `--url` / `--spreadsheet-token` / `--sheet-id` / `--sheet-name`，分成两组 XOR，**每组都必须给且只能给一个**（XOR = 二选一必填，不是“可选”）：

1. **spreadsheet 定位（必填）**：`--url` 与 `--spreadsheet-token` 二选一，**必须给其中之一**。两个都不给 → 校验报错 `specify at least one of --url or --spreadsheet-token`；两个都给 → 互斥冲突。
   - **`--url` 只解析 `/sheets/` 与 `/spreadsheets/` 两种链接**（从路径里抽出 token；也可以直接把裸 token 传给 `--spreadsheet-token`）。其它形态的链接不会被解析成表格 token。
   - ⚠️ **`/wiki/` 知识库链接不能直接当表格定位用**：wiki 链接背后可能是电子表格，也可能是文档 / 多维表格等其它类型，`--url` **不会**自动把 wiki token 解析成 spreadsheet token，直接传会失败。必须先把它解析成真实文档 token —— `lark-cli wiki +node-get --node-token "<wiki 链接或 token>"`，确认返回的 `obj_type` 为 `sheet` 后，取其 `obj_token` 作为 `--spreadsheet-token` 传入（解析细节见 [`../lark-wiki/SKILL.md`](../lark-wiki/SKILL.md)）。
   - **例外**：`+workbook-create` 是新建一个还不存在的表格，**不接受任何 spreadsheet / sheet 定位 flag**（只有 `--title` / `--folder-token` / `--headers` / `--values`）。
2. **sheet 定位（公共四件套 shortcut 必填）**：`--sheet-id` 与 `--sheet-name` 二选一，**必须给其中之一**。两个都不给 → 校验报错 `specify at least one of --sheet-id or --sheet-name`。
   - ⚠️ **不确定 sheet 名时禁止直接猜 `Sheet1`**：除非用户对话明确说出 sheet 名 / id，或上下文（之前的工具调用 / URL 锚点 `?sheet=xxx`）已经出现过具体值，否则**第一步先调 `+workbook-info --url "..."`**（或 `--spreadsheet-token`）拿 `sheets[].sheet_id` / `sheets[].title` 列表再选。中文环境下子表常叫“数据” / “Sheet”（无数字）/ “工作表 1” / 业务名，猜 `Sheet1` 大概率撞 `sheet not found`，比先查多耗一次失败调用 + 重试。
   - ⚠️ **`--range` 里的 `Sheet1!` 前缀不能替代 sheet 定位**：即使写了 `--range 'Sheet1!A1:B2'`，仍**必须**额外传 `--sheet-id` 或 `--sheet-name`，否则照样报上面的错。
   - ⚠️ **A1 reference 含 `!`**（`--source` / `--range` / `--ranges`）**：shell session 起手先 `set +H`** 关 bash history expansion，否则 `"Sheet1!A1"` 会被拦成 `event not found`；含特殊字符（`-` / 空格 / 非 ASCII）的 sheet 名还要内部 single-quote 包，如 `--source "'Sales-2025'!A1:D100"`。
   - **例外**：徽章标为 `_公共：URL/token（无 sheet 定位）…_` 的 shortcut（如 `+workbook-info` / `+workbook-export` / `+batch-update` / `+dropdown-update|delete` / `+cells-batch-set-style` / `+cells-batch-clear` / `+sheet-create`）**不接受也不需要** sheet 定位，只给一组 spreadsheet 定位即可。`+pivot-create` 用 `--target-sheet-id` / `--target-sheet-name`（XOR，可都不传，落点细节见 `lark-sheets-pivot-table`）。

| Flag | Type | 必填 | 说明 |
| --- | --- | --- | --- |
| `--url` | string | 二选一必填（与 `--spreadsheet-token`） | spreadsheet URL |
| `--spreadsheet-token` | string | 二选一必填（与 `--url`） | spreadsheet token |
| `--sheet-id` | string | 二选一必填（与 `--sheet-name`；仅公共四件套 shortcut） | 工作表 reference_id |
| `--sheet-name` | string | 二选一必填（与 `--sheet-id`；仅公共四件套 shortcut） | 工作表名称 |

**统一调用范式**（公共四件套 shortcut 的所有示例都遵循此形状，两组定位缺一不可）：

```bash
lark-cli sheets <shortcut> <workbook 定位> <sheet 定位> <其它 flag>
#   workbook 定位：--url "..."        或 --spreadsheet-token "..."           （二选一，必给）
#   sheet 定位：    --sheet-id "$SID"  或 --sheet-name "<真实表名>"            （二选一，必给；占位符不要原样填）
# 例：lark-cli sheets +csv-get --url "https://.../sheets/shtXXX" --sheet-name "<真实表名>" --range "A1:F30"
# 注意：真实表名不要直接填 "Sheet1"——大多数表的子表不叫这个；先 +workbook-info 拿 sheets[].title 再代入。
```

#### 系统 flag

| Flag | Type | 必填 | 说明 |
| --- | --- | --- | --- |
| `--dry-run` | bool | 否 | 零副作用：仅打印请求路径与参数模板，不发起调用；多步操作会输出每个子操作的请求模板 |
| `--yes` | bool | 是（仅 `high-risk-write`） | 二次确认；不带时退出码 10。 |
| `--print-schema` | bool | 否 | 本地打印复合 JSON flag 的 JSON Schema 并退出，不发起任何调用、不需要其它 required flag。与 `--flag-name <name>` 搭配指定要查哪个 flag；省略 `--flag-name` 时列出该 shortcut 所有可查询的 flag。**仅在 shortcut 含复合 JSON flag 时有效**——判断方法：该 shortcut 的 Flags 表里出现类型标注为「复合 JSON」的 flag（如 `--cells` / `--properties` / `--operations` / `--border-styles` / `--sort-keys` / `--options`）即支持；纯标量 flag 的 shortcut 不支持。 |
| `--flag-name` | string | 否 | 配合 `--print-schema` 使用，指定要打印 JSON Schema 的 flag 名（不带 `--` 前缀，如 `cells` / `properties` / `operations`）。 |

**Agent 使用提示**：写复合 JSON flag（`--cells` / `--properties` / `--operations` / `--border-styles` / `--sort-keys` / `--options` 等）时，如果对结构不确定，先跑 `lark-cli sheets <shortcut> --print-schema --flag-name <name>` 把完整 JSON Schema 读出来再构造 payload，比靠 reference 的速查表更精确，也避免因为字段拼写或缺失被服务端拒绝。reference 的 `## Schemas` 段只给一层结构，深层只能靠 `--print-schema` 或 `## Examples` 的真实示例。

#### flag 内容类型与输出约定（术语速记）

- flag 表里 JSON 类入参标三类：**复合 JSON** = 深层嵌套对象（用 `--print-schema` 取完整结构）；**简单 JSON** = 一维 / 二维标量数组（如 `["sheet1!A1:B2",...]` / `[["alice",95]]`，结构简单无需 print-schema）；**非 JSON 文本** = 原样文本（如 CSV）。`--print-schema` 只对**复合 JSON** flag 有效（同一 shortcut 的简单 JSON flag 如 `--colors` 不在此列）。
- **envelope**：所有 shortcut 返回统一外层结构 `{ok, identity, data, ...}`。正文里 `envelope.data` 指业务数据层（如 `+csv-get` 的 `annotated_csv`）；写操作不会自动回读，如需校验请自行调用对应的 `+*-list` / `+*-get` / `+cells-get`。

### 复合 JSON / 大入参：优先 stdin

flag 帮助里标注支持 **Stdin** 的入参，当 payload 较大、含换行 / 引号等特殊字符，或已经落在某个文件里时，优先用 stdin（`-`）传入，避免命令行超长与 shell 转义问题。

推荐写法：payload 写到用户项目目录之外的临时文件（放系统临时目录，避免污染项目），再用 stdin 喂进去：

```bash
# TMPFILE 指向系统临时目录下的 payload 文件（脚本里用 tempfile.gettempdir() / os.tmpdir() 等取临时目录）
lark-cli sheets +cells-set --url "..." --sheet-name "Sheet1" --range "A1:B2" --cells - < "$TMPFILE"
```

**`@file` 接绝对路径会被拒，且被拒后不要照报错提示做。** `@file` 出于安全只接受 cwd 下的相对路径，传 cwd 之外的绝对路径会被拒。此时报错会建议“先 cd 到目标目录，或改用相对路径”——**两条都不要照做**：cd 过去、或把临时文件写进用户项目目录，都会污染工作目录。正解是改用 stdin（`--<flag> - < 文件`）。

---

## 四、本地 Excel 输出质量规范（Python 引擎）

仅当产物为本地 `.xlsx` 文件（用户明确要 `.xlsx` 或禁止飞书，见 0.2）时适用。所有输出 Excel 必须满足以下标准（含格式、行高/列宽/截断、公式重算与验证）。详细技术工作流参见 `references/ref-xlsx-workflow.md`。

### 基础规范

| 项目 | 要求 |
|------|------|
| **字体** | 全文使用统一专业字体（如 Arial、宋体），不同区域字体一致 |
| **公式错误** | 交付前避免出现公式错误（`#REF!` `#DIV/0!` `#VALUE!` `#N/A` `#NAME?`），用 `scripts/formula_verify.py` 检查 |
| **现有模板** | 修改已有文件时，精确匹配其格式、样式和规范；现有模板约定优先于本规范 |
| **公式 vs 硬编码** | 计算结果必须写成 Excel 公式（如 `=SUM(B2:B9)`），**不得**在 Python 中算好再硬编码写入单元格 |

### 列宽行高自适应规范

生成或修改 Excel 表格时，列宽和行高必须根据内容自适应，确保表格不拥挤、不浪费空间。

**列宽**：扫描该列所有单元格，取最长内容的显示宽度（中文字符按 2 宽度）+ padding 3 字符。下限 8、上限 40。超过上限的列启用 `wrap_text=True` 自动换行。

**行高**：表头行 30、普通数据行 20、汇总行 26、含换行单元格的行 36。

**内边距**：通过列宽 padding（+3）和行标签列 `Alignment(indent=1)` 提供呼吸空间。

上述列宽/行高规则**适用于所有新建 Sheet 和表格区域**；可用 `scripts/format_range.py` 批量应用，单元格排版细节（行高/列宽/截断）见 `references/ref-xlsx-workflow.md`。修改用户现有模板时保持原有行高列宽不变（除非用户要求调整）。

### 样式与图表脚本（优先使用）

涉及单元格批量样式（字体/底色/边框/数值格式/条件格式）或图表生成时，**优先调用以下 CLI 脚本**，避免重复手写 openpyxl 代码：

| 脚本 | 用途 | 典型用法 |
|------|------|---------|
| `scripts/format_range.py` | 批量格式化范围（含条件格式、合并） | `python scripts/format_range.py <file> <sheet> A1:E1 --bold --bg-color FFFF00 --align center` |
| `scripts/create_chart.py` | 在 sheet 创建 bar/line/pie/scatter/area 图表 | `python scripts/create_chart.py <file> <锚点sheet> 'Data!A1:E6' bar G2 --title '季度销售'` |

两个脚本输出 JSON，失败时 `status: error`。详细参数见脚本 `--help`。条件格式参数走 JSON 串：`--cond-format '{"type":"color_scale","params":{...}}'`，支持 `color_scale / data_bar / icon_set / formula / cell_is`。

### ref-xlsx-workflow.md 中的进阶能力索引

下列场景出现时，**直接跳到** `references/ref-xlsx-workflow.md` 对应小节，不要从零写代码：

| 场景信号 | 跳到的小节 |
|---------|-----------|
| “复制这块/把 A 表的格式搬到 B 表/保留样式复制” | “范围复制（含样式）” |
| “把这一段清掉/删除并上移/重置区域格式” | “范围清空与重置” |
| 写公式前想拦住语法错/避免不安全函数 | “公式写入前自检” — 与 `formula_verify.py` 形成事前+事后闭环 |
| 用户上传表里有下拉框/限制输入/打开报错“内容存在问题” | “读取数据验证规则（下拉框 / 输入限制）” |
| “把这块做成可筛选的表/带表头排序/Excel Table” | “标准 Excel Table（ListObject）” |

### 财务/金融场景（Excel 产物）

财务/金融场景**默认走飞书载体**，遵循 `references/lark-sheets-financial-modeling-standards.md`。若用户明确要求 `.xlsx` 产物，则在「四」通用规范基础上，套用该文件的**财务逻辑与视觉原则**（科目标准分类、三表勾稽、颜色编码：蓝=输入/黑=公式/绿=跨表引用/红=外链、数字格式：货币/零值显示 `-`/负数括号/倍数 `0.0x`、Assumptions/Calc/Sensitivity 多 sheet 拆分、年份横向布局、Sensitivity 禁色阶/数据条等）。

**优先级**：用户指令 / 用户模板样式 > `lark-sheets-financial-modeling-standards.md`（金融行业惯例）> 本文档通用规范。与通用视觉规范冲突时以金融规范为准（典型冲突：财务模型禁斑马纹、Sensitivity 禁条件格式/色阶/数据条、年份列须紧凑等宽、不加竖线、主题色仅黑白+蓝/绿）。

---

## 五、References 与脚本总览

引擎无关 / Excel 引擎 reference：

| 文件 | 引擎 | 用途 |
| --- | --- | --- |
| `references/guide-semantic-analysis.md` | 引擎无关 | 文本语义抽取/归类/标准化/汇总方法学 |
| `references/template-report.md` | 引擎无关 | 数据分析报告输出模板 |
| `references/ref-xlsx-workflow.md` | Excel | Excel 创建/编辑/公式重算/范围复制/数据验证等技术工作流 |

飞书引擎 reference（18 个）见「三、References」表，那里有更详的选用说明；完整文件清单以 `references/` 目录为准。

脚本（`scripts/`，仅 Excel 引擎）：`inspect_workbook.py`（结构预检）、`preview_excel_rows.py`（多行表头预览）、`formula_verify.py`（公式重算与校验）、`format_range.py`（批量样式/条件格式）、`create_chart.py`（图表）、`_excel_utils.py` / `lo_runtime.py`（内部工具）。
