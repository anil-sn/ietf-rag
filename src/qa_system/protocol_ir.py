import re
from typing import List
from pydantic import BaseModel, Field, field_validator

class Transition(BaseModel):
    current_state: str = Field(..., description="The exact state before the transition")
    event: str = Field(..., description="The event, message, or timer expiry that triggers this transition")
    condition: str = Field(default="None", description="Explicit conditions required. Use 'None' if unconditional.")
    action: str = Field(..., description="Actions taken during the transition")
    next_state: str = Field(..., description="The exact state after the transition")
    citation: str = Field(..., description="Strict citation format: [Source: <filename>, Chunk: <id>]")

    @field_validator('citation')
    def validate_citation(cls, v):
        if not re.search(r'\[Source: .+, Chunk: \d+\]', v):
            raise ValueError(f"Citation '{v}' does not match required format '[Source: <filename>, Chunk: <id>]'")
        return v

class ProtocolIR(BaseModel):
    overview: str = Field(..., description="A concise, highly technical overview of the protocol behavior based ONLY on context.")
    states: List[str] = Field(..., description="Exhaustive list of all valid states.")
    events: List[str] = Field(..., description="Exhaustive list of all valid events/messages.")
    timers: List[str] = Field(..., description="List of all timers mentioned. Must be treated as events.")
    transitions: List[Transition] = Field(..., description="The complete state machine transitions.")
    invariants: List[str] = Field(..., description="Absolute protocol rules and invariants (e.g., 'Lease MUST be unique').")
    ambiguities: List[str] = Field(..., description="List of undefined behaviors, missing transitions, or conflicts.")
    implementation_keys: List[str] = Field(..., description="Required state variables and keys (e.g., MAC, Client-ID, Transaction-ID).")

class ProtocolVerifier:
    """Hard Verification Engine - Uses code, not an LLM, to validate the extracted logic."""
    
    @staticmethod
    def verify(ir: ProtocolIR) -> List[str]:
        errors = []
        
        # 1. Check State Completeness
        defined_states = set(s.upper() for s in ir.states)
        used_states = set()
        
        for t in ir.transitions:
            used_states.add(t.current_state.upper())
            used_states.add(t.next_state.upper())
            
        # Ensure every defined state has at least one transition in or out
        orphan_states = defined_states - used_states
        if orphan_states:
            errors.append(f"CRITICAL: States defined but have no transitions: {orphan_states}")
            
        # Ensure transitions don't hallucinate states not in the main list
        hallucinated_states = used_states - defined_states
        if hallucinated_states:
            errors.append(f"CRITICAL: Transitions use states not defined in the 'states' list: {hallucinated_states}")

        # 2. Timer check
        if ir.timers:
            timer_events = [t for t in ir.transitions if any(timer.lower() in t.event.lower() for timer in ir.timers)]
            if not timer_events:
                errors.append("CRITICAL: Timers were identified, but no transitions use them as events.")

        return errors

    @staticmethod
    def format_deterministic_markdown(ir: ProtocolIR) -> str:
        """Generates the final response using pure Python, guaranteeing 100% adherence to output contracts."""
        
        md = [
            "## 1. Protocol Overview",
            f"{ir.overview}\n",
            "## 2. Implementation Mapping",
            "**Required Keys & Variables:**",
            *[f"- {k}" for k in ir.implementation_keys],
            "\n**Timers:**",
            *[f"- {t}" for t in ir.timers] if ir.timers else ["- No timers explicitly defined."],
            "\n## 3. Deterministic State Machine",
            "| Current State | Event | Condition | Action | Next State | Citation |",
            "|---|---|---|---|---|---|"
        ]
        
        for t in ir.transitions:
            md.append(f"| {t.current_state} | {t.event} | {t.condition} | {t.action} | {t.next_state} | {t.citation} |")
            
        md.extend([
            "\n## 4. Key Normative Rules & Invariants",
            *[f"- {i}" for i in ir.invariants],
            "\n## 5. Edge Cases, Failures & Ambiguities",
            *[f"- {a}" for a in ir.ambiguities] if ir.ambiguities else ["- No ambiguities detected in provided context."]
        ])
        
        return "\n".join(md)
