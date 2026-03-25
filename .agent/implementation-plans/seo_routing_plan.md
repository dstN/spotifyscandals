# Implementation Plan: SEO & Path-Based Routing

## Goal
Replace the current hash-based routing (`/#/...`) with standard path-based routing (`/...`) to improve Search Engine Optimization (SEO). This requires updating the frontend router to use the History API and configuring the FastAPI backend to properly serve the single-page application (SPA), including handling 404s.

## Proposed Changes

---

### 1. Frontend: History API Routing
#### [MODIFY] frontend/src/App.svelte
- Replace `window.location.hash` routing logic with History API routing (`window.location.pathname`).
- Listen to the `popstate` event to handle browser back/forward navigation.
- Write a helper `navigate(path)` function that uses `history.pushState({}, '', path)` and updates the current path state, bypassing full page reloads.
- Add a fallback route condition: If `currentPath` doesn't match any known routes, render a new `NotFound` component.

#### [MODIFY] frontend/src/routes/**/*.svelte & frontend/src/App.svelte
- Search and replace all hash links in the HTML templates (e.g., `href="#/artist/{id}"` -> `href="/artist/{id}"`).
- Add event modifiers or an action to make standard `<a>` tags use the `navigate()` function so they don't trigger a full page reload but update the URL properly.

---

### 2. Frontend: 404 Page
#### [NEW] frontend/src/routes/NotFound.svelte
- Create a beautiful `<NotFound />` Svelte component matching the Apple Glass aesthetic.
- Include a "404 - Skandal nicht gefunden" message.
- Add a "Return to Home" button.

---

### 3. Backend: SPA Catch-All Route
#### [MODIFY] backend/main.py
- Currently, static files are mounted via `StaticFiles(directory="../frontend/dist", html=True)`. This only serves exact file matches. If a user directly visits `/artist/123`, the backend returns a hard 404.
- Add a Catch-All route at the very end of `main.py` (after all `/api/...` routes).
- The Catch-All route should intercept any request that does NOT start with `/api/`.
- Instead of returning a 404, it should serve the `index.html` from `frontend/dist`.
- By serving `index.html`, the frontend JavaScript initializes, reads the URL path (`/artist/123`), and renders either the correct artist page or the new `<NotFound />` component.

```python
from fastapi.responses import FileResponse

@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    # Ensure APIs still 404 properly if they don't exist
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API route not found")
        
    # Serve the frontend index.html for all other paths
    return FileResponse("../frontend/dist/index.html")
```

---

## Verification Plan
### Automated Tests
- Syntax check backend script (`py_compile`).
- Build frontend (`npm run build`) to ensure all link changes are syntactically valid.

### Manual Verification
1. **SEO Links:** Verify URLs no longer contain `#` and share links like `/artist/1` load successfully upon a direct browser refresh.
2. **SPA Navigation:** Clicking links within the app should change the URL without causing a full browser page flash/reload.
3. **404 Behavior:** Enter a random non-existent URL like `/this-does-not-exist`. The backend should serve the app, and the frontend should render the new `NotFound.svelte` page.
4. **API Integrity:** Call a non-existent API endpoint `/api/fake-route` and ensure it still returns a proper JSON `404 Not Found` response, rather than accidentally serving HTML.
