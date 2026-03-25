# Implementation Plan – Add Source to Existing Scandal

## Goal
Allow both Admins (in the backend) and Community Users (in the frontend) to add new sources to an existing scandal.
- **Admin**: Adds a source directly. It's instantly approved and added as `is_verified=True`.
- **Community**: Adds a source which lands in a pending queue for Admin review (similar to submitting a new community scandal).

## Proposed Changes

---

### 1. Database Layer
#### [MODIFY] backend/models.py
- Add a new `CommunitySource` table to track sources submitted by the public that are pending review. Fields: `id`, `scandal_id` (ForeignKey), `spotify_user_id`, `source_url`, `created_at`.
- Add relationship in [Scandal](file:///c:/Users/dstnr/Documents/web-development/github/spotifyscandals/backend/models.py#44-77) to `CommunitySource`.

---

### 2. Backend API Layer

#### [MODIFY] backend/routers/scandals.py
- Add `POST /api/scandals/{scandal_id}/sources`: Admin endpoint to directly add a verified source to a scandal.
- Add `DELETE /api/scandals/sources/{source_id}`: Admin endpoint to delete an existing source (already handled via the [report](file:///c:/Users/dstnr/Documents/web-development/github/spotifyscandals/frontend/src/lib/api.js#154-157) function perhaps, but needs a direct delete for Admins). *Wait, Admins can just use the verify toggle or delete if needed.*

#### [MODIFY] backend/routers/public.py
- Add `POST /api/public/scandals/{scandal_id}/sources`: Public endpoint for authenticated users to submit a `CommunitySource`. It requires the Spotify JWT token.

#### [MODIFY] backend/routers/community.py
- Add `GET /api/community-sources/artist/{artist_id}`: Admin endpoint to list pending community sources for a specific artist.
- Add `POST /api/community-sources/{source_id}/verify`: Admin endpoint to approve a community source (creates a [ScandalSource](file:///c:/Users/dstnr/Documents/web-development/github/spotifyscandals/backend/models.py#79-103) with `is_verified=True` and deletes the `CommunitySource`).
- Add `DELETE /api/community-sources/{source_id}`: Admin endpoint to reject and delete a community source.

#### [MODIFY] backend/schemas.py
- Add Pydantic models: `CommunitySourceCreate`, `CommunitySourceResponse`, `AdminSourceCreate`.

---

### 3. Frontend Layer

#### [MODIFY] frontend/src/lib/api.js
- Add API bindings: `submitCommunitySource`, `addAdminSource`, `fetchPendingCommunitySources`, `verifyCommunitySource`, `rejectCommunitySource`.

#### [MODIFY] frontend/src/routes/public/ArtistScandals.svelte
- Below the "Sources & References" list for each scandal, add a section:
  > *"Do you have a better/newer/whatever source? Send it to us!"*
- When clicked, open a modal with an input for the `source_url`.
- Require Spotify login to submit, opening the auth flow if not logged in.

#### [MODIFY] frontend/src/routes/ArtistScandalsAdmin.svelte
- Add an "Add Source" button to each scandal card.
- Opens a prompt/modal for the admin to input a URL and immediately adds it to the backend as a verified source via the new admin endpoint.

#### [MODIFY] frontend/src/routes/CommunityArtistAdmin.svelte
- Fetch and display pending `CommunitySources` alongside pending [CommunityScandals](file:///c:/Users/dstnr/Documents/web-development/github/spotifyscandals/frontend/src/lib/api.js#173-176).
- Show them grouped under the respective scandal they belong to.
- Allow the admin to approve or reject pending sources with the same UI flow as scandals.

## Verification Plan

### Automated Tests
- Syntax check on all modified Python files (`py_compile`).
- Server restart and confirm fastAPI loads the new routes without errors.

### Manual Verification
- **Community Flow**: Log in as a public user, navigate to an artist, and submit a new source URL to an existing scandal. Verify a success toast is shown.
- **Admin Review Flow**: Log in as an admin, check the Community Inbox for the artist, see the pending source, and click Approve. Check that it moves to the public view.
- **Admin Direct Flow**: As an admin on the Artist Scandals panel, manually add a source directly and ensure it appears immediately in the DB and UI.
