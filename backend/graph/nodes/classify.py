"""Intent x Topic classification node.

Calls ``settings.classifier_model`` (Haiku by default) with the prompts in
:mod:`backend.prompts.classifier` and enforces closed vocabularies:

- ``intent`` in {lookup, policy, lead, sensitive}
- ``topic``  in the 13-item handbook topic set

Invalid or un-parseable responses fall back to ``{intent: lookup, topic:
other}``. If the pre-call guardrail already flagged the turn as sensitive,
this node is a no-op so the sensitive classification is preserved.
"""
import json
import logging

import litellm
from langsmith import traceable

from backend.graph.history import history_messages
from backend.graph.state import GraphState
from backend.settings import settings
from backend.prompts.classifier import CLASSIFIER_SYSTEM_PROMPT, CLASSIFIER_USER_PROMPT

logger = logging.getLogger(__name__)

VALID_INTENTS = {"lookup", "policy", "lead", "sensitive"}
VALID_TOPICS = {
    "hours", "tuition", "sick_policy", "meals", "tours", "enrollment",
    "custody", "billing", "staff", "curriculum", "safety", "holidays", "other",
}


@traceable(run_type="chain", name="classify")
async def classify(state: GraphState) -> GraphState:
    if state.get("intent") == "sensitive":
        return {**state, "topic": state.get("topic") or "other"}

    response = await litellm.acompletion(
        model=settings.classifier_model,
        messages=[
            {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
            *history_messages(state.get("history")),
            {
                "role": "user",
                "content": CLASSIFIER_USER_PROMPT.format(question=state["question"]),
            },
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Classifier returned invalid JSON: %s", raw)
        data = {"intent": "lookup", "topic": "other", "confidence": 0.3}

    intent = data.get("intent", "lookup")
    topic = data.get("topic", "other")

    return {
        **state,
        "intent": intent if intent in VALID_INTENTS else "lookup",
        "topic": topic if topic in VALID_TOPICS else "other",
        "topic_guess": data.get("topic_guess"),
        "confidence": float(data.get("confidence", 0.5)),
    }
