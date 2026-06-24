#!/usr/bin/env python3
"""Check that the HTML templates expose the core research-brief UI contracts."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


REQUIRED_PARTIALS = [
    "mast.html",
    "hero.html",
    "news_section.html",
    "importance.html",
    "impact.html",
    "section_summary.html",
    "viewpoints.html",
    "verification.html",
    "sources.html",
    "risk_disclaimer.html",
]

REQUIRED_MARKERS = [
    ('data-renderer="doubao-market-hotspot"', "layout carries the fixed renderer fingerprint"),
    ('data-template="layout-v1"', "layout carries the template-version fingerprint"),
    ('<div class="wrap" id="app"></div>', "layout exposes an empty app container for Python SSR injection"),
    ('<script id="data" type="application/json">__BRIEFING_DATA__</script>', "layout exposes the public JSON payload slot"),
    ("window._toggleNews=function()", "layout keeps news expand/collapse as progressive enhancement"),
    ("window._toggleSources=function()", "layout keeps source expand/collapse as progressive enhancement"),
    ("window._ref=function", "layout keeps citation popovers as progressive enhancement"),
    ("to-top", "a back-to-top control is present"),
    ("--brand:", "layout defines a primary brand color variable"),
    ("--accent:", "layout defines an accent color variable"),
    ("--page:", "layout defines a page background color variable"),
    ('id="top"', "hero section partial exists"),
    ('id="news"', "key incremental facts section partial exists"),
    ('id="importance"', "importance section partial exists"),
    ('id="impact"', "impact section partial exists"),
    ('id="viewpoints"', "viewpoints section partial exists"),
    ('id="verification"', "verification section partial exists"),
    ('id="sources"', "source ledger section partial exists"),
    ("importance-grid", "importance uses scan-friendly reason cards"),
    ("viewpoint-list", "viewpoints render by source role"),
    ("viewpoint-stack", "viewpoints group multiple items under one source role"),
    ("viewpoint-links", "each viewpoint item exposes direct original-source links"),
    ("verify-grid", "verification/falsification cards use a responsive grid"),
    ("verify-text", "verification cards use full narrative sentences instead of watch/meaning labels"),
    ("source-ledger", "sources render as detailed ledger rows"),
    ("source-extra", "additional sources are folded behind an explicit expand control"),
    ('<a class="source-link" href="{{url}}" target="_blank" rel="noopener">{{label}}</a>', "source ledger original-source actions are real anchor links"),
    ("查看原文", "original-source actions use the required visible label"),
    ("risk-disclaimer", "full risk disclaimer renders as a stable section after sources"),
    ("risk-copy", "risk disclaimer renders as one readable text block"),
    ("module-note", "sections can carry plain-language connective notes"),
    ("section-summary", "late sections carry a concise key insight"),
    ("section-summary-label", "late section insights carry a visible label"),
    ("category-tag", "news cards expose category tags from news_items[].category"),
    ("new-badge", "fresh (<24h) items get a 新 badge"),
    ("rank", "news cards are numbered"),
    ("data-source-level", "news cards expose source level for source linking"),
    ("flow-step", "impact chain renders as adaptive causal-step cards"),
    ("flow-role", "impact chain steps carry role labels"),
    ("flow-fact", "impact facts are integrated into the corresponding causal step"),
    ("fig", "key figures get emphasized typographic treatment"),
    ("ev-key", "summary cards can highlight explicitly marked key words without coloring the whole sentence"),
    (".verify-grid{grid-template-columns:1fr}", "verification grid collapses safely on mobile"),
]

FORBIDDEN_MARKERS = [
    ("__hasSsr", "layout must not contain the removed client-side page renderer"),
    ("function summaryCards", "layout must not contain the removed client-side page renderer"),
    ("function impactChain", "layout must not contain the removed client-side page renderer"),
    ("function renderNews", "layout must not contain the removed client-side page renderer"),
    ("function sourcesHtml", "layout must not contain the removed client-side page renderer"),
    ("function riskDisclaimerHtml", "layout must not contain the removed client-side page renderer"),
    ("app.innerHTML", "layout must not rewrite the whole page on the client"),
    ("sourcePreview", "hero must not render a standalone source preview line"),
    ("source-line", "hero must not contain the removed source footnote line"),
    ("coverage-note", "risk disclaimer must not repeat the bottom coverage/source-scope line"),
    ("覆盖范围：", "risk disclaimer must not repeat the bottom coverage/source-scope line"),
    ("主要来源", "standalone main-source label must not render"),
    ("打" + "开原文", "original-source action label must be 查看原文"),
    ("return '- '+x", "risk disclaimer fallback must not add bullet hyphens"),
    ("newsImage", "key incremental facts must not render front images"),
    ("news-media", "key incremental facts must not reserve image slots"),
    ("has-image", "news cards must stay text-first without image layout"),
]


def check_disclaimer_registry(skill_root: Path) -> list[str]:
    registry_path = skill_root / "references" / "disclaimers.json"
    if not registry_path.exists():
        return [f"- {registry_path}: fixed disclaimer registry is missing"]
    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return [f"- {registry_path}: cannot parse disclaimer registry ({exc})"]

    notice = data.get("standard_v2_full_risk_notice")
    if not isinstance(notice, dict) or not isinstance(notice.get("body"), str):
        return ["- standard_v2_full_risk_notice: fixed disclaimer body is missing"]
    if re.search(r"(?m)^\s*[-*•]\s+以上内容", notice["body"]):
        return ["- standard_v2_full_risk_notice: body must be canonical text without bullet markers"]
    return []


def load_contract_text(template_root: Path) -> str:
    parts = [(template_root / "layout.html").read_text(encoding="utf-8")]
    parts.append((template_root / "ui_contract.json").read_text(encoding="utf-8"))
    for name in REQUIRED_PARTIALS:
        path = template_root / "partials" / name
        if not path.exists():
            raise SystemExit(f"[render-contract] missing partial: {path}")
    for path in sorted((template_root / "partials").glob("*.html")):
        parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify doubao-market-hotspot template contract")
    parser.add_argument(
        "template_root",
        nargs="?",
        default=str(Path(__file__).resolve().parent.parent / "templates"),
        help="Path to the templates directory",
    )
    args = parser.parse_args()

    template_root = Path(args.template_root)
    skill_root = Path(__file__).resolve().parent.parent
    root_html = sorted(path.name for path in template_root.glob("*.html"))
    text = load_contract_text(template_root)
    compact = "".join(text.split())
    missing = [f"- {marker}: {why}" for marker, why in REQUIRED_MARKERS if marker not in text and marker not in compact]
    forbidden = [f"- {marker}: {why}" for marker, why in FORBIDDEN_MARKERS if marker in text]
    disclaimer_issues = check_disclaimer_registry(skill_root)
    if missing:
        print("[render-contract] missing required markers:")
        print("\n".join(missing))
        raise SystemExit(1)
    if forbidden:
        print("[render-contract] forbidden markers found:")
        print("\n".join(forbidden))
        raise SystemExit(1)
    if root_html != ["layout.html"]:
        print("[render-contract] root template entrypoints must be exactly: layout.html")
        print("- found: " + ", ".join(root_html))
        raise SystemExit(1)
    if disclaimer_issues:
        print("[render-contract] disclaimer registry issues:")
        print("\n".join(disclaimer_issues))
        raise SystemExit(1)

    print(f"[render-contract] OK: {template_root}")


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(1)
