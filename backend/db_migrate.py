import sqlite3
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def migrate():
    conn = sqlite3.connect('spotiscandals.db')
    cursor = conn.cursor()
    
    try:
        # Add the missing column (Will throw an OperationalError if it already exists, which is fine to catch)
        cursor.execute("ALTER TABLE artists ADD COLUMN last_scanned_at DATETIME")
        logger.info("Column 'last_scanned_at' added successfully.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            logger.info("Column 'last_scanned_at' already exists.")
        else:
            logger.error("Error adding column: %s", e)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    migrate()
