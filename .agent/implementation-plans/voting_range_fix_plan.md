# Implementation Plan: 0-10 Voting Range Fix

## Goal
Currently, the severity voting slider in `ArtistScandals.svelte` defaults to a 1-10 scale. Because a 1-10 integer scale has 9 steps, the mathematical center is actually 5.5, meaning the default value of 5 sits slightly off-center (at exactly 44.4% width), which looks skewed. 

To fix the UI alignment perfectly and allow users to state a scandal is "not severe at all" (Severity: 0), we need to update the voting scale to 0-10. This requires a minor adjustement in the backend API validation logic.

## Proposed Changes

---

### 1. Backend: API Validation
#### [MODIFY] backend/routers/scandals.py
- Locate the `@router.post("/{scandal_id}/vote")` endpoint.
- Change the validation constraint from:
  ```python
  if not (1 <= body.vote <= 10):
  ```
  to:
  ```python
  if not (0 <= body.vote <= 10):
  ```
  and update the associated HTTP 400 error message.

---

### 2. Frontend: UI Slider
#### [MODIFY] frontend/src/routes/public/ArtistScandals.svelte
- Locate the `<input type="range">` element for voting.
- Update `min="1"` to `min="0"`.
- This will effortlessly align the default value of 5 to precisely 50% visually out of the 10 available steps.

---

## Verification Plan
1. Open a scandal detail page in the public frontend.
2. Observe that the slider resting at 5 represents perfect center alignment.
3. Drag the slider to 0 and vote successfully without triggering an API 400 validation error.
