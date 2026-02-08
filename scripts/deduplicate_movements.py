#!/usr/bin/env python3
"""
Master script to execute movement deduplication pipeline.

Execution Order:
1. analyze_movement_dependencies.py
2. detect_movement_duplicates.py
3. normalize_movement_names.py --dry-run
4. normalize_movement_names.py --apply
5. merge_duplicate_movements.py --dry-run
6. merge_duplicate_movements.py --apply
7. validate_movement_merge.py
"""
import asyncio
import sys
import subprocess
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent


class ScriptExecutor:
    """Executes deduplication scripts in order."""
    
    def __init__(self):
        self.scripts_dir = SCRIPTS_DIR
    
    def run_script(self, script_name: str, args: list[str] = None) -> bool:
        """Run a Python script and return success status."""
        script_path = self.scripts_dir / script_name
        
        if not script_path.exists():
            print(f"❌ Script not found: {script_name}")
            return False
        
        print(f"\n📋 Running: {script_name}...")
        
        cmd = [sys.executable, str(script_path)]
        if args:
            cmd.extend(args)
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.scripts_dir.parent,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                print(f"❌ Script failed with exit code {result.returncode}")
                if result.stdout:
                    print(f"STDOUT:\n{result.stdout}")
                if result.stderr:
                    print(f"STDERR:\n{result.stderr}")
                return False
            
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr)
            
            print(f"✅ {script_name} completed successfully")
            return True
            
        except subprocess.TimeoutExpired:
            print(f"❌ Script timed out: {script_name}")
            return False
        except Exception as e:
            print(f"❌ Error running {script_name}: {e}")
            return False
    
    def run_pipeline(self, dry_run: bool = False, verbose: bool = False) -> bool:
        """Run entire deduplication pipeline."""
        print("\n" + "="*80)
        print("MOVEMENT DEDUPLICATION PIPELINE")
        print("="*80)
        
        dry_run_flag = ["--dry-run"] if dry_run else []
        verbose_flags = ["--verbose"] if verbose else []
        
        steps = [
            ("analyze_movement_dependencies.py", "Phase 1: Dependency Analysis", []),
            ("detect_movement_duplicates.py", "Phase 2: Duplicate Detection", []),
            ("normalize_movement_names.py", "Phase 3: Name Normalization (Dry Run)", ["--dry-run"] + verbose_flags),
            ("normalize_movement_names.py", "Phase 3: Name Normalization (Apply)", ["--apply"] + verbose_flags),
            ("merge_duplicate_movements.py", "Phase 4: Merge Movements (Dry Run)", ["--dry-run"] + verbose_flags),
            ("merge_duplicate_movements.py", "Phase 4: Merge Movements (Apply)", verbose_flags),
            ("validate_movement_merge.py", "Phase 5: Validation", []),
        ]
        
        results = []
        
        for i, (script_name, description, args) in enumerate(steps, 1):
            print(f"\n{'='*80}")
            print(f"STEP {i}: {description}")
            print(f"{'='*80}")
            
            success = self.run_script(script_name, args)
            results.append((script_name, success))
            
            if not success:
                print(f"\n❌ Pipeline failed at step {i}: {script_name}")
                print("\n" + "="*80)
                print("PIPELINE FAILED")
                print("="*80)
                return False
        
        print("\n" + "="*80)
        print("PIPELINE COMPLETION SUMMARY")
        print("="*80)
        
        for script_name, success in results:
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{status}: {script_name}")
        
        all_passed = all(success for _, success in results)
        
        print("\n" + "="*80)
        if all_passed:
            print("✅ ALL STEPS COMPLETED SUCCESSFULLY")
        else:
            print("⚠️  SOME STEPS FAILED - Review logs above")
        print("="*80 + "\n")
        
        return all_passed


async def main():
    """Main execution function."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Execute movement deduplication pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying them (stops after Phase 3 dry run)"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output for all scripts"
    )
    
    args = parser.parse_args()
    
    executor = ScriptExecutor()
    success = executor.run_pipeline(
        dry_run=args.dry_run,
        verbose=args.verbose
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
