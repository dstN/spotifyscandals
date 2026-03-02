import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'spotiscandals.db')

if not os.path.exists(db_path):
    print(f"Error: Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # Delete all scandals and related data
    print("Deleting scandals...")
    cursor.execute("DELETE FROM scandals")
    print(f"Deleted {cursor.rowcount} scandals.")

    print("Deleting scandal sources...")
    cursor.execute("DELETE FROM scandal_sources")
    print(f"Deleted {cursor.rowcount} sources.")

    print("Deleting scandal votes...")
    cursor.execute("DELETE FROM scandal_votings")
    print(f"Deleted {cursor.rowcount} votes.")

    print("Deleting community scandals...")
    cursor.execute("DELETE FROM community_scandals")
    print(f"Deleted {cursor.rowcount} community submissions.")

    # Reset artist status
    print("Resetting artist states...")
    cursor.execute("UPDATE artists SET approved = 0, last_scanned_at = NULL")
    print(f"Reset {cursor.rowcount} artists to pending status and cleared timestamps.")

    conn.commit()
    print("\nDatabase reset successfully! You can now start from scratch.")
except Exception as e:
    conn.rollback()
    print(f"Error resetting database: {e}")
finally:
    conn.close()
