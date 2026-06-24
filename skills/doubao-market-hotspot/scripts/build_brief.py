#!/usr/bin/env python3
"""One-command briefing build pipeline.

Usage:
    python3 scripts/build_brief.py briefing.json out.html

Pipeline:
    strict/audit validation -> Python SSR render -> final output contract.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from briefing_validation import collect_issues, issue_report, load_json, normalize_payload, validate_payload


def run_step(cmd: list[str]) -> None:
    result = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate, render, and verify a doubao-market-hotspot HTML file")
    parser.add_argument("data", help="briefing.json 路径")
    parser.add_argument("out", help="输出 HTML 路径")
    parser.add_argument("--allow-warnings", action="store_true", help="兼容旧参数；advisory 不会作为阻断项")
    parser.add_argument("--no-audit", action="store_true", help="调试用：跳过内部审计字段检查")
    parser.add_argument("--json-errors", action="store_true", help="校验失败时输出机器可读 JSON 错误报告")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    data_path = Path(args.data)
    out_path = Path(args.out)
    if out_path.exists():
        out_path.unlink()

    briefing = normalize_payload(load_json(data_path))
    if args.json_errors:
        issues = collect_issues(briefing, strict=True, audit=not args.no_audit)
        report = issue_report(issues)
        if not report["ok"]:
            print(json.dumps(report, ensure_ascii=False, indent=2))
            raise SystemExit(1)
    else:
        validate_payload(
            briefing,
            strict=True,
            audit=not args.no_audit,
            label="build",
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        run_step([sys.executable, str(script_dir / "render.py"), str(data_path), str(out_path)])
        run_step([sys.executable, str(script_dir / "verify_output_contract.py"), str(out_path)])
    except SystemExit:
        if out_path.exists():
            out_path.unlink()
        raise

    print(f"[build] OK -> {out_path}")


if __name__ == "__main__":
    main()
