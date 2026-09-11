import pytest

from chest.agents.graph import build_graph, reviewer_output


def test_graph_has_cost_and_time_safety_limits():
    graph = build_graph()

    assert graph.max_node_executions == 5
    assert graph.execution_timeout == 300
    assert graph.node_timeout == 90


def test_only_reviewer_output_is_sent_to_the_phone():
    class Result:
        results = {
            "forecaster": "internal forecast with $999",
            "reviewer": "phone-ready reviewed draft",
        }

    assert reviewer_output(Result()) == "phone-ready reviewed draft"


def test_missing_reviewer_output_fails_closed():
    class Result:
        results = {"forecaster": "partial result"}

    with pytest.raises(RuntimeError):
        reviewer_output(Result())
