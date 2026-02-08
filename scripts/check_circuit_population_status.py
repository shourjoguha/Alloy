"""Check which circuits have been populated."""

import asyncio
import sys
from pathlib import Path
from sqlalchemy import text, func

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.database import get_db


async def main():
    """Check circuit population status."""
    async for db in get_db():
        try:
            # Get circuit counts
            result = await db.execute(text("""
                SELECT 
                    (SELECT COUNT(*) FROM circuit_templates) as total_circuits,
                    (SELECT COUNT(*) FROM circuits_melted) as melted_records,
                    (SELECT COUNT(*) FROM circuits_macro) as macro_records,
                    (SELECT COUNT(DISTINCT circuit_id) FROM circuits_melted) as circuits_with_melted,
                    (SELECT COUNT(DISTINCT circuit_id) FROM circuits_macro) as circuits_with_macro
            """))
            row = result.one()
            
            print("Circuit table population status:")
            print("-" * 80)
            print(f"Total circuits: {row.total_circuits}")
            print(f"Melted records: {row.melted_records}")
            print(f"Macro records: {row.macro_records}")
            print(f"Circuits with melted data: {row.circuits_with_melted}")
            print(f"Circuits with macro data: {row.circuits_with_macro}")
            print("-" * 80)
            
        except Exception as e:
            print(f"Error: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
