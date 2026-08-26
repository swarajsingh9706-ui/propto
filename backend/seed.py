"""
One-time seeding for self-hosted deployments.

Run this once from the cPanel Python App terminal (inside the virtualenv):
    python seed.py

It creates the MongoDB indexes and seeds the super admin + demo society,
exactly like the app's startup event. Safe to run more than once (idempotent).
"""
import asyncio
from server import startup

if __name__ == "__main__":
    asyncio.run(startup())
    print("Seeding complete.")
