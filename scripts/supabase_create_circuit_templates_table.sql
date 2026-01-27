-- ============================================
-- Create circuit_templates table for melted CSV import
-- ===========================================

-- Drop existing table if it exists
DROP TABLE IF EXISTS circuit_templates CASCADE;

-- Create table matching melted CSV structure
CREATE TABLE circuit_templates (
    -- Primary key
    id SERIAL PRIMARY KEY,

    -- Circuit identification
    circuit_id INTEGER NOT NULL,
    circuit_name TEXT NOT NULL,
    circuit_description TEXT,
    circuit_type TEXT NOT NULL,

    -- Exercise sequence information
    exercise_sequence INTEGER NOT NULL DEFAULT 0,
    total_exercises INTEGER NOT NULL DEFAULT 1,

    -- Movement information
    movement_id INTEGER,
    movement_name TEXT,
    metric_type TEXT,

    -- Exercise metrics
    reps INTEGER,
    distance_meters INTEGER,
    duration_seconds INTEGER,
    calories INTEGER,
    rest_seconds INTEGER,
    notes TEXT,
    rx_weight_male NUMERIC(10, 2),
    rx_weight_female NUMERIC(10, 2),

    -- Circuit configuration
    default_rounds INTEGER,
    default_duration_seconds INTEGER,
    difficulty_tier TEXT,
    min_recovery_hours NUMERIC(5, 2),

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add indexes for performance
CREATE INDEX idx_circuit_templates_circuit_id ON circuit_templates(circuit_id);
CREATE INDEX idx_circuit_templates_movement_id ON circuit_templates(movement_id);

-- Add comments
COMMENT ON TABLE circuit_templates IS 'Melted circuit templates - one row per exercise per circuit';
COMMENT ON COLUMN circuit_templates.circuit_id IS 'Reference to original circuit template ID';
COMMENT ON COLUMN circuit_templates.exercise_sequence IS 'Order of exercise within circuit (1, 2, 3...)';
COMMENT ON COLUMN circuit_templates.total_exercises IS 'Total number of exercises in this circuit';
COMMENT ON COLUMN circuit_templates.movement_id IS 'Reference to movements table';
COMMENT ON COLUMN circuit_templates.metric_type IS 'Type of metric (reps, time, distance, calories)';

-- ============================================
-- Verification query
-- ============================================
-- Check table structure
SELECT 
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'circuit_templates'
ORDER BY ordinal_position;
