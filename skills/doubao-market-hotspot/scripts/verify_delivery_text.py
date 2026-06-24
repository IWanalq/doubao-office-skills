#!/usr/bin/env python3
"""Verify the user-facing outer reply for a market briefing.

This checks the chat/card text. It accepts either the default dialog-first
reply that asks whether to generate HTML, or the optional HTML delivery reply
that includes a finished HTML link. Structure, safety, and source-link issues
are blocking.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def _text(*codes: int) -> str:
    return "".join(chr(code) for code in codes)


def _literal_pattern(terms: list[str]) -> str:
    return "|".join(re.escape(term) for term in terms)


STATUS_TERMS = [
    _text(0x5df2, 0x6267, 0x884c, 0x4ee3, 0x7801),
    _text(0x5df2, 0x7f16, 0x8f91, 0x6587, 0x4ef6),
    _text(0x5df2, 0x8bfb, 0x53d6, 0x6587, 0x4ef6),
    _text(0x5df2, 0x5199, 0x5165, 0x6587, 0x4ef6),
    _text(0x5df2, 0x5b8c, 0x6210, 0x538b, 0x7f29),
    _text(0x6211, 0x8bc6, 0x522b, 0x5230),
    _text(0x6211, 0x53d1, 0x73b0),
    _text(0x6211, 0x51b3, 0x5b9a),
]

PROCESS_TERMS = [
    _text(0x6211, 0x5df2, 0x5b8c, 0x6210),
    _text(0x6211, 0x4f1a, 0x5148),
    _text(0x6211, 0x8ba1, 0x5212),
    _text(0x6211, 0x5c06),
    _text(0x6211, 0x5148),
]


FORBIDDEN_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "执行记录",
        re.compile(
            r"("
            + _literal_pattern(STATUS_TERMS)
            + r"|"
            r"(?:搜索|检索)\s*\d+\s*个(?:词|条件)|参考\s*\d+\s*篇资料|"
            r"CanvasCreateFile|第\s*\d+\s*行|定位到|重新规划 HTML|"
            r"识别到用户问题|确认.*交易日期|整理.*核心信息|"
            r"我需要按照正确的 Edit 格式)"
        ),
        "用户前台不能包含工具状态、调试步骤或文件编辑记录",
    ),
    (
        "执行过程",
        re.compile(
            r"("
            + _literal_pattern(PROCESS_TERMS)
            + r"|接下来我(?:会|将)|接下来要渲染|"
            r"为确保[^。\n]*(?:修改|验证|运行|安装|渲染)|"
            r"确认[^。\n]{0,40}验证通过|确认[^。\n]{0,40}调整无误|"
            r"发现[^。\n]{0,60}(?:不存在|权限限制|验证失败|缺失|顺序错误)|"
            r"分析原因是|着手验证|准备将\s*package\.json)",
            re.I,
        ),
        "用户前台不能包含第一人称执行计划、自我验证过程或修复步骤",
    ),
    (
        "旧版渲染路径",
        re.compile(
            r"(jsdom|node_modules|npm\s+install|node/jsdom|--allow-csr|\bCSR\b|"
            r"跳过\s*SSR\s*验证|支持\s*JS\s*的环境|静态\s*HTML|reference\s+URL\s+未渲染)",
            re.I,
        ),
        "本地 HTML 验证必须走 Python SSR/run_external_delivery,不能提示 Node/jsdom/CSR 兜底或安装依赖",
    ),
    (
        "CoT/思考过程",
        re.compile(r"(CoT|chain[- ]of[- ]thought|思考过程|推理过程|深度思考过程|内部推理)", re.I),
        "用户前台不能包含 CoT、内部推理或思考过程",
    ),
    (
        "HTML",
        re.compile(r"<!doctype\s+html|<html\b|<body\b|<script\b|</(?:html|body|script)>", re.I),
        "用户前台不能直接包含手写 HTML;只能给深度对话框回复和成品 HTML 入口",
    ),
    (
        "表格残留",
        re.compile(r"(?m)^\s*表格\s*$|^\s*\|[^|\n]+(?:\|[^|\n]+)+\|\s*$"),
        "默认对话框回复不要使用 Markdown 表格或输出“表格”占位词;窄屏应改用分组要点",
    ),
    (
        "自拟报告目录",
        re.compile(
            r"(?m)^\s*[一二三四五六七八九十]+[、.．]\s*"
            r"(政策|加息|美联储|欧央行|欧洲央行|市场|当前|历史|验证|监测|核心结论|背景|影响|分析)"
        ),
        "对话框回复必须沿用固定叙事链,不能改成自拟的一二三四五报告目录",
    ),
    (
        "监测表残留",
        re.compile(r"(监测指标|观察窗口|加息触发阈值|市场定价阈值|概率区间)"),
        "验证信号应写成确认/证伪分组叙事,不要压成监测表字段",
    ),
]

REQUIRED_MARKERS = [
    ("核心观点", "对话框回复必须使用和 HTML 一致的核心观点栏目"),
    ("核心判断", "核心观点栏目必须先直接回答用户问题"),
    ("为什么这么看", "对话框回复必须给出关键依据"),
    ("有哪些关键增量信息？", "对话框回复必须使用和 HTML 一致的关键增量信息栏目"),
    ("这些信息为什么重要？", "对话框回复必须使用和 HTML 一致的重要性栏目"),
    ("上述信息如何影响市场？", "对话框回复必须使用和 HTML 一致的市场影响栏目"),
    ("各方有哪些值得关注的观点？", "对话框回复必须使用和 HTML 一致的各方观点栏目"),
    ("哪些信号会验证核心观点？哪些信号代表观点证伪？", "对话框回复必须使用和 HTML 一致的验证/证伪栏目"),
    ("信息来源", "对话框回复必须使用和 HTML 一致的信息来源栏目"),
    ("边界", "对话框回复必须说明信息边界"),
]

def collect_issues(text: str) -> list[str]:
    issues: list[str] = []
    for label, pattern, message in FORBIDDEN_PATTERNS:
        if pattern.search(text):
            issues.append(f"{label}: {message}")
    for marker, message in REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"{marker}: {message}")
    if len(re.findall(r"(?m)^\s*-\s+", text)) < 10:
        issues.append("结构完整性: 对话框回复至少需要关键依据、增量事实、影响链、分歧和验证信号")
    if "信息来源" in text and not re.search(r"https?://", text):
        issues.append("引用来源: 对话框回复应在来源账本中保留可点击原文链接")
    if len(re.findall(r"https?://", text)) < 3:
        issues.append("引用来源: 对话框回复至少应保留 3 个可点击原文链接,否则来源账本不可核验")
    if not re.search(
        r"(file://|https?://|\.html\b|详细\s*HTML\s*简报|HTML\s*展开版|生成\s*HTML|需要.*HTML)",
        text,
        flags=re.I,
    ):
        issues.append("HTML 选项: 用户前台应包含是否生成 HTML 的提示或成品 HTML 链接")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify user-facing market brief delivery text")
    parser.add_argument("text", help="Path to a UTF-8 text file containing the outer reply")
    args = parser.parse_args()

    path = Path(args.text)
    text = path.read_text(encoding="utf-8-sig")
    issues = collect_issues(text)
    if issues:
        print("[delivery-text] FAIL")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print(f"[delivery-text] OK: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
