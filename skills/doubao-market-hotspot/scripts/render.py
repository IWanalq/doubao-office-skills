#!/usr/bin/env python3
"""Render a briefing.json into self-contained, pre-rendered HTML.

Usage:
    python3 scripts/render.py <briefing.json> <out.html> [--open]

The model supplies data only. This renderer owns the deterministic view model,
loads external HTML partials, injects the public JSON payload, and writes the
initial DOM into #app using only the Python standard library.
"""
from __future__ import annotations

import argparse
import json
import re
import webbrowser
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

from briefing_validation import (
    disclaimer_for,
    load_json,
    normalize_images,
    normalize_payload,
    public_view,
    validate_payload,
)


APP_EMPTY = '<div class="wrap" id="app"></div>'
PLACEHOLDER_RE = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")
IMPORTANCE_CLASS = {"高": "high", "中": "mid", "低": "low"}
IMPORTANCE_RANK = {"高": 3, "中": 2, "低": 1}


def h(value: Any) -> str:
    return escape("" if value is None else str(value), quote=True)


def strip_end(value: Any) -> str:
    return re.sub(r"[。．.！!？?；;，,、：:]+$", "", str(value or "").strip())


def sentence(value: Any) -> str:
    text = strip_end(value)
    return f"{text}。" if text else ""


FIG_RE = re.compile(
    r"((?:\d{1,2}月\d{1,2}日(?:至\d{1,2}日)?|\d{1,2}月至\d{1,2}月|\d{4}年|"
    r"\d[\d.,]*\s*(?:%|‰|万亿\s*元|亿\s*元|万\s*元|万亿\s*美元|亿\s*美元|万\s*美元|"
    r"万亿|亿|万|美元|美分|港元|元|倍|个百分点|个基点|基点|bp|BP|点|只|家|条|个|日|年|nm|GB|TB|T|pct)))"
)


def emph(value: Any) -> str:
    return FIG_RE.sub(r'<span class="fig">\1</span>', h(value))


def metric_value(value: Any) -> str:
    raw = str(value or "").strip()
    marked = re.sub(r"【([^】]+)】", r'<span class="ev-key">\1</span>', h(raw))
    match = re.search(
        r"(^|[^0-9A-Za-z])((?:\d{1,2}月\d{1,2}日(?:至\d{1,2}日)?|\d{1,2}月至\d{1,2}月|"
        r"\d{4}年|(?:[+\-±]\s*)?\d[\d.,]*\s*(?:%|‰|万亿\s*元|亿\s*元|万\s*元|万亿\s*美元|"
        r"亿\s*美元|万\s*美元|万亿|亿|万|美元|美分|港元|元|倍|个百分点|个基点|基点|bp|BP|点|只|家|条|个|nm|GB|TB|pct)))",
        raw,
    )
    if not match:
        return f'<span class="ev-text">{marked}</span>'
    lead, num = match.group(1), match.group(2)
    idx = match.start() + len(lead)
    pre = raw[:idx]
    post = raw[idx + len(num) :]
    return (
        (f'<span class="ev-affix">{h(pre)}</span>' if pre else "")
        + f'<span class="ev-num">{h(num)}</span>'
        + (f'<span class="ev-affix">{h(post)}</span>' if post else "")
    )


def parse_ts(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2})[:：](\d{2}))?", raw)
    if not match:
        return None
    year, month, day, hour, minute = match.groups()
    return datetime(int(year), int(month), int(day), int(hour or 0), int(minute or 0))


def fmt_date(value: Any) -> str:
    raw = str(value or "").strip()
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2})[:：](\d{2}))?", raw)
    if not match:
        return raw
    _, month, day, hour, minute = match.groups()
    suffix = f"{hour}:{minute}" if hour else ""
    return f"{int(month)}月{int(day)}日{suffix}"


def rel_time(value: Any, now: datetime) -> str:
    then = parse_ts(value)
    if then is None:
        return fmt_date(value)
    delta = max(0, int((now - then).total_seconds()))
    minutes = delta // 60
    hours = minutes // 60
    days = hours // 24
    if minutes < 1:
        return "刚刚"
    if minutes < 60:
        return f"{minutes}分钟前"
    if hours < 24:
        return f"{hours}小时前"
    if days < 30:
        return f"{days}天前"
    return fmt_date(value)


def is_new(value: Any, now: datetime) -> bool:
    then = parse_ts(value)
    return then is not None and 0 <= (now - then).total_seconds() < 86400


class TemplateStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.partials = root / "partials"
        self.contract = json.loads((root / "ui_contract.json").read_text(encoding="utf-8"))
        self._cache: dict[str, str] = {}

    def layout(self) -> str:
        return self._read(self.root / "layout.html")

    def render(self, name: str, values: dict[str, Any] | None = None) -> str:
        values = values or {}
        template = self._read(self.partials / name)

        def repl(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in values:
                raise SystemExit(f"[render][error] partial {name} 缺少模板变量：{key}")
            return str(values[key])

        rendered = PLACEHOLDER_RE.sub(repl, template)
        dangling = PLACEHOLDER_RE.findall(rendered)
        if dangling:
            raise SystemExit(f"[render][error] partial {name} 仍有未替换变量：{', '.join(sorted(set(dangling)))}")
        return rendered

    def label(self, key: str) -> str:
        value = (self.contract.get("labels") or {}).get(key)
        if not isinstance(value, str) or not value:
            raise SystemExit(f"[render][error] ui_contract.json 缺少 labels.{key}")
        return value

    def session_label(self, key: Any) -> str:
        return str((self.contract.get("session_labels") or {}).get(str(key or ""), ""))

    def source_type_label(self, key: Any) -> str:
        return str((self.contract.get("source_type_labels") or {}).get(str(key or ""), "来源"))

    def chain_role(self, key: str) -> str:
        return str((self.contract.get("chain_roles") or {}).get(key, key))

    def source_visible_limit(self) -> int:
        raw = self.contract.get("source_visible_limit", 5)
        return int(raw if isinstance(raw, int) and raw > 0 else 5)

    def _read(self, path: Path) -> str:
        key = str(path)
        if key not in self._cache:
            if not path.exists():
                raise SystemExit(f"[render][error] 缺少模板文件：{path}")
            self._cache[key] = path.read_text(encoding="utf-8")
        return self._cache[key]


class BriefRenderer:
    def __init__(self, payload: dict[str, Any], templates: TemplateStore) -> None:
        self.t = templates
        self.b = payload
        self.refs = {item.get("id"): item for item in payload.get("references", []) if isinstance(item, dict)}
        self.ref_order: dict[Any, int] = {}
        seq = 0
        for item in payload.get("references", []):
            if self.public_ref(item):
                seq += 1
                self.ref_order[item.get("id")] = seq
        self.meta = payload.get("meta") or {}
        self.flags = payload.get("section_flags") or {}
        self.insight = payload.get("insight") or {}
        self.budget = payload.get("reading_budget") or {}
        self.section_summaries = payload.get("section_summaries") or {}
        self.highlight = payload.get("highlight") or {}
        self.visuals = payload.get("visuals") or {}
        self.screen1 = payload.get("screen1") or {}
        self.now = parse_ts(self.meta.get("generated_at")) or datetime.now()
        self.news = self.normalize_news()

    def public_ref(self, ref: Any) -> bool:
        return bool(
            isinstance(ref, dict)
            and ref.get("id") is not None
            and ref.get("level") != "D"
            and ref.get("type") != "unverified"
        )

    def ref_of(self, ref_id: Any) -> dict[str, Any]:
        ref = self.refs.get(ref_id)
        return ref if isinstance(ref, dict) else {}

    def ref_num(self, ref_id: Any) -> str:
        return str(self.ref_order.get(ref_id, ""))

    def url_ok(self, url: Any) -> bool:
        return bool(re.match(r"^https?://", str(url or ""), flags=re.I))

    def cite(self, ids: list[Any] | tuple[Any, ...] | None) -> str:
        out = []
        for ref_id in ids or []:
            if self.public_ref(self.ref_of(ref_id)):
                out.append(
                    f'<a class="cite" href="#ref-{h(ref_id)}" data-ref="{h(ref_id)}" '
                    f'onclick="return _ref(event,this.getAttribute(\'data-ref\'))">[{self.ref_num(ref_id)}]</a>'
                )
        return "".join(out)

    def source_text_value(self, ref: dict[str, Any]) -> str:
        try:
            count = int(ref.get("corroboration") or 0)
        except (TypeError, ValueError):
            count = 0
        return "多源印证" if count > 1 else "单一来源"

    def source_key(self, ref: dict[str, Any]) -> str:
        ref_type = str(ref.get("type") or "")
        level = str(ref.get("level") or "")
        if ref_type == "unverified" or level == "D":
            return "other"
        if ref_type == "official" or level == "A":
            return "official"
        if ref_type == "institution" or level == "C":
            return "institution"
        if ref_type == "media" or level == "B":
            return "media"
        return "other"

    def category_tag(self, category: Any) -> str:
        return self.t.render("category_tag.html", {"category": h(category)}) if category else ""

    def source_badge(self, ref: dict[str, Any]) -> str:
        key = self.source_key(ref)
        label = ref.get("source") or self.t.source_type_label(key)
        return self.t.render(
            "source_badge.html",
            {"source_key": h(key), "source_level": h(ref.get("level") or ""), "label": h(label)},
        )

    def source_link(self, ref: dict[str, Any]) -> str:
        if not self.url_ok(ref.get("url")):
            return ""
        return self.t.render("source_link.html", {"url": h(ref.get("url")), "label": self.t.label("source_link")})

    def source_meta(self, item: dict[str, Any]) -> str:
        raw, ref = item["raw"], item["ref"]
        time_value = raw.get("time") or ref.get("date") or ""
        time_html = (
            self.t.render(
                "relative_time.html",
                {"full_time": h(fmt_date(time_value)), "relative_time": h(rel_time(time_value, self.now))},
            )
            if time_value
            else ""
        )
        return self.t.render(
            "source_meta.html",
            {
                "category": self.category_tag(raw.get("category")),
                "source_badge": self.source_badge(ref),
                "time": time_html,
                "time_uncertain": self.t.render("time_uncertain.html") if raw.get("time_uncertain") else "",
                "source_text": self.t.render("source_text.html", {"text": h(self.source_text_value(ref))}),
                "source_link": self.source_link(ref),
            },
        )

    def normalize_news(self) -> list[dict[str, Any]]:
        rows = []
        for index, item in enumerate(self.b.get("news_items") or []):
            if not isinstance(item, dict):
                continue
            ref = self.ref_of(item.get("ref"))
            if not self.public_ref(ref):
                continue
            ts = parse_ts(item.get("time") or ref.get("date"))
            rows.append(
                {
                    "raw": item,
                    "ref": ref,
                    "index": index,
                    "source": self.source_key(ref),
                    "level": ref.get("level") or "",
                    "ts": ts or datetime.min,
                    "importance_rank": IMPORTANCE_RANK.get(item.get("importance"), 0),
                    "corroboration": int(ref.get("corroboration") or 0),
                    "q": "".join(
                        str(x or "")
                        for x in [
                            item.get("title"),
                            item.get("why"),
                            item.get("category"),
                            item.get("importance"),
                            ref.get("source"),
                            ref.get("title"),
                        ]
                    ).lower(),
                }
            )
        return rows

    def sorted_news(self) -> list[dict[str, Any]]:
        return sorted(
            self.news,
            key=lambda row: (
                -row["importance_rank"],
                -row["ts"].timestamp() if row["ts"] != datetime.min else 0,
                -row["corroboration"],
                row["index"],
            ),
        )

    def news_narrative(self, item: dict[str, Any]) -> str:
        raw, ref = item["raw"], item["ref"]
        detail = strip_end(raw.get("why") or ref.get("title") or raw.get("title") or "相关细节仍需要结合原文核对")
        title = strip_end(raw.get("title") or ref.get("title") or "")
        if detail and title and detail == title:
            detail = "这条信息补充了事件时间、涉及对象和市场反应，具体细节可在原文继续核对"
        return sentence(detail)

    def news_card(self, item: dict[str, Any], rank: int, default_count: int) -> str:
        raw = item["raw"]
        imp = IMPORTANCE_CLASS.get(raw.get("importance"), "low")
        classes = f"news-card imp-{imp}" + (" top" if rank <= 3 else "")
        if rank > default_count:
            classes += " news-extra is-hidden"
        time_value = raw.get("time") or item["ref"].get("date") or ""
        return self.t.render(
            "news_card.html",
            {
                "classes": h(classes),
                "query": h(item["q"]),
                "source_level": h(item["level"]),
                "source_key": h(item["source"]),
                "category": h(raw.get("category") or ""),
                "importance": h(raw.get("importance") or "低"),
                "rank": rank,
                "headline": emph(raw.get("title")),
                "citation": self.cite([raw.get("ref")]),
                "new_badge": self.t.render("new_badge.html") if is_new(time_value, self.now) else "",
                "summary": emph(self.news_narrative(item)),
                "source_meta": self.source_meta(item),
            },
        )

    def mast_html(self) -> str:
        generated = f"生成于{fmt_date(self.meta.get('generated_at'))}" if self.meta.get("generated_at") else ""
        meta_line = " · ".join(
            part
            for part in [self.meta.get("time_window"), self.t.session_label(self.meta.get("market_session")), generated]
            if part
        )
        return self.t.render(
            "mast.html",
            {
                "brand": h(self.t.label("brand")),
                "title": h(self.meta.get("title") or self.t.label("default_title")),
                "meta_line": h(meta_line),
                "source_scope": h(self.meta.get("source_scope") or self.t.label("default_source_scope")),
            },
        )

    def summary_cards_html(self) -> str:
        cards = list(self.visuals.get("summary_cards") or [])[:4]
        if not cards:
            cards = [
                {"label": "核心信号", "value": self.highlight.get("main_signal") or self.screen1.get("main_thread") or ""},
                {"label": "最大变化", "value": self.highlight.get("key_change") or self.screen1.get("biggest_change") or "", "tone": "risk"},
                {"label": "后续观察", "value": self.highlight.get("watch_point") or self.screen1.get("watch_next") or "", "tone": "positive"},
            ]
            cards = [card for card in cards if card.get("value")]
        items = "".join(
            self.t.render(
                "summary_card.html",
                {
                    "tone_class": "down" if card.get("tone") in {"risk", "negative", "warning"} else "up" if card.get("tone") == "positive" else "flat",
                    "label": h(card.get("label") or "看点"),
                    "value": metric_value(card.get("value") or ""),
                },
            )
            for card in cards
            if isinstance(card, dict)
        )
        return self.t.render("summary_cards.html", {"title": h(self.t.label("evidence")), "items": items}) if items else ""

    def hero_html(self) -> str:
        title = strip_end(
            self.insight.get("one_sentence")
            or self.screen1.get("main_thread")
            or self.meta.get("title")
            or ""
        )
        brief = self.budget.get("thirty_second")
        return self.t.render(
            "hero.html",
            {
                "section_title": h(self.t.label("hero")),
                "headline": emph(title),
                "brief": self.t.render("hero_brief.html", {"text": emph(brief)}) if brief else "",
                "summary_cards": self.summary_cards_html(),
            },
        )

    def timeline_html(self) -> str:
        timeline = self.visuals.get("timeline") or [
            {"date": item.get("date"), "label": item.get("event"), "kind": item.get("kind")}
            for item in self.b.get("timeline") or []
            if isinstance(item, dict)
        ]
        if self.flags.get("timeline") is False or not timeline:
            return ""
        items = "".join(
            self.t.render(
                "timeline_item.html",
                {"date": h(fmt_date(item.get("date"))), "label": h(item.get("label") or item.get("event"))},
            )
            for item in timeline
            if isinstance(item, dict)
        )
        return self.t.render("timeline.html", {"title": h(self.t.label("timeline")), "items": items})

    def update_diff_html(self) -> str:
        rows = self.b.get("update_diff") or []
        if self.flags.get("update_diff") is False or not rows:
            return ""
        items = []
        for row in rows:
            if isinstance(row, dict):
                items.append(self.t.render("list_item.html", {"text": h(row.get("point") or ""), "citations": self.cite(row.get("refs") or [])}))
            else:
                items.append(self.t.render("list_item.html", {"text": h(row), "citations": ""}))
        return self.t.render("update_diff.html", {"title": h(self.t.label("update_diff")), "items": "".join(items)})

    def news_section_html(self) -> str:
        rows = self.sorted_news()
        default_count = int(self.budget.get("default_news_count") if self.budget.get("default_news_count") is not None else 3)
        cards = "".join(self.news_card(item, index + 1, default_count) for index, item in enumerate(rows))
        if not cards:
            cards = self.t.render("empty_message.html", {"class_name": "why", "text": h(self.t.label("no_news"))})
        more = ""
        if len(rows) > default_count:
            more = self.t.render(
                "more_button.html",
                {
                    "extra_class": "",
                    "id": "moreNews",
                    "handler": "_toggleNews()",
                    "label": h(self.t.label("news_expand").format(count=len(rows) - default_count)),
                },
            )
        return self.t.render(
            "news_section.html",
            {
                "title": h(self.t.label("news")),
                "cards": cards,
                "more": more,
                "timeline": self.timeline_html(),
                "update_diff": self.update_diff_html(),
            },
        )

    def importance_html(self) -> str:
        cards = [
            {"label": self.t.label("importance_changed"), "text": self.insight.get("what_changed") or self.highlight.get("key_change") or self.screen1.get("biggest_change") or "上一阶段的变化还不明确。"},
            {"label": self.t.label("importance_delta"), "text": self.insight.get("consensus_vs_delta") or self.screen1.get("controversy") or "市场预期差还需要更多公开信息确认。"},
            {"label": self.t.label("importance_now"), "text": self.insight.get("why_now") or self.budget.get("thirty_second") or "现在需要看新增事实是否继续出现。"},
        ]
        items = "".join(
            self.t.render("importance_card.html", {"label": h(card["label"]), "text": emph(card["text"])})
            for card in cards
        )
        return self.t.render("importance.html", {"title": h(self.t.label("importance")), "items": items})

    def impact_facts(self, step_count: int) -> list[dict[str, Any]]:
        facts = []
        for item in self.visuals.get("impact_facts") or []:
            if isinstance(item, str):
                facts.append({"step": 0, "fact": item, "refs": []})
            elif isinstance(item, dict) and item.get("fact"):
                facts.append({"step": int(item.get("step") or 0), "fact": item.get("fact"), "refs": item.get("refs") or []})
        if not facts:
            for index, item in enumerate(self.news[: min(step_count or 3, 3)]):
                fact = item["raw"].get("why") or item["raw"].get("title")
                if fact:
                    facts.append({"step": index + 1, "fact": fact, "refs": [item["raw"].get("ref")]})
        for index, fact in enumerate(facts):
            if not fact.get("step"):
                fact["step"] = min((index % max(step_count or 1, 1)) + 1, step_count or 1)
        return facts[:8]

    def chain_role_key(self, index: int, count: int) -> str:
        if count <= 1:
            return "single"
        if index == 0:
            return "cause"
        if index == count - 1:
            return "foresight"
        if index == count - 2:
            return "result"
        return "relay"

    def chain_role_class(self, role_key: str) -> str:
        return {
            "foresight": "is-foresight",
            "cause": "is-cause",
            "result": "is-result",
            "relay": "is-relay",
            "single": "is-cause",
        }.get(role_key, "is-relay")

    def impact_html(self) -> str:
        chain = list(self.visuals.get("impact_chain") or [])
        if not chain:
            chain = [
                self.highlight.get("main_signal") or self.screen1.get("main_thread") or "事件",
                self.highlight.get("key_change") or self.screen1.get("biggest_change") or "影响",
                self.highlight.get("watch_point") or self.screen1.get("watch_next") or "观察",
            ]
        chain = chain[:6]
        facts = self.impact_facts(len(chain))
        steps = []
        for index, text in enumerate(chain):
            matched = [item for item in facts if int(item.get("step") or 0) == index + 1][:1]
            fact_html = "".join(
                self.t.render(
                    "impact_fact.html",
                    {"fact": emph(item.get("fact")), "citations": self.cite(item.get("refs") or [])},
                )
                for item in matched
            )
            role_key = self.chain_role_key(index, len(chain))
            steps.append(
                self.t.render(
                    "impact_step.html",
                    {
                        "role_class": h(self.chain_role_class(role_key)),
                        "index": index + 1,
                        "role": h(self.t.chain_role(role_key)),
                        "text": emph(text),
                        "fact": fact_html,
                    },
                )
            )
        return self.t.render(
            "impact.html",
            {
                "title": h(self.t.label("impact")),
                "summary": self.section_summary_html("impact"),
                "steps": "".join(steps),
            },
        )

    def section_summary_text(self, key: str) -> str:
        summaries = self.section_summaries if isinstance(self.section_summaries, dict) else {}
        text = summaries.get(key)
        if text:
            return str(text)
        fallback = {
            "impact": self.insight.get("why_now") or self.budget.get("thirty_second") or "这部分把新增事实放进影响链里看，重点是分清事件起点、传导路径和后续验证条件。",
            "viewpoints": self.insight.get("consensus_vs_delta") or "这部分把不同来源的观点放在一起比较，重点看共识、分歧和反向证据分别来自哪里。",
            "verification": self.insight.get("positive_case") or self.insight.get("negative_case") or "这部分把确认和证伪条件并列呈现，方便后续用公开信息检查核心观点是否仍然成立。",
        }
        return str(fallback.get(key) or "")

    def section_summary_html(self, key: str) -> str:
        text = self.section_summary_text(key)
        return self.t.render("section_summary.html", {"text": emph(text)}) if text else ""

    def viewpoint_role(self, role: Any) -> str:
        text = str(role or "其他").strip()
        if re.search(r"客观|官方|公告|监管|交易所|统计|央行|数据", text):
            return "客观事实"
        if re.search(r"市场|定价|资金|股价|交易|成交|盘面|反应", text):
            return "市场反应"
        if re.search(r"机构|券商|分析师|研报|视角|观点", text):
            return "机构观点"
        if re.search(r"反向|证伪|风险|谨慎|下修", text):
            return "反向证据"
        if re.search(r"媒体|报道", text):
            return "媒体报道"
        return text or "其他"

    def unique_refs(self, ids: list[Any] | None) -> list[Any]:
        seen: set[Any] = set()
        out = []
        for ref_id in ids or []:
            if ref_id in seen or not self.public_ref(self.ref_of(ref_id)):
                continue
            seen.add(ref_id)
            out.append(ref_id)
        return out

    def viewpoint_links(self, ids: list[Any]) -> str:
        refs = [ref_id for ref_id in self.unique_refs(ids) if self.url_ok(self.ref_of(ref_id).get("url"))]
        if not refs:
            return ""
        links = []
        for index, ref_id in enumerate(refs):
            label = f"{self.t.label('source_link')} {index + 1}" if len(refs) > 1 else self.t.label("source_link")
            links.append(self.t.render("viewpoint_link.html", {"url": h(self.ref_of(ref_id).get("url")), "label": h(label)}))
        return self.t.render("viewpoint_links.html", {"links": "".join(links)})

    def viewpoints_html(self) -> str:
        items = [item for item in self.b.get("interpretation") or [] if item and (isinstance(item, str) or item.get("point"))]
        if not items:
            items = [
                {"role": "客观事实", "point": self.highlight.get("main_signal") or self.screen1.get("main_thread") or "客观事实还不充分。", "refs": []},
                {"role": "反向证据", "point": self.insight.get("negative_case") or "反向证据还需要继续观察。", "refs": []},
            ]
        groups: list[dict[str, Any]] = []
        by_role: dict[str, dict[str, Any]] = {}
        for item in items[:8]:
            point = item if isinstance(item, str) else item.get("point") or ""
            role = self.viewpoint_role("其他" if isinstance(item, str) else item.get("role") or "其他")
            refs = [] if isinstance(item, str) else self.unique_refs(item.get("refs") or [])
            if role not in by_role:
                by_role[role] = {"role": role, "items": []}
                groups.append(by_role[role])
            by_role[role]["items"].append({"point": point, "refs": refs})
        group_html = []
        for group in groups:
            points = "".join(
                self.t.render(
                    "viewpoint_point.html",
                    {
                        "point": emph(item["point"]),
                        "citations": self.cite(item["refs"]),
                        "links": self.viewpoint_links(item["refs"]),
                    },
                )
                for item in group["items"]
            )
            group_html.append(self.t.render("viewpoint_group.html", {"role": h(group["role"]), "points": points}))
        return self.t.render(
            "viewpoints.html",
            {
                "title": h(self.t.label("viewpoints")),
                "summary": self.section_summary_html("viewpoints"),
                "groups": "".join(group_html),
            },
        )

    def verification_items(self, group: str) -> list[dict[str, Any]]:
        verification = self.b.get("verification") or {}
        rows = verification.get(group) if isinstance(verification, dict) else []
        if isinstance(rows, list) and rows:
            return [
                {
                    "signal": item.get("signal") or "",
                    "watch": item.get("watch") or "",
                    "meaning": item.get("meaning") or "",
                    "refs": item.get("refs") if isinstance(item.get("refs"), list) else [],
                }
                for item in rows
                if isinstance(item, dict) and (item.get("signal") or item.get("watch") or item.get("meaning"))
            ]
        fallback = self.insight.get("confirm_signals" if group == "confirm" else "invalidate_signals") or []
        items = []
        for row in fallback:
            text = row if isinstance(row, str) else row.get("signal") or row.get("point") or ""
            if text:
                items.append(
                    {
                        "signal": text,
                        "watch": text,
                        "meaning": "出现这个信号，会增强核心观点。" if group == "confirm" else "出现这个信号，会削弱核心观点。",
                        "refs": [],
                    }
                )
        return items

    def watch_text(self, item: dict[str, Any]) -> str:
        raw = strip_end(item.get("watch") or item.get("signal") or "等待更多公开信息")
        raw = re.sub(r"^(看|观察|跟踪|关注)", "", raw)
        return sentence(f"后续重点是{raw}")

    def verification_narrative(self, item: dict[str, Any], group: str) -> str:
        fallback = "如果该信号兑现，核心观点会得到验证" if group == "confirm" else "如果该信号出现，核心观点会被削弱或证伪"
        return self.watch_text(item) + sentence(item.get("meaning") or fallback)

    def verification_list(self, group: str) -> str:
        rows = self.verification_items(group)
        if not rows:
            return self.t.render(
                "verification_empty.html",
                {"title": h(self.t.label("no_signal")), "text": h(self.t.label("no_signal_body"))},
            )
        items = "".join(
            self.t.render(
                "verification_item.html",
                {
                    "signal": emph(item["signal"]),
                    "citations": self.cite(item["refs"]),
                    "text": emph(self.verification_narrative(item, group)),
                },
            )
            for item in rows[:4]
        )
        return self.t.render("verification_list.html", {"items": items})

    def verification_html(self) -> str:
        return self.t.render(
            "verification.html",
            {
                "title": h(self.t.label("verification")),
                "summary": self.section_summary_html("verification"),
                "confirm_title": h(self.t.label("confirm")),
                "invalidate_title": h(self.t.label("invalidate")),
                "confirm_list": self.verification_list("confirm"),
                "invalidate_list": self.verification_list("invalidate"),
            },
        )

    def sources_html(self) -> str:
        rows = [ref for ref in self.b.get("references") or [] if self.public_ref(ref)]
        if not rows:
            return self.t.render("sources_empty.html", {"title": h(self.t.label("sources")), "text": h(self.t.label("no_sources"))})
        visible_count = min(len(rows), self.t.source_visible_limit())
        extra = max(0, len(rows) - visible_count)
        items = []
        for index, ref in enumerate(rows):
            classes = "source-extra is-hidden" if index >= visible_count else ""
            label = ref.get("source") or self.t.source_type_label(ref.get("type"))
            items.append(
                self.t.render(
                    "source_item.html",
                    {
                        "id": h(ref.get("id")),
                        "classes": classes,
                        "num": h(self.ref_num(ref.get("id"))),
                        "source": h(label),
                        "date": h(fmt_date(ref.get("date") or "")),
                        "title": h(ref.get("title") or "未命名来源"),
                        "link": self.source_link(ref),
                    },
                )
            )
        more = ""
        if extra:
            more = self.t.render(
                "more_button.html",
                {
                    "extra_class": "source-more",
                    "id": "moreSources",
                    "handler": "_toggleSources()",
                    "label": h(self.t.label("source_expand").format(count=extra)),
                },
            )
        return self.t.render("sources.html", {"title": h(self.t.label("sources")), "items": "".join(items), "more": more})

    def risk_disclaimer_html(self) -> str:
        data = self.b.get("risk_disclaimer") or {}
        items = [item for item in data.get("items") or [] if item] if isinstance(data.get("items"), list) else []
        if isinstance(data.get("body"), str):
            body = data["body"]
        elif items:
            body = (data.get("title") or "风险提示与免责声明") + "：\n" + "\n".join(
                re.sub(r"^\s*[-*•]\s+", "", str(item)) for item in items
            )
        else:
            body = ""
        body = "\n".join(re.sub(r"^\s*[-*•]\s+", "", line) for line in str(body or "").split("\n"))
        return self.t.render("risk_disclaimer.html", {"body": h(body)}) if body else ""

    def render(self) -> str:
        return "".join(
            [
                self.mast_html(),
                self.hero_html(),
                self.news_section_html(),
                self.importance_html(),
                self.impact_html(),
                self.viewpoints_html(),
                self.verification_html(),
                self.sources_html(),
                self.risk_disclaimer_html(),
            ]
        )


def render_app(payload: dict[str, Any], templates: TemplateStore) -> str:
    return BriefRenderer(payload, templates).render()


def inject_app_html(template_html: str, app_html: str, payload: str) -> str:
    html = template_html.replace("__BRIEFING_DATA__", payload)
    if APP_EMPTY not in html:
        raise SystemExit("[render][error] layout.html 缺少空的 #app 容器，无法注入 Python SSR DOM。")
    html = html.replace(APP_EMPTY, f'<div class="wrap" id="app">{app_html}</div>')
    html = html.replace("<body>", '<body data-prerendered="1">', 1)
    return html


def main() -> None:
    parser = argparse.ArgumentParser(description="Render briefing.json -> pre-rendered self-contained HTML")
    parser.add_argument("data", help="briefing.json 路径")
    parser.add_argument("out", help="输出 HTML 路径")
    parser.add_argument(
        "--open",
        action="store_true",
        dest="open_browser",
        help="渲染后用默认浏览器打开（浏览器选项）",
    )
    args = parser.parse_args()

    data_path, out_path = Path(args.data), Path(args.out)
    templates = TemplateStore(Path(__file__).resolve().parent.parent / "templates")

    briefing = normalize_payload(load_json(data_path))
    validate_payload(briefing, strict=True, audit=False, label="render")

    public_payload = normalize_images(public_view(briefing))
    public_payload["risk_disclaimer"] = disclaimer_for(public_payload.get("meta", {}).get("disclaimer_id"))
    payload = json.dumps(public_payload, ensure_ascii=False)
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")

    html = inject_app_html(templates.layout(), render_app(public_payload, templates), payload)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print("[render] OK -> %s (%d bytes, python-ssr)" % (out_path, len(html)))

    uri = out_path.resolve().as_uri()
    print("[render] 浏览器打开: %s" % uri)
    if args.open_browser:
        try:
            webbrowser.open(uri)
            print("[render] 已尝试用默认浏览器打开")
        except Exception as exc:  # noqa: BLE001
            print("[render][warn] 无法自动打开浏览器: %s（请手动打开上面的链接）" % exc)


if __name__ == "__main__":
    main()
