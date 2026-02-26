"""
Google Gemini 2.5 Pro integration service with Google Search grounding.

Uses the new google-genai client to:
  1. Send a structured prompt per artist to check for scandals
  2. Ground responses in real-time Google Search results
  3. Return parsed JSON with scandal titles, descriptions, and source URLs
"""

import json
import asyncio
from urllib.parse import urlparse
import httpx
from google import genai
from google.genai import types
from config import get_settings
from datetime import datetime, timezone


async def _resolve_url(client: httpx.AsyncClient, uri: str, fallback_title: str | None) -> dict:
    """
    Follow the vertexaisearch redirect chain and return the real final URL.
    Falls back to the original URI if the request fails.
    """
    try:
        resp = await client.head(uri, follow_redirects=True)
        final_url = str(resp.url)
        # Use hostname as title (strip www.)
        domain = urlparse(final_url).hostname or fallback_title or ""
        title = domain.removeprefix("www.")
        return {"url": final_url, "title": title or fallback_title}
    except Exception:
        # If resolution fails, keep the vertexaisearch URL + original title
        return {"url": uri, "title": fallback_title}


def _match_sources_to_scandals(
    scandals: list[dict],
    resolved_sources: list[dict],
    raw_text: str,
    grounding_supports,
) -> None:
    """
    Use groundingSupports to attribute specific sources to each scandal.

    groundingSupports maps character segments of the response text to
    specific grounding chunk indices. We find each scandal's position in
    the raw JSON text, then collect only the chunks whose supports overlap
    with that position.

    Mutates each scandal dict in-place by setting its 'sources' list.
    Falls back to all sources if attribution yields nothing for a scandal.
    """
    if not grounding_supports or not resolved_sources:
        # No attribution data — share all sources as before
        for scandal in scandals:
            scandal["sources"] = list(resolved_sources)
        return

    # Build a list of (start, end, {chunk_indices}) from grounding_supports
    support_segments: list[tuple[int, int, set[int]]] = []
    for support in grounding_supports:
        seg = getattr(support, "segment", None)
        indices = list(getattr(support, "grounding_chunk_indices", []) or [])
        if seg and indices:
            start = getattr(seg, "start_index", 0) or 0
            end = getattr(seg, "end_index", 0) or 0
            support_segments.append((start, end, set(indices)))

    for scandal in scandals:
        # Find this scandal's text range in the raw response string.
        # We search for the unique description text since titles may be short.
        description = scandal.get("description", "")
        title = scandal.get("title", "")

        # Try to find the scandal block's start/end in the raw text
        pos = -1
        search_text = description[:80] if description else title  # first 80 chars is unique enough
        if search_text:
            pos = raw_text.find(search_text)

        if pos == -1:
            # Fallback: couldn't locate text — assign all sources
            scandal["sources"] = list(resolved_sources)
            continue

        scandal_start = pos
        scandal_end = pos + len(description) if description else pos + len(title)

        # Collect chunk indices whose support segments overlap with this scandal's range
        matched_indices: set[int] = set()
        for seg_start, seg_end, chunk_indices in support_segments:
            # Overlap check: segments overlap if they're not completely before or after
            if seg_end > scandal_start and seg_start < scandal_end:
                matched_indices.update(chunk_indices)

        # Map matched indices to resolved sources
        matched_sources = [
            resolved_sources[i]
            for i in sorted(matched_indices)
            if i < len(resolved_sources)
        ]

        # Fall back to all sources if nothing matched
        scandal["sources"] = matched_sources if matched_sources else list(resolved_sources)


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

    return f"""You are an investigative research assistant. Your task is to find **all scandals** involving the artist "{artist_name}" up to the date "{current_date}". If available, you can also reference the artist's Spotify page: {spotify_url}.

Instructions:
1. Collect **all known scandals** involving the artist until the given date. Use the Google Search tool to verify information.
2. For each scandal, provide:
   - A concise **title** (short, descriptive name of the scandal)
   - A brief **description** (1-2 sentences summarizing the scandal)
3. Output the results strictly as **valid JSON** using the following structure:

{{
  "scandals": [
    {{
      "title": "Title of scandal 1",
      "description": "Short description of scandal 1"
    }}
  ]
}}

4. If no scandals are found, return:
{{
  "scandals": []
}}
{exclusion_text}

Additional rules:
- Only provide valid JSON, **no extra text or explanations**.
- Do **not** include a `sources` field – sources will be resolved separately.
- Use the Spotify artist page only as a supplementary reference.
- Ensure the information is up-to-date as of "{current_date}"."""


async def scan_artist_for_scandals(artist: dict) -> dict:
    """
    Scan a single artist for scandals using Gemini 2.5 Pro with Google Search.

    Args:
        artist: Dict with 'id', 'name', and 'spotify_id' keys.

    Returns:
        Dict with artist info and scandals list:
        {
            "artist_id": int,
            "artist_name": str,
            "scandals": [
                {"title": str, "description": str, "sources": [str, ...]}
            ]
        }
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

    # ─── Call Gemini 2.5 Pro with Google Search ───
    # NOTE: response_mime_type="application/json" is INCOMPATIBLE with tool use.
    # We ask for JSON in the prompt and extract it from the plain text response.
    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-pro",
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[grounding_tool],
                temperature=0.2,  # Low temperature for factual accuracy
            ),
        )
    except Exception as e:
        print(f"[Gemini] API call failed for {artist['name']}: {e}")
        return {
            "artist_id": artist["id"],
            "artist_name": artist["name"],
            "scandals": [],
        }

    # ─── Extract source URLs from grounding metadata ───
    # Gemini 2.5 Pro will not embed source URLs in its text output reliably.
    # Instead, the real source URLs live in groundingMetadata.groundingChunks,
    # returned as vertexaisearch redirect URIs with human-readable titles
    # like "bbc.co.uk" or "theguardian.com".
    # We resolve each redirect to the actual article URL using httpx.
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
        print(f"[Gemini] Could not extract grounding chunks for {artist['name']}: {e}")

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
                    *[_resolve_url(http, uri, title) for uri, title in raw_chunks],
                    return_exceptions=True,
                )
            for item in resolved:
                if isinstance(item, dict):
                    grounding_sources.append(item)
        except Exception as e:
            print(f"[Gemini] Redirect resolution failed for {artist['name']}: {e}")
            # Fall back to raw vertexaisearch URIs with original titles
            grounding_sources = [{"url": uri, "title": title} for uri, title in raw_chunks]

    if grounding_sources:
        print(f"[Gemini] Resolved {len(grounding_sources)} source(s) for {artist['name']}")
    else:
        print(f"[Gemini] No grounding sources found for {artist['name']}")

    # ─── Parse response ───
    try:
        raw_text = response.text.strip()

        # Strip markdown code fences (```json ... ``` or ``` ... ```)
        if raw_text.startswith("```"):
            lines = raw_text.split("\n")
            # Remove first line (```json or ```) and last line (```)
            raw_text = "\n".join(lines[1:-1]).strip()

        # Try direct JSON parse first
        try:
            result = json.loads(raw_text)
        except json.JSONDecodeError:
            # Fall back: extract first JSON object/array using regex
            import re
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
        # groundingSupports maps character ranges in response.text to specific
        # chunk indices, letting us assign only the relevant sources per scandal.
        grounding_supports = []
        try:
            if response.candidates and response.candidates[0].grounding_metadata:
                gm = response.candidates[0].grounding_metadata
                grounding_supports = getattr(gm, "grounding_supports", None) or []
        except Exception as e:
            print(f"[Gemini] Could not read groundingSupports for {artist['name']}: {e}")

        _match_sources_to_scandals(
            scandals=scandals,
            resolved_sources=grounding_sources,
            raw_text=response.text,  # groundingSupports indices reference the original response text
            grounding_supports=grounding_supports,
        )

        return {
            "artist_id": artist["id"],
            "artist_name": artist["name"],
            "scandals": scandals,
        }

    except (json.JSONDecodeError, ValueError) as e:
        print(f"[Gemini] Failed to parse response for {artist['name']}: {e}")
        print(f"[Gemini] Raw response: {response.text[:500]}")
        return {
            "artist_id": artist["id"],
            "artist_name": artist["name"],
            "scandals": [],
        }


async def scan_artists_for_scandals(artists: list[dict]) -> list[dict]:
    """
    Scan multiple artists for scandals. Processes each artist individually
    to get focused, detailed results with Google Search grounding.

    Args:
        artists: List of dicts with 'id', 'name', and 'spotify_id' keys.

    Returns:
        List of per-artist results with scandals.
    """
    results = []
    for artist in artists:
        print(f"[Gemini] Scanning: {artist['name']}...")
        result = await scan_artist_for_scandals(artist)
        scandal_count = len(result.get("scandals", []))
        print(f"[Gemini] Found {scandal_count} scandal(s) for {artist['name']}")
        results.append(result)

    return results
