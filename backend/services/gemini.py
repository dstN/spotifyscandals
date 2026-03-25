"""
Google Gemini 2.5 Pro integration service with Google Search grounding.

Uses the new google-genai client to:
  1. Send a structured prompt per artist to check for scandals
  2. Ground responses in real-time Google Search results
  3. Return parsed JSON with scandal titles, descriptions, and source URLs
"""


import json
import asyncio
import subprocess
import os
import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import httpx
from google import genai
from google.genai import types
from config import get_settings
from datetime import datetime, timezone
from playwright.async_api import async_playwright


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



async def _resolve_url_ultra(uri: str, fallback_title: str | None) -> dict:
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
        print(f"[Gemini-Ultra-Resolve] Playwright failed: {e}")
    return {"url": uri, "title": fallback_title}


async def _resolve_url_deep(uri: str, fallback_title: str | None) -> dict:
    """
    Use curl as a deep-resolve fallback.
    """
    try:
        # -L follow redirects
        # -s silent
        # -o NUL don't output body (Windows)
        # -w %{url_effective} output final URL
        # --max-time 10
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
    return await _resolve_url_ultra(uri, fallback_title)


async def _resolve_url(client: httpx.AsyncClient, uri: str, fallback_title: str | None) -> dict:
    """
    Follow the vertexaisearch redirect chain and return the real final URL.
    Falls back to _resolve_url_deep if httpx fails.
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
        return await _resolve_url_deep(uri, fallback_title)


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
        # No attribution data — better to have NO sources and heal than to have random ones
        for scandal in scandals:
            scandal["sources"] = []
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

    last_search_pos = 0
    scandals_processed = 0
    
    for scandal in scandals:
        description = scandal.get("description", "")
        title = scandal.get("title", "")

        # ─── 1. Find the START of the scandal block ───
        # We try to find the description (parsed or escaped) since it's most unique
        start_candidates = []
        if description:
            snippet = description[:60] # Use a slightly shorter snippet for higher match probability
            start_candidates.append(snippet)
            try:
                start_candidates.append(json.dumps(snippet)[1:-1])
            except: pass
        if title:
            start_candidates.append(title)
            try:
                start_candidates.append(json.dumps(title)[1:-1])
            except: pass

        start_pos = -1
        for candidate in start_candidates:
            if not candidate: continue
            start_pos = raw_text.find(candidate, last_search_pos)
            if start_pos != -1:
                break

        if start_pos == -1:
            print(f"[Gemini-Match] Could not find start for scandal {scandals_processed + 1}. Falling back.")
            scandals_processed += 1
            scandal["sources"] = list(resolved_sources)
            continue

        # ─── 2. Find the END of the scandal block ───
        # We search for the end of the description starting from start_pos
        end_pos = -1
        if description:
            end_snippet = description[-60:] if len(description) > 60 else description
            end_candidates = [end_snippet]
            try:
                end_candidates.append(json.dumps(end_snippet)[1:-1])
            except: pass
            
            for ecand in end_candidates:
                found_end = raw_text.find(ecand, start_pos)
                if found_end != -1:
                    end_pos = found_end + len(ecand)
                    break
        
        # If we couldn't find a clean end, use a generous window after start
        if end_pos == -1:
            # Fallback window: parsed length + buffer (accounting for escapes)
            end_pos = start_pos + int(len(description or title) * 1.5) + 100
        
        # ─── 3. Collect sources within range [start_pos, end_pos] ───
        matched_indices: set[int] = set()
        for seg_start, seg_end, chunk_indices in support_segments:
            # If the support segment overlaps with our scandal range
            if seg_end > start_pos and seg_start < end_pos:
                matched_indices.update(chunk_indices)

        matched_sources = [
            resolved_sources[i]
            for i in sorted(matched_indices)
            if i < len(resolved_sources)
        ]

        # Final assignment
        scandal["sources"] = matched_sources if matched_sources else []
        
        # Update search position for next scandal
        last_search_pos = end_pos
        scandals_processed += 1
        
        print(f"[Gemini-Match] Scandal {scandals_processed}: range[{start_pos}:{end_pos}], sources: {len(scandal['sources'])}")


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
            model="gemini-3-flash-preview",
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[grounding_tool]
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
                    # ─── New: Backend Filter per Artist context ───
                    # Skip sources that clearly belong to irrelevant people with similar names
                    url_lower = item.get("url", "").lower()
                    title_lower = item.get("title", "").lower()

                    # Only process vertexaisearch URLs
                    if "vertexaisearch" in url_lower:
                        try:
                            # _resolve_url uses httpx and falls back to curl and playwright
                            resolved_item = await _resolve_url(http, item.get("url"), item.get("title"))
                            # If it successfully resolved to a real URL, keep it
                            if resolved_item["url"] != item.get("url") and "vertexaisearch" not in resolved_item["url"]:
                                grounding_sources.append({
                                    "url": resolved_item["url"],
                                    "title": resolved_item["title"] or item.get("title")
                                })
                            else:
                                print(f"[Gemini-Filter] Skipping unresolved vertexaisearch source for {artist['name']}: {item.get('url')}")
                        except Exception as e:
                            print(f"[Gemini-Filter] Exception resolving vertexaisearch source for {artist['name']}, skipping: {e}")
                    else:
                        # Keep normal URLs — but filter blocked domains
                        if is_blocked_domain(item.get("url", "")):
                            print(f"[Gemini-Filter] Blocked domain skipped for {artist['name']}: {item.get('url', '')[:60]}")
                        else:
                            grounding_sources.append(item)
                        
        except Exception as e:
            print(f"[Gemini] Grounding chunks processing failed for {artist['name']}: {e}")
            # Fall back to raw vertexaisearch URIs with original titles if processing fails
            # Note: This fallback might include unresolved vertexaisearch URLs if the above logic failed to filter them.
            # However, the new logic aims to resolve/filter them proactively.
            # For now, we'll keep the original fallback structure, but it might be refined.
            grounding_sources = [{"url": uri, "title": title} for uri, title in raw_chunks]

    if grounding_sources:
        print(f"[Gemini] Resolved {len(grounding_sources)} valid source(s) for {artist['name']}")
    else:
        print(f"[Gemini] No valid grounding sources found for {artist['name']}")

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
    
    # Process sequentially instead of using asyncio.gather to prevent rate-limiting
    # or overloading the Gemini/Search API
    for artist in artists:
        artist_result = await scan_artist_for_scandals(artist)
        results.append(artist_result)
        
    return results

async def verify_source_relevance(source_url: str, title: str, description: str) -> bool:
    """
    Fetches the content of a source URL and asks Gemini if it directly corroborates
    the given scandal. Returns True if relevant, False otherwise.
    """
    if not source_url or not source_url.startswith("http"):
        return False

    # Fast-reject blocked platforms before any network call
    if is_blocked_domain(source_url):
        print(f"[Gemini-Verify] Blocked domain – rejected: {source_url[:60]}")
        return False
        
    print(f"\n[Gemini-Verify] Verifying relevance of: {source_url[:60]}...")
    
    # 1. Fetch content
    html_content = ""
    try:
        # Try standard httpx first
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            # Common browser headers to bypass simple blockers
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
            resp = await client.get(source_url, headers=headers)
            resp.raise_for_status()
            html_content = resp.text
    except Exception as e:
        print(f"[Gemini-Verify] httpx failed ({e}), trying Playwright fallback...")
        try:
            # Fallback to Playwright for JS-heavy sites or strict anti-bot
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
            print(f"[Gemini-Verify] Playwright also failed: {p_err}. Cannot verify source.")
            return False

    if not html_content:
        return False

    # 2. Extract text (Basic HTML stripping)
    text_content = ""
    try:
        # Use simple regex if BS4 is not available, but try BS4 first if we added it
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            # Remove scripts and styles
            for script in soup(["script", "style"]):
                script.decompose()
            text_content = soup.get_text(separator=' ', strip=True)
        except ImportError:
            # Fallback regex
            text_content = re.sub('<[^<]+?>', ' ', html_content)
            text_content = " ".join(text_content.split())
            
    except Exception as e:
        print(f"[Gemini-Verify] Failed to extract text: {e}")
        return False

    # Prune to first ~15,000 chars to save tokens (usually the main article is at the top)
    text_content = text_content[:15000] 

    if len(text_content) < 100:
        print(f"[Gemini-Verify] Extracted text too short to evaluate.")
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
        print(f"[Gemini-Verify] Result: {result} -> Relevant: {is_relevant}")
        return is_relevant

    except Exception as e:
        print(f"[Gemini-Verify] Evaluation failed: {e}")
        # If verification mechanism fails (API error), default to keeping it (True) to prevent accidental data loss
        return True


async def score_source_relevance(source_url: str, scandal_title: str, scandal_description: str) -> int:
    """
    Scores the relevance of a source URL to a given scandal on a 0-10 scale.

    Primary:  Gemini url_context (Gemini fetches the URL itself)
    Fallback: httpx → Playwright (manual fetch + BeautifulSoup extraction)

    Returns an integer score (0-10). Returns 0 on error or blocked domain.
    A score > 7 (i.e. 8, 9, 10) is considered accepted.
    """
    if not source_url or not source_url.startswith("http"):
        return 0

    if is_blocked_domain(source_url):
        print(f"[Gemini-Score] Blocked domain – score 0: {source_url[:60]}")
        return 0

    print(f"[Gemini-Score] Scoring: {source_url[:60]}...")

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

    # ── Primary: Gemini url_context (Gemini fetches the URL itself) ──
    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-3-flash-preview",
            contents=SCORE_PROMPT,
            config=types.GenerateContentConfig(
                tools=[{"url_context": {}}],
                # NOTE: no max_output_tokens — url_context adds its own context tokens
            )
        )
        # url_context returns content in parts, not response.text
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
            print(f"[Gemini-Score] url_context score {score}/10 for: {source_url[:60]}")
            return score
        print(f"[Gemini-Score] url_context returned no score (raw='{raw[:80]}'), falling back...")
    except Exception as e:
        print(f"[Gemini-Score] url_context failed ({e}), falling back to manual fetch...")

    # ── Fallback: manual fetch → BeautifulSoup → Gemini text prompt ──
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
        print(f"[Gemini-Score] httpx failed ({e}), trying Playwright...")
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
            print(f"[Gemini-Score] Playwright also failed: {p_err}. Scoring as 0.")
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
        print(f"[Gemini-Score] Page content too short. Scoring as 0.")
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
        print(f"[Gemini-Score] Fallback score {score}/10 for: {source_url[:60]}")
        return score
    except Exception as e:
        print(f"[Gemini-Score] Fallback scoring failed: {e}")
        return 0




async def find_better_sources(artist_name: str, scandal_title: str, scandal_description: str) -> list[dict]:
    """
    Uses Google Grounding to search for NEW, reliable sources for a specific scandal described by the input.
    Returns a list of dictionaries with 'url' and 'title'. Pre-filtered by domain blocklist.
    """
    print(f"\n[Gemini-Heal] Hunting for better sources for: {scandal_title}")
    
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
                                    # Need to resolve vertexaisearch URLs from grounding
                                    if "vertexaisearch" in uri:
                                         resolved = await _resolve_url(http, uri, title)
                                         uri = resolved.get("url", uri)
                                         title = resolved.get("title", title)
                                         
                                         if "vertexaisearch" in uri:
                                             print(f"[Gemini-Heal] Skipping unresolved vertexaisearch source: {uri}")
                                             continue
                                             
                                    grounding_urls[uri] = title
                                except Exception as e:
                                    print(f"[Gemini-Heal] Chunk parsing error: {e}")
                                
        results = []
        for url, site_title in grounding_urls.items():
            if is_blocked_domain(url):
                print(f"[Gemini-Heal] Blocked domain filtered: {url[:60]}")
                continue
            results.append({"url": url, "title": site_title})
            
        print(f"[Gemini-Heal] Found {len(results)} new potential sources.")
        return results

    except Exception as e:
        print(f"[Gemini-Heal] Failed to find new sources: {e}")
        return []

        scandal_count = len(result.get("scandals", []))
        print(f"[Gemini] Found {scandal_count} scandal(s) for {artist['name']}")
        results.append(result)

    return results
