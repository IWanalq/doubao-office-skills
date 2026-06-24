# 飞书表格金融/财务建模规范

## 定位与优先级

本文用于飞书在线表格中的金融、财务、估值和经营分析场景，包括 DCF / LBO / Comps / Precedent、三张财务报表、预算与 Variance Analysis、Sensitivity / Scenario Analysis、资本结构、Unit Economics、Market Sizing、FP&A 和投研/投行/PE/咨询模型。

优先级从高到低：

1. 用户明确指令或既有模板样式。
2. 本金融/财务建模规范。
3. 通用核心操作、视觉规范与公式规则。

如果本文与通用视觉规范冲突，以本文为准。典型冲突：

| 通用规范 | 财务模型规范 |
| --- | --- |
| 数据行较多时可使用斑马纹 | 财务模型默认禁止斑马纹，避免干扰小计/合计识别 |
| 可用数据条、色阶强化可视化 | Sensitivity 禁止色阶、数据条和图标集 |
| 列宽按内容自适应 | 年份列必须紧凑等宽；标签列才加宽 |
| 可用柔和竖线分隔区域 | 普通财务模型禁止竖线；Sensitivity 矩阵浅灰细框是唯一例外 |

## 按任务裁剪

不要把全套 DCF 规范套到简单费用表。先判断任务类型，再选择规则。

| 任务类型 | 必用规则 | 不要做 |
| --- | --- | --- |
| 三表整理 / 标准化 | 科目分类、三表结构、勾稽验证、颜色编码、数字格式、单位、年份横向布局、小计/合计边框 | 不需要 Sensitivity |
| DCF / LBO / 估值模型 | 假设/计算/输出分层，多 sheet 拆分，横向年份，假设单独落地，公式引用假设，Sensitivity 按需独立 | 不要把假设硬编码进公式 |
| Comps / Precedent | 科目口径、颜色编码、数字格式、单位、分区和小计样式 | 通常不需要三表勾稽，不强制拆多 sheet |
| 预算 / Variance Analysis | 颜色编码、数字格式、横向期间、差异列公式、汇总边框 | 不需要 Terminal Value / WACC |
| 简单 FP&A 汇总 / 费用表 | 基础颜色编码、数字格式、单位、合理列宽 | 不强行拆 sheet，不强行做三层边框 |
| 单项 Sensitivity / Scenario | 假设分离、Sensitivity 专用视觉规范、baseline 标注 | 不使用色阶/数据条 |

## 财务逻辑规范

### 科目标准分类

整理原始科目时，不能把 raw data 机械拼接成报表。必须按 GAAP / IFRS 和财务建模惯例分类。

Income Statement 关键分类：

| 分类 | 示例 | 高频错误 |
| --- | --- | --- |
| Revenue | Product Revenue、Service Revenue、Subscription、License | 把 Other Income 混入主营收入 |
| COGS | 直接人工、直接材料、制造费用、SaaS hosting/infrastructure、支付处理费 | 把 Implementation SG&A / Customer Success 误归 COGS |
| SG&A | G&A、Sales & Marketing、Implementation SG&A、Customer Success、Operations SG&A、Shared Service | 把 Marketing 误归 COGS；漏掉分摊费用 |
| R&D | Research、Product Development、Engineering Payroll | 并入 G&A |
| D&A | Depreciation、Amortization | 埋在 COGS 或 SG&A 里 |
| Non-operating | Interest、FX、One-time Items | 和 Operating Income 混淆 |
| Tax | Income Tax Expense / Benefit | 当作经营费用 |

Balance Sheet 按 Current / Non-current 拆分 Assets、Liabilities、Equity；Cash、AR、Inventory、Prepaids 属 Current Assets，PP&E / Goodwill / Intangibles 属 Non-current Assets，AP / Accrued / ST Debt / Deferred Revenue 属 Current Liabilities，LT Debt / Deferred Tax 属 Non-current Liabilities。

Cash Flow Statement 使用间接法：Net Income 起步，加回 D&A / SBC，调整 Working Capital 和 Deferred Tax，分 CFO / CFI / CFF，最终 Ending Cash 必须等于 BS Cash。

### 标准报表结构

Income Statement 自上而下：

```text
Revenue
  Total Revenue
- COGS
  Total COGS
= Gross Profit
  Gross Margin %
- Operating Expenses
  Total OpEx
= EBITDA
  EBITDA Margin %
- D&A
= EBIT
- Interest / Other Income (Expense)
= Pre-tax Income
- Tax
= Net Income
  Net Income Margin % / EPS
```

Balance Sheet 必须有 `Total Assets`、`Total Liabilities`、`Total Equity`、`Total Liabilities & Equity` 和 `Check: Total Assets - Total L&E = 0`。

Cash Flow Statement 必须有 CFO、CFI、CFF、Net Change in Cash、Beginning Cash、Ending Cash，并校验 Ending Cash = BS Cash。

DCF 标准骨架：

```text
1. Key Assumptions
2. Revenue / EBITDA / EBIT / NOPAT
3. + D&A - CapEx - Change in NWC = UFCF
4. Discount Factor / PV of UFCF
5. Terminal Value
6. Enterprise Value -> Equity Value -> Implied Share Price
7. Sensitivity / Scenario
```

### 多 sheet 拆分

专业模型按 Input -> Calc -> Output 分层，复杂模型必须拆分：

- DCF / LBO：`Assumptions`、`DCF - Calc`、`Sensitivity`、`Output / Summary`，可选 `Source Data`。
- 三表模型：`Assumptions`、`IS`、`BS`、`CFS`、`Supporting Schedules`、`Check`。
- 带 Sensitivity 的任何模型：Sensitivity 必须独立 sheet 或独立清晰区块。

简单报表整理、费用汇总、Variance Analysis、单页 Comps/Precedent、总行数小于 40 的单一逻辑块可以不拆 sheet。

跨 sheet 引用规则：

1. 引用路径写完整 sheet 名，如 `='Assumptions'!$B$7`；sheet 名含空格或特殊字符时按飞书公式规则加引号。
2. 数据流单向：`Assumptions -> Calc -> Sensitivity -> Output`。
3. 禁止循环引用；Sensitivity 直接引用 Calc 结果，不链式穿透多个中间 sheet。

### 年份横向布局

时间必须横向排布，科目纵向排布。所有相关 sheet 的年份列必须对齐。

正确示例：

```text
                FY2023A   FY2024A   FY2025E   FY2026E
Revenue             500       575       644       708
EBITDA              125       155       180       205
```

假设值如果按年度变化，也必须横向排布并与计算 sheet 的年份列一一对齐：

```text
                        FY2025E   FY2026E   FY2027E
Revenue Growth %          12.0%     10.0%      9.0%
EBITDA Margin %           25.0%     26.0%     27.0%
CapEx % of Revenue         5.0%      5.0%      4.5%
Tax Rate                  25.0%     25.0%     25.0%
```

永续性假设如 WACC、Terminal Growth 可以单独放在 Assumptions 上方，不按年份展开。

### 假设值与公式

可被用户修改的假设必须集中放在 Assumptions 区或 sheet，用蓝色字体标识，并由公式引用。禁止把 Growth、Margin、WACC、Tax Rate、CapEx %、Terminal Growth、倍数等硬编码在公式里。

只有三类单元格可直接写静态值：

1. 历史真实数据。
2. 蓝色输入假设。
3. 外部来源的静态取数，且必须标注来源。

横向拉公式时必须正确使用 `$`：

| 被引用内容 | 正确模式 | 说明 |
| --- | --- | --- |
| 同行逐年变化值 | `A1` | 向右复制时跟随年份变动 |
| 单一永续假设 | `$B$7` | 向右/向下都锁定 |
| 同列假设、逐行变化 | `$B7` | 锁列不锁行 |
| 年份标题行 | `B$4` | 锁行不锁列 |

写完横向公式后，必须回读 2-3 个相邻年份列的公式字符串和值，确认年份引用跟随列移动、被锁定的假设保持不变，且没有 `#REF!`、`#DIV/0!`、`#VALUE!`、`#NAME?`、`#N/A`。

## 视觉规范

### 字体颜色编码

财务模型用字体颜色表达单元格性质。

| 颜色 | Hex | 含义 |
| --- | --- | --- |
| 蓝色字体 | `#0000FF` | 硬编码输入值、用户可修改假设 |
| 黑色字体 | `#000000` | 本 sheet 公式或普通文本 |
| 绿色字体 | `#008000` | 同工作簿跨 sheet 引用；公式中只要出现跨 sheet 引用就用绿色 |
| 红色字体 | `#FF0000` | 外部文件/外部系统链接，慎用 |
| 灰色斜体 | `#808080` + italic | YoY、Margin、Notes、单位说明、数据来源 |
| 黄色背景 | `#FFFF00` | 待确认或待复核假设 |

辅助行字号与正文一致，只靠灰色和斜体区分层级。除 sheet 顶部大标题外，全表正文、分区标题、副标题、辅助行使用统一字号。

### 数字格式

| 数据类型 | 推荐格式 |
| --- | --- |
| 年份 | `0`，不得显示千分位 |
| 整数 | `#,##0;(#,##0);"-"` |
| 小数 | `#,##0.0;(#,##0.0);"-"` 或 `#,##0.00;(#,##0.00);"-"` |
| 货币 | `$#,##0;($#,##0);"-"` 或 `$#,##0.00;($#,##0.00);"-"` |
| 百分比 | `0.0%` 或 `0.00%`，同一表内保持一致 |
| 估值倍数 | `0.0" x"` |
| 人数/股数 | `#,##0` |

零值显示为 `-`，负数使用括号法 `(123)`。如采用窄货币符号列，符号列单独放 `$` / `¥`，数值列不再带货币符号。

### 单位与来源

单位必须清晰标注：

- 全表单位统一时，在标题下方用灰色斜体副标题标注，如 `($ in Millions, Except Per Share Data)`。
- 同一表存在多种单位时，在字段名后直接标注，如 `Revenue ($mm)`、`Gross Margin (%)`、`员工人数（万人）`、`ARPU, 元/月`。

历史值、外部数据和硬编码来源必须在表尾或注释中标注：`Source: [来源], [日期], [页/表/字段]`。FY、CY、LTM、NTM、CAGR、YoY、QoQ 等缩写必须使用一致口径。

### 布局与列宽

如果 surface 支持隐藏默认网格线，财务模型应关闭网格线；如果当前 surface 不支持，则不把网格线作为阻塞验收项。

推荐像素宽度：

| 列类型 | 建议宽度 |
| --- | --- |
| 左侧留白列 | 16-24 px |
| 缩进/货币符号窄列 | 28-36 px |
| 标签/科目列 | 220-320 px |
| 年份/期间列 | 64-72 px，最多约 80 px，且所有年份列等宽 |

分区标题行用于隔离 Key Assumptions、Core Calculation、Terminal Value、Sensitivity 等区块：

- 同层级标题使用相同背景色和相同左右边界。
- 不同层级也保持左右边界一致，只用背景色深浅区分层级。
- 一级建议深蓝底白字加粗；二级中蓝；三级浅蓝。

父子层级通过缩进和加粗表达：父级/合计行加粗，子项正常字重并缩进。

### 边框

边框只表达结构，不做装饰。

| 场景 | 边框 |
| --- | --- |
| 小计行 | 上细线 |
| 关键小计，如 Gross Profit / EBITDA / NOPAT / UFCF | 上细线 + 加粗 |
| 最终合计，如 Net Income / Total Assets / Ending Cash / Implied Share Price | 上细线 + 下双线 + 加粗 |
| 普通数据行 | 无边框 |
| 年份列之间 | 禁止竖线 |

Sensitivity 矩阵可使用浅灰细框作为唯一例外，目的是表达双轴矩阵结构，不得扩展到普通财务报表区域。

### Sensitivity / Scenario

Sensitivity 必须极简、对称、可读。

禁止：

- 条件格式色阶。
- 数据条。
- 斑马纹。
- 图标集。
- 彩虹配色。

推荐：

1. 行轴和列轴以 baseline 为中心等距展开，如 WACC: 8%, 9%, 10%, 11%, 12%。
2. baseline 交点用浅黄背景 `#FFF2CC` + 加粗标注。
3. 所有结果格使用同一 `number_format`。
4. 标题下方用灰色斜体说明输出指标。

## 交付前检查

任何财务输出必须检查：

- 已按任务类型选择规则，未过度套用复杂模型结构。
- 年份横向排布，历史/预测后缀清楚，如 A / E / B。
- 假设单独落地，蓝色字体，公式引用假设而非硬编码。
- 横向公式 `$` 锁定已回读验证。
- 蓝/黑/绿/红/灰色编码正确。
- 单位、币种、来源和口径已标注。
- 数字格式统一，负数括号，零值为 `-`，年份无千分位。
- 年份列等宽紧凑，标签列较宽。
- 普通数据行无装饰边框，无竖线。
- 小计/关键小计/最终合计的边框和加粗层级正确。
- 公式结果无错误值。

三表模型额外检查：

- BS 每期 `Total Assets = Total Liabilities + Total Equity`。
- CFS Ending Cash 每期等于 BS Cash。
- Retained Earnings 与 Net Income / Dividends 口径一致。

多 sheet 模型额外检查：

- Assumptions 只放输入和说明，不写计算公式。
- Calc 引用 Assumptions，Output 引用 Calc，数据流单向。
- Sensitivity 独立 sheet 或独立区块。

Sensitivity 额外检查：

- 无色阶、无数据条、无斑马纹。
- 仅 baseline 交点高亮。
- 双轴范围围绕 baseline 对称。

## CLI 落地提示

- 写值、公式、样式时读取 `lark-sheets-write-cells`；多区域或多步骤写入优先用 `lark-sheets-batch-update`。
- 调整列宽、行高、合并、排序、复制格式时读取 `lark-sheets-range-operations` 和 `lark-sheets-sheet-structure`。
- 生成跨 sheet 公式前读取 `lark-sheets-formula-translation`，并按飞书公式语法验证引用、数组和错误值。
- 所有颜色在 CLI 参数中使用带 `#` 的 RGB hex，如 `#0000FF`。
