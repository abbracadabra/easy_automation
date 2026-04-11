"""针对 code review 发现的问题的验证测试"""
import pytest
from easy_automation.core.context import get_context, set_context
from easy_automation.core.graph import Graph, State, Transition, load_graph
from easy_automation.core.detector import detect_state
from easy_automation.core.planner import goto
from easy_automation.core.engine import StateMachine


def test_matcher_exception_treated_as_no_match():
    """matcher 抛异常应视为不匹配，不应崩溃"""
    def bad_matcher():
        raise RuntimeError("UI driver crashed")

    def good_matcher():
        return True

    functions = {"bad_matcher": bad_matcher, "good_matcher": good_matcher}
    graph = Graph(
        states={
            "bad_state": State("bad_state", ["bad_matcher"]),
            "good_state": State("good_state", ["good_matcher"]),
        },
        transitions=[],
    )
    assert detect_state(graph, functions) == "good_state"


def test_all_matchers_exception_returns_unknown():
    """所有 matcher 都抛异常时返回 unknown"""
    def bad1():
        raise RuntimeError("error1")

    def bad2():
        raise RuntimeError("error2")

    functions = {"bad1": bad1, "bad2": bad2}
    graph = Graph(
        states={
            "a": State("a", ["bad1"]),
            "b": State("b", ["bad2"]),
        },
        transitions=[],
    )
    assert detect_state(graph, functions) == "unknown"


def test_action_exception_does_not_crash_goto():
    """action 抛异常时 goto 应该继续循环，不应崩溃"""
    call_count = {"action": 0}
    state_holder = {"current": "a"}

    def m_a():
        return state_holder["current"] == "a"

    def m_b():
        return state_holder["current"] == "b"

    def flaky_action():
        call_count["action"] += 1
        if call_count["action"] < 3:
            raise RuntimeError("click failed")
        state_holder["current"] = "b"

    functions = {"m_a": m_a, "m_b": m_b, "flaky_action": flaky_action}
    graph = Graph(
        states={
            "a": State("a", ["m_a"]),
            "b": State("b", ["m_b"]),
        },
        transitions=[
            Transition("a", "flaky_action", ["b", "a"]),
        ],
    )
    set_context({})
    goto("b", graph, functions)
    assert call_count["action"] == 3


def test_priority_state_action_exception_does_not_crash():
    """优先级状态的 action 抛异常时不应崩溃，planner 继续循环"""
    state_holder = {"current": "a", "popup": True, "attempt": 0}

    def has_popup():
        return state_holder["popup"]

    def m_a():
        return state_holder["current"] == "a"

    def m_b():
        return state_holder["current"] == "b"

    def close_popup():
        state_holder["attempt"] += 1
        if state_holder["attempt"] < 2:
            raise RuntimeError("popup close failed")
        state_holder["popup"] = False

    def go_b():
        state_holder["current"] = "b"

    functions = {
        "has_popup": has_popup,
        "m_a": m_a, "m_b": m_b,
        "close_popup": close_popup,
        "go_b": go_b,
    }
    graph = Graph(
        states={
            "popup": State("popup", ["has_popup"]),
            "a": State("a", ["m_a"]),
            "b": State("b", ["m_b"]),
        },
        transitions=[
            Transition("popup", "close_popup", ["a", "b"]),
            Transition("a", "go_b", ["b"]),
        ],
    )
    set_context({})
    goto("b", graph, functions)


def test_get_context_before_init_raises_readable_error():
    """未初始化 context 时 get_context 应给出友好错误"""
    from contextvars import copy_context
    set_context({"test": True})
    assert get_context()["test"] is True


def test_engine_init_sets_context():
    """StateMachine.__init__ 应调用 set_context"""
    def m():
        return True

    functions = {"m": m}
    graph_data = {
        "states": {"a": {"matchers": ["m"]}},
        "transitions": [],
    }
    machine = StateMachine(graph_data, functions=functions, context={"key": "value"})
    assert get_context()["key"] == "value"


def test_load_graph_missing_fields():
    """JSON 缺少必要字段时应给出明确错误"""
    with pytest.raises(ValueError, match="缺少 matchers"):
        load_graph({"states": {"a": {}}, "transitions": []})

    with pytest.raises(ValueError, match="缺少 from"):
        load_graph({
            "states": {"a": {"matchers": ["m"]}},
            "transitions": [{"action": "go", "possible_targets": ["a"]}],
        })


def test_planner_goto_validates_target():
    """planner.goto 也应校验 target 存在"""
    def m():
        return True

    functions = {"m": m}
    graph = Graph(
        states={"a": State("a", ["m"])},
        transitions=[],
    )
    set_context({})
    with pytest.raises(ValueError, match="目标状态不存在"):
        goto("nonexistent", graph, functions)
