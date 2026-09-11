from chest.agents.graph import build_graph
from chest.store.accounts import Account


def test_graph_has_cost_and_time_safety_limits():
    graph = build_graph(Account(name="Test Org", id="acct_test"))

    assert graph.max_node_executions == 5
    assert graph.execution_timeout == 300
    assert graph.node_timeout == 90
