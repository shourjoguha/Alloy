# Implementation Plan: Execute Circuit Melted and Macro Tables

## Execution Strategy
Execute in 6 phases with careful testing at each step, using multiple specialized agents for coordination and review.

## Phase 1: Database Schema Design & Migration
- Design circuits_melted and circuits_macro tables
- Update CircuitTemplate model with relationships
- Create Alembic migration
- Test migration and verify schema

## Phase 2: Normalization Logic
- Implement main lift baseline calculation
- Implement 50% normalization function
- Test normalization logic

## Phase 3: Population Script
- Create populate_circuit_tables.py
- Implement melted table population
- Implement macro table population with normalization
- Run and validate

## Phase 4: Circuit Comparability
- Extract pattern and region data
- Add comparability fields to macro table

## Phase 5: API Integration
- Update Circuit API
- Update Session Generator
- Update Optimization Service
- Test performance

## Phase 6: Documentation & Final Testing
- Update documentation
- Final validation

## Agents to Use
- database-admin, postgres-pro: Schema design and migration
- python-pro: Model updates and logic implementation
- backend-developer, fullstack-developer: API integration
- data-scientist: Normalization logic
- architect-reviewer: Design review
- multiagent-coordinator: Coordination between phases
- error-detective, debugger: Testing and validation