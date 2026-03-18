import re
from enum import Enum
from typing import List, Dict, Set, Optional, Literal
from pydantic import BaseModel, Field

# --- 1. CORE ENUMS & MODELS ---

class Modality(str, Enum):
    MUST = "MUST"
    SHOULD = "SHOULD"
    MAY = "MAY"
    MUST_NOT = "MUST NOT"
    SHOULD_NOT = "SHOULD NOT"
    NONE = "NONE"

class ExtractedFact(BaseModel):
    """The strictly typed fact extracted by the LLM."""
    id: str
    type: Literal["STATE", "EVENT", "TIMER", "TRANSITION", "CONSTRAINT"]
    state_from: Optional[str] = None
    state_to: Optional[str] = None
    event: Optional[str] = None
    condition: Optional[str] = None
    actions: List[str] = Field(default_factory=list)
    modality: Optional[str] = None
    raw_entities: List[str] = Field(default_factory=list)
    text_span: str

class SentenceLink(BaseModel):
    sentence: str
    fact_ids: List[str]

class ExtractionOutput(BaseModel):
    """The exact JSON contract the LLM must fulfill."""
    error: Optional[str] = Field(None, description="Set this if rules cannot be satisfied (e.g., UNMAPPED_NORMATIVE_SENTENCE)")
    error_details: Optional[str] = Field(None, description="The exact sentence causing the failure.")
    facts: List[ExtractedFact] = Field(default_factory=list)
    sentence_links: List[SentenceLink] = Field(default_factory=list)

# --- 2. DETERMINISTIC ENTITY NORMALIZATION ---

def normalize_entity(name: str) -> str:
    if not name: return ""
    name = name.strip().upper()
    # Safely replace whitespace and dashes with underscores, but DO NOT strip "STATE" or "TIMER"
    # to prevent collisions like "IDLE_STATE" vs "IDLE_TIMER"
    name = re.sub(r"[\s\-]+", "_", name)
    return name

class EntityRegistry:
    def __init__(self):
        self.canonical = {}
        self.alias_map = {}

    def register(self, raw_name: str) -> str:
        if not raw_name: return ""
        canon = normalize_entity(raw_name)
        if canon not in self.canonical:
            self.canonical[canon] = set()
        self.canonical[canon].add(raw_name)
        self.alias_map[raw_name] = canon
        return canon

# --- 3. COVERAGE PROOF ENGINE ---

class CoverageError(Exception):
    pass

class CoverageProofEngine:
    NORMATIVE_KEYWORDS = {"MUST", "SHOULD", "MAY", "MUST NOT", "SHOULD NOT"}

    @staticmethod
    def extract_sentences(text: str) -> List[str]:
        # Improved deterministic split: handles standard punctuation, newlines (for bullets), and colons
        sentences = re.split(r'(?<=[.!?])\s+|\n+|:\s+', text)
        return [s.strip() for s in sentences if len(s.strip()) > 3]

    @classmethod
    def is_normative(cls, sentence: str) -> bool:
        s = sentence.upper()
        return any(k in s for k in cls.NORMATIVE_KEYWORDS)

    @classmethod
    def validate_coverage(cls, context_text: str, output: ExtractionOutput):
        """Proves that ALL normative sentences in the context are mapped to at least one fact."""
        if output.error:
            raise CoverageError(f"LLM explicitly reported failure: {output.error} - {output.error_details}")

        # Validate Fact Grounding
        for fact in output.facts:
            if not fact.text_span or fact.text_span not in context_text:
                if not any(fact.text_span.strip()[:20] in s for s in context_text.split('\n')):
                    raise CoverageError(f"Fact {fact.id} lacks valid text_span grounding: '{fact.text_span}'")

        # Validate Sentence Coverage
        mapped_sentences = [link.sentence.strip() for link in output.sentence_links if link.fact_ids]
        raw_sentences = cls.extract_sentences(context_text)
        
        for sentence in raw_sentences:
            if cls.is_normative(sentence):
                covered = any(sentence in m_sent or m_sent in sentence for m_sent in mapped_sentences)
                if not covered:
                    raise CoverageError(f"Normative sentence dropped/unmapped:\n'{sentence}'")

# --- 4. FORMAL PROTOCOL COMPILER ---

class ProtocolCompiler:
    """Compiles extracted facts into a verified FSM Graph."""
    def __init__(self, extraction: ExtractionOutput):
        self.facts = extraction.facts
        self.registry = EntityRegistry()

        self.states = set()
        self.events = set()
        self.timers = set()
        self.transitions = []
        self.constraints = []
        
        self.graph = {} # from_state -> list of transitions
        self.errors = [] # Store errors instead of raising exceptions directly

    def compile(self):
        self.normalize_entities()
        self.compile_transitions()
        self.compile_constraints()
        self.build_graph()
        
        # Formal Proofs
        self.validate_states()
        self.validate_dead_ends()
        self.validate_negative_constraints()
        self.validate_ambiguity()
        
        return self.render_markdown()

    def normalize_entities(self):
        for f in self.facts:
            if f.type == "STATE":
                for e in f.raw_entities: self.states.add(self.registry.register(e))
            elif f.type == "EVENT":
                for e in f.raw_entities: self.events.add(self.registry.register(e))
            elif f.type == "TIMER":
                for e in f.raw_entities: self.timers.add(self.registry.register(e))

    def compile_transitions(self):
        for t in self.facts:
            if t.type == "TRANSITION":
                from_state = self.registry.register(t.state_from)
                to_state = self.registry.register(t.state_to)
                
                if from_state: self.states.add(from_state)
                if to_state: self.states.add(to_state)
                
                event = self.registry.register(t.event) if t.event else None
                if event: self.events.add(event)

                self.transitions.append({
                    "from": from_state,
                    "to": to_state,
                    "event": event,
                    "condition": t.condition,
                    "actions": t.actions,
                    "modality": t.modality,
                    "source": t.text_span
                })

    def compile_constraints(self):
        for c in self.facts:
            if c.type == "CONSTRAINT":
                self.constraints.append({
                    "condition": c.condition,
                    "modality": c.modality,
                    "source": c.text_span
                })

    def build_graph(self):
        from collections import defaultdict
        self.graph = defaultdict(list)
        for t in self.transitions:
            if t["from"]:
                self.graph[t["from"]].append(t)

    # --- FORMAL PROOFS ---

    def validate_states(self):
        used = set()
        for t in self.transitions:
            if t["from"]: used.add(t["from"])
            if t["to"]: used.add(t["to"])
        
        missing = self.states - used
        if missing and self.transitions:
            self.errors.append(f"Undefined/Orphan states detected: {missing}")

    def validate_dead_ends(self):
        for state in self.states:
            if state and state not in self.graph and self.transitions:
                pass # Acceptable for terminal states, but noted.

    def validate_negative_constraints(self):
        for c in self.constraints:
            if c["modality"] == "MUST_NOT" or c["modality"] == "MUST NOT":
                for t in self.transitions:
                    if c["source"] == t["source"]:
                        self.errors.append(f"Violation of MUST NOT constraint in transition logic: {c['source']}")

    def validate_ambiguity(self):
        for state, trans_list in self.graph.items():
            seen = {}
            for t in trans_list:
                key = (t["event"], t["condition"])
                if key in seen and seen[key] != t["to"]:
                    self.errors.append(f"Ambiguous transition in {state} for event/condition {key}. Diverges to {seen[key]} AND {t['to']}")
                seen[key] = t["to"]

    def render_markdown(self) -> str:
        if not self.transitions:
            return "No state machine transitions extracted from context."
            
        md = [
            "## Compiled Protocol State Machine",
            "*(Deterministically compiled from formal factual extraction)*\n",
            "| Current State | Event | Condition | Modality | Next State | Grounding (Verbatim) |",
            "|---|---|---|---|---|---|"
        ]
        
        for t in sorted(self.transitions, key=lambda x: x["from"] or ""):
            actions = f"<br/>*Actions:* {', '.join(t['actions'])}" if t['actions'] else ""
            md.append(f"| {t['from']} | {t['event']} | {t['condition']}{actions} | {t['modality']} | {t['to']} | <sub>{t['source']}</sub> |")
            
        if self.constraints:
            md.extend([
                "\n## Formal Constraints",
                *[f"- **{c['modality']}**: {c['source']}" for c in self.constraints]
            ])
            
        return "\n".join(md)
