from chest.agents.graph import build_graph


def test_graph_has_cost_and_time_safety_limits():
    graph = build_graph()

    assert graph.max_node_executions == 5
    assert graph.execution_timeout == 300
    assert graph.node_timeout == 90
