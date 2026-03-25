"""
Source evaluation — verify relevance, score sources, and find better sources
using Gemini AI.
"""

import asyncio
import logging
import re

import httpx
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
from playwright.async_api import async_playwright
from urllib.parse import urlparse

from config import get_settings
from .rate_limiter import get_rate_limiter
from .url_resolver import is_blocked_domain, is_internal_url, resolve_url

logger = logging.getLogger(__name__)


async def verify_source_relevance(source_url: str, title: str, description: str) -> bool:
    """
    Fetches the content of a source URL and asks Gemini if it directly corroborates
    the given scandal. Returns True if relevant, False otherwise.
    """
    if not source_url or not source_url.startswith("http"):
        return False

    # SSRF protection — reject internal/private URLs
    if is_internal_url(source_url):
        logger.info("Internal URL rejected (SSRF protection): %s", source_url[:60])
        return False

    # Fast-reject blocked platforms before any network call
    if is_blocked_domain(source_url):
        logger.info("Blocked domain – rejected: %s", source_url[:60])
        return False

    logger.info("[Gemini-Verify] Verifying relevance of: %s...", source_url[:60])

    # 1. Fetch content
    html_content = ""
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
            resp = await client.get(source_url, headers=headers)
            resp.raise_for_status()
            html_content = resp.text
    except Exception as e:
        logger.warning("httpx failed (%s), trying Playwright fallback...", e)
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
                )
                page = await context.new_page()
                await page.goto(source_url, wait_until="domcontentloaded", timeout=15000)
                html_content = await page.content()
                await browser.close()
        except Exception as p_err:
            logger.exception("Playwright also failed: %s. Cannot verify source.", p_err)
            return False

    if not html_content:
        return False

    # 2. Extract text
    text_content = ""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        for script in soup(["script", "style"]):
            script.decompose()
        text_content = soup.get_text(separator=' ', strip=True)
    except Exception as e:
        logger.exception("Failed to extract text: %s", e)
        return False

    # Prune to first ~15,000 chars to save tokens
    text_content = text_content[:15000]

    if len(text_content) < 100:
        logger.info("Extracted text too short to evaluate.")
        return False

    # 3. Ask Gemini for a YES/NO evaluation
    try:
        settings = get_settings()
        client = genai.Client(api_key=settings.gemini_api_key)

        prompt = f"""
        You are a strict fact-checker. You must determine if the provided webpage text DIRECTLY CORROBORATES the described scandal.

        Scandal Title: {title}
        Scandal Description: {description}

        Webpage Text Snippet:
        ---
        {text_content}
        ---

        Does the text above explicitly mention or provide clear contextual evidence for the event, song, or controversy described?
        If it discusses the subject matter (e.g., the song itself, the tour, the statement, or the backlash), answer YES. It does NOT need to use the word "scandal".
        If it only mentions the artist's name but discusses a completely unrelated topic (like a different concert or album), answer NO.
        
        Answer EXACTLY with a single word: YES or NO.
        """

        await get_rate_limiter().acquire(uses_search=False)
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-3-flash-preview",
            contents=prompt,
            config=types.GenerateContentConfig(
                 max_output_tokens=5
            )
        )

        result = response.text.strip().upper()
        is_relevant = "YES" in result
        logger.info("Result: %s -> Relevant: %s", result, is_relevant)
        return is_relevant

    except Exception as e:
        logger.exception("Evaluation failed: %s", e)
        # If verification mechanism fails, default to keeping it (True)
        return True


async def score_source_relevance(source_url: str, scandal_title: str, scandal_description: str) -> int:
    """
    Scores the relevance of a source URL to a given scandal on a 0-10 scale.

    Primary:  Gemini url_context (Gemini fetches the URL itself)
    Fallback: httpx -> Playwright (manual fetch + BeautifulSoup extraction)

    Returns an integer score (0-10). Returns 0 on error or blocked domain.
    A score > 7 (i.e. 8, 9, 10) is considered accepted.
    """
    if not source_url or not source_url.startswith("http"):
        return 0

    # SSRF protection
    if is_internal_url(source_url):
        logger.info("Internal URL rejected (SSRF protection): %s", source_url[:60])
        return 0

    if is_blocked_domain(source_url):
        logger.info("Blocked domain – score 0: %s", source_url[:60])
        return 0

    logger.info("Scoring: %s...", source_url[:60])

    SCORE_PROMPT = f"""You are a strict relevance evaluator. Read the content at the given URL and rate how relevant it is to the described scandal/controversy on a scale from 0 to 10.

0 = completely unrelated to this specific event.
10 = directly and explicitly about this exact event.

Scandal Title: {scandal_title}
Scandal Description: {scandal_description}

URL to evaluate: {source_url}

Rules:
- Score 0 if the article does not mention this event at all.
- Score 5-7 if it loosely covers the topic or mentions the artist but not this specific event.
- Score 8-10 if it explicitly discusses this event, controversy, or the specific works/statements involved.
- Respond with ONLY a single integer between 0 and 10. No explanation."""

    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)

    # ── Primary: Gemini url_context ──
    try:
        await get_rate_limiter().acquire(uses_search=False)
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-3-flash-preview",
            contents=SCORE_PROMPT,
            config=types.GenerateContentConfig(
                tools=[{"url_context": {}}],
            )
        )
        raw = ""
        if response.text:
            raw = response.text.strip()
        elif response.candidates:
            for part in response.candidates[0].content.parts:
                if hasattr(part, "text") and part.text:
                    raw += part.text
            raw = raw.strip()
        match = re.search(r'\d+', raw)
        if match:
            score = max(0, min(10, int(match.group())))
            logger.info("url_context score %s/10 for: %s", score, source_url[:60])
            return score
        logger.info("url_context returned no score (raw='%s'), falling back...", raw[:80])
    except Exception as e:
        logger.warning("url_context failed (%s), falling back to manual fetch...", e)

    # ── Fallback: manual fetch -> BeautifulSoup -> Gemini text prompt ──
    html_content = ""
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as http:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
            resp = await http.get(source_url, headers=headers)
            resp.raise_for_status()
            html_content = resp.text
    except Exception as e:
        logger.warning("httpx failed (%s), trying Playwright...", e)
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
                )
                page = await context.new_page()
                await page.goto(source_url, wait_until="domcontentloaded", timeout=15000)
                html_content = await page.content()
                await browser.close()
        except Exception as p_err:
            logger.exception("Playwright also failed: %s. Scoring as 0.", p_err)
            return 0

    if not html_content:
        return 0

    try:
        soup = BeautifulSoup(html_content, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        text_content = soup.get_text(separator=" ", strip=True)[:15000]
    except Exception:
        text_content = re.sub("<[^<]+?>", " ", html_content)[:15000]

    if len(text_content) < 100:
        logger.info("Page content too short. Scoring as 0.")
        return 0

    text_prompt = f"""You are a relevance evaluator. Rate how relevant the following article text is to the described scandal/controversy on a scale from 0 to 10.

0 = completely unrelated. 10 = directly and explicitly about this exact event.

Scandal Title: {scandal_title}
Scandal Description: {scandal_description}

Article Text (may be in any language):
---
{text_content}
---

Scoring guide:
- 0-3: Article does not mention the artist or this event at all.
- 4-6: Article mentions the artist or loosely related topic but not this specific event.
- 7-8: Article covers this specific event, controversy, or the people/works involved, even if briefly.
- 9-10: Article is directly and primarily about this exact event.
- Respond with ONLY a single integer between 0 and 10. No explanation."""

    try:
        await get_rate_limiter().acquire(uses_search=False)
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-3-flash-preview",
            contents=text_prompt,
            config=types.GenerateContentConfig(max_output_tokens=5)
        )
        raw = response.text.strip()
        match = re.search(r'\d+', raw)
        score = int(match.group()) if match else 0
        score = max(0, min(10, score))
        logger.info("Fallback score %s/10 for: %s", score, source_url[:60])
        return score
    except RuntimeError:
        raise
    except Exception as e:
        logger.exception("Fallback scoring failed: %s", e)
        return 0


async def find_better_sources(artist_name: str, scandal_title: str, scandal_description: str) -> list[dict]:
    """
    Uses Google Grounding to search for NEW, reliable sources for a specific scandal.
    Returns a list of dictionaries with 'url' and 'title'. Pre-filtered by domain blocklist.
    """
    logger.info("[Gemini-Heal] Hunting for better sources for: %s", scandal_title)

    try:
        settings = get_settings()
        client = genai.Client(api_key=settings.gemini_api_key)

        prompt = f"""
        Find 1 to 5 reliable, high-quality news articles, interviews, or credible sources that corroborate or discuss the following event, song, or controversy regarding the artist "{artist_name}".

        Topic Title: {scandal_title}
        Topic Description: {scandal_description}

        Return the results strictly as a JSON array of objects, with no markdown formatting and no extra text.
        Even if the source only covers a part of the event or just discusses the song/art piece in question, include it. It does not need to explicitly call it a "scandal".
        Example:
        [
          {{"url": "https://www.bbc.com/news/...", "title": "BBC News"}},
          {{"url": "https://www.rollingstone.com/...", "title": "Rolling Stone"}}
        ]
        """

        await get_rate_limiter().acquire(uses_search=True)
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-3-flash-preview",
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[{"google_search": {}}],
                response_mime_type="application/json"
            )
        )

        # Grounding chunks (new API style)
        grounding_urls = {}
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                metadata = candidate.grounding_metadata
                if hasattr(metadata, 'grounding_chunks') and metadata.grounding_chunks:
                    async with httpx.AsyncClient(
                        follow_redirects=True,
                        timeout=8,
                        headers={"User-Agent": "Mozilla/5.0"},
                    ) as http:
                        for chunk in metadata.grounding_chunks:
                            if hasattr(chunk, 'web') and chunk.web:
                                try:
                                    uri = chunk.web.uri
                                    title = chunk.web.title
                                    if "vertexaisearch" in uri:
                                         resolved = await resolve_url(http, uri, title)
                                         uri = resolved.get("url", uri)
                                         title = resolved.get("title", title)

                                         if "vertexaisearch" in uri:
                                             logger.warning("Skipping unresolved vertexaisearch source: %s", uri)
                                             continue

                                    grounding_urls[uri] = title
                                except Exception as e:
                                    logger.exception("Chunk parsing error: %s", e)

        results = []
        for url, site_title in grounding_urls.items():
            if is_blocked_domain(url):
                logger.info("Blocked domain filtered: %s", url[:60])
                continue
            results.append({"url": url, "title": site_title})

        logger.info("Found %s new potential sources.", len(results))
        return results

    except Exception as e:
        logger.exception("Failed to find new sources: %s", e)
        return []
