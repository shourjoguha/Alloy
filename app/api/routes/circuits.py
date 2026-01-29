from pathlib import Path
import json

from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.circuit import CircuitTemplate
from app.models.circuit_extended import CircuitMacro
from app.models.movement import Movement
from app.schemas.circuit import (
    CircuitTemplateResponse,
    CircuitTemplateUpdate,
    CircuitTemplateAdminDetail,
    CircuitMacroData,
    CircuitTemplateWithMacro,
)
from app.models.enums import CircuitType
from app.services.circuit_comparison import (
    CircuitComparisonService,
    CircuitSimilarityResult,
    CircuitRecommendation,
)
from app.config.settings import get_settings

router = APIRouter()
settings = get_settings()


async def require_admin(x_admin_token: str | None = Header(default=None)) -> bool:
    if settings.admin_api_token:
        if x_admin_token != settings.admin_api_token:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    else:
        if not settings.debug:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin features disabled")
    return True


def load_raw_workout_for_circuit(name: str) -> str | None:
    path = Path("seed_data") / "scraped_circuits.json"
    try:
        with path.open() as f:
            circuits_data = json.load(f)
    except FileNotFoundError:
        return None
    for item in circuits_data:
        if item.get("name") == name:
            return item.get("raw_workout") or item.get("description")
    return None


@router.get("", response_model=list[CircuitTemplateResponse])
async def list_circuits(
    circuit_type: CircuitType | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(CircuitTemplate)
    if circuit_type:
        query = query.where(CircuitTemplate.circuit_type == circuit_type)
    query = query.order_by(CircuitTemplate.name)
    result = await db.execute(query)
    circuits = result.scalars().all()
    
    # Enrich exercises_json with movement names
    movement_ids = set()
    for circuit in circuits:
        if circuit.exercises_json:
            for ex in circuit.exercises_json:
                if isinstance(ex, dict) and ex.get("movement_id"):
                    movement_ids.add(ex["movement_id"])
    
    if movement_ids:
        movements_result = await db.execute(select(Movement).where(Movement.id.in_(movement_ids)))
        movements = {m.id: m.name for m in movements_result.scalars().all()}
        
        for circuit in circuits:
            if circuit.exercises_json:
                # Create a copy to avoid mutating the DB object directly if not intended to persist
                # But here we want to return enriched data.
                # Since exercises_json is a mutable JSON type in SQLAlchemy, modifying it might mark it dirty.
                # However, for the response, we just need the data.
                new_exercises = []
                for ex in circuit.exercises_json:
                    if isinstance(ex, dict):
                        ex_copy = ex.copy()
                        mid = ex_copy.get("movement_id")
                        if mid and mid in movements and not ex_copy.get("movement_name"):
                            ex_copy["movement_name"] = movements[mid]
                        new_exercises.append(ex_copy)
                circuit.exercises_json = new_exercises

    return circuits


@router.get("/{circuit_id}", response_model=CircuitTemplateResponse)
async def get_circuit(
    circuit_id: int,
    db: AsyncSession = Depends(get_db),
):
    circuit = await db.get(CircuitTemplate, circuit_id)
    if not circuit:
        raise HTTPException(status_code=404, detail="Circuit not found")
        
    # Enrich exercises_json with movement names
    if circuit.exercises_json:
        movement_ids = set()
        for ex in circuit.exercises_json:
            if isinstance(ex, dict) and ex.get("movement_id"):
                movement_ids.add(ex["movement_id"])
        
        if movement_ids:
            movements_result = await db.execute(select(Movement).where(Movement.id.in_(movement_ids)))
            movements = {m.id: m.name for m in movements_result.scalars().all()}
            
            new_exercises = []
            for ex in circuit.exercises_json:
                if isinstance(ex, dict):
                    ex_copy = ex.copy()
                    mid = ex_copy.get("movement_id")
                    if mid and mid in movements and not ex_copy.get("movement_name"):
                        ex_copy["movement_name"] = movements[mid]
                    new_exercises.append(ex_copy)
            circuit.exercises_json = new_exercises
            
    return circuit


@router.get("/admin/{circuit_id}", response_model=CircuitTemplateAdminDetail)
async def get_circuit_admin(
    circuit_id: int,
    db: AsyncSession = Depends(get_db),
    admin: bool = Depends(require_admin),
):
    circuit = await db.get(CircuitTemplate, circuit_id)
    if not circuit:
        raise HTTPException(status_code=404, detail="Circuit not found")
        
    # Enrich exercises_json
    enriched_exercises = []
    if circuit.exercises_json:
        movement_ids = set()
        for ex in circuit.exercises_json:
            if isinstance(ex, dict) and ex.get("movement_id"):
                movement_ids.add(ex["movement_id"])
        
        movements = {}
        if movement_ids:
            movements_result = await db.execute(select(Movement).where(Movement.id.in_(movement_ids)))
            movements = {m.id: m.name for m in movements_result.scalars().all()}
            
        for ex in circuit.exercises_json:
            if isinstance(ex, dict):
                ex_copy = ex.copy()
                mid = ex_copy.get("movement_id")
                if mid and mid in movements and not ex_copy.get("movement_name"):
                    ex_copy["movement_name"] = movements[mid]
                enriched_exercises.append(ex_copy)
    else:
        enriched_exercises = []

    raw_workout = load_raw_workout_for_circuit(circuit.name)
    return CircuitTemplateAdminDetail(
        id=circuit.id,
        name=circuit.name,
        description=circuit.description,
        circuit_type=circuit.circuit_type,
        exercises_json=enriched_exercises,
        default_rounds=circuit.default_rounds,
        default_duration_seconds=circuit.default_duration_seconds,
        tags=circuit.tags or [],
        difficulty_tier=circuit.difficulty_tier,
        raw_workout=raw_workout,
    )


@router.put("/admin/{circuit_id}", response_model=CircuitTemplateResponse)
async def update_circuit_admin(
    circuit_id: int,
    payload: CircuitTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    admin: bool = Depends(require_admin),
):
    circuit = await db.get(CircuitTemplate, circuit_id)
    if not circuit:
        raise HTTPException(status_code=404, detail="Circuit not found")
    circuit.exercises_json = payload.exercises_json
    await db.commit()
    await db.refresh(circuit)
    return circuit


@router.get("/{circuit_id}/macro", response_model=CircuitMacroData)
async def get_circuit_macro(
    circuit_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get macro data for a circuit."""
    stmt = select(CircuitMacro).where(CircuitMacro.circuit_id == circuit_id)
    result = await db.execute(stmt)
    macro = result.scalar_one_or_none()
    if not macro:
        raise HTTPException(status_code=404, detail="Circuit macro data not found")
    return macro


@router.get("/{circuit_id}/with-macro", response_model=CircuitTemplateWithMacro)
async def get_circuit_with_macro(
    circuit_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get circuit template with macro data included."""
    circuit = await db.get(CircuitTemplate, circuit_id)
    if not circuit:
        raise HTTPException(status_code=404, detail="Circuit not found")
    
    # Enrich exercises_json with movement names
    if circuit.exercises_json:
        movement_ids = set()
        for ex in circuit.exercises_json:
            if isinstance(ex, dict) and ex.get("movement_id"):
                movement_ids.add(ex["movement_id"])
        
        if movement_ids:
            movements_result = await db.execute(select(Movement).where(Movement.id.in_(movement_ids)))
            movements = {m.id: m.name for m in movements_result.scalars().all()}
            
            new_exercises = []
            for ex in circuit.exercises_json:
                if isinstance(ex, dict):
                    ex_copy = ex.copy()
                    mid = ex_copy.get("movement_id")
                    if mid and mid in movements and not ex_copy.get("movement_name"):
                        ex_copy["movement_name"] = movements[mid]
                    new_exercises.append(ex_copy)
            circuit.exercises_json = new_exercises
    
    # Get macro data
    stmt = select(CircuitMacro).where(CircuitMacro.circuit_id == circuit_id)
    result = await db.execute(stmt)
    macro = result.scalar_one_or_none()
    
    # Convert macro to schema
    macro_data = CircuitMacroData.model_validate(macro) if macro else None
    
    return CircuitTemplateWithMacro(
        id=circuit.id,
        name=circuit.name,
        description=circuit.description,
        circuit_type=circuit.circuit_type,
        exercises_json=circuit.exercises_json,
        default_rounds=circuit.default_rounds,
        default_duration_seconds=circuit.default_duration_seconds,
        tags=circuit.tags or [],
        difficulty_tier=circuit.difficulty_tier,
        macro=macro_data,
    )


@router.get("/{circuit_id}/similar", response_model=list[CircuitSimilarityResult])
async def get_similar_circuits(
    circuit_id: int,
    limit: int = 10,
    min_similarity: float = 0.5,
    db: AsyncSession = Depends(get_db),
):
    """Get circuits similar to a given circuit.
    
    Similarity is based on patterns, regions, muscles, equipment, and intensity.
    """
    service = CircuitComparisonService(db)
    return await service.find_similar_circuits(
        circuit_id=circuit_id,
        limit=limit,
        min_similarity=min_similarity,
    )


@router.get("/{circuit_id}/complementary", response_model=list[CircuitRecommendation])
async def get_complementary_circuits(
    circuit_id: int,
    limit: int = 10,
    min_complementarity: float = 0.3,
    db: AsyncSession = Depends(get_db),
):
    """Get circuits that complement a given circuit.
    
    Complementary circuits target different muscles/regions/patterns,
    making them good for variety in training programs.
    """
    service = CircuitComparisonService(db)
    return await service.find_complementary_circuits(
        circuit_id=circuit_id,
        limit=limit,
        min_complementarity=min_complementarity,
    )


@router.post("/recommendations", response_model=list[CircuitRecommendation])
async def get_circuit_recommendations(
    circuit_ids: list[int] = [],
    target_regions: list[str] = [],
    target_patterns: list[str] = [],
    difficulty_tier: str = None,
    max_equipment: int = None,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """Get circuit recommendations for a training session.
    
    Supports filtering by regions, patterns, difficulty, and equipment.
    """
    service = CircuitComparisonService(db)
    return await service.recommend_circuits_for_session(
        circuit_ids=circuit_ids if circuit_ids else None,
        target_regions=target_regions if target_regions else None,
        target_patterns=target_patterns if target_patterns else None,
        difficulty_tier=difficulty_tier,
        max_equipment=max_equipment,
        limit=limit,
    )
