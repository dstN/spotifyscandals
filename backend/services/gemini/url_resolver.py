"""
URL resolution and domain filtering utilities.
Handles redirect chains, SSRF protection, and blocked domains.
"""

import asyncio
import ipaddress
import logging
import os
from urllib.parse import urlparse

import httpx
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)


# ─── Source Blocklist ───
# YouTube and Reddit are not acceptable journalistic sources.
BLOCKED_SOURCE_DOMAINS = {
    "youtube.com", "youtu.be",
    "reddit.com", "redd.it",
}


def is_blocked_domain(url: str) -> bool:
    """Returns True if the URL belongs to a blocked platform."""
    try:
        hostname = urlparse(url).hostname or ""
        hostname = hostname.lower().removeprefix("www.")
        return any(hostname == blocked or hostname.endswith("." + blocked) for blocked in BLOCKED_SOURCE_DOMAINS)
    except Exception:
        return False


def is_internal_url(url: str) -> bool:
    """Returns True if the URL targets a private/internal address (SSRF protection)."""
    BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal"}
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return True
        hostname = (parsed.hostname or "").lower()
        if hostname in BLOCKED_HOSTS:
            return True
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return True
        except ValueError:
            pass  # Not an IP literal — hostname is fine
    except Exception:
        return True
    return False


async def resolve_url_ultra(uri: str, fallback_title: str | None) -> dict:
    """
    Final fallback: Use headless chrome to follow redirects.
    Handles JS-based redirects and sophisticated anti-bot checks.
    """
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            # Wait for navigation to complete
            await page.goto(uri, wait_until="networkidle", timeout=15000)
            final_url = page.url
            await browser.close()

            if final_url and final_url != uri:
                domain = urlparse(final_url).hostname or fallback_title or ""
                title = domain.removeprefix("www.")
                return {"url": final_url, "title": title or fallback_title}
    except Exception as e:
        logger.exception("Playwright failed: %s", e)
    return {"url": uri, "title": fallback_title}


async def resolve_url_deep(uri: str, fallback_title: str | None) -> dict:
    """
    Use curl as a deep-resolve fallback.
    """
    try:
        # -L follow redirects, -s silent, -o NUL don't output body, -w final URL
        devnull = "NUL" if os.name == "nt" else "/dev/null"
        process = await asyncio.create_subprocess_exec(
            "curl", "-Ls", "-o", devnull, "-w", "%{url_effective}", "--max-time", "10", uri,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await process.communicate()
        final_url = stdout.decode().strip()

        if final_url and final_url != uri:
            domain = urlparse(final_url).hostname or fallback_title or ""
            title = domain.removeprefix("www.")
            return {"url": final_url, "title": title or fallback_title}
    except Exception:
        pass

    # Final fallback if curl fails
    return await resolve_url_ultra(uri, fallback_title)


async def resolve_url(client: httpx.AsyncClient, uri: str, fallback_title: str | None) -> dict:
    """
    Follow the vertexaisearch redirect chain and return the real final URL.
    Falls back to resolve_url_deep if httpx fails.
    """
    try:
        resp = await client.head(uri, follow_redirects=True, timeout=8)
        final_url = str(resp.url)
        # Use hostname as title (strip www.)
        domain = urlparse(final_url).hostname or fallback_title or ""
        title = domain.removeprefix("www.")
        return {"url": final_url, "title": title or fallback_title}
    except Exception:
        # Fallback to deep resolve with curl
        return await resolve_url_deep(uri, fallback_title)


# Backwards-compatible aliases (used by scanner_cli.py)
_resolve_url_ultra = resolve_url_ultra
_resolve_url_deep = resolve_url_deep
_resolve_url = resolve_url
