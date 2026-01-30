"""API routes for daily planning and adaptation with SSE streaming."""
import json
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.config.settings import get_settings
from app.models import (
    Program,
    Microcycle,
    Session,
    SessionExercise,  # Added
    ConversationThread,
    ConversationTurn,
    SorenessLog,
    RecoverySignal,
    MicrocycleStatus,
    RecoverySource,
)
from sqlalchemy.orm import selectinload  # Added
from app.models.circuit import CircuitTemplate
from app.schemas.daily import (
    DailyPlanResponse,
    AdaptationRequest,
    AdaptationResponse,
    AcceptPlanRequest,
    AcceptPlanResponse,
    AdaptedSessionPlan,
)
from app.schemas.program import SessionResponse
from app.schemas.circuit import (
    CircuitAssignmentCreate,
    CircuitAssignmentUpdate,
    CircuitAssignmentResponse,
    CircuitRecommendationRequest,
    CircuitRecommendationResponse,
    CircuitPreviewResponse,
)
from app.llm import get_llm_provider, LLMConfig, Message, PromptBuilder
from app.services.adaptation import adaptation_service
from app.services.deload import deload_service
from app.services.time_estimation import time_estimation_service
from app.services.circuit_assignment import circuit_assignment_service
from app.api.routes.dependencies import get_current_user_id

router = APIRouter()
settings = get_settings()


@router.get("/{target_date}/plan", response_model=DailyPlanResponse)
async def get_daily_plan(
    target_date: date,
    program_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    Get the planned session for a specific date.
    
    Returns the session from the active microcycle, or indicates if it's a rest day.
    """
    # Verify program belongs to user
    program = await db.get(Program, program_id)
    if not program or program.user_id != user_id:
        raise HTTPException(status_code=404, detail="Program not found")
    
    # Get active microcycle
    microcycle_result = await db.execute(
        select(Microcycle).where(
            and_(
                Microcycle.program_id == program_id,
                Microcycle.status == MicrocycleStatus.ACTIVE
            )
        )
    )
    microcycle = microcycle_result.scalar_one_or_none()
    
    if not microcycle:
        raise HTTPException(status_code=404, detail="No active microcycle found")
    
    # Get session for the date
    session_result = await db.execute(
        select(Session)
        .where(
            and_(
                Session.microcycle_id == microcycle.id,
                Session.date == target_date
            )
        )
        .options(
            selectinload(Session.exercises).selectinload(SessionExercise.movement),
            selectinload(Session.main_circuit).selectinload(CircuitTemplate.melted_exercises),
            selectinload(Session.finisher_circuit).selectinload(CircuitTemplate.melted_exercises)
        )
    )
    session = session_result.scalar_one_or_none()
    
    if not session:
        # Check if it's a deload day
        should_deload, deload_reason = await deload_service.should_trigger_deload(
            db, user_id, program_id
        )
        
        # It's a rest day or no session planned
        coach_message = "Rest day - take it easy and recover!"
        if should_deload and microcycle and not microcycle.is_deload:
            coach_message = f"Rest day. Note: Deload may be recommended ({deload_reason})"
        
        return DailyPlanResponse(
            plan_date=target_date,
            session=None,
            is_rest_day=True,
            coach_message=coach_message,
        )
    
    # Estimate duration if not already calculated
    if not session.estimated_duration_minutes:
        try:
            duration_estimate = await time_estimation_service.estimate_session_duration(
                db, user_id, session.id
            )
            session.estimated_duration_minutes = duration_estimate["total_minutes"]
            session.warmup_duration_minutes = duration_estimate["breakdown"]["warmup_minutes"]
            session.main_duration_minutes = duration_estimate["breakdown"]["main_minutes"]
            session.cooldown_duration_minutes = duration_estimate["breakdown"]["cooldown_minutes"]
        except Exception:
            # If estimation fails, continue without it
            pass
    
    # Convert to response
    session_response = SessionResponse.model_validate(session)
    
    return DailyPlanResponse(
        plan_date=target_date,
        session=session_response,
        is_rest_day=False,
    )


@router.post("/{target_date}/adapt", response_model=AdaptationResponse)
async def adapt_session(
    target_date: date,
    request: AdaptationRequest,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    Adapt a session based on constraints and recovery status.
    
    Creates or continues a conversation thread for iterative refinement.
    """
    # Verify program belongs to user
    program = await db.get(Program, program_id=request.program_id)
    if not program or program.user_id != user_id:
        raise HTTPException(status_code=404, detail="Program not found")
    
    # Get or create conversation thread
    if request.thread_id:
        thread = await db.get(ConversationThread, request.thread_id)
        if not thread or thread.user_id != user_id:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        thread = ConversationThread(
            user_id=user_id,
            context_type="daily_adaptation",
            context_date=datetime.combine(target_date, datetime.min.time()),
            is_active=True,
        )
        db.add(thread)
        await db.flush()
    
    # Get current session if exists
    microcycle_result = await db.execute(
        select(Microcycle).where(
            and_(
                Microcycle.program_id == request.program_id,
                Microcycle.status == MicrocycleStatus.ACTIVE
            )
        )
    )
    microcycle = microcycle_result.scalar_one_or_none()
    
    original_session = None
    if microcycle:
        session_result = await db.execute(
            select(Session).where(
                and_(
                    Session.microcycle_id == microcycle.id,
                    Session.date == target_date
                )
            )
        )
        original_session = session_result.scalar_one_or_none()
    
    # Get recent soreness logs
    soreness_result = await db.execute(
        select(SorenessLog).where(
            and_(
                SorenessLog.user_id == user_id,
                SorenessLog.date >= target_date
            )
        ).order_by(SorenessLog.date.desc()).limit(5)
    )
    recent_soreness = list(soreness_result.scalars().all())
    
    # Get recent recovery signals
    recovery_result = await db.execute(
        select(RecoverySignal).where(
            and_(
                RecoverySignal.user_id == user_id,
                RecoverySignal.date == target_date
            )
        ).order_by(RecoverySignal.created_at.desc()).limit(1)
    )
    recovery_signal = recovery_result.scalar_one_or_none()
    
    # Assess recovery using AdaptationService
    recovery_assessment = await adaptation_service._assess_recovery(db, user_id, request)
    recovery_score = recovery_assessment.get("recovery_score", 50)
    
    # Get user movement rules for constraint context
    movement_rules = await adaptation_service._get_movement_rules(db, user_id)
    user_preferences = await adaptation_service._get_user_preferences(db, user_id)
    
    # Build prompt for LLM
    prompt_builder = PromptBuilder()
    
    # Add program context
    prompt_builder.add_program_context({
        "goal_1": program.goal_1.value,
        "goal_2": program.goal_2.value,
        "goal_3": program.goal_3.value,
        "goal_weight_1": program.goal_weight_1,
        "goal_weight_2": program.goal_weight_2,
        "goal_weight_3": program.goal_weight_3,
        "split_template": program.split_template.value,
        "progression_style": program.progression_style.value,
        "duration_weeks": program.duration_weeks,
        "deload_every_n_microcycles": program.deload_every_n_microcycles,
    })
    
    # Add constraints from both request and user rules
    constraints = {
        "recovery_score": recovery_score,
        "user_movement_rules": movement_rules,
        "user_preferences": user_preferences.get("enjoyable_activities", []),
    }
    if request.excluded_movements:
        constraints["excluded_movements"] = request.excluded_movements
    if request.excluded_patterns:
        constraints["excluded_patterns"] = request.excluded_patterns
    if request.focus_for_today:
        constraints["focus"] = request.focus_for_today
    if request.preference:
        constraints["preference"] = request.preference
    if request.time_available_minutes:
        constraints["time_available_minutes"] = request.time_available_minutes
    
    if constraints:
        prompt_builder.add_constraints(constraints)
    
    # Add recovery context with assessment
    soreness_data = [{"body_part": s.body_part, "soreness_1_5": s.soreness_1_5} for s in recent_soreness]
    recovery_data = None
    if recovery_signal:
        recovery_data = {
            "sleep_score": recovery_signal.sleep_score,
            "readiness": recovery_signal.readiness,
            "hrv": recovery_signal.hrv,
        }
    prompt_builder.add_recovery_context(soreness_data, recovery_data)
    
    # Build system prompt
    system_prompt = prompt_builder.build()
    
    # Build user message
    user_message = request.user_message or f"Adapt my session for {target_date}."
    if request.adherence_vs_optimality != "balanced":
        user_message += f" I prefer {request.adherence_vs_optimality} today."
    
    # Get conversation history
    turns_result = await db.execute(
        select(ConversationTurn)
        .where(ConversationTurn.thread_id == thread.id)
        .order_by(ConversationTurn.turn_number)
    )
    existing_turns = list(turns_result.scalars().all())
    
    # Build messages for LLM
    messages = [Message(role="system", content=system_prompt)]
    for turn in existing_turns:
        messages.append(Message(role=turn.role, content=turn.content))
    messages.append(Message(role="user", content=user_message))
    
    # Store user turn
    user_turn = ConversationTurn(
        thread_id=thread.id,
        turn_number=len(existing_turns) + 1,
        role="user",
        content=user_message,
    )
    db.add(user_turn)
    
    # Call LLM
    from app.llm.ollama_provider import ADAPTATION_RESPONSE_SCHEMA
    
    provider = get_llm_provider()
    config = LLMConfig(
        model=settings.ollama_model,
        temperature=0.7,
        json_schema=ADAPTATION_RESPONSE_SCHEMA,
    )
    
    try:
        response = await provider.chat(messages, config)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"LLM service unavailable: {str(e)}")
    
    # Parse response
    if response.structured_data:
        llm_response = response.structured_data
    else:
        # Try to parse from content
        try:
            llm_response = json.loads(response.content)
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="Failed to parse LLM response")
    
    # Store assistant turn
    assistant_turn = ConversationTurn(
        thread_id=thread.id,
        turn_number=len(existing_turns) + 2,
        role="assistant",
        content=response.content,
        structured_response_json=llm_response,
    )
    db.add(assistant_turn)
    
    await db.commit()
    
    # Build response with adaptation context
    adapted_plan = llm_response.get("adapted_plan", {})
    
    # Include adaptation assessment context
    changes_made = llm_response.get("changes_made", [])
    if recovery_score < 40:
        changes_made.insert(0, f"Reduced volume due to low recovery score ({recovery_score}/100)")
    elif recovery_score > 75:
        changes_made.insert(0, f"Enhanced workout due to strong recovery score ({recovery_score}/100)")
    
    return AdaptationResponse(
        plan_date=target_date,
        original_session_type=original_session.session_type if original_session else None,
        adapted_plan=AdaptedSessionPlan(
            warmup=adapted_plan.get("warmup"),
            main=adapted_plan.get("main"),
            accessory=adapted_plan.get("accessory"),
            finisher=adapted_plan.get("finisher"),
            cooldown=adapted_plan.get("cooldown"),
            estimated_duration_minutes=adapted_plan.get("estimated_duration_minutes", 60),
            reasoning=adapted_plan.get("reasoning", ""),
            trade_offs=adapted_plan.get("trade_offs"),
        ),
        changes_made=changes_made,
        reasoning=f"Recovery score: {recovery_score}/100. {llm_response.get('reasoning', '')}",
        trade_offs=llm_response.get("trade_offs"),
        alternative_suggestion=llm_response.get("alternative_suggestion"),
        follow_up_question=llm_response.get("follow_up_question"),
        thread_id=thread.id,
    )


@router.post("/{target_date}/adapt/stream")
async def adapt_session_stream(
    target_date: date,
    request: AdaptationRequest,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    Adapt a session with SSE streaming response.
    
    Returns a Server-Sent Events stream with incremental LLM output.
    """
    # Similar setup as adapt_session, but with streaming
    
    async def generate_sse():
        """Generate SSE events from LLM stream."""
        # Verify program
        program = await db.get(Program, request.program_id)
        if not program or program.user_id != user_id:
            yield f"data: {json.dumps({'error': 'Program not found'})}\n\n"
            return
        
        # Create conversation thread
        thread = ConversationThread(
            user_id=user_id,
            context_type="daily_adaptation",
            context_date=datetime.combine(target_date, datetime.min.time()),
            is_active=True,
        )
        db.add(thread)
        await db.flush()
        
        # Get adaptation assessment for streaming context
        recovery_assessment = await adaptation_service._assess_recovery(db, user_id, request)
        recovery_score = recovery_assessment.get("recovery_score", 50)
        movement_rules = await adaptation_service._get_movement_rules(db, user_id)
        user_preferences = await adaptation_service._get_user_preferences(db, user_id)
        
        # Build prompt with adaptation context
        prompt_builder = PromptBuilder()
        prompt_builder.add_program_context({
            "goal_1": program.goal_1.value,
            "goal_2": program.goal_2.value,
            "goal_3": program.goal_3.value,
            "goal_weight_1": program.goal_weight_1,
            "goal_weight_2": program.goal_weight_2,
            "goal_weight_3": program.goal_weight_3,
            "split_template": program.split_template.value,
            "progression_style": program.progression_style.value,
            "duration_weeks": program.duration_weeks,
            "deload_every_n_microcycles": program.deload_every_n_microcycles,
        })
        
        # Add constraints with recovery assessment
        constraints = {
            "recovery_score": recovery_score,
            "user_movement_rules": movement_rules,
            "user_preferences": user_preferences.get("enjoyable_activities", []),
        }
        if request.excluded_movements:
            constraints["excluded_movements"] = request.excluded_movements
        if request.excluded_patterns:
            constraints["excluded_patterns"] = request.excluded_patterns
        if request.focus_for_today:
            constraints["focus"] = request.focus_for_today
        if request.time_available_minutes:
            constraints["time_available_minutes"] = request.time_available_minutes
        
        if constraints:
            prompt_builder.add_constraints(constraints)
        
        system_prompt = prompt_builder.build()
        
        # Send recovery score as early metadata
        yield f"data: {json.dumps({"recovery_score": recovery_score})}\n\n"
        user_message = request.user_message or f"Adapt my session for {target_date}."
        
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_message),
        ]
        
        # Stream from LLM
        provider = get_llm_provider()
        config = LLMConfig(
            model=settings.ollama_model,
            temperature=0.7,
            stream=True,
        )
        
        # Send thread_id first
        yield f"data: {json.dumps({'thread_id': thread.id})}\n\n"
        
        full_content = ""
        try:
            async for chunk in provider.chat_stream(messages, config):
                full_content += chunk.content
                yield f"data: {json.dumps({'content': chunk.content, 'done': chunk.done})}\n\n"
                
                if chunk.done:
                    # Store the conversation
                    user_turn = ConversationTurn(
                        thread_id=thread.id,
                        turn_number=1,
                        role="user",
                        content=user_message,
                    )
                    assistant_turn = ConversationTurn(
                        thread_id=thread.id,
                        turn_number=2,
                        role="assistant",
                        content=full_content,
                    )
                    db.add(user_turn)
                    db.add(assistant_turn)
                    await db.commit()
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post("/accept-plan", response_model=AcceptPlanResponse)
async def accept_plan(
    request: AcceptPlanRequest,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    Accept a plan from an adaptation conversation.
    
    This finalizes the conversation and optionally updates the session.
    """
    thread = await db.get(ConversationThread, request.thread_id)
    
    if not thread:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    if thread.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if thread.final_plan_accepted:
        raise HTTPException(status_code=400, detail="Plan already accepted")
    
    # Get the last assistant turn with structured response
    turns_result = await db.execute(
        select(ConversationTurn)
        .where(
            and_(
                ConversationTurn.thread_id == thread.id,
                ConversationTurn.role == "assistant"
            )
        )
        .order_by(ConversationTurn.turn_number.desc())
        .limit(1)
    )
    last_turn = turns_result.scalar_one_or_none()
    
    if not last_turn or not last_turn.structured_response_json:
        raise HTTPException(status_code=400, detail="No plan to accept")
    
    # Mark thread as accepted
    thread.final_plan_accepted = True
    thread.is_active = False
    thread.accepted_plan_json = last_turn.structured_response_json.get("adapted_plan")
    
    await db.commit()
    
    return AcceptPlanResponse(
        success=True,
        message="Plan accepted successfully",
    )


@router.post("/{session_id}/circuits", response_model=CircuitAssignmentResponse, status_code=201)
async def assign_circuit_to_session(
    session_id: int,
    assignment: CircuitAssignmentCreate,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    Atomically assign a circuit to a session.
    
    Atomic constraint: All circuit exercises are added or none.
    """
    result = await circuit_assignment_service.assign_circuit_to_session(
        db, session_id, assignment.circuit_id, assignment.circuit_role,
        assignment.rounds, assignment.replace_existing
    )
    return result


@router.patch("/{session_id}/circuits/{circuit_role}")
async def update_circuit_assignment(
    session_id: int,
    circuit_role: str,
    update: CircuitAssignmentUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Update circuit assignment parameters."""
    if update.action == "UPDATE_ROUNDS" and update.rounds is None:
        raise HTTPException(status_code=400, detail="rounds required for UPDATE_ROUNDS action")
    
    if update.action == "REMOVE":
        session = await db.get(Session, session_id)
        if not session or session.user_id != user_id:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if circuit_role == "MAIN_CIRCUIT":
            session.main_circuit_id = None
        elif circuit_role == "FINISHER_CIRCUIT":
            session.finisher_circuit_id = None
        else:
            raise HTTPException(status_code=400, detail="Invalid circuit_role")
        
        await db.execute(
            SessionExercise.__table__.delete().where(
                and_(
                    SessionExercise.session_id == session_id,
                    SessionExercise.circuit_id != None
                )
            )
        )
        await db.commit()
        
        return {
            "session_id": session_id,
            "circuit_role": circuit_role,
            "action_completed": update.action,
        }
    
    return {
        "session_id": session_id,
        "circuit_role": circuit_role,
        "action_completed": update.action,
    }


@router.get("/{session_id}/available-circuits")
async def get_available_circuits(
    session_id: int,
    circuit_type: str | None = None,
    difficulty_tier: int | None = None,
    primary_region: str | None = None,
    exclude_used: bool = True,
    max_duration_minutes: int | None = None,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get circuit recommendations for a session."""
    result = await circuit_assignment_service.get_available_circuits_for_session(
        db, session_id, circuit_type, difficulty_tier, primary_region,
        exclude_used, max_duration_minutes, limit
    )
    return result


@router.post("/circuits-preview", response_model=CircuitPreviewResponse)
async def preview_circuit_assignment(
    session_id: int,
    circuit_id: int,
    circuit_role: str = "MAIN_CIRCUIT",
    rounds: int | None = None,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Preview circuit assignment before committing."""
    result = await circuit_assignment_service.preview_circuit_assignment(
        db, session_id, circuit_id, circuit_role, rounds
    )
    return result
