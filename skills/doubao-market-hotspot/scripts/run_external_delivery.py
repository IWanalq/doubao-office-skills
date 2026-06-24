#!/usr/bin/env python3
"""External workflow gate for model-produced market briefings.

This script is the single handoff point for hosts such as Doubao/Coze/Canvas:
the model output must be pure briefing.json, while this runner owns building,
HTML contract verification, deterministic deep reply rendering, and final reply
verification.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from briefing_validation import normalize_payload


def fail(message: str, code: int = 1) -> int:
    print(f"[external-delivery] FAIL: {message}", file=sys.stderr)
    return code


def load_pure_json(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "模型输出必须是纯 JSON 对象,不能包 Markdown 代码块、HTML、执行记录或解释性散文"
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError("模型输出必须是纯 JSON 对象,顶层不能是数组、字符串或其他类型")
    return payload


def run_step(cmd: list[str]) -> int:
    result = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.returncode


def candidate_path(final_path: Path, suffix: str) -> Path:
    return final_path.parent / f".{final_path.name}.{os.getpid()}.{suffix}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build and verify a doubao-market-hotspot delivery from pure briefing.json"
    )
    parser.add_argument("model_output", help="Path to the model's raw output; must be pure briefing.json")
    parser.add_argument("out_html", help="Final rendered HTML path")
    parser.add_argument("--reply-text", required=True, help="Where to write the generated user-facing reply/card")
    parser.add_argument(
        "--briefing-json",
        help="Where to save the canonical briefing.json after all gates pass; defaults to <out>.briefing.json",
    )
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    model_output = Path(args.model_output)
    out_html = Path(args.out_html)
    reply_text = Path(args.reply_text)
    saved_json = Path(args.briefing_json) if args.briefing_json else out_html.with_suffix(".briefing.json")

    try:
        payload = load_pure_json(model_output)
    except OSError as exc:
        return fail(f"无法读取模型输出: {exc}")
    except ValueError as exc:
        return fail(str(exc))
    payload = normalize_payload(payload)

    out_html.parent.mkdir(parents=True, exist_ok=True)
    reply_text.parent.mkdir(parents=True, exist_ok=True)
    saved_json.parent.mkdir(parents=True, exist_ok=True)
    tmp_json = candidate_path(out_html, "briefing.json")
    tmp_html = candidate_path(out_html, "html")
    tmp_reply = candidate_path(reply_text, "txt")

    try:
        tmp_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        build_code = run_step(
            [sys.executable, str(script_dir / "build_brief.py"), str(tmp_json), str(tmp_html), "--json-errors"]
        )
        if build_code != 0:
            return build_code

        render_reply_code = run_step(
            [sys.executable, str(script_dir / "render_dialog_brief.py"), str(tmp_json), str(out_html), str(tmp_reply)]
        )
        if render_reply_code != 0:
            return render_reply_code

        reply_code = run_step([sys.executable, str(script_dir / "verify_delivery_text.py"), str(tmp_reply)])
        if reply_code != 0:
            return reply_code

        os.replace(tmp_html, out_html)
        os.replace(tmp_json, saved_json)
        os.replace(tmp_reply, reply_text)
    finally:
        for path in (tmp_html, tmp_json, tmp_reply):
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                pass

    print("[external-delivery] OK")
    print(f"- briefing_json: {saved_json}")
    print(f"- html: {out_html}")
    print(f"- reply_text: {reply_text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
