#!/usr/bin/env python3
"""Create a fill-in briefing.json scaffold for doubao-market-hotspot."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


ROLE_KEYS = ("fact_change", "market_meaning", "disagreement", "verification")
ANALYSIS_MODES = ("market_event", "policy_macro", "dated_catalyst", "earnings_event", "theme_watch")


def default_question_type(mode: str) -> str:
    if mode == "policy_macro":
        return "policy"
    if mode == "dated_catalyst":
        return "event"
    return "market"


def scaffold(args: argparse.Namespace) -> dict:
    generated_at = args.generated_at or datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    return {
        "schema_version": "0.6",
        "meta": {
            "title": args.title,
            "question_type": args.question_type or default_question_type(args.mode),
            "analysis_mode": args.mode,
            "time_window": args.time_window,
            "market_session": args.market_session,
            "generated_at": generated_at,
            "source_scope": args.source_scope,
            "disclaimer_id": "standard_v2_full_risk_notice",
            "locale": "zh-CN",
        },
        "section_flags": {
            "screen1": True,
            "visuals": True,
            "news": True,
            "interpretation": True,
            "timeline": False,
            "update_diff": False,
            "source_check": True,
        },
        "dialog_brief": {
            "verdict": "",
            "executive_summary": "",
            "key_points": {role: {"text": "", "refs": []} for role in ROLE_KEYS},
            "watch_signals": [],
        },
        "insight": {
            "one_sentence": "",
            "why_now": "",
            "what_changed": "",
            "consensus_vs_delta": "",
            "positive_case": "",
            "negative_case": "",
            "confirm_signals": [],
            "invalidate_signals": [],
            "confidence": "中",
        },
        "reading_budget": {
            "thirty_second": "",
            "one_minute": ["核心观点", "关键增量信息", "为什么重要", "验证/证伪信号"],
            "three_minute": ["市场影响链", "各方观点", "信息来源"],
            "default_news_count": 3,
            "max_frontstage_chars": 1200,
        },
        "section_summaries": {
            "impact": "",
            "viewpoints": "",
            "verification": "",
        },
        "highlight": {
            "lead_ref": "",
            "main_signal": "",
            "key_change": "",
            "watch_point": "",
            "tone": "neutral",
        },
        "visuals": {
            "summary_cards": [],
            "impact_chain": [],
            "impact_facts": [],
        },
        "screen1": {
            "main_thread": "",
            "biggest_change": "",
            "controversy": "",
            "controversy_level": "中",
            "watch_next": "",
        },
        "news_items": [],
        "interpretation": [],
        "verification": {
            "confirm": [],
            "invalidate": [],
        },
        "source_check": {
            "official": [],
            "media": [],
            "institution": [],
            "internal_excluded": [],
        },
        "references": [],
        "query_log": [],
        "evidence_atoms": [],
        "coverage_gaps": [],
        "conflicts": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a canonical briefing.json scaffold")
    parser.add_argument("--out", required=True, help="Where to write the scaffold JSON")
    parser.add_argument("--mode", choices=ANALYSIS_MODES, default="market_event", help="Analysis lens")
    parser.add_argument("--title", default="市场热点简报", help="Briefing title")
    parser.add_argument("--question-type", choices=("market", "policy", "event", "update"))
    parser.add_argument("--time-window", default="", help="Time window, e.g. 2026-06-14")
    parser.add_argument("--market-session", choices=("pre", "intraday", "post", "non_trading"), default="post")
    parser.add_argument("--generated-at", help="ISO8601 timestamp; defaults to current local timestamp")
    parser.add_argument("--source-scope", default="公开新闻、官方数据和权威财经来源")
    args = parser.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(scaffold(args), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[new-briefing] OK -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
