---
description: Reset all scandals, community submissions, and artist approvals
---

Reset the database to a clean state for a fresh Gemini scan.

// turbo

1. Run the database reset command:

```bash
backend/venv/Scripts/python.exe -c "import sqlite3, os; db_path = os.path.join('backend', 'skandal_tracker.db'); conn = sqlite3.connect(db_path); cursor = conn.cursor(); cursor.execute('DELETE FROM scandal_sources'); cursor.execute('DELETE FROM scandal_votings'); cursor.execute('DELETE FROM scandals'); cursor.execute('DELETE FROM community_scandals'); cursor.execute('UPDATE artists SET approved = 0, last_scanned_at = NULL'); conn.commit(); conn.close()"
```

The database is now reset:

- 0 Scandals
- 0 Community Submissions
- 0 Approved Artists
- All scan timestamps cleared
