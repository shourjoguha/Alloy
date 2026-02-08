-- ============================================
-- Create circuit_templates table for melted CSV import
-- ===========================================

-- Drop existing table and view if they exist
DROP VIEW IF EXISTS circuit_templates_view CASCADE;
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
-- Create view to reconstruct circuits (for easier querying)
-- ============================================
CREATE VIEW circuit_templates_view AS
SELECT 
    circuit_id,
    circuit_name,
    circuit_description,
    circuit_type,
    -- Aggregate exercises
    array_agg(
        json_build_object(
            'exercise_sequence', exercise_sequence,
            'movement_id', movement_id,
            'movement_name', movement_name,
            'metric_type', metric_type,
            'reps', reps,
            'distance_meters', distance_meters,
            'duration_seconds', duration_seconds,
            'calories', calories,
            'rest_seconds', rest_seconds,
            'notes', notes,
            'rx_weight_male', rx_weight_male,
            'rx_weight_female', rx_weight_female
        ) ORDER BY exercise_sequence
    ) as exercises,
    -- Circuit-level metadata (from first exercise row)
    default_rounds,
    default_duration_seconds,
    difficulty_tier,
    min_recovery_hours,
    -- Counts
    COUNT(*) as total_exercises_count,
    created_at,
    updated_at
FROM circuit_templates
GROUP BY 
    circuit_id, circuit_name, circuit_description, circuit_type,
    default_rounds, default_duration_seconds, difficulty_tier, min_recovery_hours,
    created_at, updated_at;

COMMENT ON VIEW circuit_templates_view IS 'Reconstructed circuit templates with exercises as JSON array';

-- ============================================
-- Verification queries
-- ============================================

-- Check table structure
SELECT 
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'circuit_templates'
ORDER BY ordinal_position;

-- Sample data check
SELECT * FROM circuit_templates LIMIT 5;

-- View sample data (reconstructed circuits)
SELECT 
    circuit_id,
    circuit_name,
    jsonb_pretty(exercises) as exercises_formatted
FROM circuit_templates_view
LIMIT 3;
