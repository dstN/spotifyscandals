import sqlite3

def migrate():
    conn = sqlite3.connect('skandal_tracker.db')
    cursor = conn.cursor()
    
    try:
        # Add the missing column (Will throw an OperationalError if it already exists, which is fine to catch)
        cursor.execute("ALTER TABLE artists ADD COLUMN last_scanned_at DATETIME")
        print("Column 'last_scanned_at' added successfully.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("Column 'last_scanned_at' already exists.")
        else:
            print(f"Error adding column: {e}")
            
    try:
        # Delete all scandals
        cursor.execute("DELETE FROM scandals")
        print("All existing scandals wiped successfully.")
    except Exception as e:
        print(f"Error deleting scandals: {e}")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    migrate()
