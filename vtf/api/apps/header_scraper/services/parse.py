"""Parse VTF topbar CMS HTML into ordered text/link segments.

Uses the stdlib HTML parser only — no new third-party dependency.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse


# Prefer the Wysiwyg text node; fall back to the whole topbar item.
BANNER_SELECTORS = [
    ".swiper-Topbar .nq-c-BlockCms-Wysiwyg-text",
    ".swiper-Topbar .nq-c-Wysiwyg",
    ".nq-c-Topbar-item .nq-c-BlockCms-Wysiwyg-text",
    ".nq-c-Topbar-item",
]

_LANG_SWITCHER_RE = re.compile(
    r'<div[^>]*class="[^"]*nq-c-Header-Language[^"]*"[^>]*>.*?</div>\s*',
    re.IGNORECASE | re.DOTALL,
)


def extract_banner_html_from_page(page_html: str) -> str:
    """Pull the topbar CMS block out of a full page HTML document.

    Used by tests with fixtures; Playwright normally returns the node HTML
    directly via ``inner_html()``.
    """
    cleaned = _LANG_SWITCHER_RE.sub("", page_html)
    # Prefer the Wysiwyg container content.
    for pattern in (
        r'<div[^>]*class="[^"]*nq-c-BlockCms-Wysiwyg-text[^"]*"[^>]*>(.*?)</div>',
        r'<div[^>]*class="[^"]*nq-c-Wysiwyg[^"]*"[^>]*>(.*?)</div>',
        r'<li[^>]*class="[^"]*nq-c-Topbar-item[^"]*"[^>]*>(.*?)</li>',
    ):
        match = re.search(pattern, cleaned, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
    return ""


def parse_banner_html(html: str, *, base_url: str) -> list[dict[str, Any]]:
    """Convert banner HTML into ordered ``text`` / ``link`` / ``br`` segments."""
    if not html or not html.strip():
        return []

    parser = _BannerSegmentParser(base_url=base_url)
    parser.feed(html)
    parser.close()
    return _normalize_segments(parser.segments)


def segments_to_plain_text(segments: list[dict[str, Any]]) -> str:
    """Flatten segments to a single plain-text string."""
    parts: list[str] = []
    for seg in segments:
        kind = seg.get("type")
        if kind == "text":
            parts.append(str(seg.get("value") or ""))
        elif kind == "link":
            parts.append(str(seg.get("text") or ""))
        elif kind == "br":
            parts.append(" ")
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def resolve_href(href: str, base_url: str) -> str | None:
    """Resolve relative links; keep only http(s) URLs."""
    if not href:
        return None
    href = href.strip()
    if href.startswith("#") or href.lower().startswith("javascript:"):
        return None
    absolute = urljoin(base_url, href)
    parsed = urlparse(absolute)
    if parsed.scheme not in ("http", "https"):
        return None
    return absolute


class _BannerSegmentParser(HTMLParser):
    """Walk banner HTML and emit text/link/br segments in document order."""

    def __init__(self, *, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.segments: list[dict[str, Any]] = []
        self._link_depth = 0
        self._link_href: str | None = None
        self._link_parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._skip_depth:
            self._skip_depth += 1
            return

        attr = {k.lower(): (v or "") for k, v in attrs}
        classes = attr.get("class", "")

        # Never include the language switcher if it slipped into the HTML.
        if "nq-c-header-language" in classes.lower() or tag == "select":
            self._skip_depth = 1
            return

        if tag == "br":
            self._flush_link()
            self.segments.append({"type": "br"})
            return

        if tag == "a" and self._link_depth == 0:
            self._flush_text_buffer_noop()
            self._link_depth = 1
            self._link_href = resolve_href(attr.get("href", ""), self.base_url)
            self._link_parts = []
            return

        if self._link_depth:
            self._link_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if self._skip_depth:
            self._skip_depth -= 1
            return

        if self._link_depth:
            self._link_depth -= 1
            if self._link_depth == 0 and tag == "a":
                text = "".join(self._link_parts)
                text = _collapse_ws(text)
                if text and self._link_href:
                    self.segments.append(
                        {"type": "link", "text": text, "href": self._link_href}
                    )
                elif text:
                    self.segments.append({"type": "text", "value": text})
                self._link_href = None
                self._link_parts = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._link_depth:
            self._link_parts.append(data)
            return
        if not data:
            return
        # Preserve intentional spaces around tags; collapse later.
        self.segments.append({"type": "text", "value": data})

    def _flush_link(self) -> None:
        return

    def _flush_text_buffer_noop(self) -> None:
        return


def _collapse_ws(value: str) -> str:
    return re.sub(r"[ \t\r\f\v]+", " ", value).replace("\xa0", " ").strip()


def _normalize_segments(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge adjacent text nodes and drop empty ones."""
    out: list[dict[str, Any]] = []
    for seg in raw:
        kind = seg.get("type")
        if kind == "text":
            value = str(seg.get("value") or "").replace("\xa0", " ")
            # Keep spaces that separate links; trim only fully empty.
            if value == "":
                continue
            if out and out[-1].get("type") == "text":
                out[-1]["value"] = out[-1]["value"] + value
            else:
                out.append({"type": "text", "value": value})
        elif kind == "link":
            text = _collapse_ws(str(seg.get("text") or ""))
            href = seg.get("href")
            if not text or not href:
                continue
            out.append({"type": "link", "text": text, "href": href})
        elif kind == "br":
            # Avoid leading / duplicate breaks.
            if not out or out[-1].get("type") == "br":
                continue
            out.append({"type": "br"})

    # Trim whitespace-only text edges and trailing br.
    while out and out[0].get("type") == "text":
        out[0]["value"] = out[0]["value"].lstrip()
        if out[0]["value"]:
            break
        out.pop(0)
    while out and out[-1].get("type") == "br":
        out.pop()
    while out and out[-1].get("type") == "text":
        out[-1]["value"] = out[-1]["value"].rstrip()
        if out[-1]["value"]:
            break
        out.pop()

    # Collapse runs of whitespace inside text nodes (keep single spaces).
    for seg in out:
        if seg.get("type") == "text":
            seg["value"] = re.sub(r"[ \t\r\f\v]+", " ", seg["value"])

    return out
