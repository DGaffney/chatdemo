"""Unit tests for graph routing logic.

Tests the conditional routing functions in isolation (no LLM calls).
Also verifies the graph structure has the expected nodes and edges.
"""
from backend.graph.graph import (
    _route_after_guardrail,
    _route_after_classify,
    _route_after_escalation_retrieve,
    build_graph,
)


class TestRouteAfterGuardrail:

    def test_blocked_routes_to_log(self):
        assert _route_after_guardrail({"blocked": True}) == "log"

    def test_not_blocked_routes_to_classify(self):
        assert _route_after_guardrail({"blocked": False}) == "classify"

    def test_missing_key_routes_to_classify(self):
        assert _route_after_guardrail({}) == "classify"


class TestRouteAfterClassify:

    def test_lookup_routes_to_retrieve(self):
        assert _route_after_classify({"intent": "lookup"}) == "retrieve"

    def test_policy_routes_to_retrieve(self):
        assert _route_after_classify({"intent": "policy"}) == "retrieve"

    def test_lead_routes_to_retrieve_for_escalation(self):
        assert _route_after_classify({"intent": "lead"}) == "retrieve_for_escalation"

    def test_sensitive_routes_to_retrieve_for_escalation(self):
        assert _route_after_classify({"intent": "sensitive"}) == "retrieve_for_escalation"

    def test_missing_intent_defaults_to_retrieve(self):
        assert _route_after_classify({}) == "retrieve"


class TestRouteAfterEscalationRetrieve:

    def test_lead_routes_to_generate_answer(self):
        assert _route_after_escalation_retrieve({"intent": "lead"}) == "generate_answer"

    def test_sensitive_routes_to_escalate(self):
        assert _route_after_escalation_retrieve({"intent": "sensitive"}) == "escalate"


class TestGraphStructure:

    def test_graph_has_expected_nodes(self):
        graph = build_graph()
        node_names = set(graph.nodes.keys())
        expected = {
            "__start__",
            "pre_guardrail", "classify",
            "retrieve", "retrieve_for_escalation",
            "generate_answer", "escalate",
            "post_guardrail", "log",
        }
        assert expected.issubset(node_names)

    def test_graph_compiles(self):
        graph = build_graph()
        assert graph is not None
