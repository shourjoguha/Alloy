"""Verify movement relationships were created successfully."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import select
from app.db.database import async_session_maker
from app.models.movement import Movement, MovementRelationship

async def verify_relationships():
    """Verify relationships were created correctly."""
    async with async_session_maker() as db:
        result = await db.execute(
            select(MovementRelationship, Movement)
            .join(Movement, MovementRelationship.target_movement_id == Movement.id)
            .order_by(MovementRelationship.id)
            .limit(30)
        )
        
        relationships = result.scalars().all()
        
        print(f'Total relationships found: {len(relationships)}')
        print('\nSample relationships created:')
        print('-' * 80)
        
        for rel in relationships:
            result2 = await db.execute(
                select(Movement).where(Movement.id == rel.source_movement_id)
            )
            source = result2.scalar_one()
            
            result3 = await db.execute(
                select(Movement).where(Movement.id == rel.target_movement_id)
            )
            target = result3.scalar_one()
            
            print(f'{rel.relationship_type}: {source.name} -> {target.name}')
            if rel.notes:
                print(f'  Notes: {rel.notes}')
            print()
        
        print('-' * 80)
        
        from sqlalchemy import func
        count_by_type = await db.execute(
            select(MovementRelationship.relationship_type, func.count(MovementRelationship.id))
            .group_by(MovementRelationship.relationship_type)
        )
        
        print('\nRelationship count by type:')
        for rel_type, count in count_by_type:
            print(f'  {rel_type}: {count}')

if __name__ == '__main__':
    asyncio.run(verify_relationships())
