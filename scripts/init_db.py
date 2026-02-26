"""
Database initialization script.
Run standalone to create tables and optionally seed sample data.

Usage:
    python scripts/init_db.py
    python scripts/init_db.py --seed
"""

import sys
import os

# Add backend to path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from database import init_db, SessionLocal
from models import Artist, Scandal, ScandalSource


def seed_sample_data():
    """Insert sample data for development and testing."""
    db = SessionLocal()
    try:
        # Sample artists
        artists = [
            Artist(
                name="Kanye West",
                spotify_id="5K4W6rqBFWDnAN6FQUkS6x",
                image_url="https://i.scdn.co/image/ab6761610000e5eb6e835a500e791bf9c27f9c2a",
                approved=True,
            ),
            Artist(
                name="Drake",
                spotify_id="3TVXtAsR1Inumwj472S9r4",
                image_url="https://i.scdn.co/image/ab6761610000e5eb4293385d429161f6e1db9cf9",
                approved=True,
            ),
            Artist(
                name="Taylor Swift",
                spotify_id="06HL4z0CvFAxyc27GXpf02",
                image_url="https://i.scdn.co/image/ab6761610000e5ebe672b5f553298dcdccb0e676",
                approved=False,
            ),
        ]

        for artist in artists:
            existing = db.query(Artist).filter(Artist.spotify_id == artist.spotify_id).first()
            if not existing:
                db.add(artist)

        db.commit()

        # Sample scandal
        kanye = db.query(Artist).filter(Artist.spotify_id == "5K4W6rqBFWDnAN6FQUkS6x").first()
        if kanye:
            existing_scandal = db.query(Scandal).filter(Scandal.artist_id == kanye.id).first()
            if not existing_scandal:
                scandal = Scandal(
                    artist_id=kanye.id,
                    description="Antisemitic remarks on social media leading to major brand partnerships being terminated.",
                    verified=False,
                )
                db.add(scandal)
                db.flush()

                source = ScandalSource(
                    scandal_id=scandal.id,
                    source_url="https://www.bbc.com/news/entertainment-arts-63377767",
                )
                db.add(source)
                db.commit()

        print("[OK] Sample data seeded")

    finally:
        db.close()


if __name__ == "__main__":
    print("Initializing database...")
    init_db()
    print("[OK] Tables created")

    if "--seed" in sys.argv:
        print("Seeding sample data...")
        seed_sample_data()

    print("Done!")
