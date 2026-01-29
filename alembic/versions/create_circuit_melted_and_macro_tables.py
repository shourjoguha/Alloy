"""Create circuits_melted and circuits_macro tables

Revision ID: create_circuit_melted_and_macro_tables
Revises: remove_old_muscle_unique
Create Date: 2026-01-29

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "circuit_melted_macro_tables"
down_revision: Union[str, Sequence[str], None] = "remove_old_muscle_unique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # Check if tables already exist and skip creation if they do
    if inspector.has_table("circuits_melted"):
        print("circuits_melted table already exists, skipping creation")
        if inspector.has_table("circuits_macro"):
            print("circuits_macro table already exists, skipping creation")
            return
    
    # Add calories to metrictype enum if not present
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum 
                JOIN pg_type ON pg_enum.enumtypid = pg_type.oid 
                WHERE pg_type.typname = 'metrictype' 
                AND pg_enum.enumlabel = 'calories'
            ) THEN
                ALTER TYPE metrictype ADD VALUE 'calories' AFTER 'distance';
            END IF;
        END$$;
    """)
    
    # Create primaryregion enum if not exists
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'primaryregion') THEN
                CREATE TYPE primaryregion AS ENUM (
                    'anterior_upper',
                    'posterior_upper',
                    'shoulder',
                    'upper_body',
                    'anterior_lower',
                    'posterior_lower',
                    'lower_body',
                    'full_body'
                );
            END IF;
        END$$;
    """)

    # Create circuits_melted table (use raw SQL for enum type)
    op.execute("""
        CREATE TABLE circuits_melted (
            id SERIAL PRIMARY KEY,
            circuit_id INTEGER NOT NULL REFERENCES circuit_templates(id) ON DELETE CASCADE,
            movement_id INTEGER REFERENCES movements(id) ON DELETE RESTRICT,
            exercise_sequence INTEGER NOT NULL,
            movement_name VARCHAR(200) NOT NULL,
            metric_type metrictype NOT NULL,
            reps INTEGER,
            distance_meters FLOAT,
            duration_seconds INTEGER,
            calories INTEGER,
            rest_seconds INTEGER,
            notes TEXT,
            rx_weight_male FLOAT,
            rx_weight_female FLOAT,
            created_at FLOAT,
            updated_at FLOAT,
            CONSTRAINT valid_exercise_sequence CHECK (exercise_sequence > 0),
            CONSTRAINT at_least_one_metric CHECK (
                (reps IS NOT NULL) OR 
                (distance_meters IS NOT NULL) OR 
                (duration_seconds IS NOT NULL) OR 
                (calories IS NOT NULL)
            ),
            CONSTRAINT uq_circuit_exercise_sequence UNIQUE (circuit_id, exercise_sequence)
        )
    """)
    
    # Indexes for circuits_melted
    op.create_index(op.f("ix_circuits_melted_circuit_id"), "circuits_melted", ["circuit_id"], unique=False)
    op.create_index(op.f("ix_circuits_melted_movement_id"), "circuits_melted", ["movement_id"], unique=False)
    op.create_index(op.f("ix_circuits_melted_exercise_sequence"), "circuits_melted", ["exercise_sequence"], unique=False)
    op.create_index(op.f("ix_circuits_melted_metric_type"), "circuits_melted", ["metric_type"], unique=False)
    
    # Covering index for circuit reconstruction
    op.create_index(
        op.f("ix_circuits_melted_reconstruction"),
        "circuits_melted",
        ["circuit_id", "exercise_sequence"],
        unique=False
    )

    # Create circuits_macro table (use raw SQL for enum type)
    op.execute("""
        CREATE TABLE circuits_macro (
            circuit_id INTEGER PRIMARY KEY REFERENCES circuit_templates(id) ON DELETE CASCADE,
            total_exercises INTEGER NOT NULL,
            unique_movements INTEGER NOT NULL,
            total_reps INTEGER,
            total_distance_meters FLOAT,
            total_work_seconds INTEGER,
            total_rest_seconds INTEGER,
            estimated_duration_seconds INTEGER,
            difficulty_tier movementtier NOT NULL,
            min_recovery_hours INTEGER NOT NULL,
            max_rx_weight_male FLOAT,
            max_rx_weight_female FLOAT,
            primary_muscles JSONB NOT NULL,
            muscle_engagement_score FLOAT NOT NULL,
            primary_region primaryregion NOT NULL DEFAULT 'full_body',
            region_diversity_score FLOAT NOT NULL DEFAULT 0.0,
            required_equipment JSONB NOT NULL,
            equipment_complexity INTEGER NOT NULL,
            movement_pattern_counts JSONB NOT NULL,
            pattern_diversity_score FLOAT NOT NULL,
            metabolic_profile JSONB NOT NULL,
            estimated_calories_per_hour INTEGER,
            space_requirement_meters FLOAT,
            station_count INTEGER NOT NULL,
            default_rounds INTEGER,
            circuit_type_intensity FLOAT NOT NULL,
            data_completeness_score FLOAT NOT NULL,
            validation_errors JSONB NOT NULL,
            created_at FLOAT,
            updated_at FLOAT,
            CONSTRAINT valid_exercise_count CHECK (total_exercises >= 1),
            CONSTRAINT valid_unique_movements CHECK (unique_movements >= 1),
            CONSTRAINT valid_recovery CHECK (min_recovery_hours >= 0)
        )
    """)
    
    # Indexes for circuits_macro
    op.create_index(op.f("ix_circuits_macro_circuit_id"), "circuits_macro", ["circuit_id"], unique=True)
    op.create_index(op.f("ix_circuits_macro_total_exercises"), "circuits_macro", ["total_exercises"], unique=False)
    op.create_index(op.f("ix_circuits_macro_difficulty_tier"), "circuits_macro", ["difficulty_tier"], unique=False)
    op.create_index(op.f("ix_circuits_macro_estimated_duration_seconds"), "circuits_macro", ["estimated_duration_seconds"], unique=False)
    op.create_index(op.f("ix_circuits_macro_primary_region"), "circuits_macro", ["primary_region"], unique=False)
    
    # GIN indexes for JSONB columns
    op.create_index(
        op.f("ix_circuits_macro_primary_muscles_gin"),
        "circuits_macro",
        ["primary_muscles"],
        unique=False,
        postgresql_using="gin"
    )
    op.create_index(
        op.f("ix_circuits_macro_required_equipment_gin"),
        "circuits_macro",
        ["required_equipment"],
        unique=False,
        postgresql_using="gin"
    )
    op.create_index(
        op.f("ix_circuits_macro_movement_pattern_counts_gin"),
        "circuits_macro",
        ["movement_pattern_counts"],
        unique=False,
        postgresql_using="gin"
    )
    op.create_index(
        op.f("ix_circuits_macro_metabolic_profile_gin"),
        "circuits_macro",
        ["metabolic_profile"],
        unique=False,
        postgresql_using="gin"
    )


def downgrade() -> None:
    # Drop circuits_macro table and indexes
    op.drop_index(op.f("ix_circuits_macro_metabolic_profile_gin"), table_name="circuits_macro")
    op.drop_index(op.f("ix_circuits_macro_movement_pattern_counts_gin"), table_name="circuits_macro")
    op.drop_index(op.f("ix_circuits_macro_required_equipment_gin"), table_name="circuits_macro")
    op.drop_index(op.f("ix_circuits_macro_primary_muscles_gin"), table_name="circuits_macro")
    op.drop_index(op.f("ix_circuits_macro_estimated_duration_seconds"), table_name="circuits_macro")
    op.drop_index(op.f("ix_circuits_macro_difficulty_tier"), table_name="circuits_macro")
    op.drop_index(op.f("ix_circuits_macro_total_exercises"), table_name="circuits_macro")
    op.drop_index(op.f("ix_circuits_macro_circuit_id"), table_name="circuits_macro")
    op.drop_table("circuits_macro")
    
    # Drop circuits_melted table and indexes
    op.drop_index(op.f("ix_circuits_melted_reconstruction"), table_name="circuits_melted")
    op.drop_index(op.f("ix_circuits_melted_metric_type"), table_name="circuits_melted")
    op.drop_index(op.f("ix_circuits_melted_exercise_sequence"), table_name="circuits_melted")
    op.drop_index(op.f("ix_circuits_melted_movement_id"), table_name="circuits_melted")
    op.drop_index(op.f("ix_circuits_melted_circuit_id"), table_name="circuits_melted")
    op.drop_table("circuits_melted")
