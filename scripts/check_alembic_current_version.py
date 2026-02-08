"""Check current alembic version."""

import asyncio
import sys
from pathlib import Path
from sqlalchemy import text

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.database import get_db


async def main():
    """Check current alembic version."""
    async for db in get_db():
        try:
            result = await db.execute(text("SELECT version_num FROM alembic_version"))
            version = result.scalar()
            print(f"Current alembic version: {version}")
            
        except Exception as e:
            print(f"Error: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
