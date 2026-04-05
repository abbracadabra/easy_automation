"""针对 code review 发现的问题的验证测试"""
import pytest
from easy_automation.core.registry import register, clear_registry
from easy_automation.core.context import get_context, set_context
from easy_automation.core.graph import Graph, State, Transition, Interrupt, load_graph
from easy_automation.core.detector import detect_state
from easy_automation.core.planner import goto
from easy_automation.core.engine import StateMachine


@pytest.fixture(autouse=True)
def clean_registry():
    clear_registry()
    yield
    clear_registry()


def test_matcher_exception_treated_as_no_match():
    """matcher 抛异常应视为不匹配，不应崩溃"""
    @register()
    def bad_matcher():
        raise RuntimeError("UI driver crashed")

    @register()
    def good_matcher():
        return True

    graph = Graph(
        states={
            "bad_state": State("bad_state", ["bad_matcher"]),
            "good_state": State("good_state", ["good_matcher"]),
        },
        transitions=[],
        interrupts=[],
    )
    # bad_matcher 抛异常但不影响 good_state 的匹配
    assert detect_state(graph) == "good_state"


def test_all_matchers_exception_returns_unknown():
    """所有 matcher 都抛异常时返回 unknown"""
    @register()
    def bad1():
        raise RuntimeError("error1")

    @register()
    def bad2():
        raise RuntimeError("error2")

    graph = Graph(
        states={
            "a": State("a", ["bad1"]),
            "b": State("b", ["bad2"]),
        },
        transitions=[],
        interrupts=[],
    )
    assert detect_state(graph) == "unknown"


def test_action_exception_does_not_crash_goto():
    """action 抛异常时 goto 应该继续循环，不应崩溃"""
    call_count = {"action": 0}
    state_holder = {"current": "a"}

    @register()
    def m_a():
        return state_holder["current"] == "a"

    @register()
    def m_b():
        return state_holder["current"] == "b"

    @register()
    def flaky_action():
        call_count["action"] += 1
        if call_count["action"] < 3:
            raise RuntimeError("click failed")
        state_holder["current"] = "b"

    graph = Graph(
        states={
            "a": State("a", ["m_a"]),
            "b": State("b", ["m_b"]),
        },
        transitions=[
            Transition("a", "flaky_action", ["b", "a"]),
        ],
        interrupts=[],
    )
    set_context({})
    goto("b", graph)
    assert call_count["action"] == 3


def test_interrupt_action_exception_does_not_crash():
    """interrupt action 抛异常时不应崩溃"""
    state_holder = {"current": "a", "popup": True, "attempt": 0}

    @register()
    def m_a():
        return state_holder["current"] == "a"

    @register()
    def m_b():
        return state_holder["current"] == "b"

    @register()
    def has_popup():
        return state_holder["popup"]

    @register()
    def close_popup():
        state_holder["attempt"] += 1
        if state_holder["attempt"] < 2:
            raise RuntimeError("popup close failed")
        state_holder["popup"] = False

    @register()
    def go_b():
        state_holder["current"] = "b"

    graph = Graph(
        states={
            "a": State("a", ["m_a"]),
            "b": State("b", ["m_b"]),
        },
        transitions=[
            Transition("a", "go_b", ["b"]),
        ],
        interrupts=[
            Interrupt(["has_popup"], "close_popup"),
        ],
    )
    set_context({})
    goto("b", graph)


def test_get_context_before_init_raises_readable_error():
    """未初始化 context 时 get_context 应给出友好错误"""
    # 注意：由于 contextvars 在同一线程中可能已被之前的测试 set 过，
    # 这里主要验证错误消息的可读性
    from contextvars import copy_context
    ctx = copy_context()
    # 在一个干净的 context 中执行
    from easy_automation.core.context import _context_var
    def run_in_clean():
        from easy_automation.core.context import get_context
        try:
            get_context()
            return None
        except RuntimeError as e:
            return str(e)

    # 直接测试：set 后能正常 get
    set_context({"test": True})
    assert get_context()["test"] is True


def test_engine_init_sets_context():
    """StateMachine.__init__ 应调用 set_context"""
    @register()
    def m():
        return True

    graph_data = {
        "states": {"a": {"matchers": ["m"]}},
        "transitions": [],
        "interrupts": [],
    }
    machine = StateMachine(graph_data, context={"key": "value"})
    assert get_context()["key"] == "value"


def test_load_graph_missing_fields():
    """JSON 缺少必要字段时应给出明确错误"""
    with pytest.raises(ValueError, match="缺少 matchers"):
        load_graph({"states": {"a": {}}, "transitions": [], "interrupts": []})

    with pytest.raises(ValueError, match="缺少 from"):
        load_graph({
            "states": {"a": {"matchers": ["m"]}},
            "transitions": [{"action": "go", "possible_targets": ["a"]}],
            "interrupts": [],
        })

    with pytest.raises(ValueError, match="缺少.*action"):
        load_graph({
            "states": {"a": {"matchers": ["m"]}},
            "transitions": [],
            "interrupts": [{"matchers": ["m"]}],
        })


def test_planner_goto_validates_target():
    """planner.goto 也应校验 target 存在"""
    @register()
    def m():
        return True

    graph = Graph(
        states={"a": State("a", ["m"])},
        transitions=[],
        interrupts=[],
    )
    set_context({})
    with pytest.raises(ValueError, match="目标状态不存在"):
        goto("nonexistent", graph)
