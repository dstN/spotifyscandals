# Implementation Plan: Gemini Async Batch API Integration

## Goal
To drastically reduce input and output token costs, we will migrate the bulk scanning of artists from real-time sequential/concurrent API calls to the official asynchronous **Gemini Batch API**. 
According to documentation (`https://ai.google.dev/gemini-api/docs/batch-api`), the Batch API provides a rigid **50% discount** on input and output tokens. This is crucial for mass-scanning artists on the free limits or maximizing paid credits.

## Proposed Changes

---

### 1. File Conversion & Upload Logic
#### [MODIFY] backend/scanner_cli.py
- Instead of immediately running an `asyncio.Semaphore` event loop to scan artists via `scan_artists_for_scandals`:
- Introduce a two-step process:
  - **Step 1:** Iterate over the target artists, generate the raw JSON requests that the Gemini API accepts, and write them sequentially into a JSONL (`.jsonl`) file.
  - **Step 2:** Upload the local JSONL file to Google using the `google.genai` Files API (`client.files.upload(...)`).
  - **Step 3:** Initiate the Batch Job using `client.batches.create(file=...)`.
- Store the returned `batch_job.name` (ID) in a local cache or SQLite table (`BatchJobs`) to track progress.

---

### 2. Database Tracking for Asynchronous Jobs
#### [MODIFY] backend/models.py
- Introduce a new table `BatchJob` to track the state of ongoing Google Batch API jobs.
  - columns: `id`, `job_name` (string), `status` (string), `created_at`.
- Artists included in the batch should temporarily have their `last_scanned_at` or a new field (`scan_status`) marked as `"PENDING_BATCH"`.

---

### 3. Polling and Resolution
#### [NEW] backend/cron/batch_poller.py (or similar script)
- Create a script that periodically queries the Gemini API for the status of active batch jobs (`client.batches.get(name=...)`).
- If the job `state` changes to `SUCCEEDED` or `FAILED`:
  - Retrieve the output JSONL file URI from the API.
  - Download and parse the `response` lines.
  - Feed the successful text outputs through the existing `_match_sources_to_scandals` pipeline to write the Scandals and Sources into our SQLite database.
- Mark the `BatchJob` as completed and update the affected `Artist` records.

---

### Limitations & Next Steps
- **Latency:** The Batch API is strictly asynchronous and can take up to 48 hours. This feature should only be used for "background library fills" (e.g., millions of artists), while real-time user-requested artists (from playlist submissions) still use the synchronous, immediate API call.
- **Search Grounding:** We need to verify if giving a tool config (`google_search`) works identically inside a Batch JSONL element. If Grounding tokens aren't discounted or available, we might only use batching for the expensive "Scan & Output" text-generation step.

## Verification Plan
1. Send a test batch with 10 artists via `scanner_cli.py --batch-mode`.
2. Ensure the JSONL is formatted correctly and accepted by Google.
3. Wait for the `batch_job` state to complete.
4. Download the result JSONL, map the outputs to the respective Artists, and verify the Scandals insert correctly into SQLite.
