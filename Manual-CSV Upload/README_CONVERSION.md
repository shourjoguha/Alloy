# SQL to CSV Conversion Summary

## Overview
Successfully converted all INSERT statements from `cleaned_dump.sql` to properly formatted CSV files.

## Conversion Statistics
- **Total Tables Converted:** 29
- **Total Rows Extracted:** 13,861
- **Output Directory:** `/Users/shourjosmac/Documents/alloy/Manual-CSV Upload`

## Files Created

### Core Tables
- `activity_definitions.csv` - 19 rows (activity definitions)
- `circuit_templates.csv` - 27 rows (CrossFit circuit templates with exercises)
- `users.csv` - 8 rows (user accounts)
- `programs.csv` - 58 rows (workout programs)
- `microcycles.csv` - 462 rows (program microcycles)

### Sessions & Exercises
- `sessions.csv` - 4,620 rows (training sessions)
- `sessions_legacy_temp.csv` - 4,480 rows (legacy session data)
- `session_exercises.csv` - 174 rows (session exercises)

### Movement Data
- `movements.csv` - 439 rows (movement catalog)
- `movements_legacy.csv` - 389 rows (legacy movement data)
- `movement_coaching_cues.csv` - 1,082 rows (coaching instructions)
- `movement_disciplines.csv` - 235 rows (movement-discipline mapping)
- `movement_equipment.csv` - 432 rows (movement-equipment mapping)
- `movement_muscle_map.csv` - 612 rows (movement-muscle mapping)
- `movement_relationships.csv` - 21 rows (movement relationships)
- `movement_tags.csv` - 466 rows (movement tags)

### Reference Data
- `muscles.csv` - 19 rows (muscle catalog)
- `equipment.csv` - 28 rows (equipment catalog)
- `tags.csv` - 30 rows (tag catalog)
- `heuristic_configs.csv` - 10 rows (heuristic configurations)

### User Data
- `user_profiles.csv` - 1 row (user preferences)
- `user_settings.csv` - 1 row (user settings)
- `user_enjoyable_activities.csv` - 9 rows (user activity preferences)
- `user_movement_rules.csv` - 6 rows (user movement rules)
- `favorites.csv` - 2 rows (user favorites)
- `soreness_logs.csv` - 7 rows (soreness tracking)
- `muscle_recovery_states.csv` - 1 row (recovery states)

### System
- `alembic_version.csv` - 1 row (database version)
- `program_disciplines.csv` - 222 rows (program-discipline mapping)

## Features

### Special Character Handling
- Properly handles quotes (single and double)
- Escapes commas and newlines within fields
- Preserves special characters in text fields

### JSON Column Support
- Automatically detects JSON columns (by name and content validation)
- Preserves JSON structure without extra escaping
- Validates JSON before writing to CSV
- JSON columns are written directly without CSV quoting to maintain proper format

### NULL Value Handling
- SQL NULL values are converted to empty strings
- Maintains data integrity

### CSV Formatting
- Uses proper CSV quoting (QUOTE_NONNUMERIC)
- Headers are always quoted
- Numeric columns remain unquoted for readability
- Text columns with special characters are properly quoted

## Technical Details

### Parser Features
- Handles multi-line INSERT statements
- Parses quoted strings with embedded commas
- Handles SQL escape sequences (double quotes, backslashes)
- Robust regex-based parsing with fallback handling

### JSON Detection
- Detects columns with 'json' or 'blob' in name
- Validates by attempting JSON parse
- Preserves original JSON structure

### Error Handling
- Logs warning for unparsed lines
- Continues processing on errors
- Creates detailed conversion log

## Usage

The CSV files can be:
1. Imported directly into spreadsheet applications (Excel, Google Sheets)
2. Loaded into database management tools
3. Processed by data analysis scripts
4. Used for data migration and backup purposes

## Notes

### Large Files
- `sessions.csv` (4,620 rows)
- `sessions_legacy_temp.csv` (4,480 rows)
- `movement_coaching_cues.csv` (1,082 rows)

### Complex JSON Columns
- `circuit_templates.exercises_json` - Contains exercise arrays
- `sessions.intent_tags` - Contains tag arrays
- `movements.embedding_vector` - Contains numeric arrays
- `user_profiles.*` - Contains preference objects

### Encoding
- All files use UTF-8 encoding
- Supports international characters
- Preserves emoji and special symbols

## Log Files

### conversion_log.txt
Contains detailed information about:
- Each table processed
- Number of columns and rows
- Which columns contain JSON data
- Output file paths

## Verification

The CSV files have been verified for:
- Proper header structure
- Correct row counts matching SQL
- Valid JSON formatting
- Proper escaping of special characters
- UTF-8 encoding compatibility

---
**Conversion Date:** 2026-01-27
**Script:** convert_sql_to_csv_fixed.py
**Source:** cleaned_dump.sql
