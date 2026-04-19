import pytest
from easy_automation.core.graph import load_graph, validate_graph_functions


def test_load_from_dict():
    graph = load_graph({
        "states": {
            "a": {"matchers": ["m_a"]},
            "b": {"matchers": ["m_b"]},
        },
        "transitions": [
            {"from": "a", "action": "go_b", "possible_targets": ["b"]},
        ],
    })
    assert "a" in graph.states
    assert "b" in graph.states
    assert len(graph.transitions) == 1
    assert graph.transitions[0].action == "go_b"


def test_load_invalid_from_state():
    with pytest.raises(ValueError, match="from 状态不存在"):
        load_graph({
            "states": {"a": {"matchers": ["m"]}},
            "transitions": [
                {"from": "nonexistent", "action": "go", "possible_targets": ["a"]},
            ],
        })


def test_load_invalid_possible_target():
    with pytest.raises(ValueError, match="possible_target 状态不存在"):
        load_graph({
            "states": {"a": {"matchers": ["m"]}},
            "transitions": [
                {"from": "a", "action": "go", "possible_targets": ["nonexistent"]},
            ],
        })


def test_load_empty_matchers():
    with pytest.raises(ValueError, match="matchers 不能为空"):
        load_graph({
            "states": {"a": {"matchers": []}},
            "transitions": [],
        })


def test_validate_functions_all_present():
    def m_a():
        return True

    def go_b():
        pass

    functions = {"m_a": m_a, "go_b": go_b}
    graph = load_graph({
        "states": {"a": {"matchers": ["m_a"]}},
        "transitions": [
            {"from": "a", "action": "go_b", "possible_targets": ["a"]},
        ],
    })
    validate_graph_functions(graph, functions)


def test_validate_functions_missing():
    graph = load_graph({
        "states": {"a": {"matchers": ["unregistered_matcher"]}},
        "transitions": [],
    })
    with pytest.raises(ValueError, match="校验失败"):
        validate_graph_functions(graph, {})
