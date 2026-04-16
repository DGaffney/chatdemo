"""Pre- and post-call guardrails for the graph.

Pre-call (``pre_call_guardrail``) runs before the LLM is invoked:

- ``INJECTION_PATTERNS`` short-circuit prompt-injection attempts with a
  canned refusal and ``blocked=True``.
- ``SENSITIVE_KEYWORDS`` re-classify the turn as ``intent='sensitive'`` so
  it routes straight to escalation even if the classifier would have called
  it something else.
- ``OFF_TOPIC_PATTERNS`` block generic "write me a poem"/trivia requests.

Post-call (``post_call_guardrail``) runs after answer generation:

- Citation guardrail: ``[source:...]`` must appear in lookup/policy answers
  when handbook context was retrieved.
- Numeric guardrail: any ``$amount`` or ``H:MM AM/PM`` in the answer must
  literally appear in the retrieved context (catches hallucinated prices
  or hours).
- Confidence threshold: below ``settings.confidence_threshold_*``, the turn
  is auto-escalated with ``reason='low_confidence'``.
"""
import re

from langsmith import traceable

from backend.graph.state import GraphState
from backend.settings import settings

SENSITIVE_KEYWORDS = [
    "custody", "divorce", "separated", "court order", "restraining",
    "abuse", "neglect", "cps", "child protective",
    "lawyer", "attorney", "legal", "lawsuit", "sue",
    "medical emergency", "ambulance", "911", "hospital",
    "weapon", "gun", "knife", "threat",
]

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+(all\s+)?above",
    r"you\s+are\s+now",
    r"system\s*prompt",
    r"pretend\s+you\s+are",
    r"act\s+as\s+(if\s+)?you",
    r"jailbreak",
    r"do\s+anything\s+now",
]

OFF_TOPIC_PATTERNS = [
    r"write\s+(me\s+)?(a\s+)?(poem|story|essay|song|code|script)",
    r"(what|who)\s+is\s+(the\s+)?(president|prime minister|capital\s+of)",
    r"solve\s+this\s+(math|equation)",
    r"translate\s+.+\s+(to|into)\s+",
]


@traceable(run_type="chain", name="pre_call_guardrail")
def pre_call_guardrail(state: GraphState) -> GraphState:
    question_lower = state.get("question", "").lower()
    flags = list(state.get("guardrail_flags", []))

    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, question_lower):
            return {
                **state,
                "blocked": True,
                "block_reason": "prompt_injection_detected",
                "guardrail_flags": flags + ["prompt_injection"],
                "answer": (
                    "I'm sorry, I can only help with questions about our daycare center. "
                    "Is there something about our center I can help you with?"
                ),
            }

    for keyword in SENSITIVE_KEYWORDS:
        if keyword in question_lower:
            return {
                **state,
                "intent": "sensitive",
                "guardrail_flags": flags + [f"sensitive_keyword:{keyword}"],
            }

    for pattern in OFF_TOPIC_PATTERNS:
        if re.search(pattern, question_lower):
            return {
                **state,
                "blocked": True,
                "block_reason": "off_topic",
                "guardrail_flags": flags + ["off_topic"],
                "answer": (
                    "I'm designed to help with questions about our daycare center — things like "
                    "hours, tuition, policies, and scheduling tours. "
                    "Is there something about our center I can help you with?"
                ),
            }

    return {**state, "guardrail_flags": flags}


@traceable(run_type="chain", name="post_call_guardrail")
def post_call_guardrail(state: GraphState) -> GraphState:
    flags = list(state.get("guardrail_flags", []))
    answer = state.get("answer", "")
    context = state.get("retrieved_context", "")
    intent = state.get("intent", "")
    confidence = state.get("confidence", 0.5)

    if intent in ("lookup", "policy") and settings.enable_citation_guardrail:
        if "[source:" not in answer.lower() and context:
            flags.append("missing_citation")
            confidence = min(confidence, 0.5)

    if settings.enable_numeric_guardrail and context:
        numbers_in_answer = re.findall(
            r"\$[\d,]+(?:\.\d{2})?|\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)", answer
        )
        for num in numbers_in_answer:
            if num not in context:
                flags.append(f"unverified_numeric:{num}")
                confidence = min(confidence, 0.5)

    escalated = state.get("escalated", False)
    escalation_reason = state.get("escalation_reason", "")

    threshold = (
        settings.confidence_threshold_lookup
        if intent == "lookup"
        else settings.confidence_threshold_policy
    )
    if confidence < threshold and not escalated:
        escalated = True
        escalation_reason = "low_confidence"
        flags.append("low_confidence_escalation")

    return {
        **state,
        "confidence": confidence,
        "guardrail_flags": flags,
        "escalated": escalated,
        "escalation_reason": escalation_reason,
    }
