"""Scrape the VTF homepage top announcement banner."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from apps.header_scraper.services.parse import (
    BANNER_SELECTORS,
    extract_banner_html_from_page,
)

logger = logging.getLogger("header_scraper")

LANGUAGE_URLS = {
    "FR": "https://www.vtf-vacances.com/fr_FR/",
    "GB": "https://www.vtf-vacances.com/en_GB/",
}

NAV_TIMEOUT_MS = 45_000
SELECTOR_TIMEOUT_MS = 20_000
HTTP_TIMEOUT_SECONDS = 40.0

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


@dataclass
class BannerScrapeResult:
    """Outcome of one banner scrape (no DB writes)."""

    language: str
    source_url: str
    ok: bool
    banner_html: str = ""
    error: str = ""
    method: str = ""
    page_html: str = ""


def fetch_header_page_html(url: str, timeout: float = HTTP_TIMEOUT_SECONDS) -> str:
    """HTTP GET the header page HTML."""
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util import Retry

    retry = Retry(
        total=2,
        connect=2,
        read=1,
        status=1,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=set(Retry.DEFAULT_ALLOWED_METHODS),
    )
    adapter = HTTPAdapter(max_retries=retry)

    with requests.Session() as session:
        session.headers.update(HTTP_HEADERS)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        resp = session.get(url, timeout=timeout)
        resp.raise_for_status()
        if not resp.encoding:
            resp.encoding = "utf-8"
        return resp.text


def _dismiss_cookie_banners(page) -> None:
    """Best-effort click through common cookie consent UIs."""
    selectors = [
        "#onetrust-accept-btn-handler",
        "button:has-text('Tout accepter')",
        "button:has-text('Accepter')",
        "button:has-text('Accept all')",
        "button:has-text('Accept')",
    ]
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click(timeout=2_000)
                page.wait_for_timeout(400)
                return
        except Exception:
            continue


def _extract_banner_html(page) -> str:
    """Locate the topbar CMS node and return its inner HTML."""
    for sel in BANNER_SELECTORS:
        try:
            loc = page.locator(sel).first
            if loc.count() == 0:
                continue
            loc.wait_for(state="attached", timeout=SELECTOR_TIMEOUT_MS)
            html = loc.inner_html(timeout=5_000)
            if html and html.strip():
                return html.strip()
        except Exception as exc:
            logger.debug("header banner selector miss sel=%s err=%s", sel, exc)
            continue
    return ""


def _validate_language(language: str) -> BannerScrapeResult | None:
    language = (language or "FR").upper()
    if language not in LANGUAGE_URLS:
        return BannerScrapeResult(
            language=language,
            source_url="",
            ok=False,
            error=f"Unsupported language '{language}'. Use FR or GB.",
        )
    return None


def scrape_header_banner_html_http(language: str) -> BannerScrapeResult:
    """Tier 1: fetch page HTML over HTTP and extract the banner node."""
    language = (language or "FR").upper()
    invalid = _validate_language(language)
    if invalid:
        return invalid

    source_url = LANGUAGE_URLS[language]
    try:
        page_html = fetch_header_page_html(source_url)
    except Exception as exc:
        logger.warning(
            "header_scraper http fetch failed language=%s url=%s err=%s",
            language,
            source_url,
            exc,
        )
        return BannerScrapeResult(
            language=language,
            source_url=source_url,
            ok=False,
            error=(
                "Step 1 (HTTP Fetch) | scrape.py → scrape_header_banner_html_http() | "
                f"HTTP fetch failed: {exc}"
            ),
            method="http",
        )

    banner_html = extract_banner_html_from_page(page_html)
    if not banner_html:
        return BannerScrapeResult(
            language=language,
            source_url=source_url,
            ok=False,
            error=(
                "Step 1 (HTTP Fetch) | scrape.py → scrape_header_banner_html_http() | "
                "Banner node not found in HTTP page HTML."
            ),
            method="http",
            page_html=page_html,
        )

    return BannerScrapeResult(
        language=language,
        source_url=source_url,
        ok=True,
        banner_html=banner_html,
        method="http",
        page_html=page_html,
    )


def scrape_header_banner_html_llm(
    language: str,
    *,
    page_html: str = "",
) -> BannerScrapeResult:
    """Tier 3: use LLM to extract the banner from page HTML."""
    language = (language or "FR").upper()
    invalid = _validate_language(language)
    if invalid:
        return invalid

    source_url = LANGUAGE_URLS[language]
    try:
        from apps.header_scraper.services.llm_fallback import (
            extract_banner_html_with_llm,
            llm_fallback_enabled,
        )
    except ImportError:
        return BannerScrapeResult(
            language=language,
            source_url=source_url,
            ok=False,
            error=(
                "Step 3 (LLM Fallback) | scrape.py → scrape_header_banner_html_llm() | "
                "LLM fallback module is not installed."
            ),
            method="llm_fallback",
        )

    if not llm_fallback_enabled():
        return BannerScrapeResult(
            language=language,
            source_url=source_url,
            ok=False,
            error=(
                "Step 3 (LLM Fallback) | scrape.py → scrape_header_banner_html_llm() | "
                "LLM fallback is disabled."
            ),
            method="llm_fallback",
        )

    if not page_html:
        try:
            page_html = fetch_header_page_html(source_url)
        except Exception as exc:
            return BannerScrapeResult(
                language=language,
                source_url=source_url,
                ok=False,
                error=(
                    "Step 3 (LLM Fallback) | scrape.py → scrape_header_banner_html_llm() | "
                    f"LLM fallback page fetch failed: {exc}"
                ),
                method="llm_fallback",
            )

    try:
        banner_html = extract_banner_html_with_llm(
            page_html,
            language,
            base_url=source_url,
        )
    except Exception as exc:
        logger.exception(
            "header_scraper llm fallback failed language=%s url=%s",
            language,
            source_url,
        )
        return BannerScrapeResult(
            language=language,
            source_url=source_url,
            ok=False,
            error=(
                "Step 3 (LLM Fallback) | scrape.py → scrape_header_banner_html_llm() | "
                f"LLM fallback failed: {exc}"
            ),
            method="llm_fallback",
        )

    if not banner_html:
        return BannerScrapeResult(
            language=language,
            source_url=source_url,
            ok=False,
            error=(
                "Step 3 (LLM Fallback) | scrape.py → scrape_header_banner_html_llm() | "
                "LLM fallback returned no parseable banner."
            ),
            method="llm_fallback",
        )

    return BannerScrapeResult(
        language=language,
        source_url=source_url,
        ok=True,
        banner_html=banner_html,
        method="llm_fallback",
        page_html=page_html,
    )


def scrape_header_banner_html_playwright(language: str) -> BannerScrapeResult:
    """Tier 2: open the VTF homepage in Chromium and extract the top banner HTML."""
    language = (language or "FR").upper()
    invalid = _validate_language(language)
    if invalid:
        return invalid

    source_url = LANGUAGE_URLS[language]
    try:
        from playwright.sync_api import TimeoutError as PWTimeout
        from playwright.sync_api import sync_playwright
    except ImportError:
        return BannerScrapeResult(
            language=language,
            source_url=source_url,
            ok=False,
            error=(
                "Step 2 (Playwright Scrape) | scrape.py → scrape_header_banner_html_playwright() | "
                "Playwright is not installed. "
                "Run: pip install playwright && playwright install chromium"
            ),
            method="playwright",
        )

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                context = browser.new_context(
                    locale="fr-FR" if language == "FR" else "en-GB",
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/126.0.0.0 Safari/537.36"
                    ),
                )
                page = context.new_page()
                try:
                    page.goto(
                        source_url,
                        wait_until="domcontentloaded",
                        timeout=NAV_TIMEOUT_MS,
                    )
                except Exception as exc:
                    # Still try whatever DOM landed.
                    logger.warning(
                        "header_scraper goto partial language=%s url=%s err=%s",
                        language,
                        source_url,
                        exc,
                    )

                try:
                    page.wait_for_load_state("networkidle", timeout=12_000)
                except PWTimeout:
                    pass

                _dismiss_cookie_banners(page)
                banner_html = _extract_banner_html(page)
                context.close()
            finally:
                browser.close()
    except Exception as exc:
        logger.exception(
            "header_scraper playwright failed language=%s url=%s", language, source_url
        )
        return BannerScrapeResult(
            language=language,
            source_url=source_url,
            ok=False,
            error=(
                "Step 2 (Playwright Scrape) | scrape.py → scrape_header_banner_html_playwright() | "
                f"Playwright scrape failed: {exc}"
            ),
            method="playwright",
        )

    if not banner_html:
        return BannerScrapeResult(
            language=language,
            source_url=source_url,
            ok=False,
            error=(
                "Step 2 (Playwright Scrape) | scrape.py → scrape_header_banner_html_playwright() | "
                "Banner node not found on page (selector cascade empty)."
            ),
            method="playwright",
        )

    return BannerScrapeResult(
        language=language,
        source_url=source_url,
        ok=True,
        banner_html=banner_html,
        method="playwright",
    )


def scrape_header_banner_html(language: str) -> BannerScrapeResult:
    """Scrape with Tier 1 HTTP, Tier 2 Playwright, then Tier 3 LLM fallback."""
    http_result = scrape_header_banner_html_http(language)
    if http_result.ok:
        return http_result
    if not http_result.source_url:
        return http_result

    playwright_result = scrape_header_banner_html_playwright(language)
    if playwright_result.ok:
        return playwright_result

    llm_result = scrape_header_banner_html_llm(
        language,
        page_html=http_result.page_html,
    )
    if llm_result.ok:
        return llm_result

    errors = " | ".join(
        e for e in (http_result.error, playwright_result.error, llm_result.error) if e
    )
    return BannerScrapeResult(
        language=http_result.language,
        source_url=http_result.source_url,
        ok=False,
        error=errors or "Header banner scrape failed.",
        method="http+playwright+llm_fallback",
    )


def scrape_header_banner_html_from_string(
    language: str,
    page_or_banner_html: str,
    *,
    source_url: Optional[str] = None,
) -> BannerScrapeResult:
    """Test helper: treat preloaded HTML as a successful Playwright extract."""
    from apps.header_scraper.services.parse import extract_banner_html_from_page

    language = (language or "FR").upper()
    url = source_url or LANGUAGE_URLS.get(language, "")
    # If the string already looks like the inner banner, use it; else extract.
    if "nq-c-Wysiwyg" in page_or_banner_html or "swiper-Topbar" in page_or_banner_html:
        banner_html = extract_banner_html_from_page(page_or_banner_html)
    else:
        banner_html = page_or_banner_html.strip()

    if not banner_html:
        return BannerScrapeResult(
            language=language,
            source_url=url,
            ok=False,
            error="Banner HTML empty in fixture.",
        )
    return BannerScrapeResult(
        language=language,
        source_url=url,
        ok=True,
        banner_html=banner_html,
        method="fixture",
    )
