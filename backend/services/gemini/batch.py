"""
Gemini Batch API — submit, poll, and parse batch scanning jobs.
"""

import json
import logging
import re
from datetime import datetime, timezone

from google import genai
from google.genai import types

from config import get_settings
from .scanner import _get_client, _build_prompt
from .url_resolver import is_blocked_domain
from .source_matcher import match_sources_to_scandals

logger = logging.getLogger(__name__)


def create_batch_requests(artists: list[dict]) -> list[dict]:
    """
    Build inline batch request dicts for `client.batches.create()`.
    Each request is one artist scan with Google Search grounding.
    """
    current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    requests = []
    for artist in artists:
        prompt = _build_prompt(
            artist_name=artist["name"],
            spotify_id=artist["spotify_id"],
            current_date=current_date,
            existing_scandals=artist.get("existing_scandals", []),
        )
        requests.append({
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "config": {
                "tools": [{"google_search": {}}],
            },
        })
    return requests


def submit_batch_job(artists: list[dict]) -> str:
    """
    Submit a batch of artist scan requests to the Gemini Batch API.
    Returns the batch job name (ID) for polling.
    """
    client = _get_client()
    requests = create_batch_requests(artists)

    logger.info("Submitting batch with %s requests...", len(requests))

    batch_job = client.batches.create(
        model="gemini-3-flash-preview",
        src=requests,
        config=types.CreateBatchJobConfig(
            display_name=f"scandal-scan-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
        ),
    )

    job_name = batch_job.name
    logger.info("Job submitted: %s (state: %s)", job_name, batch_job.state)
    return job_name


def poll_batch_job(job_name: str) -> dict:
    """
    Check the status of a batch job.
    Returns dict with 'state' and optionally 'responses' if completed.
    """
    client = _get_client()
    job = client.batches.get(name=job_name)

    result = {
        "name": job.name,
        "state": str(job.state.name) if hasattr(job.state, "name") else str(job.state),
    }

    if result["state"] == "JOB_STATE_SUCCEEDED":
        # Extract inline responses
        responses = []
        if hasattr(job, "dest") and job.dest and hasattr(job.dest, "inlined_responses"):
            for resp in job.dest.inlined_responses:
                responses.append(resp)
        result["responses"] = responses

    return result


def parse_batch_response(response, artist: dict) -> dict:
    """
    Parse a single batch response into the same format as scan_artist_for_scandals.
    Returns dict: {"artist_id": ..., "artist_name": ..., "scandals": [...]}
    """
    try:
        raw_text = ""
        if hasattr(response, "response"):
            inner = response.response
            if hasattr(inner, "text"):
                raw_text = inner.text.strip()
            elif hasattr(inner, "candidates") and inner.candidates:
                for part in inner.candidates[0].content.parts:
                    if hasattr(part, "text") and part.text:
                        raw_text += part.text
                raw_text = raw_text.strip()

        if not raw_text:
            return {"artist_id": artist["id"], "artist_name": artist["name"], "scandals": []}

        # Strip markdown fences
        if raw_text.startswith("```"):
            lines = raw_text.split("\n")
            raw_text = "\n".join(lines[1:-1]).strip()

        # Parse JSON
        try:
            result = json.loads(raw_text)
        except json.JSONDecodeError:
            match = re.search(r'\{[\s\S]*\}', raw_text)
            if match:
                result = json.loads(match.group())
            else:
                return {"artist_id": artist["id"], "artist_name": artist["name"], "scandals": []}

        if isinstance(result, dict) and "scandals" in result:
            scandals = result["scandals"]
        elif isinstance(result, list):
            scandals = result
        else:
            scandals = []

        # Extract grounding sources from batch response
        grounding_sources = []
        try:
            inner = response.response
            if hasattr(inner, "candidates") and inner.candidates:
                gm = getattr(inner.candidates[0], "grounding_metadata", None)
                if gm:
                    chunks = getattr(gm, "grounding_chunks", None) or []
                    for chunk in chunks:
                        web = getattr(chunk, "web", None)
                        if web:
                            uri = getattr(web, "uri", None)
                            title = getattr(web, "title", None)
                            if uri and not is_blocked_domain(uri):
                                grounding_sources.append({"url": uri, "title": title})

                    # Attribute sources to scandals
                    grounding_supports = getattr(gm, "grounding_supports", None) or []
                    inner_text = inner.text if hasattr(inner, "text") else raw_text
                    match_sources_to_scandals(scandals, grounding_sources, inner_text, grounding_supports)
        except Exception as e:
            logger.exception("Grounding extraction failed for %s: %s", artist['name'], e)
            for s in scandals:
                s["sources"] = []

        return {"artist_id": artist["id"], "artist_name": artist["name"], "scandals": scandals}

    except Exception as e:
        logger.exception("Failed to parse batch response for %s: %s", artist['name'], e)
        return {"artist_id": artist["id"], "artist_name": artist["name"], "scandals": []}
