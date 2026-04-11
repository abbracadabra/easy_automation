from easy_automation.core.graph import Graph, State
from easy_automation.core.detector import detect_state


def test_detect_single_state():
    def always_true():
        return True

    functions = {"always_true": always_true}
    graph = Graph(
        states={"page_a": State(name="page_a", matchers=["always_true"])},
        transitions=[],
    )
    assert detect_state(graph, functions) == "page_a"


def test_detect_unknown_when_no_match():
    def always_false():
        return False

    functions = {"always_false": always_false}
    graph = Graph(
        states={"page_a": State(name="page_a", matchers=["always_false"])},
        transitions=[],
    )
    assert detect_state(graph, functions) == "unknown"


def test_first_match_wins():
    """定义在前面的 state 优先匹配，即使后面的 state matcher 更多"""
    def check_url():
        return True

    def check_element():
        return True

    def check_popup():
        return True

    functions = {
        "check_url": check_url,
        "check_element": check_element,
        "check_popup": check_popup,
    }
    graph = Graph(
        states={
            "page_a": State(name="page_a", matchers=["check_url", "check_element"]),
            "page_a_with_popup": State(
                name="page_a_with_popup",
                matchers=["check_url", "check_element", "check_popup"],
            ),
        },
        transitions=[],
    )
    assert detect_state(graph, functions) == "page_a"


def test_first_match_wins_reversed_order():
    """更多 matcher 的 state 放前面时，它先匹配"""
    def check_url():
        return True

    def check_element():
        return True

    def check_popup():
        return True

    functions = {
        "check_url": check_url,
        "check_element": check_element,
        "check_popup": check_popup,
    }
    graph = Graph(
        states={
            "page_a_with_popup": State(
                name="page_a_with_popup",
                matchers=["check_url", "check_element", "check_popup"],
            ),
            "page_a": State(name="page_a", matchers=["check_url", "check_element"]),
        },
        transitions=[],
    )
    assert detect_state(graph, functions) == "page_a_with_popup"


def test_partial_match_not_candidate():
    """只有部分 matcher 通过的状态不是候选"""
    def is_true():
        return True

    def is_false():
        return False

    functions = {"is_true": is_true, "is_false": is_false}
    graph = Graph(
        states={
            "page_a": State(name="page_a", matchers=["is_true"]),
            "page_b": State(name="page_b", matchers=["is_true", "is_false"]),
        },
        transitions=[],
    )
    assert detect_state(graph, functions) == "page_a"


def test_skips_failed_state_matches_next():
    """前面的 state 不匹配时，继续尝试后面的"""
    def is_false():
        return False

    def is_true():
        return True

    functions = {"is_false": is_false, "is_true": is_true}
    graph = Graph(
        states={
            "first": State(name="first", matchers=["is_false"]),
            "second": State(name="second", matchers=["is_true"]),
        },
        transitions=[],
    )
    assert detect_state(graph, functions) == "second"
