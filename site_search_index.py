"""Build a local, privacy-friendly search index for the static site."""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote


_SKIP_DIRS = {
    ".git", ".cache", "__pycache__", ".pytest_cache", "vendor", "tests",
    "docs", "samples", "backups", "release", "node_modules",
}
_SKIP_TAGS = {"script", "style", "nav", "header", "footer", "noscript", "svg"}
_VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}
_MAX_PAGE_TEXT = 24000


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


class _PageText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.h1_parts: list[str] = []
        self.body_parts: list[str] = []
        self.description = ""
        self.noindex = False
        self.redirect = False
        self.rm_data: dict | None = None
        self._in_title = False
        self._in_h1 = False
        self._ignored_root = ""
        self._ignored_depth = 0
        self._capture_rm = False
        self._rm_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if self._ignored_depth:
            if tag not in _VOID_TAGS:
                self._ignored_depth += 1
            return
        if tag in _SKIP_TAGS:
            self._ignored_root = tag
            self._ignored_depth = 1
            self._capture_rm = tag == "script" and attr.get("id") == "rm-data"
            if self._capture_rm:
                self._rm_parts = []
            return
        if tag == "title":
            self._in_title = True
        elif tag == "h1":
            self._in_h1 = True
        elif tag == "meta":
            name = (attr.get("name") or "").lower()
            content = attr.get("content") or ""
            if name == "description":
                self.description = content
            if name == "robots" and "noindex" in content.lower():
                self.noindex = True
            if (attr.get("http-equiv") or "").lower() == "refresh":
                self.redirect = True
        for key in ("aria-label", "title", "alt"):
            val = attr.get(key)
            if val:
                self.body_parts.append(val)

    def handle_endtag(self, tag: str) -> None:
        if self._ignored_depth:
            if tag == self._ignored_root and self._ignored_depth == 1:
                if self._capture_rm:
                    try:
                        value = json.loads("".join(self._rm_parts))
                        if isinstance(value, dict):
                            self.rm_data = value
                    except (json.JSONDecodeError, TypeError):
                        pass
                self._ignored_root = ""
                self._ignored_depth = 0
                self._capture_rm = False
            else:
                self._ignored_depth = max(1, self._ignored_depth - 1)
            return
        if tag == "title":
            self._in_title = False
        elif tag == "h1":
            self._in_h1 = False

    def handle_data(self, data: str) -> None:
        if self._capture_rm:
            self._rm_parts.append(data)
            return
        if self._ignored_depth:
            return
        if self._in_title:
            self.title_parts.append(data)
        if self._in_h1:
            self.h1_parts.append(data)
        self.body_parts.append(data)


def _strings(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [part for item in value.values() for part in _strings(item)]
    if isinstance(value, list):
        return [part for item in value for part in _strings(item)]
    return []


def _make_entry(title: str, url: str, summary: str, text: str, category: str) -> dict:
    return {
        "title": _clean(title) or "未命名内容",
        "url": url,
        "summary": _clean(summary)[:500],
        "text": _clean(text)[:_MAX_PAGE_TEXT],
        "category": category,
    }


def _map_entries(data: dict, page_url: str) -> list[dict]:
    entries: list[dict] = []
    refs = {
        str(ref.get("id")): str(ref.get("title", ""))
        for ref in data.get("references", [])
        if isinstance(ref, dict) and ref.get("id")
    }

    def view_url(view: str, anchor: str = "", extra: str = "") -> str:
        query = "view=" + quote(view)
        if extra:
            query += "&" + extra
        return page_url + "?" + query + (("#" + quote(anchor, safe="-_")) if anchor else "")

    for case in data.get("impactCases", []):
        if not isinstance(case, dict) or not case.get("id"):
            continue
        parts = [
            case.get("title", ""), case.get("fieldLabel", ""), case.get("evidenceLabel", ""),
            case.get("problem", ""), case.get("contribution", ""), case.get("boundary", ""),
            case.get("searchTerms", ""),
        ]
        for algo in case.get("algorithms", []):
            if isinstance(algo, dict):
                parts.extend((algo.get("name", ""), algo.get("type", ""), algo.get("result", "")))
        parts.extend(refs.get(str(ref), "") for ref in case.get("refs", []))
        parts.extend(
            team.get("name", "") for team in data.get("teams", [])
            if isinstance(team, dict) and team.get("id") in case.get("teamIds", [])
        )
        entries.append(_make_entry(
            case.get("title", "研究案例"),
            view_url("impact", "impact-" + str(case["id"])),
            case.get("problem", "") or case.get("contribution", ""),
            " ".join(_strings(parts)),
            "问题成果",
        ))

    for team in data.get("teams", []):
        if not isinstance(team, dict) or not team.get("id"):
            continue
        entries.append(_make_entry(
            team.get("name", "研究团队"),
            view_url("teams", "rm-team-" + str(team["id"])),
            team.get("focus", "") or team.get("contribution", ""),
            " ".join(_strings(team)),
            "研究团队",
        ))

    for app in data.get("applications", []):
        if not isinstance(app, dict) or not app.get("id"):
            continue
        entries.append(_make_entry(
            app.get("name", "应用问题"),
            view_url("applications", "rm-app-" + str(app["id"])),
            app.get("decision", "") or app.get("summary", ""),
            " ".join(_strings(app)),
            "应用问题",
        ))

    for node in data.get("nodes", []):
        if not isinstance(node, dict) or not node.get("id"):
            continue
        entries.append(_make_entry(
            node.get("title", node.get("name", "研究节点")),
            view_url("history", extra="node=" + quote(str(node["id"]), safe="-_")),
            node.get("summary", "") or node.get("contribution", ""),
            " ".join(_strings(node)),
            "研究主线",
        ))
    return entries


def generate(root: str | Path) -> tuple[int, int]:
    root = Path(root)
    entries: list[dict] = []
    dynamic_entries: list[dict] = []
    for path in sorted(root.rglob("*.html")):
        relative = path.relative_to(root)
        if path.name.lower() == "404.html" or any(part.lower() in _SKIP_DIRS for part in relative.parts):
            continue
        try:
            parser = _PageText()
            parser.feed(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        if parser.noindex or parser.redirect:
            continue
        title = _clean(" ".join(parser.title_parts)) or _clean(" ".join(parser.h1_parts))
        if not title:
            continue
        text = _clean(" ".join([parser.description, *parser.body_parts]))
        page_url = relative.as_posix()
        entries.append(_make_entry(title, page_url, parser.description, text, "页面"))
        if parser.rm_data:
            dynamic_entries.extend(_map_entries(parser.rm_data, page_url))

    entries.extend(dynamic_entries)
    payload = json.dumps(
        {"version": 1, "items": entries},
        ensure_ascii=False,
        separators=(",", ":"),
    ) + "\n"
    target = root / "search-index.json"
    target.write_text(payload, encoding="utf-8", newline="\n")
    return len(entries), target.stat().st_size
