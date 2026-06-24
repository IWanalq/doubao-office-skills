#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from html import unescape
from pathlib import Path


REQUIRED_ORDER = [
    ("top", "核心观点", "hero/core view"),
    ("news", "有哪些关键增量信息", "incremental facts"),
    ("importance", "这些信息为什么重要", "importance"),
    ("impact", "上述信息如何影响市场", "impact chain"),
    ("viewpoints", "各方有哪些值得关注的观点", "viewpoints"),
    ("verification", "哪些信号会验证核心观点", "verification"),
    ("sources", "信息来源", "sources"),
]


def strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html)


def compact_text(html: str) -> str:
    return re.sub(r"\s+", "", unescape(strip_tags(html)))


def script_json(text: str) -> dict | None:
    match = re.search(
        r'<script\s+id="data"\s+type="application/json"\s*>(.*?)</script>',
        text,
        flags=re.S,
    )
    if not match:
        return None
    payload = unescape(match.group(1))
    return json.loads(payload)


class RenderedAppParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_app = False
        self.depth = 0
        self.section_ids: list[str] = []
        self.section_stack: list[str] = []
        self.text_parts: list[str] = []
        self.source_links = 0
        self.source_ledger_depth = 0
        self.source_ledger_links = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key: value or "" for key, value in attrs}
        if self.in_app:
            self.depth += 1
            classes = set(attr.get("class", "").split())
            if tag == "section":
                section_id = attr.get("id", "")
                self.section_ids.append(section_id)
                self.section_stack.append(section_id)
            if self.source_ledger_depth:
                self.source_ledger_depth += 1
            if (
                tag == "ol"
                and "source-ledger" in classes
                and self.section_stack
                and self.section_stack[-1] == "sources"
            ):
                self.source_ledger_depth = 1
            if (
                tag == "a"
                and "source-link" in classes
                and re.match(r"^https?://", attr.get("href", ""), flags=re.I)
            ):
                self.source_links += 1
                if self.source_ledger_depth:
                    self.source_ledger_links += 1
            return

        if tag == "div" and attr.get("id") == "app":
            self.in_app = True
            self.depth = 1

    def handle_endtag(self, tag: str) -> None:
        if not self.in_app:
            return
        if self.source_ledger_depth:
            self.source_ledger_depth -= 1
        if tag == "section" and self.section_stack:
            self.section_stack.pop()
        self.depth -= 1
        if self.depth <= 0:
            self.in_app = False
            self.depth = 0
            self.section_stack = []
            self.source_ledger_depth = 0

    def handle_data(self, data: str) -> None:
        if self.in_app:
            self.text_parts.append(data)

    @property
    def app_text(self) -> str:
        return "".join(self.text_parts)


def parse_rendered_app(text: str) -> RenderedAppParser:
    parser = RenderedAppParser()
    parser.feed(text)
    return parser


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify a rendered doubao-market-hotspot HTML file."
    )
    parser.add_argument("html", help="Path to the final rendered HTML")
    args = parser.parse_args()

    path = Path(args.html)
    text = path.read_text(encoding="utf-8-sig")
    issues: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            issues.append(message)

    require(
        'data-renderer="doubao-market-hotspot"' in text,
        "missing renderer fingerprint: use templates/layout.html through scripts/render.py",
    )
    require(
        'data-template="layout-v1"' in text,
        "missing layout template fingerprint: final HTML was not rendered from templates/layout.html",
    )
    require(
        '<script id="data" type="application/json">' in text,
        "missing script#data: final HTML was likely hand-written or copied instead of rendered from briefing.json",
    )
    require(
        'data-prerendered="1"' in text,
        'missing body data-prerendered="1": final HTML was not SSR-prerendered',
    )
    require(
        '<div class="wrap" id="app"></div>' not in text,
        "empty #app: final HTML was not SSR-prerendered",
    )
    for marker in ["__hasSsr", "function summaryCards", "function impactChain", "function renderNews", "function sourcesHtml", "function riskDisclaimerHtml", "app.innerHTML"]:
        require(marker not in text, f"removed client-side page renderer marker found: {marker}")
    require("__BRIEFING_DATA__" not in text, "template placeholder was not replaced")
    require("risk-disclaimer" in text, "missing rendered risk disclaimer section")
    require('"risk_disclaimer"' in text, "missing injected risk_disclaimer JSON")
    require("打开原文" not in text, "removed source label found; use linked text '查看原文'")
    require("覆盖范围：" not in text, "removed coverage label found in final UI")
    require("主要来源" not in text, "removed primary-source row found in final UI")
    require("复制摘要" not in text, "removed toolbar/copy control found in final UI")
    require("window.print()" not in text, "removed print control found in final UI")
    require("news-media" not in text, "key incremental facts should not render or reserve front image slots")
    require("has-image" not in text, "news cards should use the stable text-first layout")
    require("section-summary" in text, "late section insight blocks are missing")
    require("section-summary-label" in text and "关键洞见" in text, "late sections must render standalone key insight blocks")
    require(
        not re.search(r"(?m)^\s*[-*•]\s+以上内容", text),
        "risk disclaimer still uses bullet markers before '以上内容'",
    )

    app_dom = parse_rendered_app(text)
    app_plain = compact_text(app_dom.app_text)
    require(bool(app_plain), "empty #app: rendered DOM has no text content")
    require(
        "risk-disclaimer" in app_dom.section_ids,
        "missing rendered risk disclaimer section",
    )
    source_links = app_dom.source_links
    require(
        source_links > 0,
        "source ledger has no clickable '查看原文' HTTP links",
    )
    require(
        app_dom.source_ledger_links > 0,
        "source ledger has no clickable '查看原文' HTTP links",
    )

    section_cursor = -1
    for section_id, label, section in REQUIRED_ORDER:
        try:
            idx = app_dom.section_ids.index(section_id, section_cursor + 1)
        except ValueError:
            issues.append(f"missing or out-of-order rendered section id: {section_id} ({section})")
        else:
            section_cursor = idx

    text_cursor = -1
    for _, label, section in REQUIRED_ORDER:
        idx = app_plain.find(label.replace(" ", ""), text_cursor + 1)
        if idx < 0:
            issues.append(f"missing or out-of-order rendered section label: {label} ({section})")
        else:
            text_cursor = idx

    data = None
    try:
        data = script_json(text)
    except Exception as exc:  # pragma: no cover - defensive CLI feedback
        issues.append(f"script#data JSON is not parseable: {exc}")

    if data is not None:
        disclaimer_body = str((data.get("risk_disclaimer") or {}).get("body") or "")
        require(
            "以上内容为AI自动生成或AI辅助生成" in disclaimer_body,
            "risk_disclaimer body does not contain the required full notice",
        )
        require(
            not re.search(r"(?m)^\s*[-*•]\s+以上内容", disclaimer_body),
            "risk_disclaimer JSON still contains bullet markers",
        )
        require(
            all("image" not in item for item in data.get("news_items") or [] if isinstance(item, dict)),
            "news_items[].image should be stripped from public output data",
        )
        summaries = data.get("section_summaries") if isinstance(data.get("section_summaries"), dict) else {}
        for key in ("impact", "viewpoints", "verification"):
            require(bool(summaries.get(key)), f"public JSON missing section_summaries.{key}")
        references = data.get("references") or []
        refs_with_url = [
            item
            for item in references
            if isinstance(item, dict)
            and re.match(r"^https?://", str(item.get("url") or ""))
        ]
        if len(refs_with_url) > 5:
            require("source-extra" in text and "_toggleSources" in text, "more than 5 public sources should render folded source rows with expand/collapse")
            require("默认展示" not in text and "已折叠" not in text, "source ledger should fold extra rows without showing source-count summary copy")
        require(
            source_links >= min(1, len(refs_with_url)),
            "reference URLs exist in JSON but are not rendered as source links",
        )

    if issues:
        print("[output-contract] FAIL")
        for item in issues:
            print(f"- {item}")
        return 1

    print(f"[output-contract] OK: {path} (source_links={source_links})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
