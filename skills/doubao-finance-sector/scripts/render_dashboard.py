#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
板块热度仪表盘渲染器（第二阶段渲染；渲染前可 --check-only 校验）

用法:
    python3 scripts/render_dashboard.py <payload.json> <输出目录>

产出:
    <板块>板块热度仪表盘.html   —— 自包含、可交互、无需联网（唯一输出文件）

渲染前内置「校验门」validate_payload()：对 payload 做硬性结构校验（评分自洽、10 股与分组
已由第一阶段 facts 水合且未被改动、每个展示数值的来源 lane 符合分级约束、催化为一手/权威 general_search
且带原文、板块口径自洽等）；任何一处不通过都会报错并拒绝渲染（fail-loud），而非静默出图。
完整校验清单见 references/payload_fields.md。可加 --check-only 只跑校验、不输出 HTML；可加 --warn-only
将硬错误降级为打印并继续渲染，仅供本地调试。

评分体系：综合 / 信息 / 行情热度均为 1-5 分（不使用历史分位）。
1 冷清 · 2 温和 · 3 活跃 · 4 高热 · 5 过热。具体评分标准见 references/scoring_and_divergence.md。
视觉：深蓝 / 蓝 / 红涨绿跌 / 暖色预警；半圆仪表盘（指针与分数不重叠）；
四维度卡 + 双轨背离四象限 + 消息催化时间线 + 代表股热力图。
"""
import sys
import os
import json
import math
import hashlib
import html as _html
import re
from datetime import date
from pathlib import Path

# 复算门：与独立预检脚本 check_market_facts.py 共用的数字复算/量纲/事实表校验
sys.path.insert(0, str(Path(__file__).resolve().parent))
import market_checks as _mc  # noqa: E402

ASSETS = Path(__file__).resolve().parent / "assets"

# 标准化风险提示与免责声明（首行为标题，正文三段；white-space:pre-wrap 保留换行）
RISK_DISCLAIMER = (
    "风险提示与免责声明：\n"
    "以上内容为AI自动生成或AI辅助生成，仅用于信息整理、投研辅助、教育交流或一般性分析参考，"
    "不构成对任何金融产品、交易策略或投资行为的推荐、邀约、承诺或保证，也不构成投资、法律、税务、会计等专业意见。\n"
    "以上内容可能基于公开信息、历史数据或用户提供材料进行总结、归纳、推演与情景分析，"
    "但相关内容可能存在时效性不足、信息缺漏、事实误差、模型偏差或生成性错误，"
    "历史数据、历史业绩、回测结果及情景假设均不代表未来表现。\n"
    "用户应基于自身风险承受能力、投资目标、财务状况及适用法律法规独立作出判断，"
    "必要时咨询持牌专业机构或顾问。任何因依赖以上内容而作出的决策及其后果，由用户自行承担。"
)

BANDS = ["冷清", "温和", "活跃", "高热", "过热"]
# 1-5 各档配色（冷→热）
BAND_COLORS = ["#5B83C4", "#46A89A", "#E8B53C", "#E8842E", "#D8392C"]

# ---------------------------------------------------------------- 基础工具

def esc(s):
    return _html.escape("" if s is None else str(s), quote=True)


def rich(s):
    """支持 **加粗** / <em> / <br>，其余转义。"""
    if s is None:
        return ""
    s = str(s)
    s = s.replace("<br>", "\u0001BR\u0001").replace("<br/>", "\u0001BR\u0001")
    s = re.sub(r"<em>(.*?)</em>", "\u0001EMO\u0001\\1\u0001EMC\u0001", s, flags=re.S)
    s = re.sub(r"\*\*(.+?)\*\*", "\u0001BO\u0001\\1\u0001BC\u0001", s, flags=re.S)
    s = esc(s)
    s = (s.replace("\u0001BR\u0001", "<br>")
          .replace("\u0001EMO\u0001", "<em>").replace("\u0001EMC\u0001", "</em>")
          .replace("\u0001BO\u0001", "<b>").replace("\u0001BC\u0001", "</b>"))
    return s


def num(v):
    try:
        f = float(v)
        return f"{f:+.0f}" if abs(f - round(f)) < 1e-9 else f"{f:+.1f}"
    except Exception:
        return esc(v)


def clamp_score(score):
    """把分数夹到 1-5。"""
    try:
        return max(1.0, min(5.0, float(score)))
    except Exception:
        return 1.0


def band_index(score):
    """1-5 分 → 档位下标 0-4（四舍五入）。"""
    return max(0, min(4, int(round(clamp_score(score))) - 1))


def fmt_score(score):
    s = clamp_score(score)
    return str(int(round(s))) if abs(s - round(s)) < 1e-9 else f"{s:.1f}"


# ---------------------------------------------------------------- 仪表盘 SVG（1-5）

_GCX, _GCY, _GR = 110, 116, 88          # 圆心与半径
_GBOUNDS = [180, 144, 108, 72, 36, 0]    # 五档边界角度（度）


def _arc_pt(deg, r=_GR):
    rad = math.radians(deg)
    return (_GCX + r * math.cos(rad), _GCY - r * math.sin(rad))


def gauge_svg(score, band_word):
    s = clamp_score(score)
    active = band_index(s) + 1                       # 1-5
    needle_deg = 180 - 36 * s                         # 指向 s/5 位置：s=1→144°(1/5)、3→72°(3/5)、5→0°(5/5)
    nx, ny = _arc_pt(needle_deg, _GR - 24)
    # 底弧
    lx, ly = _arc_pt(180); rx, ry = _arc_pt(0)
    base = (f'<path d="M {lx:.1f} {ly:.1f} A {_GR} {_GR} 0 0 1 {rx:.1f} {ry:.1f}" '
            f'fill="none" stroke="#E9EEF5" stroke-width="14" stroke-linecap="round"/>')
    arcs = []
    for i in range(5):
        a, b = _GBOUNDS[i], _GBOUNDS[i + 1]
        x1, y1 = _arc_pt(a); x2, y2 = _arc_pt(b)
        op = "1" if (i + 1) <= active else "0.2"
        arcs.append(f'<path d="M {x1:.1f} {y1:.1f} A {_GR} {_GR} 0 0 1 {x2:.1f} {y2:.1f}" '
                    f'fill="none" stroke="{BAND_COLORS[i]}" stroke-width="14" '
                    f'stroke-linecap="round" opacity="{op}"/>')
    return (
        f'<svg class="gauge" viewBox="0 0 220 132" role="img" aria-label="综合热度 {fmt_score(s)} 分（{esc(band_word)}）">'
        f'{base}{"".join(arcs)}'
        f'<g id="needle" data-angle="{(90 - needle_deg):.1f}">'
        f'<line x1="{_GCX}" y1="{_GCY}" x2="{nx:.1f}" y2="{ny:.1f}" '
        f'stroke="#1E3A5F" stroke-width="4" stroke-linecap="round"/></g>'
        f'<circle cx="{_GCX}" cy="{_GCY}" r="8" fill="#1E3A5F"/>'
        f'<circle cx="{_GCX}" cy="{_GCY}" r="3" fill="#fff"/>'
        f'</svg>'
    )


# ---------------------------------------------------------------- 顶栏 + 头图

def build_topbar(p):
    sector = esc(p.get("sector", "板块"))
    market = p.get("market")
    ts = p.get("timestamp", "")
    rm = p.get("read_minutes", 3)
    chips = [f'<span class="chip chip-navy">板块：{sector}</span>']
    cal = p.get("index_caliber")
    if cal:
        chips.append(f'<span class="chip">行情口径：{esc(cal)}</span>')
    if ts:
        chips.append(f'<span class="chip">{esc(ts)}</span>')
    chips.append(f'<span class="chip">约 {esc(rm)} 分钟读完</span>')
    if market:
        chips.insert(1, f'<span class="chip">{esc(market)}</span>')
    mark = ('<div class="brand-mark"><svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">'
            '<rect x="1.5" y="8.5" width="3.4" height="6" rx="1" fill="#fff" opacity=".5"/>'
            '<rect x="6.3" y="5" width="3.4" height="9.5" rx="1" fill="#fff" opacity=".75"/>'
            '<rect x="11.1" y="1.5" width="3.4" height="13" rx="1" fill="#fff"/></svg></div>')
    return (
        '<header class="topbar"><div class="wrap topbar-in">'
        f'<div class="brand">{mark}<div>'
        '<div class="brand-t">板块热度分析</div><div class="brand-s">热度监测报告</div></div></div>'
        f'<div class="meta">{"".join(chips)}</div>'
        '</div></header>'
    )


def selected_stock_names(p, limit=10):
    """本次选取的代表股名称（最多 limit 只）。优先 selected_stocks，否则取 stocks 名称。"""
    names = p.get("selected_stocks")
    if isinstance(names, list) and names:
        out = [str(n).strip() for n in names if str(n).strip()]
    else:
        out = [s.get("name", "").strip() for s in (p.get("stocks") or []) if s.get("name")]
    return out[:limit]


def build_hero(p):
    score = p.get("composite_score", 1)
    bidx = band_index(score)
    band = BANDS[bidx]
    pill = p.get("gauge_pill") or band
    color = BAND_COLORS[bidx]
    scale = "".join(
        f'<span class="{"on" if i == bidx else ""}">{b}</span>' for i, b in enumerate(BANDS)
    )
    chips = []
    for c in (p.get("key_chips") or [])[:_MAX_KEY_CHIPS]:
        cls = {"up": " up-c", "down": " down-c"}.get(c.get("color", ""), "")
        unit = c.get("unit")
        unit_html = f'<span class="kunit">{esc(unit)}</span>' if unit else ""
        chips.append(
            f'<div class="kchip"><div class="k num{cls}"><span>{esc(c.get("value",""))}</span>{unit_html}</div>'
            f'<div class="kl">{esc(c.get("label",""))}</div></div>'
        )
    chips_html = f'<div class="kchips">{"".join(chips)}</div>' if chips else ""

    # 核心结论处显式标注【目标概念板块】（取自 index_caliber）
    cal = p.get("index_caliber")
    target_html = (f'<div class="hero-target">目标概念板块　<b>{esc(cal)}</b></div>'
                   if cal else "")

    # 数据口径说明已废弃：板块核心数据必须来自目标板块自身。
    note_html = ""

    # 核心结论后一行小字：本次选取的 10 只代表股名称
    names = selected_stock_names(p, 10)
    stocks_note_html = (
        f'<div class="hero-stocks-note">本次选取的 {len(names)} 只代表股：'
        f'{esc("、".join(names))}</div>' if names else ""
    )

    return (
        '<section class="hero wrap"><div class="card hero-card reveal" id="heroCard"><div class="hero-grid">'
        '<div class="gauge-col">'
        '<div class="gauge-eyebrow">综合热度</div>'
        f'{gauge_svg(score, band)}'
        f'<div class="gauge-score" style="color:{color}">{fmt_score(score)}'
        f'<span class="gs-max">/ 5</span></div>'
        f'<div><span class="gauge-pill" style="background:{color}1f;color:{color}">{esc(pill)}</span></div>'
        f'<div class="scale">{scale}</div></div>'
        '<div class="hero-text">'
        '<div class="kicker">核心结论</div>'
        f'{target_html}'
        f'<h1>{rich(p.get("headline",""))}</h1>'
        f'<p>{rich(p.get("summary",""))}</p>'
        f'{note_html}'
        f'{stocks_note_html}'
        f'{chips_html}'
        '</div></div></div></section>'
    )


# ---------------------------------------------------------------- 双轨背离卡（1-5 + 四象限）

def build_divergence(p):
    dv = p.get("divergence") or {}
    info = p.get("info_score")
    mkt = p.get("market_score")
    if info is None and mkt is None and not dv:
        return ""
    info_v = clamp_score(info) if info is not None else 1.0
    mkt_v = clamp_score(mkt) if mkt is not None else 1.0
    info_hot, mkt_hot = info_v >= 3, mkt_v >= 3      # 阈值：3 分（活跃）及以上为“热”
    if info_hot and mkt_hot:
        default_quad, cls = "双热 · 强趋势共振", "q-hot"
    elif mkt_hot and not info_hot:
        default_quad, cls = "行情热 · 信息冷 · 纯资金驱动", "q-warn"
    elif info_hot and not mkt_hot:
        default_quad, cls = "信息热 · 行情冷 · 题材未启动 / 利好兑现回落", "q-warn"
    else:
        default_quad, cls = "双冷 · 低关注", "q-cool"
    quad = dv.get("type") or default_quad

    def cell(on, title, sub):
        return (f'<div class="qq{" on" if on else ""}"><b>{esc(title)}</b>'
                f'<span>{esc(sub)}</span></div>')
    matrix = (
        '<div class="dq-matrix"><div class="dq-mgrid">'
        + cell(info_hot and not mkt_hot, "信息热 · 行情冷", "题材未启动 / 利好兑现回落")
        + cell(info_hot and mkt_hot, "双热", "强趋势共振")
        + cell((not info_hot) and (not mkt_hot), "双冷", "低关注")
        + cell((not info_hot) and mkt_hot, "行情热 · 信息冷", "纯资金驱动")
        + '</div><div class="dq-axis-x">纵轴 = 信息热度（上热 / 下冷）　·　横轴 = 行情热度（左冷 / 右热）</div></div>'
    )
    verdict, meaning = dv.get("verdict", ""), dv.get("meaning", "")
    vparts = []
    if verdict:
        vparts.append(f"<b>{rich(verdict)}</b>")
    if meaning:
        vparts.append(rich(meaning))
    verdict_html = (f'<div class="dq-verdict">{"。".join([v for v in vparts if v])}</div>'
                    if vparts else "")
    return (
        '<section class="wrap" style="margin-top:16px"><div class="card dq-card reveal">'
        f'<div class="dq-head"><h2>双轨热度 · 信息 vs 行情</h2><span class="dq-quad {cls}">{esc(quad)}</span></div>'
        '<div class="dq-body">'
        '<div class="dq-tracks">'
        '<div class="dq-track"><div class="lab"><b>信息热度</b>'
        f'<span class="sc num" style="color:var(--blue)">{fmt_score(info_v)}<span class="sc-max">/5</span></span></div>'
        f'<div class="dq-bar"><i class="info" style="width:{info_v/5*100:.0f}%"></i></div>'
        '<div class="pctl">消息 / 催化 / 公开讨论的密度与强度</div></div>'
        '<div class="dq-track"><div class="lab"><b>行情热度</b>'
        f'<span class="sc num" style="color:var(--up)">{fmt_score(mkt_v)}<span class="sc-max">/5</span></span></div>'
        f'<div class="dq-bar"><i class="mkt" style="width:{mkt_v/5*100:.0f}%"></i></div>'
        '<div class="pctl">价格 / 成交 / 代表股 / 估值的强度</div></div>'
        '</div>'
        f'{matrix}'
        '</div>'
        f'{verdict_html}'
        '</div></section>'
    )


# ---------------------------------------------------------------- 直接回答

def build_answer(p):
    a = p.get("answer") or {}
    if not a:
        return ""
    rows = []
    if a.get("restate"):
        rows.append(f'<b>问题：</b>{rich(a["restate"])}')
    if a.get("conclusion"):
        rows.append(f'<b>结论：</b>{rich(a["conclusion"])}')
    if a.get("next"):
        rows.append(f'<b>下一步：</b>{rich(a["next"])}')
    body = "<br>".join(rows)
    return (
        '<section id="s0" class="sec wrap reveal"><div class="card qstrip">'
        '<div class="qstrip-head"><h2>直接回答</h2></div>'
        f'<div class="answer-copy">{body}</div>'
        '</div></section>'
    )


# ---------------------------------------------------------------- 导航

_NAV = [("s1", "现在有多热"), ("s2", "为什么涨/跌"), ("s3", "谁在动、谁没动"),
        ("s4", "接下来盯什么"), ("s5", "风险提示"), ("s6", "信息来源")]


def build_nav():
    pills = "".join(
        f'<a class="pill{" active" if i == 0 else ""}" href="#{sid}">{esc(t)}</a>'
        for i, (sid, t) in enumerate(_NAV)
    )
    return f'<nav class="nav"><div class="wrap nav-in">{pills}</div></nav>'


def _sec_head(no, title, en):
    return (f'<div class="sec-h"><span class="sec-no">{no}</span><div>'
            f'<h2>{esc(title)}</h2><div class="sec-en">{esc(en)}</div></div></div>')


def _module_note(text):
    return f'<div class="module-note"><b>本段结论：</b>{rich(text)}</div>' if text else ""


# ---------------------------------------------------------------- 模块1 · 现在有多热（四维度）

_STATE_META = {"确认": "st-ok", "弱确认": "st-weak", "背离": "st-div"}
_TRACK_META = {"行情": "trk-mkt", "信息": "trk-info"}


def build_dimensions(p):
    ss = (p.get("section_summaries") or {}).get("heat", "")
    dims = p.get("dimensions") or []
    cards = []
    for d in dims:
        track = d.get("track", "行情")
        state = d.get("state", "")
        trk_cls = _TRACK_META.get(track, "trk-mkt")
        st_cls = _STATE_META.get(state, "st-weak")
        st_html = f'<span class="st {st_cls}">{esc(state)}</span>' if state else ""
        cards.append(
            f'<article class="card dimc">'
            f'<div class="dim-top"><div class="dim-name">{esc(d.get("name",""))}'
            f'<span class="trk {trk_cls}">{esc(track)}</span></div>{st_html}</div>'
            f'<div class="dim-val">{rich(d.get("value",""))}</div>'
            f'<div class="dim-read">{rich(d.get("read",""))}</div>'
            f'</article>'
        )
    grid = (f'<div class="dimg">{"".join(cards)}</div>'
            if cards else '<div class="note">维度字段未通过固定 4 项校验。</div>')
    return (
        '<section id="s1" class="sec wrap reveal">'
        + _sec_head(1, "现在有多热", "价格、量能、代表股、估值")
        + _module_note(ss)
        + grid
        + '</section>'
    )


# ---------------------------------------------------------------- 模块2 · 为什么涨/跌（时间线）

# 利好=红，利空=绿，中性=蓝
_TONE = {
    "利好": ("tag-good", "dot-red"),
    "利空": ("tag-bad", "dot-green"),
    "中性": ("tag-mid", "dot-blue"),
}


def _fmt_cn_date(d):
    """把日期规整为 “M月D日”：支持 6/12、06.06、2026-06-12；已是中文/描述性的（如 6月初）原样返回。"""
    s = str(d or "").strip()
    if not s:
        return ""
    m = re.match(r"^\d{4}-(\d{1,2})-(\d{1,2})$", s)          # ISO
    if m:
        return f"{int(m.group(1))}月{int(m.group(2))}日"
    m = re.match(r"^(\d{1,2})[/.](\d{1,2})$", s)             # 6/12 或 06.06
    if m:
        return f"{int(m.group(1))}月{int(m.group(2))}日"
    return s


def _date_key(d):
    """解析日期为 (年, 月, 日) 用于排序；月初/中/底近似为 3/15/28。"""
    s = str(d or "")
    yr = re.search(r"(\d{4})\s*年", s)
    year = int(yr.group(1)) if yr else 2026
    m = re.search(r"(\d{1,2})\s*月", s)
    if m:
        month = int(m.group(1))
        da = re.search(r"(\d{1,2})\s*日", s)
        if da:
            day = int(da.group(1))
        elif "初" in s:
            day = 3
        elif "中" in s:
            day = 15
        elif "底" in s or "末" in s:
            day = 28
        else:
            day = 0
        return (year, month, day)
    m = re.match(r"^\s*(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.search(r"(?<!\d)(\d{1,2})[/.](\d{1,2})(?!\d)", s)
    if m:
        return (year, int(m.group(1)), int(m.group(2)))
    return (year, 0, 0)


def _strip_watch_prefix(s):
    """模块4 模板已带“盯：”前缀；若 watch 文本又以“盯 / 紧盯 / 盯紧 / 盯住 …”开头，则去掉，避免渲染出“盯：盯…”。"""
    t = str(s or "").strip()
    return re.sub(r"^(紧盯|盯紧|盯住|盯着|盯)\s*[：:，,]?\s*", "", t)


def _catalyst_source_name(c):
    """兼容多种来源字段写法，统一取模块2 徽标里的来源名。"""
    src = c.get("source") if isinstance(c.get("source"), dict) else {}
    for obj, keys in (
        (c, ("source_name", "sourceName", "source", "publisher", "media", "outlet")),
        (src, ("name", "source_name", "sourceName", "publisher", "media", "outlet")),
    ):
        for key in keys:
            val = obj.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return ""


def _catalyst_url(c):
    src = c.get("source") if isinstance(c.get("source"), dict) else {}
    for obj in (c, src):
        val = obj.get("url") if isinstance(obj, dict) else ""
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def build_catalysts(p):
    ss = (p.get("section_summaries") or {}).get("catalysts", "")
    cats = p.get("catalysts") or []
    # 模块2 事件按时间倒序：最新的排在最上面（同日期保持原顺序）
    cats = sorted(cats, key=lambda c: _date_key(c.get("date")), reverse=True)
    if not cats:
        body = ('<div class="tl-empty"><b>暂无可核验的公开催化</b>'
                '<p>当前缺少可追溯的事件、政策或数据来源；信息热度判断置信度有限。</p></div>')
    else:
        items = []
        for c in cats:
            tone = c.get("tone", "中性")
            tagcls, dotcls = _TONE.get(tone, ("tag-mid", "dot-blue"))
            label = tone + (f" · {c.get('category')}" if c.get("category") else "")
            url = c.get("url")
            detail = []
            if c.get("why"):
                detail.append(f'<p><b>为什么重要：</b>{rich(c["why"])}</p>')
            if c.get("verify"):
                detail.append(f'<p><b>后续验证：</b>{rich(c["verify"])}</p>')
            detail_html = f'<div class="tl-detail">{"".join(detail)}</div>' if detail else ""
            fact = f'<div class="tl-d">{rich(c.get("fact",""))}</div>' if c.get("fact") else ""
            link = (f'<a class="source-link" href="{esc(url)}" target="_blank" rel="noopener">打开原文 ↗</a>'
                    if url else '')
            title_row = ('<div class="tl-head">'
                         f'<span class="tag {tagcls}">{esc(label)}</span>{link}</div>')
            # 信息来源标签：每条事件标题前显名标注来源，如“信息来源 · 新华社”
            src_name = _catalyst_source_name(c)
            src_badge = (f'<span class="src-badge" title="信息来源">信息来源 · {esc(src_name)}</span>'
                         if src_name else "")
            items.append(
                f'<div class="tl-item"><div class="tl-date">{esc(_fmt_cn_date(c.get("date","")))}</div>'
                f'<div class="tl-dot {dotcls}"></div><div class="tl">'
                f'{title_row}<div class="tl-t">{src_badge}<span class="tl-title-text">{rich(c.get("title",""))}</span></div>{fact}{detail_html}'
                f'</div></div>'
            )
        body = f'<div class="card tl-card">{"".join(items)}</div>'
    return (
        '<section id="s2" class="sec wrap reveal">'
        + _sec_head(2, "为什么涨/跌", "驱动事件时间线")
        + _module_note(ss)
        + body
        + '</section>'
    )


# ---------------------------------------------------------------- 模块3 · 谁在动、谁没动

# 四象限分组（量价配合）：放量上攻 / 缩量上行 / 缩量回调 / 放量杀跌；每组带固定副标题
_GRP_META = [
    ("放量上攻", "g-lead", "量价齐升·参与充分"),
    ("缩量上行", "g-hold", "量能不足·持续性存疑"),
    ("缩量回调", "g-lag", "抛压衰竭·多近企稳"),
    ("放量杀跌", "g-deep", "抛压沉重·资金出逃"),
]


def build_treemap(p):
    ss = (p.get("section_summaries") or {}).get("divergence", "")
    # 热力图数据限定为本次选取的 10 只代表股（多于 10 只时只取前 10）
    stocks = (p.get("stocks") or [])[:10]
    js_stocks = []
    for s in stocks:
        js_stocks.append({
            "name": s.get("name", ""),
            "role": s.get("role", s.get("group", "")),
            # 当日口径：当日涨跌幅 + 当日成交额
            "change": s.get("change", 0),
            "turnover": s.get("turnover", abs(float(s.get("change", 1) or 1)) or 1),
            # 近7日口径：近7日涨跌幅 + 近7个交易日日均成交额；字段由第一阶段 facts 校验并自动映射
            "change_7d": s.get("change_7d"),
            "turnover_7d": s.get("turnover_7d"),
            # 选取理由：悬停时一句话说明为什么选这只股票（优先 select_reason，回退 note）
            "reason": s.get("select_reason") or s.get("note") or "",
        })
    # 两个视图按【时间口径】切换：当日数据 / 近7日数据；每个视图都同时呈现该口径的“涨跌幅”（色）与“成交额”（块大小）
    seg = ('<div class="seg" id="modeSeg"><button class="seg-btn active" data-mode="daily">当日数据</button>'
           '<button class="seg-btn" data-mode="d7">近7日数据</button></div>')
    legend = ('<div class="legend"><span id="legendText">当日涨跌幅</span>'
              '<span id="legendL">-20%</span><span class="legend-bar"></span>'
              '<span id="legendR">+20%</span></div>')
    # 热力图脚注只保留审计信息，避免把交互说明渲染进最终报告。
    qsrc = esc(p.get("quote_source") or "同花顺数据库")
    ts = esc(p.get("timestamp") or "")
    cap_date = f"{ts}（收盘价）" if ts else "收盘价"
    treemap = ('<div class="hm-body"><div class="treemap-wrap"><div class="treemap" id="treemap"></div>'
               '<div class="tooltip" id="tooltip"></div></div></div>'
               f'<div class="hm-foot">{cap_date} · 个股涨跌幅 / 成交额数据来源：{qsrc}</div>')
    card = f'<div class="card hm-card"><div class="hm-head">{seg}{legend}</div>{treemap}</div>'
    groups = p.get("divergence_groups") or {}
    gcards = []
    # 四组固定全部展示；某组无对应个股时填“无”，不强行归类
    for name, cls, sub in _GRP_META:
        g = groups.get(name) or {}
        names = [x for x in (g.get("stocks") or []) if str(x).strip()]
        if names:
            tags = "".join(f"<span>{esc(x)}</span>" for x in names)
            feat = rich(g.get("feature", "") or "")
        else:
            tags = '<span class="grp-empty">无</span>'
            feat = rich(g.get("feature", "") or "本期无此类个股。")
        gcards.append(
            f'<div class="grp {cls}"><h4>{esc(name)}组<span class="grp-sub">{esc(sub)}</span></h4>'
            f'<div class="grp-tags">{tags}</div><p>{feat}</p></div>'
        )
    groups_html = f'<div class="grp-grid">{"".join(gcards)}</div>' if gcards else ""
    meaning = groups.get("meaning", "")
    top_summary = meaning or ss
    return (
        '<section id="s3" class="sec wrap reveal">'
        + _sec_head(3, "谁在动、谁没动", "板块内部结构分化")
        + _module_note(top_summary)
        + card + groups_html
        + '</section>'
    ), js_stocks


# ---------------------------------------------------------------- 模块4 · 接下来盯什么

def build_watch(p):
    ss = (p.get("section_summaries") or {}).get("watch", "")
    sigs = p.get("watch_signals") or []
    cards = []
    for i, s in enumerate(sigs, 1):
        tag = s.get("tag", "")
        gn = f"信号 {i}" + (f" · {tag}" if tag else "")
        watch = _strip_watch_prefix(s.get("watch", ""))  # 模板已带“盯：”，避免出现“盯：盯…”
        improve = s.get("improve", "")
        worsen = s.get("worsen", "")
        read_lines = ""
        if watch:
            read_lines += f'<p><b>盯：</b>{rich(watch)}</p>'
        if improve:
            read_lines += f'<p><b>改善：</b>{rich(improve)}</p>'
        if worsen:
            read_lines += f'<p><b>恶化：</b>{rich(worsen)}</p>'
        read_block = f'<div class="gread">{read_lines}</div>' if read_lines else ""
        cards.append(
            f'<article class="card gcard"><div class="ghead"><div class="gn">{esc(gn)}</div>'
            f'<div class="gv">{rich(s.get("signal",""))}</div>'
            f'</div>'
            f'{read_block}</article>'
        )
    grid = f'<div class="watch-grid">{"".join(cards)}</div>' if cards else '<div class="note">暂无前瞻信号。</div>'
    return (
        '<section id="s4" class="sec wrap reveal">'
        + _sec_head(4, "接下来盯什么", "后续验证信号")
        + _module_note(ss)
        + grid
        + '</section>'
    )


# ---------------------------------------------------------------- 模块5 · 风险提示

def build_risks(p):
    ss = (p.get("section_summaries") or {}).get("risks", "")
    risks = p.get("risks") or []
    lis = []
    for i, r in enumerate(risks, 1):
        parts = []
        if r.get("trigger"):
            parts.append(f'<p><b>触发：</b>{rich(r["trigger"])}</p>')
        if r.get("why"):
            parts.append(f'<p>{rich(r["why"])}</p>')
        if r.get("invalidate"):
            parts.append(f'<p><b>证伪：</b>{rich(r["invalidate"])}</p>')
        lis.append(
            f'<li><div class="risk-index">{i}</div><strong>{rich(r.get("title",""))}</strong>'
            f'<div class="risk-detail">{"".join(parts)}</div></li>'
        )
    body = (f'<div class="card risk-compact"><ol>{"".join(lis)}</ol></div>'
            if lis else '<div class="note">暂无风险情景。</div>')
    return (
        '<section id="s5" class="sec wrap reveal">'
        + _sec_head(5, "风险提示", "会让热度判断失效的条件")
        + _module_note(ss)
        + body
        + '</section>'
    )


# ---------------------------------------------------------------- 模块6 · 信息来源（仅公开原文）

def _fmt_src_date(d):
    """ISO 日期 → "6月12日"；其它格式原样返回。"""
    m = re.match(r"^\s*\d{4}-(\d{1,2})-(\d{1,2})", str(d or ""))
    if m:
        return f"{int(m.group(1))}月{int(m.group(2))}日"
    return str(d or "")


def build_sources(p):
    # 展示公开来源与数据终端；有 URL 的可点击，无 URL 的作为“数据终端”展示。
    sources = [s for s in (p.get("sources") or []) if s.get("url") or s.get("name") or s.get("title")]
    sources = sorted(sources, key=lambda s: _date_key(s.get("date")), reverse=True)
    public_n = sum(1 for s in sources if s.get("url"))
    terminal_n = len(sources) - public_n
    summ = [f"<span><b>{public_n}</b> 条可点击核验的公开来源</span>"]
    if terminal_n:
        summ.append(f"<span><b>{terminal_n}</b> 条行情 / 数据终端来源</span>")
    lis = []
    for i, s in enumerate(sources, 1):
        url = s.get("url")
        name = s.get("name") or s.get("category") or "来源"
        date = _fmt_src_date(s.get("date"))
        title = str(s.get("title") or "").strip()
        date_html = f'<span class="source-date">{esc(date)}</span>' if date else ""
        if url:
            link = f'<a class="source-link" href="{esc(url)}" target="_blank" rel="noopener">查看原文</a>'
        else:
            link = '<span class="source-link source-terminal">数据终端</span>'
        lis.append(
            f'<li><div class="source-title">'
            f'<span class="source-name">[{i}] {esc(name)}</span>{date_html}'
            f'<strong>{rich(title)}</strong>{link}</div></li>'
        )
    ledger = (f'<ol class="source-ledger">{"".join(lis)}</ol>'
              if lis else '<div class="note">暂无可公开追溯的原文链接。</div>')
    return (
        '<section id="s6" class="sec wrap reveal">'
        + _sec_head(6, "信息来源", "可点击核验的公开来源")
        + f'<div class="card source-card"><div class="source-summary">{"".join(summ)}</div>{ledger}</div>'
        + '</section>'
    )


def build_footer(p):
    # 标准化「风险提示与免责声明」：首行标题 + 三段正文（pre-wrap 保留换行）
    return ('<section class="wrap reveal" style="margin-top:40px">'
            f'<div class="risk-disclaimer"><div class="risk-copy">{esc(RISK_DISCLAIMER)}</div></div>'
            '</section>')


# ---------------------------------------------------------------- 渲染前校验门（数据硬校验）

class PayloadError(ValueError):
    """payload 未通过渲染前校验门：数据存在硬性错误，拒绝渲染。"""
    pass


# 两条来源 lane
_LANE_FINANCE = "seed_finance_search"
_LANE_GENERAL = "general_search"
_VALID_LANES = {_LANE_FINANCE, _LANE_GENERAL}
_LANE_ZH = {
    _LANE_FINANCE: "seed_finance_search（金融数据库）",
    _LANE_GENERAL: "general_search（公开检索）",
}
# 模块2 催化来源分级：一级 / 二级允许，命中三级来源会拒绝渲染
_FIRSTHAND_LEVELS = {"一手", "权威"}

# ===== 模块2「为什么涨/跌」新闻来源三级分级（只允许一级/二级，禁止三级）=====
# 三级（FORBIDDEN）：行情 / 研报摘要 / 自媒体 / UGC / 个人作者发表的文章。
# 雪球 / 今日头条 / 东方财富等聚合平台页面不按域名一刀切：若明确署名 / 作者 / 采编主体为机构媒体、
# 上市公司、行业协会、第三方机构或券商，可作为二级承载页保留；个人、自媒体或无法确认机构作者仍拦截。
# 注意：此处禁的是把这些平台或个人作者当“新闻来源”；证券市场数字与上市公司个股业务 / 财务【数字】仍走 seed_finance_search（同花顺数据库），二者不冲突。
_PLATFORM_OUTLET_KEYS = (
    "东方财富", "eastmoney", "同花顺", "10jqka", "雪球", "xueqiu",
    "今日头条", "微博", "weibo",
)
_TIER3_OUTLET_KEYS = (
    "股吧", "贴吧", "论坛", "头条号", "百家号", "大鱼号",
    "自媒体", "博主", "个人专栏", "@",
)
_PERSONAL_SOURCE_KEYS = (
    "个人", "作者", "博主", "达人", "号主", "自媒体", "专栏作者", "个人专栏",
    "头条号", "百家号", "大鱼号", "公众号作者", "@",
)
# 聚合 / 分发 URL：仅在来源名或作者类型可确认为机构媒体 / 新闻网站时按二级放行，否则按三级拦截。
_AGGREGATOR_URL_KEYS = (
    "toutiao.com", "m.toutiao.com", "weibo.com", "m.weibo.cn",
    "baijiahao.baidu.com", "mbd.baidu.com", "xueqiu.com", "eastmoney.com", "guba.eastmoney.com",
)
# 可疑转载 / 移动分发 / 跳转 URL：给 warning，不直接拒图，避免误伤官方号或门户原文。
_SUSPECT_CATALYST_URL_KEYS = (
    "sohu.com/a/", "qq.com/rain/a/", "c.m.163.com", "m.163.com/news",
    "sina.com.cn/wm/", "t.m.youth.cn/transfer/", "transfer/index/url",
    "mp.weixin.qq.com",
)
# 一级：官方 / 一手 / 监管 / 交易所 / 公司公告（事实类）——巨潮、沪深交易所、证监会、央行、统计局、官媒、公司公告 / 年报、券商研报原文。
_TIER1_OUTLET_KEYS = (
    "巨潮", "cninfo", "上交所", "上海证券交易所", "sse", "深交所", "深圳证券交易所", "szse",
    "北交所", "证监会", "csrc", "央行", "人民银行", "pbc", "国家统计局", "统计局", "stats",
    "国务院", "政府网", "全国人大", "发改委", "财政部", "工信部", "外汇局",
    "新华社", "中新社", "中国新闻社", "人民日报", "公司公告", "年报", "季报", "招股", "券商研报",
)
# 二级：机构媒体 / 新闻网站（含财经媒体与综合新闻媒体）+ 行业第三方。下列只是常见来源识别表，不是封闭名单；
# 其它可核验、非三级的平台 / 机构可通过显式 source.tier=2 放行。
_TIER2_OUTLET_KEYS = (
    "财联社", "cls", "证券时报", "stcn", "上海证券报", "cnstock", "中国证券报", "中证",
    "第一财经", "yicai", "界面新闻", "界面", "jiemian", "华尔街见闻", "wallstreetcn",
    "财新", "caixin", "21世纪经济报道", "21财经", "21jingji", "经济观察", "证券日报",
    "路透", "reuters", "彭博", "bloomberg", "上海有色", "smm", "中汽协", "乘联会",
    "光明网", "gmw", "新京报", "bjnews", "中国经济网", "ce.cn", "中国青年网", "中国旅游报",
    "海外网", "羊城晚报", "北京商报", "澎湃新闻", "thepaper",
)
_INSTITUTION_AUTHOR_TYPES = {
    "机构", "机构号", "机构账号", "机构媒体", "新闻机构", "媒体机构", "媒体", "新闻媒体", "新闻网站", "机构报道",
    "上市公司", "公司号", "行业协会", "第三方机构", "券商", "券商号", "官方号", "官方账号",
    "media", "institution", "institution_account", "institutional_account", "official", "official_account",
    "mainstream_media", "official_news_agency", "industry_data", "industry_association", "news_website",
    "institutional_media", "listed_company", "company_account", "broker", "brokerage", "third_party_institution",
}
# 由 source.level 文字映射到分级
_LEVEL_TO_TIER = {
    "一手": 1, "权威": 1, "官方": 1, "一级": 1,
    "二级": 2, "主流媒体": 2, "持证媒体": 2, "媒体原创": 2, "转载": 2, "二手": 2,
    "三级": 3, "自媒体": 3, "ugc": 3, "UGC": 3, "股吧": 3, "传闻": 3,
}


def _resolve_catalyst_tier(c):
    """判定模块2 单条催化的新闻来源分级（1/2/3）。返回 (tier 或 None, 判定依据字符串)。

    优先级：来源名 / 作者类型命中三级黑名单（最高；个人 / 自媒体，或把承载平台名当来源名，纵使误标更高级也判三级）
    → 显式 source.tier / source.level 为三级 → 来源名识别 / 显式一级二级 → 聚合承载页最高降为二级。
    都不命中则返回 None（无法判定，可显式 source.tier=1/2）。
    """
    src = c.get("source") if isinstance(c.get("source"), dict) else {}
    name = _catalyst_source_name(c)
    nl = name.lower()
    url = _catalyst_url(c)
    ul = url.lower()
    author_type = str(src.get("author_type") or src.get("source_type") or "").strip().lower()
    institution_author = author_type in _INSTITUTION_AUTHOR_TYPES
    # 1) 来源名 / 作者类型命中三级黑名单 —— 个人 / 自媒体优先级最高
    if author_type in {"个人", "personal", "self_media", "自媒体", "ugc"}:
        return 3, f"source.author_type=“{author_type}”属个人 / 自媒体"
    for k in _TIER3_OUTLET_KEYS:
        if k in name or k.lower() in nl:
            return 3, f"来源名“{name}”属三级（{k}）"
    for k in _PERSONAL_SOURCE_KEYS:
        if k in name or k.lower() in nl:
            return 3, f"来源名“{name}”疑似个人 / 自媒体作者（{k}）"

    explicit_tier = None
    level_tier = None
    name_tier = None
    name_basis = ""

    # 2) 显式 tier
    t = src.get("tier")
    try:
        ti = int(t)
        if ti in (1, 2, 3):
            explicit_tier = ti
    except (TypeError, ValueError):
        pass
    if explicit_tier == 3:
        return 3, "显式 source.tier=3"
    # 3) level 文字映射
    lvl = str(src.get("level") or "").strip()
    if lvl in _LEVEL_TO_TIER:
        level_tier = _LEVEL_TO_TIER[lvl]
    if level_tier == 3:
        return 3, f"source.level=“{lvl}”"
    # 4) 来源名命中一级 / 二级常见来源识别表
    for k in _TIER1_OUTLET_KEYS:
        if k in name or k.lower() in nl:
            name_tier, name_basis = 1, f"来源名“{name}”属一级（{k}）"
            break
    for k in _TIER2_OUTLET_KEYS:
        if name_tier is None and (k in name or k.lower() in nl):
            name_tier, name_basis = 2, f"来源名“{name}”属二级（{k}）"
            break

    tier = name_tier or explicit_tier or level_tier
    basis = name_basis or ("显式 source.tier" if explicit_tier else (f"source.level=“{lvl}”" if level_tier else ""))

    # 5) 平台名 / 聚合名：只有机构主体 + 二级标注可保留；个人或无法确认机构主体仍按三级。
    for k in _PLATFORM_OUTLET_KEYS:
        if k in name or k.lower() in nl:
            if explicit_tier == 2 and institution_author:
                return 2, f"source_name 为平台 / 聚合名（{k}），但 source.author_type 可确认机构主体，按二级"
            return 3, f"source_name 为平台 / 聚合名（{k}），未确认机构主体；平台不按域名放行"

    # 6) 聚合 / 分发 URL：如果署名 / 作者 / 采编主体是机构主体，可按二级放行；个人或无法确认则拦截。
    for k in _AGGREGATOR_URL_KEYS:
        if k.lower() in ul:
            if tier in (1, 2) and (name_tier in (1, 2) or institution_author):
                return 2, f"{basis}；链接为聚合 / 分发承载页（{k}），来源名“{name}”可识别为机构媒体 / 新闻网站，最高按二级"
            return 3, f"链接“{url}”落在聚合 / 分发承载页（{k}），但未能确认署名 / 作者 / 采编主体为机构媒体 / 新闻网站"

    if tier in (1, 2, 3):
        return tier, basis
    return None, ""
# A 股单日涨跌幅绝对上限（创业板 / 科创板 ±20%）
_CHANGE_ABS_MAX = 20.0
_GROUP_ORDER = ["放量上攻", "缩量上行", "缩量回调", "放量杀跌"]
_DIMENSION_ORDER = ["价格涨跌", "成交量能", "代表股表现", "估值位置"]
# 量价配合：上行组（放量上攻 / 缩量上行）涨跌幅应≥0；下行组（缩量回调 / 放量杀跌）涨跌幅应<0。
# 放量/缩量由复算门按 turnover vs turnover_7d 硬校验。
_GROUP_UP = {"放量上攻", "缩量上行"}
_GROUP_DOWN = {"缩量回调", "放量杀跌"}
# 估值口径强制：值里出现 PE/PB/PS（市盈 / 市净 / 市销）就必须出现一个口径词
_VAL_METRIC_RE = re.compile(r"P\s*[EBS]\b|市盈|市净|市销", re.I)
_INTERNAL_HEAT_SCORE_RE = re.compile(r"(?:综合|信息|行情)?热度\s*[+\-＋－]\s*\d|热度\s*(?:上调|下调)\s*\d", re.I)
_VAL_CALIBER_RE = re.compile(r"TTM|LYR|MRQ|静态|动态|滚动|静|动", re.I)
# 具体日期 token（含“日 / 号”或 ISO，要求有“日”分量，避免误伤只写到月的模糊表述）——用于模块4 预定型信号检测
_DATE_TOKEN_RE = re.compile(r"\d{1,2}\s*月\s*\d{1,2}\s*[日号]|\d{4}-\d{1,2}-\d{1,2}")

# 核心结论 key_chips 的「固定指标」（规则·只展示这几个，且口径只取自同花顺数据库）
# 1 收盘点位 · 2 当日涨跌幅 · 3 近7日涨跌幅 · 4 当日成交额 · 5 近7个交易日日均成交额 · 6 代表股当日 PE(TTM)（10 只代表股中市值最大那只，非板块 PE）
# —— 近7日（近7个交易日）口径锁定，杜绝算错；且计算前先取并校验所需历史分量：
#   T / T0      ＝ 最近一个已经完成收盘的交易日；盘中生成时不得用当日未收盘行情，
#                    应回退到上一已收盘交易日，并在 meta.timestamp 写清“数据截至 YYYY-MM-DD 收盘”。
#   取数动作    ＝ 第一轮就取 T-7 至 T 的 8 个已收盘交易日日线；不要先搜 T-6 至 T 再补 T-7。
#   change_7d   ＝ (T日收盘价 ÷ T-7交易日收盘价 − 1) × 100%；当天作为 Day 0，
#                    基准为从数据截止日 T 往前数第 7 个交易日的收盘价，不是最近 7 个交易日窗口第一天(T-6)；
#                    用首尾收盘价比值（复利口径），不得把每日涨跌幅简单相加。
#   turnover_7d ＝ 近7个交易日日均成交额（亿元）＝ T-6 至 T 的 7 个交易日成交额之和 ÷ 7；
#                    取“日均”而非“累计”，是为了与“当日成交额”同量纲、可直接判断今日是否放量。
#   计算前的校验（无误后再算）：①涨幅分量是否包含 T-7 与 T 两个收盘价；②成交额数组是否恰为 T-6 至 T
#                    的 7 个交易日且无缺失/断档；③有无异常值（收盘价为 0 或相邻日跳变异常、成交额为负）。
#                    任一项不过先修正取数或按缺口降级。
_FIXED_KEY_METRICS = {
    "close_point",       # 收盘点位（目标概念板块指数当日收盘点位）
    "daily_change",      # 当日涨跌幅（板块指数当日收盘较前收盘 %）
    "change_7d",        # 近7日涨跌幅（板块指数，首尾收盘价比值，% —— 口径见上）
    "turnover_amount",   # 当日成交额（板块成分股当日成交额合计，亿元）
    "turnover_7d",      # 近7个交易日日均成交额（板块成分股，亿元 —— 口径见上）
    "pe_ttm",            # 代表股当日 PE(TTM)（已选 10 只代表股中市值最大那只的当日滚动市盈率，倍；非板块 PE）
}
_FIXED_KEY_METRICS_ZH = ("收盘点位 / 当日涨跌幅 / 近7日涨跌幅 / 当日成交额 / "
                         "近7个交易日日均成交额 / 代表股当日 PE(TTM)（已选代表股中市值最大者）")
# 核心结论展示卡固定逻辑：固定 4 张——
#   ① close_point 与 ⑥ pe_ttm 必须展示（两张定卡）；
#   另外两张在「当日组」(daily_change + turnover_amount) 与「近7日组」(change_7d + turnover_7d) 之间二选一，
#   两组成对出现、不得交叉混搭（不可同时出现 daily_change 与 change_7d，也不可同时出现 turnover_amount 与 turnover_7d）。
_KEY_CHIPS_REQUIRED = {"close_point", "pe_ttm"}          # 必须展示的两张定卡
_KEY_CHIPS_DAILY_PAIR = {"daily_change", "turnover_amount"}   # 当日组
_KEY_CHIPS_D7_PAIR = {"change_7d", "turnover_7d"}         # 近7日组
_MAX_KEY_CHIPS = 4   # 固定 4 张（收盘点位 + 代表股 PE + 当日组 / 近7日组 二选一）


def _as_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _pct_from(numer, denom):
    if numer is None or denom in (None, 0):
        return None
    return (numer / denom - 1.0) * 100.0


def _within_pct_tol(expected, claimed):
    if expected is None or claimed is None:
        return True
    tol = max(0.6, abs(expected) * 0.06)
    return abs(expected - claimed) <= tol


def _any_date_key(s):
    """从任意字符串中尽量解析出 (年, 月, 日)；解析不到“月”时返回 (year, 0, 0)。
    比 _date_key 更宽松：ISO 日期可出现在字符串任意位置（如“数据截至 2026-06-12 收盘”）。"""
    s = str(s or "")
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)          # ISO（任意位置）
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    yr = re.search(r"(\d{4})\s*年", s)
    year = int(yr.group(1)) if yr else 2026
    mm = re.search(r"(\d{1,2})\s*月", s)
    if mm:
        month = int(mm.group(1))
        dd = re.search(r"(\d{1,2})\s*日", s)
        if dd:
            day = int(dd.group(1))
        elif "初" in s:
            day = 3
        elif "中" in s:
            day = 15
        elif "底" in s or "末" in s:
            day = 28
        else:
            day = 0
        return (year, month, day)
    m = re.search(r"(?<!\d)(\d{1,2})[/.](\d{1,2})(?!\d)", s)  # 6/12 或 06.06
    if m:
        return (year, int(m.group(1)), int(m.group(2)))
    return (year, 0, 0)


def _days_between_keys(later_key, earlier_key):
    """返回两个完整日期 key 的自然日差；日期不完整或非法时返回 None。"""
    try:
        if not later_key or not earlier_key or not (later_key[1] and later_key[2] and earlier_key[1] and earlier_key[2]):
            return None
        return (date(later_key[0], later_key[1], later_key[2]) -
                date(earlier_key[0], earlier_key[1], earlier_key[2])).days
    except ValueError:
        return None


_FRESH_CATALYST_DAYS = 14
_FRESHNESS_EXEMPT_RE = re.compile(
    r"政策|监管|公告|官方|通知|意见|规划|方案|条例|办法|征求意见|批复|会议|国常会|发改委|工信部|证监会|交易所|央行|美联储|FOMC|利率|加息|降息|财报|业绩|订单|数据|报告|指数|销量|装机|交付|招标",
    re.I,
)


def _score_quadrant(info_hot, mkt_hot):
    if info_hot and mkt_hot:
        return "BB"            # 双热
    if (not info_hot) and (not mkt_hot):
        return "CC"            # 双冷
    if info_hot and not mkt_hot:
        return "IH_MC"         # 信息热 · 行情冷
    return "MH_IC"             # 行情热 · 信息冷


def _classify_quadrant(type_str):
    """把 divergence.type 文本归类到四象限；归类不出则返回 None（不报错，交由分数自动判定）。"""
    t = str(type_str or "").replace(" ", "")
    if "双热" in t or "强趋势共振" in t:
        return "BB"
    if "双冷" in t or "低关注" in t:
        return "CC"
    info_hot, info_cold = "信息热" in t, "信息冷" in t
    mkt_hot, mkt_cold = "行情热" in t, "行情冷" in t
    if info_hot and mkt_cold:
        return "IH_MC"
    if mkt_hot and info_cold:
        return "MH_IC"
    if "利好兑现回落" in t or "题材未启动" in t or ("题材" in t and "启动" in t):
        return "IH_MC"
    if "纯资金" in t or "资金驱动" in t:
        return "MH_IC"
    return None


_QUAD_ZH = {"BB": "双热 · 强趋势共振", "CC": "双冷 · 低关注",
            "IH_MC": "信息热 · 行情冷", "MH_IC": "行情热 · 信息冷"}


def _stock_transfer_snapshot(payload):
    stocks = []
    for s in payload.get("stocks") or []:
        if not isinstance(s, dict):
            continue
        stocks.append({
            "name": s.get("name"),
            "group": s.get("group"),
            "role": s.get("role"),
            "select_reason": s.get("select_reason"),
            "change": s.get("change"),
            "turnover": s.get("turnover"),
            "change_7d": s.get("change_7d"),
            "turnover_7d": s.get("turnover_7d"),
            "d7_close_base": s.get("d7_close_base"),
            "d7_close_t": s.get("d7_close_t"),
            "d7_turnovers": s.get("d7_turnovers"),
            "source": s.get("source"),
        })
    groups = {}
    raw_groups = payload.get("divergence_groups") or {}
    for g in _GROUP_ORDER:
        raw = raw_groups.get(g)
        groups[g] = list((raw or {}).get("stocks") or []) if isinstance(raw, dict) else []
    return {
        "selected_stocks": payload.get("selected_stocks") or [],
        "stocks": stocks,
        "divergence_groups": groups,
    }


def _stock_transfer_hash(payload):
    raw = json.dumps(_stock_transfer_snapshot(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _check_source(obj, want_lane, label, err, ts_key, ts_has_date, require_url):
    """核对单个数据项的 source.lane 是否符合分级约束，并校验时点 / 链接。"""
    src = obj.get("source")
    if not isinstance(src, dict) or not str(src.get("lane") or "").strip():
        err(f"{label} 缺少 source.lane —— 每个展示数值都必须标注来源 lane 以便溯源。")
        return
    lane = str(src.get("lane")).strip()
    if lane not in _VALID_LANES:
        err(f"{label} 的 source.lane=“{lane}” 非法，只能是 seed_finance_search 或 general_search。")
    elif lane != want_lane:
        err(f"{label} 必须取自 {_LANE_ZH[want_lane]}，当前却标为 {_LANE_ZH.get(lane, lane)}"
            f"（分级约束：只有「为什么涨/跌」可用 general_search，其余行情 / 财务数据一律 seed_finance_search）。")
    if require_url and not str(obj.get("url") or "").strip():
        err(f"{label} 缺少 url（可打开的一级 / 二级原文或机构署名承载页链接）。")
    ao = src.get("as_of")
    if ao and ts_has_date:
        ak = _any_date_key(ao)
        if ak[1] and ak > ts_key:
            err(f"{label} 的 source.as_of({ao}) 晚于数据截止日，时点矛盾。")


def validate_payload(p, warn_only=False):
    """渲染前校验门：把数据真实性硬规则做成代码化的硬断言。

    - 发现硬错误：抛 PayloadError 并逐条列出（warn_only=True 时降级为打印、仍渲染，仅供调试）。
    - 软问题：打印到 stderr，不阻断。
    返回 warnings 列表。
    """
    errors, warns = [], []
    def err(m): errors.append(m)
    def warn(m): warns.append(m)

    # ---- E. 核心字段存在性（fail-loud，过去缺失会被静默默认值掩盖）----
    if not str(p.get("sector") or "").strip():
        err("缺少 sector（板块名）。")
    if not str(p.get("index_caliber") or "").strip():
        err("缺少 index_caliber（目标概念板块：名称+代码）—— 必须显式标注唯一目标板块。")
    ts = str(p.get("timestamp") or "").strip()
    if not ts:
        err("缺少 timestamp（数据截止时点，如“数据截至 2026-06-12 收盘”）。")
    ts_key = _any_date_key(ts) if ts else (2026, 0, 0)
    ts_has_date = bool(ts_key[1])

    # ---- A. 三个热度分（1-5、综合分公式、背离象限自洽）----
    comp, info, mkt = _as_float(p.get("composite_score")), _as_float(p.get("info_score")), _as_float(p.get("market_score"))
    for lab, v in (("composite_score", comp), ("info_score", info), ("market_score", mkt)):
        if v is None:
            err(f"{lab} 缺失或非数值（三个热度分都必须给出、且落在 1-5）。")
        elif not (1 <= v <= 5):
            err(f"{lab} = {v} 不在 1-5 范围内。")
    if comp is not None and info is not None and mkt is not None:
        expect = max(1, min(5, round(0.55 * mkt + 0.45 * info)))
        if round(comp) != expect:
            err(f"composite_score={comp} 与公式不符：round(0.55×行情{mkt:g} + 0.45×信息{info:g}) 应为 {expect}。")
    if info is not None and mkt is not None:
        dtype = str((p.get("divergence") or {}).get("type") or "").strip()
        claimed = _classify_quadrant(dtype)
        if claimed:
            want = _score_quadrant(info >= 3, mkt >= 3)
            if claimed != want:
                err(f"divergence.type=“{dtype}” 与分数不符：信息{info:g} / 行情{mkt:g}（阈值3）应落在“{_QUAD_ZH[want]}”象限。")

    answer = p.get("answer") if isinstance(p.get("answer"), dict) else {}
    for fld, zh in (("restate", "问题"), ("conclusion", "结论"), ("next", "下一步")):
        if not str(answer.get(fld) or "").strip():
            err(f"answer 缺少 {fld}（直接回答的“{zh}”）。HTML 直接回答统一只渲染：问题 / 结论 / 下一步。")
    if str(answer.get("status") or "").strip():
        err("answer.status 已废弃；请把需要展示的当前状态并入 answer.next，直接回答统一为：问题 / 结论 / 下一步。")

    # ---- B. 代表股 / 分组：第二阶段只确认搬运一致，不重复做内容判断 ----
    stocks = p.get("stocks") or []
    hydration = p.get("_facts_hydration") if isinstance(p.get("_facts_hydration"), dict) else {}
    expected_hash = str(hydration.get("stocks_sha256") or "").strip()
    if not expected_hash:
        err("payload 缺少 _facts_hydration.stocks_sha256 —— 第二阶段必须先运行 scripts/hydrate_payload_from_facts.py，从第一阶段 facts.json 自动映射 stocks / divergence_groups。")
    else:
        actual_hash = _stock_transfer_hash(p)
        if actual_hash != expected_hash:
            err("payload 的 stocks / divergence_groups 与 facts 自动映射结果不一致——请重新运行 scripts/hydrate_payload_from_facts.py，不要在第二阶段手工改 10 股行情、分组或选股说明。")

    # ---- C. provenance / 分级来源约束（核心）----
    # 行情 / 财务数据（含四维度、key_chips、stocks）→ seed_finance_search；仅「为什么涨/跌」催化 → general_search。
    chips = p.get("key_chips") or []
    # 核心结论展示数值（固定 4 张）：① 收盘点位 与 ⑥ 代表股当日 PE(TTM) 必须展示；
    # 另外两张在「当日组」(daily_change + turnover_amount) 与「近7日组」(change_7d + turnover_7d) 之间二选一，
    # 两组成对、不交叉混搭。口径只取自同花顺数据库，每个 chip 以 metric_key 标明取自哪一个候选。
    seen_metric = set()
    for i, c in enumerate(chips):
        _check_source(c, _LANE_FINANCE, f"key_chips[{i}]（{c.get('label','')}）", err, ts_key, ts_has_date, False)
        mk = str(c.get("metric_key") or "").strip()
        if not mk:
            err(f"key_chips[{i}]（{c.get('label','')}）缺少 metric_key —— 核心结论展示值必须取自 6 个候选指标"
                f"（{_FIXED_KEY_METRICS_ZH}）之一，并以 metric_key 标明是哪一个。")
        elif mk not in _FIXED_KEY_METRICS:
            err(f"key_chips[{i}] 的 metric_key=“{mk}” 不在 6 个候选指标内，只能是 "
                f"{sorted(_FIXED_KEY_METRICS)} 之一（对应 {_FIXED_KEY_METRICS_ZH}）。")
        elif mk in seen_metric:
            err(f"key_chips 指标 metric_key=“{mk}” 重复 —— 每张 chip 必须是不同的候选指标。")
        else:
            seen_metric.add(mk)
        if mk == "pe_ttm":
            pe_text = " ".join(str(c.get(k) or "") for k in ("label", "value", "read", "source_name"))
            if re.search(r"(?:板块|指数).*(?:PE|P/E|市盈)|(?:PE|P/E|市盈).*(?:板块|指数)", pe_text, re.I):
                err(f"key_chips[{i}] 的 pe_ttm 禁止使用板块 PE / 板块市盈率；必须取 10 只代表股中市值最大那只的股票 PE(TTM)。")
    # —— 固定 4 张展示逻辑的硬校验 ——
    if chips:
        if len(chips) != _MAX_KEY_CHIPS:
            err(f"核心结论 key_chips 必须恰好 {_MAX_KEY_CHIPS} 张（收盘点位 + 代表股当日 PE(TTM) 两张定卡，"
                f"再加「当日组」或「近7日组」二选一共两张），当前 {len(chips)} 张。")
        missing_req = _KEY_CHIPS_REQUIRED - seen_metric
        if missing_req:
            zh = {"close_point": "当日收盘点位", "pe_ttm": "代表股当日 PE(TTM)"}
            err("核心结论 key_chips 缺少必须展示的定卡："
                f"{'、'.join(zh[m] for m in sorted(missing_req))} —— 收盘点位与代表股当日 PE(TTM) 两张必须始终展示。")
        has_daily = bool(_KEY_CHIPS_DAILY_PAIR & seen_metric)
        has_d7 = bool(_KEY_CHIPS_D7_PAIR & seen_metric)
        if has_daily and has_d7:
            err("核心结论 key_chips 不得交叉混搭「当日组」(当日涨跌幅 + 当日成交额) 与「近7日组」"
                "(近7日涨跌幅 + 近7个交易日日均成交额) —— 两组成对、只能二选一。")
        elif has_daily and _KEY_CHIPS_DAILY_PAIR - seen_metric:
            err("核心结论 key_chips 选了「当日组」却不成对 —— 当日涨跌幅(daily_change) 与 当日成交额(turnover_amount) 必须同时出现。")
        elif has_d7 and _KEY_CHIPS_D7_PAIR - seen_metric:
            err("核心结论 key_chips 选了「近7日组」却不成对 —— 近7日涨跌幅(change_7d) 与 近7个交易日日均成交额(turnover_7d) 必须同时出现。")
        elif not has_daily and not has_d7:
            err("核心结论 key_chips 除两张定卡外，还须从「当日组」或「近7日组」中二选一补满两张可变卡。")
    dims = p.get("dimensions") or []
    for d in dims:
        track = str(d.get("track") or "行情").strip()
        if track != "行情":
            err(f"维度“{d.get('name','')}” track=“{track}” 不合规——模块1固定四维均为行情轨，结构化行情/估值/成交/资金/财务数字必须来自 seed_finance_search。")
        _check_source(d, _LANE_FINANCE, f"维度“{d.get('name','')}”（{track}轨）", err, ts_key, ts_has_date, False)
    cats_for_check = p.get("catalysts") or []
    if len(cats_for_check) > 6:
        err(f"catalysts 最多 6 条，建议精选 3-5 条核心驱动事件；当前 {len(cats_for_check)} 条。请合并同一逻辑、保留最高等级原文，其余只留在取数笔记 / facts 内部裁定。")
    elif cats_for_check and len(cats_for_check) < 3:
        warn(f"catalysts 当前 {len(cats_for_check)} 条；模块2通常建议精选 3-5 条核心驱动事件。若板块确实缺少可核验催化，可保持当前条数。")
    for i, c in enumerate(cats_for_check):
        nm = c.get("title") or f"catalysts[{i}]"
        _check_source(c, _LANE_GENERAL, f"催化“{nm}”", err, ts_key, ts_has_date, True)
        # 每条事件必须显名标注信息来源；来源名也用于渲染标题前的“信息来源 · XX”标签。
        src_name = _catalyst_source_name(c)
        if not src_name:
            err(f"催化“{nm}”缺少 source_name —— 模块2 每条事件必须显名标注来源，并提供可用于渲染“信息来源 · XX”标签的来源名（须为一级 / 二级；新华社 / 财联社 / 证券时报只是示例，二级名单非封闭）。")
        else:
            title = str(c.get("title") or "").strip()
            if len(src_name) > 16:
                warn(f"催化“{nm}”的 source_name=“{src_name}”较长，请确认只填来源名本身、没有把标题或描述粘进去。")
            if title and len(title) >= 6 and title in src_name:
                err(f"催化“{nm}”的 source_name 含新闻标题内容。source_name 只填来源名本身，标题请放在 title 字段。")
        # 来源分级硬约束：模块2 新闻只允许一级 / 二级，禁止三级（行情 / 研报摘要 / 自媒体 / 个人作者，以及无法确认机构作者的聚合 / 分发页）。
        tier, basis = _resolve_catalyst_tier(c)
        if tier == 3:
            err(f"催化“{nm}”的信息来源为【三级】（{basis}）——模块2「为什么涨/跌」禁止使用三级来源"
                f"（行情 / 研报摘要 / 自媒体 / UGC，尤其个人作者发表的文章，以及无法确认机构作者的聚合 / 分发页）。"
                f"请改用一级（官方 / 监管 / 交易所 / 公司公告 / 官媒，如新华社）或二级（机构媒体 / 新闻网站、行业第三方等非三级来源；名单非封闭）来源并回溯原文。")
        elif tier is None:
            warn(f"催化“{nm}”无法判定来源分级 —— 模块2 仅允许一级 / 二级来源；二级名单是非封闭示例。"
                 f"请显式标注 source.tier 为 1 或 2；若 url 是聚合承载页且机构署名，只能标 2，并确认其非个人 / 自媒体 / 无法确认机构作者。")
        url = _catalyst_url(c).lower()
        for key in _AGGREGATOR_URL_KEYS:
            if key in url:
                src = c.get("source") if isinstance(c.get("source"), dict) else {}
                try:
                    explicit_tier = int(src.get("tier"))
                except (TypeError, ValueError):
                    explicit_tier = None
                if explicit_tier == 1:
                    err(f"催化“{nm}”的 url 为聚合 / 分发承载页（{key}）——即使署名为机构媒体 / 新闻网站，也不能标一级；请改为 source.tier=2，或回溯到一级原文链接。")
                else:
                    warn(f"催化“{nm}”的 url 为聚合 / 分发承载页（{key}）——URL 不自动判三级；仅在 source_name 或作者类型可确认为机构媒体 / 新闻网站且非个人作者时允许，并且最高按二级。能回溯原文直链时仍优先改用原文直链。")
                break
        for key in _SUSPECT_CATALYST_URL_KEYS:
            if key in url:
                warn(f"催化“{nm}”的 url 命中可疑转载 / 移动分发 / 跳转特征（{key}）——建议回溯到一级 / 二级原文；若确认为来源方原文，可保留并显式标注 source.tier。")
                break
        if ts_has_date:
            ck = _any_date_key(c.get("date"))
            if ck[1] and ck > ts_key:
                err(f"催化“{nm}”日期({c.get('date')}) 晚于数据截止日({ts})——模块2 只能解释截至该收盘日已经发生的涨跌驱动。"
                    f"截止日之后发生、尚未交易验证的新闻不能进 catalysts；如有必要，应在“接下来盯什么”里转写为后续交易 / 数据验证信号。")
            age_days = _days_between_keys(ts_key, ck)
            if age_days is not None and age_days > _FRESH_CATALYST_DAYS:
                ctype = " ".join(str(c.get(k) or "") for k in ("type", "tag", "category", "direction", "title", "fact"))
                reason = str(c.get("freshness_reason") or c.get("still_relevant_reason") or "").strip()
                if not reason and not _FRESHNESS_EXEMPT_RE.search(ctype):
                    warn(f"催化“{nm}”距数据截止日已 {age_days} 天，超过默认 {_FRESH_CATALYST_DAYS} 天新闻窗口。"
                         f"模块2应尽量使用近14天内催化；若这是仍在兑现的政策 / 监管 / 官方文件 / 业绩数据等，请补 freshness_reason 说明为什么仍与本轮行情直接相关，否则建议替换为更新来源。")

    # ---- C2. 模块4 盯盘信号必须前瞻（确认验证结果尚未兑现，落在数据截止时间之后，与模块2 对称）----
    # 规则：①带 event_date / as_of 的预定型信号，该日必须【晚于】数据截止日（否则在盯已发生、已定价的旧事件）；
    #      ②event_date 表示“验证日期”（如下一个交易日 / 关键数据发布日期），不是截止日后背景新闻的发生日；
    #      ③信号文本里出现了具体日期（如“6月17日 FOMC”），却没登记 event_date 的，必须补 event_date 以便校验其在截止日之后——
    #        防“写了个有确切日子的验证项、却绕过未来性校验”。持续型信号（无固定日期、靠阈值界定）无须 event_date。
    watch_signals = p.get("watch_signals") or []
    if len(watch_signals) > 4:
        err(f"watch_signals 最多 4 条，建议优先写 4 条真正决定结论的前瞻信号；当前 {len(watch_signals)} 条。请合并同一类暑期数据 / 量能 / 核心标的信号，避免新闻式罗列。")
    elif watch_signals and len(watch_signals) < 3:
        warn(f"watch_signals 当前 {len(watch_signals)} 条；模块4通常建议 3-4 条前瞻信号，优先 4 条。若确实只有少数胜负手变量，可保持当前条数。")
    seen_watch_signal = set()
    for i, w in enumerate(watch_signals):
        if not isinstance(w, dict):
            continue
        nm = w.get("signal") or w.get("tag") or f"watch_signals[{i}]"
        sig_norm = re.sub(r"\s+", "", str(w.get("signal") or "")).lower()
        if sig_norm:
            if sig_norm in seen_watch_signal:
                err(f"盯盘信号“{nm}”重复 —— 模块4应合并同一变量，只保留一个最能改变结论的观察条件。")
            seen_watch_signal.add(sig_norm)
        # 字段非空校验：HTML 卡片标题=signal、"盯："=watch、"改善："=improve、"恶化："=worsen
        if not str(w.get("signal") or "").strip():
            err(f"盯盘信号[{i}] 缺少 signal（被观察的变量）—— HTML 卡片标题取 signal，不能为空。")
        if not str(w.get("watch") or "").strip():
            err(f"盯盘信号“{nm}”缺少 watch（盯什么阈值）—— HTML 卡片“盯：”取 watch，为空会渲染出空白的“盯：”。"
                f"请把可量化阈值写进 watch，不要全塞进 signal。")
        if not str(w.get("improve") or "").strip():
            err(f"盯盘信号“{nm}”缺少 improve（改善解读）—— HTML 卡片“改善：”取 improve，不能为空。")
        if not str(w.get("worsen") or "").strip():
            err(f"盯盘信号“{nm}”缺少 worsen（恶化解读）—— HTML 卡片“恶化：”取 worsen，不能为空。")
        for fld in ("signal", "watch", "improve", "worsen"):
            txt = str(w.get(fld) or "")
            if _INTERNAL_HEAT_SCORE_RE.search(txt):
                err(f"盯盘信号“{nm}”的 {fld} 含内部评分语言（如“信息热度+1 / 行情热度-1”）。模块4给用户看，只写结论如何升级 / 转弱 / 失效，不暴露热度加减分。")
        ev = w.get("event_date") or w.get("as_of") or (w.get("source") or {}).get("as_of")
        if ev and ts_has_date:
            ek = _any_date_key(ev)
            if ek[1] and ek <= ts_key:
                err(f"盯盘信号“{nm}”的 event_date({ev}) 不晚于数据截止日({ts})——这是已发生 / 已可被本次行情定价的旧事，"
                    f"应作为模块2 的驱动事件回顾，或改写为数据截止日之后尚未兑现的交易 / 数据验证条件（见 references/chat_contract.md）。")
        elif not ev:
            # 信号 / 盯什么文本里若含具体日期 token，视为预定型信号，必须补 event_date 以校验未来性
            text = f"{w.get('signal','')} {w.get('watch','')}"
            if _DATE_TOKEN_RE.search(text):
                hit = _DATE_TOKEN_RE.search(text).group(0)
                err(f"盯盘信号“{nm}”含具体日期“{hit}”却未登记 event_date —— 预定型信号必须提供 event_date，"
                    f"以便校验门确认该验证项【晚于数据截止日({ts})、尚未兑现】；若是无固定日期的持续型信号，请去掉文本中的具体日期、改用阈值表述。")

    # ---- C3. 模块5 风险卡四字段非空（title/trigger/why/invalidate）----
    # HTML 风险卡：序号旁标题=title、"触发："=trigger、说明段=why、"证伪："=invalidate；why 只作说明段，不显示字段名。
    for i, r in enumerate(p.get("risks") or []):
        if not isinstance(r, dict):
            continue
        rnm = r.get("title") or f"risks[{i}]"
        if not str(r.get("title") or "").strip():
            err(f"风险[{i}] 缺少 title（风险标题）—— HTML 风险卡序号旁的标题取 title，为空会留下空白标题。")
        if not str(r.get("trigger") or "").strip():
            err(f"风险“{rnm}”缺少 trigger（触发条件）—— HTML 风险卡“触发：”取 trigger，不能为空。")
        if not str(r.get("why") or "").strip():
            err(f"风险“{rnm}”缺少 why（风险说明 / 影响机制）—— HTML 风险卡标题下的说明段取 why，不能为空。")
        if not str(r.get("invalidate") or "").strip():
            err(f"风险“{rnm}”缺少 invalidate（证伪信号）—— HTML 风险卡“证伪：”取 invalidate，不能为空。")

    # ---- C4. 模块6 来源标题提示 ----
    for i, s in enumerate(p.get("sources") or []):
        if not isinstance(s, dict):
            continue
        if not str(s.get("title") or s.get("purpose") or s.get("usage") or "").strip():
            warn(f"sources[{i}] 缺少 title（来源标题 / 用途）—— 建议从模块6原句搬运标题，或让 hydrate_payload_from_facts.py 从分析草稿自动抽取。")

    # ---- D. 板块口径配套 ----
    mode = str(p.get("data_mode") or "full").strip().lower()
    if mode != "full":
        err(f"data_mode=“{mode}” 非法；当前只允许 full，板块指标必须是目标板块自身数据。")
    if str(p.get("data_note") or "").strip():
        err("data_note 已废弃；不要用 10 股样本替代板块指标，也不要写替代口径说明。")

    # ---- E2. 四维度固定 4 个 ----
    if len(dims) != 4:
        err(f"dimensions 必须为固定 4 个维度（价格涨跌 / 成交量能 / 代表股表现 / 估值位置），当前 {len(dims)} 个。")
    else:
        got_dims = [str(d.get("name") or "").strip() for d in dims]
        if got_dims != _DIMENSION_ORDER:
            err("dimensions 必须按固定顺序填写："
                f"{' / '.join(_DIMENSION_ORDER)}。当前顺序为：{' / '.join(got_dims)}。"
                "模块1“现在有多热”只渲染这四张维度卡，不再添加资金流、公开催化等旧维度。")

    # ---- E3. 估值口径强制：估值维度若含 PE/PB/PS，必须标 TTM/静态/动态/LYR 口径 ----
    # PE/PB 不同口径数值差异很大，是行情数字最常出错处之一；不标口径的估值数字一律不合格。
    for d in dims:
        if "估值" in str(d.get("name") or ""):
            val = str(d.get("value") or "")
            if _VAL_METRIC_RE.search(val) and not _VAL_CALIBER_RE.search(val):
                err(f"估值维度数值“{val[:40]}…”含 PE/PB/PS 但未标口径——"
                    f"估值必须注明口径（TTM / 静态 / 动态 / LYR）与时点，如“PE(TTM) 约 22x（截至 6月12日）”。")

    # ---- F. 复算门：把能从原始分量算出来的财务/股票数字真的算一遍 ----
    # 复算对不上（回撤/单日涨跌/反弹/比值）、量纲越界（成交额负、PB≤0）、登记值与展示值打架 → 硬错误。
    # 事实表(numeric_facts)结构 / 来源分级错误 → 硬错误；未登记 / 未绑定 / 缺 source_name → 警告（不阻断）。
    try:
        for m in _mc.hard_checks(p):
            err(m)
        reg_err, reg_warn = _mc.registry_checks(p, timestamp_key=(ts_key if ts_has_date else None))
        for m in reg_err:
            err(m)
        for m in reg_warn:
            warn(m)
    except Exception as _exc:  # 复算门自身异常不应吞掉其它校验结果
        warn(f"复算门执行异常（已跳过复算硬校验，请检查 typed 分量字段类型）：{_exc}")

    # ---- 汇总 ----
    if errors:
        msg = (f"payload 未通过渲染前校验门，发现 {len(errors)} 处数据硬错误：\n"
               + "\n".join(f"  [{i + 1}] {m}" for i, m in enumerate(errors)))
        if warn_only:
            print("⚠ (warn-only) " + msg, file=sys.stderr)
        else:
            raise PayloadError(msg)
    for w in warns:
        print("⚠ " + w, file=sys.stderr)
    return warns


# ---------------------------------------------------------------- 组装

def render(payload_path, out_dir, warn_only=False):
    with open(payload_path, encoding="utf-8") as f:
        p = json.load(f)
    # 渲染前硬校验：数据存在错误时直接抛 PayloadError、拒绝出图（fail-loud）
    validate_payload(p, warn_only=warn_only)
    css = (ASSETS / "dashboard.css").read_text(encoding="utf-8")
    js_tpl = (ASSETS / "dashboard.js").read_text(encoding="utf-8")

    sec3_html, js_stocks = build_treemap(p)
    js = js_tpl.replace("__STOCKS_JSON__", json.dumps(js_stocks, ensure_ascii=False))

    sector = p.get("sector", "板块")
    title = f"{sector}板块热度仪表盘"

    body = (
        '<body><div id="heatbar" aria-hidden="true"></div>'
        + build_topbar(p)
        + '<main>'
        + build_hero(p)
        + build_divergence(p)
        + build_answer(p)
        + build_nav()
        + build_dimensions(p)
        + build_catalysts(p)
        + sec3_html
        + build_watch(p)
        + build_risks(p)
        + build_sources(p)
        + '</main>'
        + build_footer(p)
        + f'<script>{js}</script></body>'
    )
    doc = (
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>{esc(title)}</title><style>{css}</style></head>'
        + body + '</html>'
    )

    os.makedirs(out_dir, exist_ok=True)
    html_path = os.path.join(out_dir, f"{title}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(doc)
    return html_path


def main():
    args = list(sys.argv[1:])
    warn_only = "--warn-only" in args
    check_only = "--check-only" in args or "--validate-only" in args
    args = [a for a in args if a not in ("--warn-only", "--check-only", "--validate-only")]
    if (check_only and len(args) != 1) or ((not check_only) and len(args) < 2):
        print("用法: python3 render_dashboard.py <payload.json> <输出目录> [--warn-only]\n"
              "      python3 render_dashboard.py --check-only <payload.json>", file=sys.stderr)
        sys.exit(1)
    try:
        if check_only:
            with open(args[0], encoding="utf-8") as f:
                validate_payload(json.load(f), warn_only=warn_only)
            print("payload 校验通过（check-only，未生成 HTML）")
            return
        html_path = render(args[0], args[1], warn_only=warn_only)
    except PayloadError as e:
        print(str(e), file=sys.stderr)
        print("\n渲染已中止：请按上面逐条修正 payload 后重试。"
              "（仅本地调试页面时，可加 --warn-only 将错误降级为打印。）", file=sys.stderr)
        sys.exit(2)
    print("已生成:")
    print(" -", html_path)


if __name__ == "__main__":
    main()
