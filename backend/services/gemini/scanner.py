"""
Core Gemini scanning — single-artist and multi-artist scandal scanning
with Google Search grounding.
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from google import genai
from google.genai import types

from config import get_settings
from .rate_limiter import get_rate_limiter
from .url_resolver import resolve_url, is_blocked_domain
from .source_matcher import match_sources_to_scandals

logger = logging.getLogger(__name__)


def _get_client() -> genai.Client:
    """Create a configured Gemini client."""
    settings = get_settings()
    return genai.Client(api_key=settings.gemini_api_key)


def _build_prompt(artist_name: str, spotify_id: str, current_date: str, existing_scandals: list = None) -> str:
    """
    Build the investigative research prompt for a single artist.
    Uses the user-defined prompt template with Google Search grounding.
    """
    spotify_url = f"https://open.spotify.com/artist/{spotify_id}"

    exclusion_text = ""
    if existing_scandals and len(existing_scandals) > 0:
        exclusion_text = "\n\nExclude the following scandals from the JSON output because they are already known/recorded in the database:\n"
        exclusion_text += json.dumps(existing_scandals, indent=2)

    return f"""You are an investigative research assistant. Your task is to find **all scandals and controversies** involving the artist "{artist_name}" (Musician/Artist) up to the date "{current_date}". If available, you can also reference the artist's Spotify page: {spotify_url}.

Instructions:
1. Collect **all known scandals and controversies** involving the artist until the given date. Use the Google Search tool to verify information. (Note: Wikipedia and other neutral sources often use the term "controversies").
2. **STRICT IDENTITY VERIFICATION**: Do NOT include any information, controversies, or sources for people with similar names who are not the specific artist "{artist_name}". For example, if searching for a musician, do not return results for actors, politicians, or other public figures with similar names.
3. For each scandal/controversy, provide:
   - A concise **title** (short, descriptive name of the event)
   - A brief **description** (1-2 sentences summarizing the event)
4. Output the results strictly as **valid JSON** using the following structure (keep the key as "scandals" for compatibility):

{{
  "scandals": [
    {{
      "title": "Title of scandal/controversy 1",
      "description": "Short description of the event"
    }}
  ]
}}

5. If no scandals are found, return:
{{
  "scandals": []
}}
{exclusion_text}

Additional rules:
- Only provide valid JSON, **no extra text or explanations**.
- Do **not** include a `sources` field – sources will be resolved separately.
- Ensure the information is up-to-date as of "{current_date}"."""


async def scan_artist_for_scandals(artist: dict) -> dict:
    """
    Scan a single artist for scandals using Gemini with Google Search.

    Args:
        artist: Dict with 'id', 'name', and 'spotify_id' keys.

    Returns:
        Dict with artist info and scandals list.
    """
    client = _get_client()
    current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    prompt = _build_prompt(
        artist_name=artist["name"],
        spotify_id=artist["spotify_id"],
        current_date=current_date,
        existing_scandals=artist.get("existing_scandals", []),
    )

    # ─── Google Search grounding tool ───
    grounding_tool = types.Tool(
        google_search=types.GoogleSearch()
    )

    # ─── Call Gemini with Google Search ───
    try:
        await get_rate_limiter().acquire(uses_search=True)
        response = await client.aio.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[grounding_tool]
            ),
        )
    except Exception as e:
        logger.exception("API call failed for %s: %s", artist['name'], e)
        return {
            "artist_id": artist["id"],
            "artist_name": artist["name"],
            "scandals": [],
        }

    # ─── Extract source URLs from grounding metadata ───
    raw_chunks: list[tuple[str, str | None]] = []  # (uri, title)
    try:
        candidates = response.candidates
        if candidates and candidates[0].grounding_metadata:
            gm = candidates[0].grounding_metadata
            chunks = getattr(gm, "grounding_chunks", None) or []
            for chunk in chunks:
                web = getattr(chunk, "web", None)
                if web:
                    uri = getattr(web, "uri", None)
                    title = getattr(web, "title", None)
                    if uri:
                        raw_chunks.append((uri, title))
    except Exception as e:
        logger.info("Could not extract grounding chunks for %s: %s", artist['name'], e)

    # Resolve all redirects concurrently
    grounding_sources: list[dict] = []
    if raw_chunks:
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=8,
                headers={"User-Agent": "Mozilla/5.0"},
            ) as http:
                resolved = await asyncio.gather(
                    *[resolve_url(http, uri, title) for uri, title in raw_chunks],
                    return_exceptions=True,
                )
            for item in resolved:
                if isinstance(item, dict):
                    url_lower = item.get("url", "").lower()

                    # Only process vertexaisearch URLs
                    if "vertexaisearch" in url_lower:
                        try:
                            resolved_item = await resolve_url(http, item.get("url"), item.get("title"))
                            if resolved_item["url"] != item.get("url") and "vertexaisearch" not in resolved_item["url"]:
                                grounding_sources.append({
                                    "url": resolved_item["url"],
                                    "title": resolved_item["title"] or item.get("title")
                                })
                            else:
                                logger.warning("Skipping unresolved vertexaisearch source for %s: %s", artist['name'], item.get('url'))
                        except Exception as e:
                            logger.warning("Exception resolving vertexaisearch source for %s, skipping: %s", artist['name'], e)
                    else:
                        if is_blocked_domain(item.get("url", "")):
                            logger.info("Blocked domain skipped for %s: %s", artist['name'], item.get('url', '')[:60])
                        else:
                            grounding_sources.append(item)

        except Exception as e:
            logger.exception("Grounding chunks processing failed for %s: %s", artist['name'], e)
            grounding_sources = [{"url": uri, "title": title} for uri, title in raw_chunks]

    if grounding_sources:
        logger.info("Resolved %s valid source(s) for %s", len(grounding_sources), artist['name'])
    else:
        logger.info("No valid grounding sources found for %s", artist['name'])

    # ─── Parse response ───
    try:
        raw_text = response.text.strip()

        # Strip markdown code fences
        if raw_text.startswith("```"):
            lines = raw_text.split("\n")
            raw_text = "\n".join(lines[1:-1]).strip()

        # Try direct JSON parse first
        try:
            result = json.loads(raw_text)
        except json.JSONDecodeError:
            match = re.search(r'\{[\s\S]*\}', raw_text)
            if match:
                result = json.loads(match.group())
            else:
                raise ValueError("No JSON found in response")

        # Handle both {"scandals": [...]} and direct [...] formats
        if isinstance(result, dict) and "scandals" in result:
            scandals = result["scandals"]
        elif isinstance(result, list):
            scandals = result
        else:
            scandals = []

        # ─── Attribute sources to each scandal using groundingSupports ───
        grounding_supports = []
        try:
            if response.candidates and response.candidates[0].grounding_metadata:
                gm = response.candidates[0].grounding_metadata
                grounding_supports = getattr(gm, "grounding_supports", None) or []
        except Exception as e:
            logger.info("Could not read groundingSupports for %s: %s", artist['name'], e)

        match_sources_to_scandals(
            scandals=scandals,
            resolved_sources=grounding_sources,
            raw_text=response.text,
            grounding_supports=grounding_supports,
        )

        return {
            "artist_id": artist["id"],
            "artist_name": artist["name"],
            "scandals": scandals,
        }

    except (json.JSONDecodeError, ValueError) as e:
        logger.exception("Failed to parse response for %s: %s", artist['name'], e)
        logger.info("Raw response: %s", response.text[:500])
        return {
            "artist_id": artist["id"],
            "artist_name": artist["name"],
            "scandals": [],
        }


async def scan_artists_for_scandals(artists: list[dict]) -> list[dict]:
    """
    Scan multiple artists for scandals. Processes each artist individually
    to get focused, detailed results with Google Search grounding.
    """
    results = []

    for artist in artists:
        artist_result = await scan_artist_for_scandals(artist)
        results.append(artist_result)

    return results
