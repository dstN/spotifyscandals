"""
Source-to-scandal attribution using Gemini groundingSupports metadata.
"""

import json
import logging

logger = logging.getLogger(__name__)


def match_sources_to_scandals(
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
        start_candidates = []
        if description:
            snippet = description[:60]
            start_candidates.append(snippet)
            try:
                start_candidates.append(json.dumps(snippet)[1:-1])
            except Exception:
                pass
        if title:
            start_candidates.append(title)
            try:
                start_candidates.append(json.dumps(title)[1:-1])
            except Exception:
                pass

        start_pos = -1
        for candidate in start_candidates:
            if not candidate:
                continue
            start_pos = raw_text.find(candidate, last_search_pos)
            if start_pos != -1:
                break

        if start_pos == -1:
            logger.info("Could not find start for scandal %s. Falling back.", scandals_processed + 1)
            scandals_processed += 1
            scandal["sources"] = list(resolved_sources)
            continue

        # ─── 2. Find the END of the scandal block ───
        end_pos = -1
        if description:
            end_snippet = description[-60:] if len(description) > 60 else description
            end_candidates = [end_snippet]
            try:
                end_candidates.append(json.dumps(end_snippet)[1:-1])
            except Exception:
                pass

            for ecand in end_candidates:
                found_end = raw_text.find(ecand, start_pos)
                if found_end != -1:
                    end_pos = found_end + len(ecand)
                    break

        # If we couldn't find a clean end, use a generous window after start
        if end_pos == -1:
            end_pos = start_pos + int(len(description or title) * 1.5) + 100

        # ─── 3. Collect sources within range [start_pos, end_pos] ───
        matched_indices: set[int] = set()
        for seg_start, seg_end, chunk_indices in support_segments:
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

        logger.debug("Scandal %s: range[%s:%s], sources: %s", scandals_processed, start_pos, end_pos, len(scandal['sources']))


# Backwards-compatible alias
_match_sources_to_scandals = match_sources_to_scandals
