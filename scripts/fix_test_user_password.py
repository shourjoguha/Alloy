"""Script to fix the test user password using raw SQL."""
import asyncio
import bcrypt
import os
from dotenv import load_dotenv

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text


async def check_and_update_password():
    """Check current password and update if needed."""
    # Load environment variables
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        print("ERROR: DATABASE_URL not found in environment!")
        return

    print(f"Database URL: {database_url}")

    # Create engine
    engine = create_async_engine(
        database_url,
        echo=False
    )

    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as db:
        # Get current user data
        result = await db.execute(
            text("SELECT id, email, hashed_password FROM users WHERE email = 'gainsmith@gainsly.com'")
        )
        row = result.fetchone()

        if not row:
            print("ERROR: User gainsmith@gainsly.com not found!")
            return

        user_id, email, current_hash = row
        print(f"User found: ID={user_id}, Email={email}")
        print(f"Current password hash: {current_hash}")

        # Test various passwords
        test_passwords = [
            'password123',
            'gainsmith123',
            'gainsmith',
            'password'
        ]

        print("\nTesting passwords:")
        for pwd in test_passwords:
            try:
                result = bcrypt.checkpw(
                    pwd.encode('utf-8'),
                    current_hash.encode('utf-8')
                )
                print(f"  '{pwd}': {'MATCH!' if result else 'failed'}")
                if result:
                    print(f"  ✓ Password '{pwd}' is correct!")
                    break
            except Exception as e:
                print(f"  '{pwd}': Error - {e}")

        # Update to password123 if it doesn't match
        print("\nUpdating password to 'password123'...")
        new_hash = bcrypt.hashpw('password123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        print(f"New hash: {new_hash}")

        await db.execute(
            text("UPDATE users SET hashed_password = :hash WHERE email = 'gainsmith@gainsly.com'"),
            {"hash": new_hash}
        )
        await db.commit()

        # Verify the update
        result = await db.execute(
            text("SELECT hashed_password FROM users WHERE email = 'gainsmith@gainsly.com'")
        )
        updated_hash = result.fetchone()[0]
        print(f"Updated hash in database: {updated_hash}")

        print("\nVerifying new password:")
        if bcrypt.checkpw('password123'.encode('utf-8'), updated_hash.encode('utf-8')):
            print("✓ Password 'password123' now works correctly!")
        else:
            print("✗ Password verification failed!")

        print("\n" + "="*60)
        print("SUCCESS! You can now login with:")
        print("  Email:    gainsmith@gainsly.com")
        print("  Password: password123")
        print("="*60)


if __name__ == "__main__":
    asyncio.run(check_and_update_password())
