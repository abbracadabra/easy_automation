import pytest
from easy_automation.core.context import set_context
from easy_automation.core.cache import get_frame_cache, reset_snapshot_cache
from easy_automation.core.graph import Graph, State, Transition
from easy_automation.core.planner import goto


def test_cache_basic():
    reset_snapshot_cache()
    cache = get_frame_cache()
    cache["key"] = "value"
    assert get_frame_cache()["key"] == "value"


def test_cache_reset():
    reset_snapshot_cache()
    get_frame_cache()["key"] = "value"
    reset_snapshot_cache()
    assert "key" not in get_frame_cache()


def test_cache_cleared_each_iteration():
    """每次 iteration cache 应被清空，matcher 产生的数据可被 action 读取"""
    iteration_caches = []
    state_holder = {"current": "a", "step": 0}

    def m_a():
        cache = get_frame_cache()
        cache["screenshot"] = f"screenshot_{state_holder['step']}"
        cache["btn_pos"] = (100, 200)
        return state_holder["current"] == "a"

    def m_b():
        return state_holder["current"] == "b"

    def go_b():
        cache = get_frame_cache()
        iteration_caches.append(dict(cache))
        state_holder["current"] = "b"
        state_holder["step"] += 1

    functions = {"m_a": m_a, "m_b": m_b, "go_b": go_b}
    graph = Graph(
        states={
            "a": State("a", ["m_a"]),
            "b": State("b", ["m_b"]),
        },
        transitions=[
            Transition("a", "go_b", ["b"]),
        ],
        interrupts=[],
    )
    set_context({})
    goto("b", graph, functions)

    assert len(iteration_caches) == 1
    assert iteration_caches[0]["btn_pos"] == (100, 200)
    assert "screenshot" in iteration_caches[0]


def test_cache_not_leak_across_iterations():
    """上一次 iteration 的 cache 不能泄漏到下一次"""
    seen_keys = []
    state_holder = {"current": "a", "step": 0}

    def m_a():
        cache = get_frame_cache()
        seen_keys.append(list(cache.keys()))
        cache[f"iter_{state_holder['step']}"] = True
        return state_holder["current"] == "a"

    def m_b():
        return state_holder["current"] == "b"

    def go_b():
        state_holder["step"] += 1
        if state_holder["step"] >= 3:
            state_holder["current"] = "b"

    functions = {"m_a": m_a, "m_b": m_b, "go_b": go_b}
    graph = Graph(
        states={
            "a": State("a", ["m_a"]),
            "b": State("b", ["m_b"]),
        },
        transitions=[
            Transition("a", "go_b", ["b", "a"]),
        ],
        interrupts=[],
    )
    set_context({})
    goto("b", graph, functions)

    for keys in seen_keys:
        assert keys == [], f"cache 不应有上次 iteration 的残留数据: {keys}"


def test_shared_matcher_cached_once():
    """多个 state 共享同一个 matcher，matcher 内的图像匹配结果通过 cache 复用"""
    match_count = {"cv_match": 0}
    state_holder = {"current": "a"}

    def match_common_element():
        cache = get_frame_cache()
        if "common_element_pos" not in cache:
            match_count["cv_match"] += 1
            cache["common_element_pos"] = (50, 50)
        return True

    def is_page_a():
        return state_holder["current"] == "a"

    def is_page_a_with_popup():
        return state_holder["current"] == "a" and False

    functions = {
        "match_common_element": match_common_element,
        "is_page_a": is_page_a,
        "is_page_a_with_popup": is_page_a_with_popup,
    }
    graph = Graph(
        states={
            "page_a": State("page_a", ["match_common_element", "is_page_a"]),
            "page_a_popup": State("page_a_popup", ["match_common_element", "is_page_a_with_popup"]),
        },
        transitions=[],
        interrupts=[],
    )
    set_context({})
    reset_snapshot_cache()

    from easy_automation.core.detector import detect_state
    result = detect_state(graph, functions)

    assert result == "page_a"
    assert match_count["cv_match"] == 1
