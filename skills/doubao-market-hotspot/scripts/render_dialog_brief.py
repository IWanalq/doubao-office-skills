#!/usr/bin/env python3
"""Render the user-facing deep dialog brief from briefing.json."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from briefing_validation import normalize_payload


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("briefing.json 顶层必须是对象")
    return normalize_payload(payload)


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def html_entry(html_path: Path) -> str:
    path = str(html_path if html_path.is_absolute() else html_path.resolve())
    return f"file://{path}"


def public_ref_order(payload: dict[str, Any]) -> dict[Any, int]:
    order: dict[Any, int] = {}
    seq = 0
    for item in payload.get("references") or []:
        if not isinstance(item, dict):
            continue
        if item.get("id") is None or item.get("level") == "D" or item.get("type") == "unverified":
            continue
        seq += 1
        order[item.get("id")] = seq
    return order


def public_ref_map(payload: dict[str, Any]) -> dict[Any, dict[str, Any]]:
    refs: dict[Any, dict[str, Any]] = {}
    for item in payload.get("references") or []:
        if not isinstance(item, dict):
            continue
        if item.get("id") is None or item.get("level") == "D" or item.get("type") == "unverified":
            continue
        refs[item.get("id")] = item
    return refs


def cite(refs: Any, order: dict[Any, int]) -> str:
    if not isinstance(refs, list):
        return ""
    marks = [f"[{order[rid]}]" for rid in refs if rid in order]
    return "".join(marks)


def cited_ref_ids(key_points: list[Any], order: dict[Any, int]) -> list[Any]:
    seen: set[Any] = set()
    ids: list[Any] = []
    for item in key_points:
        if not isinstance(item, dict) or not isinstance(item.get("refs"), list):
            continue
        for rid in item["refs"]:
            if rid in order and rid not in seen:
                seen.add(rid)
                ids.append(rid)
    return ids


def source_line(ref_id: Any, order: dict[Any, int], refs: dict[Any, dict[str, Any]]) -> str:
    ref = refs.get(ref_id) or {}
    title = clean(ref.get("title") or "来源")
    source = clean(ref.get("source"))
    date = clean(ref.get("date"))
    url = clean(ref.get("url"))
    meta = "，".join(part for part in [source, date] if part)
    suffix = f"（{meta}）" if meta else ""
    if url:
        return f"- [{order[ref_id]}] {title}{suffix}：{url}"
    return f"- [{order[ref_id]}] {title}{suffix}"


def require_text(dialog: dict[str, Any], key: str) -> str:
    value = clean(dialog.get(key))
    if not value:
        raise ValueError(f"dialog_brief.{key} 缺失,无法生成前台深度回复")
    return value


def add_ref_ids(target: list[Any], refs: Any, order: dict[Any, int]) -> None:
    if not isinstance(refs, list):
        return
    for ref_id in refs:
        if ref_id in order and ref_id not in target:
            target.append(ref_id)


def ref_ids_from_payload(payload: dict[str, Any], key_points: list[Any], order: dict[Any, int]) -> list[Any]:
    ids = cited_ref_ids(key_points, order)
    for item in payload.get("news_items") or []:
        if isinstance(item, dict):
            add_ref_ids(ids, [item.get("ref")], order)
    visuals = payload.get("visuals") if isinstance(payload.get("visuals"), dict) else {}
    for item in visuals.get("impact_facts") or []:
        if isinstance(item, dict):
            add_ref_ids(ids, item.get("refs"), order)
    for item in payload.get("interpretation") or []:
        if isinstance(item, dict):
            add_ref_ids(ids, item.get("refs"), order)
    verification = payload.get("verification") if isinstance(payload.get("verification"), dict) else {}
    for group in ("confirm", "invalidate"):
        for item in verification.get(group) or []:
            if isinstance(item, dict):
                add_ref_ids(ids, item.get("refs"), order)
    return ids


def append_if_any(lines: list[str], heading: str, body: list[str]) -> None:
    clean_body = [line for line in body if clean(line)]
    if clean_body:
        lines.extend(["", heading])
        lines.extend(clean_body)


def section_summary(payload: dict[str, Any], key: str) -> str:
    summaries = payload.get("section_summaries") if isinstance(payload.get("section_summaries"), dict) else {}
    return clean(summaries.get(key))


def reading_summary(payload: dict[str, Any]) -> str:
    budget = payload.get("reading_budget") if isinstance(payload.get("reading_budget"), dict) else {}
    return clean(budget.get("thirty_second"))


def append_unique_paragraph(lines: list[str], text: str, existing: str) -> None:
    text = clean(text)
    existing = clean(existing)
    if not text:
        return
    if existing and (text in existing or existing in text):
        return
    lines.extend(["", text])


def render_key_points(key_points: list[Any], ref_order: dict[Any, int]) -> list[str]:
    lines: list[str] = []
    for item in key_points[:6]:
        if not isinstance(item, dict):
            continue
        label = clean(item.get("label"))
        text = clean(item.get("text"))
        if not label or not text:
            raise ValueError("dialog_brief.key_points[].label/text 缺失")
        lines.append(f"- {label}：{text}{cite(item.get('refs'), ref_order)}")
    return lines


def render_news(payload: dict[str, Any], ref_order: dict[Any, int]) -> list[str]:
    lines: list[str] = []
    budget = payload.get("reading_budget") if isinstance(payload.get("reading_budget"), dict) else {}
    count = budget.get("default_news_count")
    count = count if isinstance(count, int) else 3
    count = max(3, min(count, 4))
    for item in (payload.get("news_items") or [])[:count]:
        if not isinstance(item, dict):
            continue
        title = clean(item.get("title"))
        why = clean(item.get("why"))
        if title and why:
            lines.append(f"- **{title}**：{why}{cite([item.get('ref')], ref_order)}")
    return lines


def render_insight(payload: dict[str, Any]) -> list[str]:
    insight = payload.get("insight") if isinstance(payload.get("insight"), dict) else {}
    specs = [
        ("现在重要", "why_now"),
        ("真正变化", "what_changed"),
        ("共识与分歧", "consensus_vs_delta"),
        ("支持主线的条件", "positive_case"),
        ("削弱主线的条件", "negative_case"),
    ]
    lines = []
    for label, key in specs:
        text = clean(insight.get(key))
        if text:
            lines.append(f"- {label}：{text}")
    return lines


def chain_label(index: int, total: int) -> str:
    if index == 1:
        return "起点"
    if index == total:
        return "验证"
    return "传导"


def render_impact(payload: dict[str, Any], ref_order: dict[Any, int]) -> list[str]:
    visuals = payload.get("visuals") if isinstance(payload.get("visuals"), dict) else {}
    chain = visuals.get("impact_chain") if isinstance(visuals.get("impact_chain"), list) else []
    facts_by_step: dict[int, list[tuple[str, str]]] = {}
    loose_facts: list[str] = []
    for item in visuals.get("impact_facts") or []:
        if isinstance(item, str):
            text = clean(item)
            if text:
                loose_facts.append(f"- 补充：{text}")
            continue
        if not isinstance(item, dict):
            continue
        fact = clean(item.get("fact"))
        if not fact:
            continue
        fact = f"{fact}{cite(item.get('refs'), ref_order)}"
        step = item.get("step")
        if isinstance(step, int):
            facts_by_step.setdefault(step, []).append((fact, cite(item.get("refs"), ref_order)))
        else:
            loose_facts.append(f"- 补充：{fact}")

    lines: list[str] = []
    for index, step_name in enumerate(chain[:6], start=1):
        step_text = clean(step_name)
        if not step_text:
            continue
        facts = [fact for fact, _ in facts_by_step.get(index, [])]
        if facts:
            for fact in facts:
                lines.append(f"- {chain_label(index, len(chain))}：{step_text}。{fact}")
        else:
            lines.append(f"- {chain_label(index, len(chain))}：{step_text}。")
    if not lines:
        lines.extend(loose_facts[:4])
    else:
        lines.extend(loose_facts[:2])
    return lines


def render_interpretation(payload: dict[str, Any], ref_order: dict[Any, int]) -> list[str]:
    lines: list[str] = []
    for item in (payload.get("interpretation") or [])[:4]:
        if not isinstance(item, dict):
            continue
        role = clean(item.get("role") or "观点")
        point = clean(item.get("point"))
        if point:
            lines.append(f"- **{role}**：{point}{cite(item.get('refs'), ref_order)}")
    return lines


def render_verification(payload: dict[str, Any], ref_order: dict[Any, int], watch_signals: list[Any]) -> list[str]:
    verification = payload.get("verification") if isinstance(payload.get("verification"), dict) else {}
    lines: list[str] = []
    confirm = verification.get("confirm") if isinstance(verification.get("confirm"), list) else []
    invalidate = verification.get("invalidate") if isinstance(verification.get("invalidate"), list) else []

    if confirm:
        lines.append("确认主线：")
        for item in confirm[:3]:
            if not isinstance(item, dict):
                continue
            signal = clean(item.get("signal"))
            watch = clean(item.get("watch"))
            meaning = clean(item.get("meaning"))
            if signal and (watch or meaning):
                tail = "；".join(part for part in [watch, meaning] if part)
                lines.append(f"- {signal}：{tail}{cite(item.get('refs'), ref_order)}")
    if invalidate:
        lines.append("削弱或推翻：")
        for item in invalidate[:3]:
            if not isinstance(item, dict):
                continue
            signal = clean(item.get("signal"))
            watch = clean(item.get("watch"))
            meaning = clean(item.get("meaning"))
            if signal and (watch or meaning):
                tail = "；".join(part for part in [watch, meaning] if part)
                lines.append(f"- {signal}：{tail}{cite(item.get('refs'), ref_order)}")
    if not lines:
        for signal in watch_signals[:4]:
            text = clean(signal)
            if text:
                lines.append(f"- {text}")
    return lines


def render_reply(payload: dict[str, Any], html_path: Path | None = None) -> str:
    dialog = payload.get("dialog_brief")
    if not isinstance(dialog, dict):
        raise ValueError("dialog_brief 缺失,无法生成前台深度回复")

    verdict = require_text(dialog, "verdict")
    summary = require_text(dialog, "executive_summary")
    risk_boundary = require_text(dialog, "risk_boundary")
    key_points = dialog.get("key_points")
    if not isinstance(key_points, list) or len(key_points) < 4:
        raise ValueError("dialog_brief.key_points 至少需要 4 条,覆盖事实变化、市场含义、分歧点和后续验证")
    watch_signals = dialog.get("watch_signals")
    if not isinstance(watch_signals, list) or len(watch_signals) < 2:
        raise ValueError("dialog_brief.watch_signals 至少需要 2 条")

    ref_order = public_ref_order(payload)
    ref_map = public_ref_map(payload)
    lines = [
        "核心观点",
        "",
        f"核心判断：{verdict}",
        "",
        summary,
    ]
    append_unique_paragraph(lines, reading_summary(payload), summary)
    lines.extend(["", "为什么这么看："])
    lines.extend(render_key_points(key_points, ref_order))

    append_if_any(lines, "有哪些关键增量信息？", render_news(payload, ref_order))
    append_if_any(lines, "这些信息为什么重要？", render_insight(payload))
    append_if_any(
        lines,
        "上述信息如何影响市场？",
        [section_summary(payload, "impact"), *render_impact(payload, ref_order)],
    )
    append_if_any(
        lines,
        "各方有哪些值得关注的观点？",
        [section_summary(payload, "viewpoints"), *render_interpretation(payload, ref_order)],
    )
    append_if_any(
        lines,
        "哪些信号会验证核心观点？哪些信号代表观点证伪？",
        [section_summary(payload, "verification"), *render_verification(payload, ref_order, watch_signals)],
    )

    cited_ids = ref_ids_from_payload(payload, key_points, ref_order)
    if cited_ids:
        lines.extend(["", "信息来源"])
        lines.extend(source_line(ref_id, ref_order, ref_map) for ref_id in cited_ids[:8])

    lines.extend(["", f"边界：{risk_boundary}", ""])
    if html_path is None:
        lines.append("需要为你生成一份精美的热点报告么？")
    else:
        lines.append(f"详细 HTML 简报: {html_entry(html_path)}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Render deep dialog brief reply text from briefing.json. "
            "Use DATA OUT for the default no-HTML reply, or DATA HTML OUT to include an HTML link."
        )
    )
    parser.add_argument("paths", nargs="+", help="DATA OUT, or DATA HTML OUT")
    args = parser.parse_args()

    if len(args.paths) == 2:
        data_path = Path(args.paths[0])
        html_path = None
        out_path = Path(args.paths[1])
    elif len(args.paths) == 3:
        data_path = Path(args.paths[0])
        html_path = Path(args.paths[1])
        out_path = Path(args.paths[2])
    else:
        parser.error("expected DATA OUT or DATA HTML OUT")

    payload = load_json(data_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_reply(payload, html_path), encoding="utf-8")
    print(f"[dialog-brief] OK -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
