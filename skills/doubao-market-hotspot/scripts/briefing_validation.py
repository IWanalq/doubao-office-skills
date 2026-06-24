"""Validation and normalization helpers for doubao-market-hotspot.

Keep this module stdlib-only so the skill can validate and render offline.
"""
from __future__ import annotations

import copy
import json
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from pathlib import Path
from typing import Any


def _load_machine_schema() -> dict[str, Any]:
    schema_path = Path(__file__).resolve().parent.parent / "references" / "briefing.schema.json"
    try:
        return json.loads(schema_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


MACHINE_SCHEMA = _load_machine_schema()


def _load_disclaimers() -> dict[str, Any]:
    disclaimer_path = Path(__file__).resolve().parent.parent / "references" / "disclaimers.json"
    try:
        data = json.loads(disclaimer_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


DISCLAIMER_REGISTRY = _load_disclaimers()
DISCLAIMER_IDS = set(DISCLAIMER_REGISTRY)


def disclaimer_for(disclaimer_id: Any) -> dict[str, Any]:
    """Return the fixed public disclaimer text for the requested version."""
    disclaimer = DISCLAIMER_REGISTRY.get(str(disclaimer_id or ""))
    out = copy.deepcopy(disclaimer) if isinstance(disclaimer, dict) else {}
    body = out.get("body")
    if isinstance(body, str):
        out["body"] = "\n".join(re.sub(r"^\s*[-*•]\s+", "", line) for line in body.splitlines())
    items = out.get("items")
    if isinstance(items, list):
        out["items"] = [
            re.sub(r"^\s*[-*•]\s+", "", str(item))
            for item in items
            if item not in (None, "")
        ]
    return out


def _schema_prop(*names: str) -> dict[str, Any]:
    node: dict[str, Any] = MACHINE_SCHEMA
    for name in names:
        node = node.get("properties", {}).get(name, {})
        if not isinstance(node, dict):
            return {}
    return node


def _schema_def(name: str) -> dict[str, Any]:
    node = MACHINE_SCHEMA.get("$defs", {}).get(name, {})
    return node if isinstance(node, dict) else {}


def _def_prop(def_name: str, prop: str) -> dict[str, Any]:
    node = _schema_def(def_name).get("properties", {}).get(prop, {})
    return node if isinstance(node, dict) else {}


def _schema_enum(node: dict[str, Any], fallback: set[str]) -> set[str]:
    values = node.get("enum")
    return set(values) if isinstance(values, list) and values else fallback


def _schema_required(node: dict[str, Any], fallback: list[str]) -> list[str]:
    values = node.get("required")
    return list(values) if isinstance(values, list) and values else fallback


REQUIRED = _schema_required(MACHINE_SCHEMA, [
    "schema_version",
    "meta",
    "dialog_brief",
    "insight",
    "reading_budget",
    "section_summaries",
    "highlight",
    "visuals",
    "screen1",
    "news_items",
    "verification",
    "source_check",
    "references",
])
DICT_FIELDS = [
    "meta",
    "dialog_brief",
    "insight",
    "reading_budget",
    "section_summaries",
    "highlight",
    "visuals",
    "screen1",
    "source_check",
]
LIST_FIELDS = ["news_items", "follow_ups", "references"]
URL_KEYS = {"url", "href"}
TRACKING_QUERY_KEYS = {
    "fbclid",
    "from",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "spm",
    "utm_id",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
}
TRACKING_QUERY_PREFIXES = ("utm_",)
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
BARE_DOMAIN_RE = re.compile(
    r"^(?![a-z][a-z0-9+.-]*:)(?!//)([A-Za-z0-9-]+\.)+[A-Za-z]{2,}(/|$)"
)
HTTP_URL_RE = re.compile(r"^https?://", re.I)
INLINE_URL_RE = re.compile(r"https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+", re.I)
ASCII_TIME_RE = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b")
RAW_TEXT_KEYS = {"time", "date", "generated_at", "time_window"}

READING_BUDGET_SCHEMA = _schema_prop("reading_budget")
QUESTION_TYPES = _schema_enum(_schema_prop("meta", "question_type"), {"market", "policy", "event", "update"})
ANALYSIS_MODES = _schema_enum(
    _schema_prop("meta", "analysis_mode"),
    {"market_event", "policy_macro", "dated_catalyst", "earnings_event", "theme_watch"},
)
MARKET_SESSIONS = _schema_enum(_schema_prop("meta", "market_session"), {"pre", "intraday", "post", "non_trading"})
REF_LEVELS = _schema_enum(_def_prop("reference", "level"), {"A", "B", "C", "D"})
REF_TYPES = _schema_enum(_def_prop("reference", "type"), {"official", "media", "institution", "background", "unverified"})
NEWS_CATEGORIES = _schema_enum(_def_prop("news_item", "category"), {"政策", "产业", "公司", "海外映射", "市场反应", "机构观点", "后续观察"})
TIMELINE_KINDS = _schema_enum(_def_prop("timeline_item", "kind"), {"official", "media", "institution", "background"})
IMPORTANCE_LEVELS = _schema_enum(_def_prop("news_item", "importance"), {"高", "中", "低"})
TONES = _schema_enum(_schema_prop("highlight", "tone"), {"neutral", "positive", "risk"})
INTERPRETATION_ROLES = _schema_enum(
    _def_prop("interpretation_item", "role"),
    {"客观事实", "市场反应", "机构观点", "官方事实", "市场定价", "机构视角", "媒体报道", "反向证据", "资金信号", "政策信号", "市场数据", "其他"},
)
READING_BUDGET_REQUIRED = _schema_required(READING_BUDGET_SCHEMA, ["thirty_second", "one_minute", "three_minute", "default_news_count", "max_frontstage_chars"])
READING_BUDGET_MINIMUMS = {
    key: node.get("minimum")
    for key, node in READING_BUDGET_SCHEMA.get("properties", {}).items()
    if isinstance(node, dict) and "minimum" in node
}
REFERENCE_CORROBORATION_MINIMUM = _def_prop("reference", "corroboration").get("minimum", 1)
MAX_REPAIR_ATTEMPTS = 2

DIALOG_BRIEF_REQUIRED_LABELS = {"事实变化", "市场含义", "分歧点", "后续验证"}
DIALOG_BRIEF_ROLE_KEYS = [
    ("fact_change", "事实变化"),
    ("market_meaning", "市场含义"),
    ("disagreement", "分歧点"),
    ("verification", "后续验证"),
]
DEFAULT_DIALOG_RISK_BOUNDARY = "这里只做公开信息梳理和验证条件拆解，不构成投资建议。"

POLICY_MACRO_AUTHORITY_DOMAINS = {
    "bea.gov",
    "bls.gov",
    "cbo.gov",
    "cmegroup.com",
    "ecb.europa.eu",
    "eia.gov",
    "federalreserve.gov",
    "iea.org",
    "opec.org",
    "pbc.gov.cn",
    "stats.gov.cn",
    "treasury.gov",
}

def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _protect_text(s: str, pattern: re.Pattern[str], replacements: list[tuple[str, str]]) -> str:
    def repl(match: re.Match[str]) -> str:
        token = f"\ue000{len(replacements)}\ue001"
        replacements.append((token, match.group(0)))
        return token

    return pattern.sub(repl, s)


def _restore_text(s: str, replacements: list[tuple[str, str]]) -> str:
    for token, raw in replacements:
        s = s.replace(token, raw)
    return s


def normalize_zh_text(s: str) -> str:
    if not isinstance(s, str) or not CJK_RE.search(s):
        return s
    protected: list[tuple[str, str]] = []
    s = _protect_text(s, INLINE_URL_RE, protected)
    s = _protect_text(s, ASCII_TIME_RE, protected)
    replacements = {
        ",": "，",
        ":": "：",
        ";": "；",
        "?": "？",
        "!": "！",
        "(": "（",
        ")": "）",
    }
    for src, dst in replacements.items():
        s = s.replace(src, dst)
    s = re.sub(r"([\u4e00-\u9fff])\s+([A-Za-z0-9])", r"\1\2", s)
    s = re.sub(r"([A-Za-z0-9])\s+([\u4e00-\u9fff])", r"\1\2", s)
    s = re.sub(r"\s+([，。；：？！、）])", r"\1", s)
    s = re.sub(r"([（])\s+", r"\1", s)
    return _restore_text(s, protected)


def normalize_url(s: Any) -> Any:
    if not isinstance(s, str):
        return s
    raw = s.strip()
    if not raw:
        return raw
    if raw.startswith("//"):
        return "https:" + raw
    if raw.startswith(("data:", "mailto:", "#")):
        return raw
    if BARE_DOMAIN_RE.search(raw):
        return "https://" + raw
    return raw


def canonical_source_url(url: Any) -> str:
    """Return a stable article identity key for duplicate source detection."""
    normalized = normalize_url(url)
    if not isinstance(normalized, str):
        return ""
    raw = normalized.strip()
    if not is_http_url(raw):
        return ""
    try:
        parts = urlsplit(raw)
    except ValueError:
        return raw.lower()

    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    try:
        port = parts.port
    except ValueError:
        port = None
    if port and port not in (80, 443):
        host = f"{host}:{port}"

    path = re.sub(r"/+", "/", parts.path or "/")
    if len(path) > 1:
        path = path.rstrip("/")

    query_pairs = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        key_l = key.lower()
        if key_l in TRACKING_QUERY_KEYS or any(key_l.startswith(prefix) for prefix in TRACKING_QUERY_PREFIXES):
            continue
        query_pairs.append((key_l, value))
    query = urlencode(sorted(query_pairs))
    return urlunsplit(("https", host, path, query, ""))


def normalize_payload(value: Any, key: str | None = None) -> Any:
    if isinstance(value, dict):
        normalized = {k: normalize_payload(v, k) for k, v in value.items()}
        if key is None:
            normalized = normalize_dialog_contract(normalized)
        return normalized
    if isinstance(value, list):
        return [normalize_payload(v, key) for v in value]
    if isinstance(value, str) and key in URL_KEYS:
        return normalize_url(value)
    if isinstance(value, str) and key in RAW_TEXT_KEYS:
        return value
    if isinstance(value, str):
        return normalize_zh_text(value)
    return value


def normalize_dialog_contract(payload: dict[str, Any]) -> dict[str, Any]:
    dialog = payload.get("dialog_brief")
    if not isinstance(dialog, dict):
        return payload

    key_points = dialog.get("key_points")
    if isinstance(key_points, dict):
        normalized_points: list[dict[str, Any]] = []
        for role_key, label in DIALOG_BRIEF_ROLE_KEYS:
            item = key_points.get(role_key)
            if item is None:
                item = key_points.get(label)
            if isinstance(item, dict):
                point = {k: v for k, v in item.items() if k != "label"}
                point["label"] = label
                normalized_points.append(point)
        extras = key_points.get("extra")
        if isinstance(extras, list):
            normalized_points.extend(item for item in extras if isinstance(item, dict))
        dialog["key_points"] = normalized_points

    if not dialog.get("risk_boundary"):
        dialog["risk_boundary"] = DEFAULT_DIALOG_RISK_BOUNDARY
    return payload


def is_http_url(url: Any) -> bool:
    return isinstance(url, str) and bool(HTTP_URL_RE.search(url.strip()))


def source_host(url: Any) -> str:
    normalized = normalize_url(url)
    if not isinstance(normalized, str):
        return ""
    try:
        host = urlsplit(normalized.strip()).hostname or ""
    except ValueError:
        return ""
    host = host.lower()
    return host[4:] if host.startswith("www.") else host


def host_matches_domain(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def is_int_like(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    return isinstance(value, float) and value.is_integer()


def _issue(level: str, path: str, message: str, **meta: Any) -> dict[str, Any]:
    issue: dict[str, Any] = {"level": level, "path": path, "message": message}
    issue.update({key: value for key, value in meta.items() if value is not None})
    return issue


def _schema_ref(schema: dict[str, Any]) -> dict[str, Any]:
    ref = schema.get("$ref")
    if not isinstance(ref, str) or not ref.startswith("#/$defs/"):
        return schema
    return _schema_def(ref.rsplit("/", 1)[-1])


def _schema_path(base: str, key: str) -> str:
    if base in ("", "$"):
        return key
    return f"{base}.{key}"


def _schema_type_label(schema_type: Any) -> str:
    if isinstance(schema_type, list):
        return "/".join(str(item) for item in schema_type)
    return str(schema_type)


def _schema_type_matches(value: Any, schema_type: Any) -> bool:
    if isinstance(schema_type, list):
        return any(_schema_type_matches(value, item) for item in schema_type)
    if schema_type == "object":
        return isinstance(value, dict)
    if schema_type == "array":
        return isinstance(value, list)
    if schema_type == "string":
        return isinstance(value, str)
    if schema_type == "boolean":
        return isinstance(value, bool)
    if schema_type == "integer":
        return is_int_like(value)
    if schema_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if schema_type == "null":
        return value is None
    return True


def _schema_option_applies(value: Any, schema: dict[str, Any]) -> bool:
    schema = _schema_ref(schema)
    schema_type = schema.get("type")
    if schema_type is None:
        return True
    return _schema_type_matches(value, schema_type)


def _check_schema_contract(
    value: Any,
    schema: dict[str, Any],
    issues: list[dict[str, Any]],
    path: str = "$",
) -> None:
    schema = _schema_ref(schema)
    if not isinstance(schema, dict):
        return

    if "anyOf" in schema:
        options = [item for item in schema.get("anyOf", []) if isinstance(item, dict)]
        for option in options:
            if _schema_option_applies(value, option):
                _check_schema_contract(value, option, issues, path)
                return
        issues.append(_issue("error", path, "不符合 briefing.schema.json 允许的数据形态"))
        return

    schema_type = schema.get("type")
    if schema_type is not None and not _schema_type_matches(value, schema_type):
        issues.append(_issue("error", path, f"必须是 JSON Schema 类型 {_schema_type_label(schema_type)}"))
        return

    if "const" in schema and value != schema.get("const"):
        issues.append(_issue("error", path, f"必须是固定值：{schema.get('const')!r}"))
    enum = schema.get("enum")
    if isinstance(enum, list) and value not in enum:
        issues.append(_issue("error", path, f"必须是 {enum} 之一"))

    if isinstance(value, str):
        min_length = schema.get("minLength")
        if isinstance(min_length, int) and len(value) < min_length:
            issues.append(_issue("error", path, "必填"))
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and not re.search(pattern, value):
            issues.append(_issue("error", path, f"必须匹配 pattern：{pattern}"))

    if is_int_like(value) or (isinstance(value, (int, float)) and not isinstance(value, bool)):
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if isinstance(minimum, (int, float)) and value < minimum:
            issues.append(_issue("error", path, f"必须 >= {minimum}"))
        if isinstance(maximum, (int, float)) and value > maximum:
            issues.append(_issue("error", path, f"必须 <= {maximum}"))

    if schema_type == "array" and isinstance(value, list):
        min_items = schema.get("minItems")
        max_items = schema.get("maxItems")
        if isinstance(min_items, int) and len(value) < min_items:
            issues.append(_issue("error", path, f"数组长度必须 >= {min_items}"))
        if isinstance(max_items, int) and len(value) > max_items:
            issues.append(_issue("error", path, f"数组长度必须 <= {max_items}"))
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for i, item in enumerate(value):
                _check_schema_contract(item, item_schema, issues, f"{path}[{i}]")
        return

    if schema_type != "object" or not isinstance(value, dict):
        return

    props = schema.get("properties", {})
    props = props if isinstance(props, dict) else {}
    required = schema.get("required")
    if isinstance(required, list):
        for key in required:
            if key not in value:
                issues.append(_issue("error", _schema_path(path, str(key)), "briefing.schema.json 必填"))

    additional = schema.get("additionalProperties", True)
    if additional is False:
        for key in value:
            if key not in props:
                issues.append(_issue("error", _schema_path(path, key), "不在 briefing.schema.json 契约中"))

    for key, item in value.items():
        child_schema = props.get(key)
        if isinstance(child_schema, dict):
            _check_schema_contract(item, child_schema, issues, _schema_path(path, key))
        elif isinstance(additional, dict):
            _check_schema_contract(item, additional, issues, _schema_path(path, key))


def collect_issues(b: Any, *, strict: bool = False, audit: bool = False) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if not isinstance(b, dict):
        return [_issue("error", "$", "briefing.json 顶层必须是对象")]

    missing = [k for k in REQUIRED if k not in b]
    if missing:
        issues.append(_issue("error", "$", "缺少必填字段：" + "，".join(missing)))
    if MACHINE_SCHEMA:
        _check_schema_contract(b, MACHINE_SCHEMA, issues)

    for key in DICT_FIELDS:
        if key in b and not isinstance(b.get(key), dict):
            issues.append(_issue("error", key, "必须是对象"))
    for key in LIST_FIELDS:
        if key in b and not isinstance(b.get(key), list):
            issues.append(_issue("error", key, "必须是数组"))

    _check_meta(b, issues)
    ref_ids, internal_ids = _check_references(b, issues)
    _check_news_items(b, issues, ref_ids, internal_ids)
    _check_source_check(b, issues, ref_ids, internal_ids)
    _check_highlight(b, issues, ref_ids, internal_ids)
    _check_dialog_brief(b, issues, ref_ids, internal_ids)
    _check_insight(b, issues)
    _check_reading_budget(b, issues)
    _check_section_summaries(b, issues)
    _check_visuals(b, issues, ref_ids, internal_ids)
    _check_analysis_mode_rules(b, issues)
    _check_verification(b, issues, ref_ids, internal_ids)
    _check_source_usage(b, issues)
    _check_interpretation_and_timeline(b, issues, ref_ids, internal_ids)
    _check_optional_audit_fields(b, issues, audit)

    return issues


def _check_meta(b: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    meta = b.get("meta") if isinstance(b.get("meta"), dict) else {}
    if meta.get("question_type") not in QUESTION_TYPES:
        issues.append(_issue("error", "meta.question_type", f"必须是 {sorted(QUESTION_TYPES)} 之一"))
    analysis_mode = meta.get("analysis_mode")
    if analysis_mode not in (None, "") and analysis_mode not in ANALYSIS_MODES:
        issues.append(_issue("error", "meta.analysis_mode", f"必须是 {sorted(ANALYSIS_MODES)} 之一"))
    if meta.get("market_session") not in MARKET_SESSIONS:
        issues.append(_issue("error", "meta.market_session", f"必须是 {sorted(MARKET_SESSIONS)} 之一"))
    for key in ("title", "time_window", "generated_at", "source_scope", "disclaimer_id", "locale"):
        if not meta.get(key):
            issues.append(_issue("error", f"meta.{key}", "必填"))
    disclaimer_id = meta.get("disclaimer_id")
    if not DISCLAIMER_IDS:
        issues.append(_issue("error", "meta.disclaimer_id", "无法加载固定免责声明版本库"))
    elif disclaimer_id and disclaimer_id not in DISCLAIMER_IDS:
        issues.append(_issue("error", "meta.disclaimer_id", f"必须是固定免责声明版本：{sorted(DISCLAIMER_IDS)}"))


def _check_references(b: dict[str, Any], issues: list[dict[str, Any]]) -> tuple[set[Any], set[Any]]:
    refs = b.get("references") if isinstance(b.get("references"), list) else []
    ref_ids: set[Any] = set()
    internal_ids: set[Any] = set()
    canonical_urls: dict[str, int] = {}
    for i, r in enumerate(refs):
        path = f"references[{i}]"
        if not isinstance(r, dict):
            issues.append(_issue("error", path, "必须是对象"))
            continue
        rid = r.get("id")
        if rid in (None, ""):
            issues.append(_issue("error", f"{path}.id", "必填"))
        elif rid in ref_ids:
            issues.append(_issue("error", f"{path}.id", f"重复：{rid!r}"))
        else:
            ref_ids.add(rid)
        if not r.get("title"):
            issues.append(_issue("error", f"{path}.title", "必填"))
        if not r.get("source"):
            issues.append(_issue("error", f"{path}.source", "必填"))
        if r.get("level") not in REF_LEVELS:
            issues.append(_issue("error", f"{path}.level", f"必须是 {sorted(REF_LEVELS)} 之一"))
        if r.get("type") not in REF_TYPES:
            issues.append(_issue("error", f"{path}.type", f"必须是 {sorted(REF_TYPES)} 之一"))
        if r.get("type") == "unverified" or r.get("level") == "D":
            internal_ids.add(rid)
        corr = r.get("corroboration")
        if not is_int_like(corr) or corr < REFERENCE_CORROBORATION_MINIMUM:
            issues.append(_issue("error", f"{path}.corroboration", f"必须是 >={REFERENCE_CORROBORATION_MINIMUM} 的整数"))
        if not r.get("date"):
            issues.append(_issue("error", f"{path}.date", "必填"))
        if not is_http_url(r.get("url")):
            issues.append(_issue("error", f"{path}.url", f"必须是 http(s) 地址：{r.get('url')!r}"))
        canonical_url = canonical_source_url(r.get("url"))
        if canonical_url:
            previous = canonical_urls.get(canonical_url)
            if previous is not None:
                issues.append(
                    _issue(
                        "error",
                        f"{path}.url",
                        f"与 references[{previous}].url 指向同一网页；同一网页只能保留一个 reference id",
                    )
                )
            else:
                canonical_urls[canonical_url] = i
    public_refs = [
        r for r in refs
        if isinstance(r, dict) and r.get("level") != "D" and r.get("type") != "unverified"
    ]
    if len(public_refs) > 5:
        front = public_refs[:5]
        if not any(r.get("type") == "official" or r.get("level") == "A" for r in front):
            issues.append(_issue("advisory", "references", "来源超过 5 条时,前 5 条应优先放核心来源,且尽量包含一手/官方来源;其余会在前台折叠"))
    return ref_ids, internal_ids


def _check_news_items(
    b: dict[str, Any],
    issues: list[dict[str, Any]],
    ref_ids: set[Any],
    internal_ids: set[Any],
) -> None:
    news_items = b.get("news_items") if isinstance(b.get("news_items"), list) else []
    for i, n in enumerate(news_items):
        path = f"news_items[{i}]"
        if not isinstance(n, dict):
            issues.append(_issue("error", path, "必须是对象"))
            continue
        if not n.get("title"):
            issues.append(_issue("error", f"{path}.title", "必填"))
        ref_id = n.get("ref")
        if ref_id not in ref_ids:
            issues.append(_issue("error", f"{path}.ref", f"未在 references 中：{ref_id!r}"))
        if ref_id in internal_ids:
            issues.append(_issue("error", f"{path}.ref", f"指向 D/unverified 来源，不能进入前台新闻：{ref_id!r}"))
        if not n.get("time"):
            issues.append(_issue("error", f"{path}.time", "必填；无法确认时填原始口径并设 time_uncertain=true"))
        if n.get("importance") not in IMPORTANCE_LEVELS:
            issues.append(_issue("error", f"{path}.importance", f"必须是 {sorted(IMPORTANCE_LEVELS)} 之一"))
        if n.get("category") not in NEWS_CATEGORIES:
            issues.append(_issue("error", f"{path}.category", f"必须是 {sorted(NEWS_CATEGORIES)} 之一"))
        if not n.get("why"):
            issues.append(_issue("error", f"{path}.why", "必填"))
        _check_news_image(issues, f"{path}.image", n.get("image"))


def _check_source_check(
    b: dict[str, Any],
    issues: list[dict[str, Any]],
    ref_ids: set[Any],
    internal_ids: set[Any],
) -> None:
    source_check = b.get("source_check") if isinstance(b.get("source_check"), dict) else {}
    for group, ids in source_check.items():
        if not isinstance(ids, list):
            issues.append(_issue("error", f"source_check.{group}", "必须是数组"))
            continue
        for ref_id in ids:
            if ref_id not in ref_ids:
                issues.append(_issue("error", f"source_check.{group}", f"引用不存在：{ref_id!r}"))
            if group != "internal_excluded" and ref_id in internal_ids:
                issues.append(_issue("error", f"source_check.{group}", f"不能引用 D/unverified 来源：{ref_id!r}"))


def _check_highlight(
    b: dict[str, Any],
    issues: list[dict[str, Any]],
    ref_ids: set[Any],
    internal_ids: set[Any],
) -> None:
    highlight = b.get("highlight") if isinstance(b.get("highlight"), dict) else {}
    lead_ref = highlight.get("lead_ref")
    if lead_ref not in ref_ids:
        issues.append(_issue("error", "highlight.lead_ref", f"未在 references 中：{lead_ref!r}"))
    elif lead_ref in internal_ids:
        issues.append(_issue("error", "highlight.lead_ref", f"不能指向 D/unverified 来源：{lead_ref!r}"))
    if highlight.get("tone") not in TONES:
        issues.append(_issue("error", "highlight.tone", f"必须是 {sorted(TONES)} 之一"))


def _check_dialog_brief(
    b: dict[str, Any],
    issues: list[dict[str, Any]],
    ref_ids: set[Any],
    internal_ids: set[Any],
) -> None:
    dialog = b.get("dialog_brief") if isinstance(b.get("dialog_brief"), dict) else {}
    key_points = dialog.get("key_points")
    if isinstance(key_points, list):
        labels = {str(item.get("label") or "").strip() for item in key_points if isinstance(item, dict)}
        missing = sorted(DIALOG_BRIEF_REQUIRED_LABELS - labels)
        if missing:
            issues.append(_issue("error", "dialog_brief.key_points", "缺少必备角色：" + "，".join(missing)))
        for i, item in enumerate(key_points):
            path = f"dialog_brief.key_points[{i}]"
            if not isinstance(item, dict):
                continue
            refs = item.get("refs")
            if not isinstance(refs, list) or not refs:
                issues.append(_issue("error", f"{path}.refs", "至少引用一个公开来源"))
                continue
            for rid in refs:
                if rid not in ref_ids:
                    issues.append(_issue("error", f"{path}.refs", f"未在 references 中：{rid!r}"))
                elif rid in internal_ids:
                    issues.append(_issue("error", f"{path}.refs", f"不能指向 D/unverified 来源：{rid!r}"))


def _check_insight(b: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    insight = b.get("insight") if isinstance(b.get("insight"), dict) else {}
    for key in ("confirm_signals", "invalidate_signals"):
        values = insight.get(key)
        if not isinstance(values, list):
            issues.append(_issue("error", f"insight.{key}", "必须是数组"))
            continue
    if insight.get("confidence") not in IMPORTANCE_LEVELS:
        issues.append(_issue("error", "insight.confidence", f"必须是 {sorted(IMPORTANCE_LEVELS)} 之一"))


def _check_reading_budget(b: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    reading_budget = b.get("reading_budget") if isinstance(b.get("reading_budget"), dict) else {}
    for key in READING_BUDGET_REQUIRED:
        if key not in reading_budget or reading_budget.get(key) in (None, ""):
            issues.append(_issue("error", f"reading_budget.{key}", "必填"))
    for key in ("one_minute", "three_minute"):
        if not isinstance(reading_budget.get(key), list):
            issues.append(_issue("error", f"reading_budget.{key}", "必须是数组"))
    for key in ("default_news_count", "max_frontstage_chars"):
        if key not in reading_budget:
            continue
        minimum = READING_BUDGET_MINIMUMS.get(key, 1)
        value = reading_budget.get(key)
        if not is_int_like(value) or value < minimum:
            issues.append(_issue("error", f"reading_budget.{key}", f"必须是 >={minimum} 的整数"))


def _check_section_summaries(b: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    summaries = b.get("section_summaries")
    if summaries in (None, ""):
        issues.append(_issue("error", "section_summaries", "必填；必须提供 impact/viewpoints/verification 三段关键洞见"))
        return
    if not isinstance(summaries, dict):
        issues.append(_issue("error", "section_summaries", "必须是对象"))
        return
    required = {
        "impact": "影响市场洞见",
        "viewpoints": "各方观点洞见",
        "verification": "验证证伪洞见",
    }
    for key, label in required.items():
        path = f"section_summaries.{key}"
        text = summaries.get(key)
        if not text:
            issues.append(_issue("error", path, "必填"))


def _check_visuals(
    b: dict[str, Any],
    issues: list[dict[str, Any]],
    ref_ids: set[Any],
    internal_ids: set[Any],
) -> None:
    visuals = b.get("visuals") if isinstance(b.get("visuals"), dict) else {}
    for key in ("summary_cards", "impact_chain"):
        if not isinstance(visuals.get(key), list):
            issues.append(_issue("error", f"visuals.{key}", "必须是数组"))
    summary_cards = visuals.get("summary_cards")
    if isinstance(summary_cards, list):
        if len(summary_cards) < 3:
            issues.append(_issue("advisory", "visuals.summary_cards", "首屏关键证据建议 3-4 条,少于 3 条会显得信息不足"))
        if len(summary_cards) > 4:
            issues.append(_issue("advisory", "visuals.summary_cards", "首屏只展示前 4 条关键证据,多余证据应放入增量信息或观点区"))
    impact_facts = visuals.get("impact_facts")
    if impact_facts is not None and not isinstance(impact_facts, list):
        issues.append(_issue("error", "visuals.impact_facts", "必须是数组"))
    elif isinstance(impact_facts, list):
        for i, item in enumerate(impact_facts):
            path = f"visuals.impact_facts[{i}]"
            if isinstance(item, str):
                continue
            if not isinstance(item, dict):
                issues.append(_issue("error", path, "必须是字符串或对象"))
                continue
            if "step" not in item:
                issues.append(_issue("advisory", f"{path}.step", "建议填写 step,让节点正文直接挂到对应传导步骤"))
            if not item.get("fact"):
                issues.append(_issue("error", f"{path}.fact", "必填"))
            if "refs" in item and not isinstance(item.get("refs"), list):
                issues.append(_issue("error", f"{path}.refs", "必须是数组"))
            elif isinstance(item.get("refs"), list):
                for ref_id in item["refs"]:
                    if ref_id not in ref_ids:
                        issues.append(_issue("error", f"{path}.refs", f"引用不存在：{ref_id!r}"))
                    elif ref_id in internal_ids:
                        issues.append(_issue("error", f"{path}.refs", f"不能引用 D/unverified 来源：{ref_id!r}"))
    if "timeline" in visuals:
        timeline = visuals.get("timeline")
        if not isinstance(timeline, list):
            issues.append(_issue("error", "visuals.timeline", "必须是数组"))
        else:
            for i, item in enumerate(timeline):
                path = f"visuals.timeline[{i}]"
                if not isinstance(item, dict):
                    issues.append(_issue("error", path, "必须是对象"))
                    continue
                for key in ("date", "label"):
                    if not item.get(key):
                        issues.append(_issue("error", f"{path}.{key}", "必填"))

def _check_analysis_mode_rules(b: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    meta = b.get("meta") if isinstance(b.get("meta"), dict) else {}
    visuals = b.get("visuals") if isinstance(b.get("visuals"), dict) else {}
    references = b.get("references") if isinstance(b.get("references"), list) else []
    mode = meta.get("analysis_mode")
    if not mode:
        return

    if mode in {"market_event", "policy_macro", "theme_watch"}:
        chain = visuals.get("impact_chain") if isinstance(visuals.get("impact_chain"), list) else []
        impact_facts = visuals.get("impact_facts") if isinstance(visuals.get("impact_facts"), list) else []
        if not impact_facts:
            issues.append(_issue("advisory", "visuals.impact_facts", f"{mode} 建议提供节点正文补足影响链"))
        elif chain:
            covered_steps = {
                item.get("step")
                for item in impact_facts
                if isinstance(item, dict) and isinstance(item.get("step"), int) and 1 <= item["step"] <= len(chain)
            }
            if len(covered_steps) < len(chain):
                issues.append(_issue("advisory", "visuals.impact_facts", f"{mode} 建议为每个影响链节点提供对应节点正文"))

    if mode == "policy_macro":
        public_refs = [
            r for r in references
            if isinstance(r, dict) and r.get("level") != "D" and r.get("type") != "unverified"
        ]
        has_authoritative_ref = any(
            r.get("type") == "official" or r.get("level") == "A"
            for r in public_refs
        )
        if not has_authoritative_ref:
            issues.append(_issue("quality_error", "references", "policy_macro 必须至少包含一个 official 或 A 级一手/准一手来源,不能只靠媒体转述或预测平台摘要"))
        top_public_refs = public_refs[:5]
        has_authoritative_domain = any(
            any(
                host_matches_domain(source_host(ref.get("url")), domain)
                for domain in POLICY_MACRO_AUTHORITY_DOMAINS
            )
            for ref in top_public_refs
        )
        if not has_authoritative_domain:
            issues.append(_issue("quality_error", "references", "policy_macro 前 5 个公开来源必须优先包含 ECB/Fed/CME 等央行、交易所、清算所或官方数据域名"))

    if mode == "dated_catalyst" and not (visuals.get("timeline") or b.get("timeline")):
        issues.append(_issue("advisory", "meta.analysis_mode", "dated_catalyst 建议提供 timeline 或 visuals.timeline"))


def _check_interpretation_and_timeline(
    b: dict[str, Any],
    issues: list[dict[str, Any]],
    ref_ids: set[Any],
    internal_ids: set[Any],
) -> None:
    for name in ("interpretation", "timeline", "update_diff"):
        if name in b and not isinstance(b.get(name), list):
            issues.append(_issue("error", name, "必须是数组"))
    interpretation = b.get("interpretation") if isinstance(b.get("interpretation"), list) else []
    if len(interpretation) < 3:
        issues.append(_issue("error", "interpretation", "至少 3 条,覆盖客观事实/市场反应/机构观点/反向证据等不同来源角色"))
    for name in ("interpretation", "update_diff"):
        for i, item in enumerate(b.get(name, []) or []):
            path = f"{name}[{i}]"
            if isinstance(item, dict):
                if name == "interpretation":
                    role = item.get("role")
                    if not role:
                        issues.append(_issue("advisory", f"{path}.role", "建议填写来源角色: 客观事实/市场反应/机构观点/反向证据/媒体报道"))
                    elif role not in INTERPRETATION_ROLES:
                        issues.append(_issue("error", f"{path}.role", f"必须是 {sorted(INTERPRETATION_ROLES)} 之一"))
                refs = item.get("refs")
                if not isinstance(refs, list):
                    issues.append(_issue("error", f"{path}.refs", "必须是数组"))
                else:
                    for ref_id in refs:
                        if ref_id not in ref_ids:
                            issues.append(_issue("error", f"{path}.refs", f"引用不存在：{ref_id!r}"))
                        elif ref_id in internal_ids:
                            issues.append(_issue("error", f"{path}.refs", f"不能引用 D/unverified 来源：{ref_id!r}"))
    for i, item in enumerate(b.get("timeline", []) or []):
        path = f"timeline[{i}]"
        if not isinstance(item, dict):
            issues.append(_issue("error", path, "必须是对象"))
            continue
        for key in ("date", "event"):
            if not item.get(key):
                issues.append(_issue("error", f"{path}.{key}", "必填"))
        if item.get("kind") not in (None, *TIMELINE_KINDS):
            issues.append(_issue("error", f"timeline[{i}].kind", f"必须是 {sorted(TIMELINE_KINDS)} 之一"))


def _check_verification(
    b: dict[str, Any],
    issues: list[dict[str, Any]],
    ref_ids: set[Any],
    internal_ids: set[Any],
) -> None:
    verification = b.get("verification")
    if verification in (None, ""):
        issues.append(_issue("error", "verification", "必填；必须提供 confirm 和 invalidate 结构化信号"))
        return
    if not isinstance(verification, dict):
        issues.append(_issue("error", "verification", "必须是对象"))
        return
    for group in ("confirm", "invalidate"):
        values = verification.get(group)
        path = f"verification.{group}"
        if not isinstance(values, list):
            issues.append(_issue("error", path, "必须是数组"))
            continue
        if len(values) < 2:
            issues.append(_issue("error", path, "至少 2 项"))
        for i, item in enumerate(values):
            item_path = f"{path}[{i}]"
            if not isinstance(item, dict):
                issues.append(_issue("error", item_path, "必须是对象"))
                continue
            for key in ("signal", "watch", "meaning"):
                if not item.get(key):
                    issues.append(_issue("error", f"{item_path}.{key}", "必填"))
            refs = item.get("refs", [])
            if refs in (None, ""):
                continue
            if not isinstance(refs, list):
                issues.append(_issue("error", f"{item_path}.refs", "必须是数组"))
                continue
            for ref_id in refs:
                if ref_id not in ref_ids:
                    issues.append(_issue("error", f"{item_path}.refs", f"引用不存在：{ref_id!r}"))
                elif ref_id in internal_ids:
                    issues.append(_issue("error", f"{item_path}.refs", f"不能引用 D/unverified 来源：{ref_id!r}"))


def _collect_frontstage_ref_ids(b: dict[str, Any]) -> set[Any]:
    used: set[Any] = set()
    dialog = b.get("dialog_brief") if isinstance(b.get("dialog_brief"), dict) else {}
    for item in dialog.get("key_points", []) or []:
        if isinstance(item, dict) and isinstance(item.get("refs"), list):
            used.update(item["refs"])
    for item in b.get("news_items", []) or []:
        if isinstance(item, dict) and item.get("ref") not in (None, ""):
            used.add(item.get("ref"))
    for section in ("interpretation", "update_diff"):
        for item in b.get(section, []) or []:
            if isinstance(item, dict) and isinstance(item.get("refs"), list):
                used.update(item["refs"])
    visuals = b.get("visuals") if isinstance(b.get("visuals"), dict) else {}
    for item in visuals.get("impact_facts", []) or []:
        if isinstance(item, dict) and isinstance(item.get("refs"), list):
            used.update(item["refs"])
    verification = b.get("verification") if isinstance(b.get("verification"), dict) else {}
    for group in ("confirm", "invalidate"):
        for item in verification.get(group, []) or []:
            if isinstance(item, dict) and isinstance(item.get("refs"), list):
                used.update(item["refs"])
    return used


def _check_source_usage(b: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    refs = b.get("references") if isinstance(b.get("references"), list) else []
    used = _collect_frontstage_ref_ids(b)
    for i, ref in enumerate(refs):
        if not isinstance(ref, dict):
            continue
        rid = ref.get("id")
        if ref.get("level") == "D" or ref.get("type") == "unverified":
            continue
        if rid not in used:
            issues.append(_issue("advisory", f"references[{i}]", "公开来源未被对话框依据、前台事实、观点、影响链或验证信号引用"))


def _check_optional_audit_fields(b: dict[str, Any], issues: list[dict[str, Any]], audit: bool) -> None:
    if not audit:
        return
    for key in ("query_log", "evidence_atoms", "coverage_gaps", "conflicts"):
        if key not in b:
            issues.append(_issue("advisory", key, "建议补齐内部审计字段"))
    if "evidence_atoms" in b and not isinstance(b.get("evidence_atoms"), list):
        issues.append(_issue("error", "evidence_atoms", "必须是数组"))
    if "query_log" in b and not isinstance(b.get("query_log"), list):
        issues.append(_issue("error", "query_log", "必须是数组"))
    if "coverage_gaps" in b and not isinstance(b.get("coverage_gaps"), list):
        issues.append(_issue("error", "coverage_gaps", "必须是数组"))
    if "conflicts" in b and not isinstance(b.get("conflicts"), list):
        issues.append(_issue("error", "conflicts", "必须是数组"))


def _check_news_image(issues: list[dict[str, Any]], path: str, image: Any) -> None:
    if image in (None, ""):
        return
    issues.append(_issue("advisory", path, "关键增量信息不渲染前置图片；请移除 image，构建会拒绝图片字段"))


def validate_payload(
    b: Any,
    *,
    strict: bool = False,
    audit: bool = False,
    fail_on_warning: bool = False,
    label: str = "validate",
) -> list[dict[str, Any]]:
    issues = collect_issues(b, strict=strict, audit=audit)
    report = issue_report(issues, fail_on_warning=fail_on_warning)
    errors = [i for i in issues if i["level"] == "error"]
    quality_errors = [i for i in issues if i["level"] == "quality_error"]
    advisories = [i for i in issues if i["level"] == "advisory"]
    for issue in quality_errors:
        print(f"[{label}][quality] {issue['path']}: {issue['message']}")
    for issue in advisories:
        print(f"[{label}][advisory] {issue['path']}: {issue['message']}")
    blocking = report["blocking_issues"]
    if blocking:
        lines = [f"[{i['level']}] {i['path']}: {i['message']}" for i in blocking]
        raise SystemExit(f"[{label}] briefing.json 校验失败:\n - " + "\n - ".join(lines))
    return issues


def issue_report(issues: list[dict[str, Any]], *, fail_on_warning: bool = False) -> dict[str, Any]:
    """Return a machine-readable validation report for external orchestrators."""
    _ = fail_on_warning  # Backward-compatible no-op: advisory issues never block delivery.
    blocking_levels = {"error", "quality_error"}
    counts = {
        "error": 0,
        "quality_error": 0,
        "advisory": 0,
    }
    for issue in issues:
        level = issue.get("level")
        if level in counts:
            counts[level] += 1
    blocking = []
    for issue in issues:
        if issue.get("level") not in blocking_levels:
            continue
        blocking.append(issue)
    advisories = [issue for issue in issues if issue.get("level") == "advisory"]
    return {
        "ok": not blocking,
        "issues": issues,
        "blocking_issues": blocking,
        "advisory_issues": advisories,
        "counts": counts,
        "max_repair_attempts": MAX_REPAIR_ATTEMPTS,
    }


def normalize_images(b: dict[str, Any]) -> dict[str, Any]:
    for item in b.get("news_items", []) or []:
        if isinstance(item, dict):
            item.pop("image", None)
    return b


def public_view(b: dict[str, Any]) -> dict[str, Any]:
    """Drop internal-only low-trust and audit material before injecting data into HTML."""
    out = copy.deepcopy(b)
    refs = out.get("references", [])
    internal_ids = {
        r.get("id")
        for r in refs
        if isinstance(r, dict) and (r.get("type") == "unverified" or r.get("level") == "D")
    }
    out["references"] = [r for r in refs if isinstance(r, dict) and r.get("id") not in internal_ids]
    public_ids = {r.get("id") for r in out["references"] if isinstance(r, dict)}
    out["news_items"] = [
        n
        for n in out.get("news_items", [])
        if isinstance(n, dict) and n.get("ref") in public_ids and not n.get("unverified")
    ]
    for section in ("interpretation", "update_diff"):
        cleaned_items = []
        for item in out.get(section, []) or []:
            if isinstance(item, dict):
                refs = item.get("refs")
                if isinstance(refs, list):
                    item["refs"] = [rid for rid in refs if rid in public_ids]
            cleaned_items.append(item)
        if section in out:
            out[section] = cleaned_items
    visuals = out.get("visuals") if isinstance(out.get("visuals"), dict) else {}
    impact_facts = visuals.get("impact_facts")
    if isinstance(impact_facts, list):
        for item in impact_facts:
            if isinstance(item, dict) and isinstance(item.get("refs"), list):
                item["refs"] = [rid for rid in item["refs"] if rid in public_ids]
    source_check = out.get("source_check") if isinstance(out.get("source_check"), dict) else {}
    out["source_check"] = {
        group: [rid for rid in source_check.get(group, []) if rid in public_ids]
        for group in ("official", "media", "institution")
    }
    for internal_key in ("query_log", "evidence_atoms", "coverage_gaps", "conflicts"):
        out.pop(internal_key, None)
    return out
