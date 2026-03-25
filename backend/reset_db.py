import sqlite3
import os
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

db_path = os.path.join(os.path.dirname(__file__), 'spotiscandals.db')

if not os.path.exists(db_path):
    logger.error("Database not found at %s", db_path)
    sys.exit(1)

# Require explicit confirmation to prevent accidental data loss
confirmation = input("This will DELETE ALL scandals, votes, and community data. Type 'yes' to continue: ")
if confirmation.strip().lower() != "yes":
    logger.info("Aborted.")
    sys.exit(0)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    logger.info("Deleting scandals...")
    cursor.execute("DELETE FROM scandals")
    logger.info("Deleted %d scandals.", cursor.rowcount)

    logger.info("Deleting scandal sources...")
    cursor.execute("DELETE FROM scandal_sources")
    logger.info("Deleted %d sources.", cursor.rowcount)

    logger.info("Deleting scandal votes...")
    cursor.execute("DELETE FROM scandal_votings")
    logger.info("Deleted %d votes.", cursor.rowcount)

    logger.info("Deleting community scandals...")
    cursor.execute("DELETE FROM community_scandals")
    logger.info("Deleted %d community submissions.", cursor.rowcount)

    logger.info("Resetting artist states...")
    cursor.execute("UPDATE artists SET approved = 0, last_scanned_at = NULL")
    logger.info("Reset %d artists to pending status and cleared timestamps.", cursor.rowcount)

    conn.commit()
    logger.info("Database reset successfully! You can now start from scratch.")
except Exception as e:
    conn.rollback()
    logger.error("Error resetting database: %s", e)
finally:
    conn.close()
