#!/usr/bin/env python3
"""Validate a doubao-market-hotspot briefing.json payload.

Usage:
    python3 scripts/validate_briefing.py briefing.json
    python3 scripts/validate_briefing.py briefing.json --strict --audit
    python3 scripts/validate_briefing.py briefing.json --json
"""
from __future__ import annotations

import argparse
import json

from briefing_validation import collect_issues, issue_report, load_json, normalize_payload, validate_payload


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate briefing.json")
    ap.add_argument("data", help="briefing.json 路径")
    ap.add_argument("--strict", action="store_true", help="启用结构、引用、来源和交付契约校验")
    ap.add_argument("--audit", action="store_true", help="检查内部审计字段 query_log/evidence_atoms 等")
    ap.add_argument("--fail-on-warning", action="store_true", help="兼容旧参数；advisory 不会作为阻断项")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出 issues")
    args = ap.parse_args()

    briefing = normalize_payload(load_json(args.data))
    if args.json:
        issues = collect_issues(briefing, strict=args.strict, audit=args.audit)
        report = issue_report(issues, fail_on_warning=args.fail_on_warning)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        raise SystemExit(0 if report["ok"] else 1)

    issues = validate_payload(
        briefing,
        strict=args.strict,
        audit=args.audit,
        fail_on_warning=args.fail_on_warning,
        label="validate",
    )
    advisory_count = sum(1 for issue in issues if issue["level"] == "advisory")
    quality_count = sum(1 for issue in issues if issue["level"] == "quality_error")
    print(f"[validate] OK: {args.data} (quality={quality_count}, advisories={advisory_count})")


if __name__ == "__main__":
    main()
