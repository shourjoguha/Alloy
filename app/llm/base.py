"""LLM provider interface and base classes."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator


@dataclass
class Message:
    """Chat message."""
    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class LLMConfig:
    """Configuration for LLM request."""
    model: str
    temperature: float = 0.7
    max_tokens: int | None = None
    json_schema: dict | None = None  # For structured output
    stream: bool = False


@dataclass
class LLMResponse:
    """Response from LLM."""
    content: str
    structured_data: dict | None = None  # Parsed JSON if schema provided
    usage: dict | None = None  # Token usage stats
    model: str | None = None
    finish_reason: str | None = None


@dataclass
class StreamChunk:
    """Chunk from streaming response."""
    content: str
    done: bool = False
    usage: dict | None = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        config: LLMConfig,
    ) -> LLMResponse:
        """
        Send messages to LLM and get response.
        
        Args:
            messages: List of chat messages (system, user, assistant)
            config: LLM configuration including model, temperature, schema
            
        Returns:
            LLMResponse with content and optionally structured data
        """
        pass
    
    @abstractmethod
    async def chat_stream(
        self,
        messages: list[Message],
        config: LLMConfig,
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream response from LLM.
        
        Args:
            messages: List of chat messages
            config: LLM configuration
            
        Yields:
            StreamChunk objects with partial content
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is available."""
        pass


class PromptBuilder:
    """Builder for composing system prompts."""
    
    def __init__(self):
        self.sections: list[str] = []
    
    def add_persona(self, tone: str, aggression: int, tone_config: dict) -> "PromptBuilder":
        """Add persona configuration to prompt."""
        tone_info = tone_config.get("tones", {}).get(tone, {})
        language_style = tone_info.get("language_style", "balanced")
        explanation_depth = tone_info.get("explanation_depth", "moderate")
        
        aggression_info = tone_config.get("aggression_levels", {}).get(str(aggression), {})
        aggression_name = aggression_info.get("name", "Balanced")
        risk_tolerance = aggression_info.get("risk_tolerance", "moderate")
        
        self.sections.append(f"""## Coach Persona
- Communication style: {language_style}
- Explanation depth: {explanation_depth}
- Programming approach: {aggression_name}
- Risk tolerance: {risk_tolerance}""")
        return self
    
    def add_program_context(self, program: dict) -> "PromptBuilder":
        """Add current program context."""
        goals_str = ", ".join([
            f"{program['goal_1']} ({program['goal_weight_1']}/10)",
            f"{program['goal_2']} ({program['goal_weight_2']}/10)",
            f"{program['goal_3']} ({program['goal_weight_3']}/10)"
        ])
        
        self.sections.append(f"""## Current Program
- Goals: {goals_str}
- Split: {program['split_template']}
- Progression style: {program['progression_style']}
- Duration: {program['duration_weeks']} weeks
- Deload every: {program['deload_every_n_microcycles']} microcycles""")
        return self
    
    def add_user_rules(self, rules: list[dict]) -> "PromptBuilder":
        """Add user movement rules."""
        if not rules:
            return self
            
        rules_text = []
        for rule in rules:
            rules_text.append(f"- {rule['movement_name']}: {rule['rule_type']} ({rule['cadence']})")
        
        self.sections.append(f"""## User Movement Rules
{chr(10).join(rules_text)}""")
        return self
    
    def add_recovery_context(self, soreness: list[dict], recovery: dict | None) -> "PromptBuilder":
        """Add recovery and soreness context."""
        context_parts = []
        
        if soreness:
            soreness_text = ", ".join([f"{s['body_part']}: {s['soreness_1_5']}/5" for s in soreness])
            context_parts.append(f"Soreness: {soreness_text}")
        
        if recovery:
            if recovery.get("sleep_score"):
                context_parts.append(f"Sleep score: {recovery['sleep_score']}/100")
            if recovery.get("readiness"):
                context_parts.append(f"Readiness: {recovery['readiness']}/100")
            if recovery.get("hrv"):
                context_parts.append(f"HRV: {recovery['hrv']}")
        
        if context_parts:
            self.sections.append(f"""## Today's Recovery Status
{chr(10).join(['- ' + p for p in context_parts])}""")
        return self
    
    def add_constraints(self, constraints: dict) -> "PromptBuilder":
        """Add daily constraints and preferences."""
        parts = []
        
        if constraints.get("excluded_movements"):
            parts.append(f"Excluded movements: {', '.join(constraints['excluded_movements'])}")
        if constraints.get("excluded_patterns"):
            parts.append(f"Excluded patterns: {', '.join(constraints['excluded_patterns'])}")
        if constraints.get("focus"):
            parts.append(f"Focus for today: {constraints['focus']}")
        if constraints.get("preference"):
            parts.append(f"Preference: {constraints['preference']}")
        if constraints.get("time_available_minutes"):
            parts.append(f"Time available: {constraints['time_available_minutes']} minutes")
        
        if parts:
            self.sections.append(f"""## Today's Constraints
{chr(10).join(['- ' + p for p in parts])}""")
        return self
    
    def add_output_schema(self, schema_description: str) -> "PromptBuilder":
        """Add output format instructions."""
        self.sections.append(f"""## Required Output Format
{schema_description}

You MUST respond with valid JSON matching the schema. Do not include any text outside the JSON.""")
        return self
    
    def build(self) -> str:
        """Build the complete system prompt."""
        base_prompt = """You are an expert strength and fitness coach. Your role is to create and adapt training programs based on the user's goals, constraints, and recovery status.

Key principles:
1. Safety first - never recommend exercises the user cannot perform safely
2. Progressive overload - ensure consistent progress within recovery limits
3. Goal alignment - all recommendations should serve the user's stated goals
4. Adaptability - adjust based on daily context and feedback
"""
        return base_prompt + "\n\n" + "\n\n".join(self.sections)
