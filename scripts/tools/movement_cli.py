"""
CLI tool for managing movements and relationships dynamically.

Usage examples:
    # Add a single movement interactively
    python -m scripts.tools.movement_cli add-movement
    
    # Add movement from JSON file
    python -m scripts.tools.movement_cli add-movement --file movement.json
    
    # Add a relationship
    python -m scripts.tools.movement_cli add-relationship \\
        --source "Barbell Squat" \\
        --target "Goblet Squat" \\
        --type regression \\
        --notes "Easier variation"
    
    # Import movements and relationships from JSON
    python -m scripts.tools.movement_cli import --file movements.json
    
    # Get movement summary
    python -m scripts.tools.movement_cli show "Barbell Squat"
    
    # List all movements
    python -m scripts.tools.movement_cli list
"""
import argparse
import asyncio
import json
import sys
from typing import Dict, Any

from scripts.tools.movement_manager import MovementManager


def get_movement_input_interactive() -> Dict[str, Any]:
    """Get movement data from user via interactive prompts."""
    print("\n=== Add New Movement ===\n")
    
    movement_data = {
        "name": input("Movement name: ").strip(),
        "pattern": input("Pattern (squat, hinge, horizontal_push, etc.): ").strip() or "isolation",
        "primary_muscle": input("Primary muscle (quadriceps, hamstrings, glutes, etc.): ").strip() or "full_body",
        "primary_region": input("Primary region (anterior_lower, posterior_upper, etc.): ").strip() or "full_body",
        "skill_level": input("Skill level (beginner, intermediate, advanced, expert): ").strip() or "intermediate",
        "compound": input("Is compound? (y/n): ").strip().lower() == "y",
        "tier": input("Tier (bronze, silver, gold, diamond): ").strip() or "bronze",
    }
    
    equipment = input("Equipment (comma-separated, or press Enter to skip): ").strip()
    if equipment:
        movement_data["equipment"] = [e.strip() for e in equipment.split(",")]
    
    tags = input("Tags (comma-separated, or press Enter to skip): ").strip()
    if tags:
        movement_data["tags"] = [t.strip() for t in tags.split(",")]
    
    disciplines = input("Disciplines (comma-separated, or press Enter to skip): ").strip()
    if disciplines:
        movement_data["disciplines"] = [d.strip() for d in disciplines.split(",")]
    
    notes = input("Description (or press Enter to skip): ").strip()
    if notes:
        movement_data["description"] = notes
    
    return movement_data


async def add_movement_command(args):
    """Handle add-movement command."""
    if args.file:
        with open(args.file, 'r') as f:
            movement_data = json.load(f)
    else:
        movement_data = get_movement_input_interactive()
    
    async with MovementManager() as manager:
        movement = await manager.add_movement(movement_data)
        if movement:
            print(f"\n✅ Movement created successfully!")
            print(f"   ID: {movement.id}")
            print(f"   Name: {movement.name}")
            print(f"   Tier: {movement.tier.value}")
        else:
            print("\n❌ Failed to create movement.")
            sys.exit(1)


async def add_relationship_command(args):
    """Handle add-relationship command."""
    async with MovementManager() as manager:
        success = await manager.add_relationship(
            args.source,
            args.target,
            args.type,
            args.notes
        )
        if success:
            print(f"\n✅ Relationship created successfully!")
        else:
            print(f"\n❌ Failed to create relationship.")
            sys.exit(1)


async def import_command(args):
    """Handle import command."""
    async with MovementManager() as manager:
        results = await manager.import_from_json(args.file)
        
        print("\n=== Import Results ===")
        print(f"Movements created: {results['movements_created']}")
        print(f"Movements failed: {results['movements_failed']}")
        print(f"Relationships created: {results['relationships_created']}")
        print(f"Relationships failed: {results['relationships_failed']}")
        
        if results['movements_failed'] > 0 or results['relationships_failed'] > 0:
            print("\n⚠️  Some items failed to import. Check logs above.")


async def show_command(args):
    """Handle show command."""
    async with MovementManager() as manager:
        summary = await manager.get_movement_summary(args.movement)
        
        if summary:
            print(f"\n=== Movement Summary ===")
            print(f"Name: {summary['name']}")
            print(f"ID: {summary['id']}")
            print(f"Pattern: {summary['pattern']}")
            print(f"Primary Muscle: {summary['primary_muscle']}")
            print(f"Tier: {summary['tier']}")
            print(f"Skill Level: {summary['skill_level']}")
            print(f"Outgoing Relationships: {summary['outgoing_relationships']}")
            print(f"Incoming Relationships: {summary['incoming_relationships']}")
        else:
            print(f"\n❌ Movement not found: {args.movement}")
            sys.exit(1)


async def list_command(args):
    """Handle list command."""
    from app.models.movement import Movement
    from sqlalchemy import select
    from app.db.database import async_session_maker
    
    async with async_session_maker() as db:
        result = await db.execute(
            select(Movement).order_by(Movement.name)
        )
        movements = result.scalars().all()
        
        print(f"\n=== Movements ({len(movements)}) ===")
        for m in movements:
            print(f"  {m.name} ({m.tier.value}, {m.pattern.value})")


def create_parser() -> argparse.ArgumentParser:
    """Create CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Movement Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Add movement interactively
  python -m scripts.tools.movement_cli add-movement
  
  # Add movement from JSON
  python -m scripts.tools.movement_cli add-movement --file movement.json
  
  # Add relationship
  python -m scripts.tools.movement_cli add-relationship \\
      --source "Barbell Squat" \\
      --target "Goblet Squat" \\
      --type regression
  
  # Import from JSON
  python -m scripts.tools.movement_cli import --file movements.json
  
  # Show movement details
  python -m scripts.tools.movement_cli show "Barbell Squat"
  
  # List all movements
  python -m scripts.tools.movement_cli list
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # add-movement command
    add_movement_parser = subparsers.add_parser(
        "add-movement",
        help="Add a new movement"
    )
    add_movement_parser.add_argument(
        "--file", "-f",
        help="JSON file containing movement data"
    )
    add_movement_parser.set_defaults(func=add_movement_command)
    
    # add-relationship command
    add_relationship_parser = subparsers.add_parser(
        "add-relationship",
        help="Add a relationship between movements"
    )
    add_relationship_parser.add_argument(
        "--source", "-s",
        required=True,
        help="Source movement name"
    )
    add_relationship_parser.add_argument(
        "--target", "-t",
        required=True,
        help="Target movement name"
    )
    add_relationship_parser.add_argument(
        "--type", "-r",
        required=True,
        choices=["progression", "regression", "variation", "antagonist"],
        help="Relationship type"
    )
    add_relationship_parser.add_argument(
        "--notes", "-n",
        help="Optional notes about the relationship"
    )
    add_relationship_parser.set_defaults(func=add_relationship_command)
    
    # import command
    import_parser = subparsers.add_parser(
        "import",
        help="Import movements and relationships from JSON"
    )
    import_parser.add_argument(
        "--file", "-f",
        required=True,
        help="JSON file containing movements and relationships"
    )
    import_parser.set_defaults(func=import_command)
    
    # show command
    show_parser = subparsers.add_parser(
        "show",
        help="Show details of a specific movement"
    )
    show_parser.add_argument(
        "movement",
        help="Movement name"
    )
    show_parser.set_defaults(func=show_command)
    
    # list command
    subparsers.add_parser(
        "list",
        help="List all movements"
    ).set_defaults(func=list_command)
    
    return parser


def main():
    """Main entry point for CLI."""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    asyncio.run(args.func(args))


if __name__ == "__main__":
    main()
