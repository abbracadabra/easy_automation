import pytest
from easy_automation.core.registry import register, clear_registry
from easy_automation.core.graph import load_graph, validate_graph_functions


@pytest.fixture(autouse=True)
def clean_registry():
    clear_registry()
    yield
    clear_registry()


def test_load_from_dict():
    graph = load_graph({
        "states": {
            "a": {"matchers": ["m_a"]},
            "b": {"matchers": ["m_b"]},
        },
        "transitions": [
            {"from": "a", "action": "go_b", "possible_targets": ["b"]},
        ],
        "interrupts": [],
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
            "interrupts": [],
        })


def test_load_invalid_possible_target():
    with pytest.raises(ValueError, match="possible_target 状态不存在"):
        load_graph({
            "states": {"a": {"matchers": ["m"]}},
            "transitions": [
                {"from": "a", "action": "go", "possible_targets": ["nonexistent"]},
            ],
            "interrupts": [],
        })


def test_load_empty_matchers():
    with pytest.raises(ValueError, match="matchers 不能为空"):
        load_graph({
            "states": {"a": {"matchers": []}},
            "transitions": [],
            "interrupts": [],
        })


def test_validate_functions_all_registered():
    @register()
    def m_a():
        return True

    @register()
    def go_b():
        pass

    graph = load_graph({
        "states": {"a": {"matchers": ["m_a"]}},
        "transitions": [
            {"from": "a", "action": "go_b", "possible_targets": ["a"]},
        ],
        "interrupts": [],
    })
    validate_graph_functions(graph)  # 不应抛异常


def test_validate_functions_missing():
    graph = load_graph({
        "states": {"a": {"matchers": ["unregistered_matcher"]}},
        "transitions": [],
        "interrupts": [],
    })
    with pytest.raises(ValueError, match="校验失败"):
        validate_graph_functions(graph)
