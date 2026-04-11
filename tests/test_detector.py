from easy_automation.core.graph import Graph, State, Interrupt
from easy_automation.core.detector import detect_state, detect_interrupt


def test_detect_single_state():
    def always_true():
        return True

    functions = {"always_true": always_true}
    graph = Graph(
        states={"page_a": State(name="page_a", matchers=["always_true"])},
        transitions=[],
        interrupts=[],
    )
    assert detect_state(graph, functions) == "page_a"


def test_detect_unknown_when_no_match():
    def always_false():
        return False

    functions = {"always_false": always_false}
    graph = Graph(
        states={"page_a": State(name="page_a", matchers=["always_false"])},
        transitions=[],
        interrupts=[],
    )
    assert detect_state(graph, functions) == "unknown"


def test_most_matchers_wins():
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
        interrupts=[],
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
        interrupts=[],
    )
    assert detect_state(graph, functions) == "page_a"


def test_detect_interrupt():
    def has_popup():
        return True

    functions = {"has_popup": has_popup}
    graph = Graph(
        states={},
        transitions=[],
        interrupts=[
            Interrupt(matchers=["has_popup"], action="close_popup"),
        ],
    )
    result = detect_interrupt(graph, functions)
    assert result is not None
    assert result.action == "close_popup"


def test_detect_no_interrupt():
    def has_popup():
        return False

    functions = {"has_popup": has_popup}
    graph = Graph(
        states={},
        transitions=[],
        interrupts=[
            Interrupt(matchers=["has_popup"], action="close_popup"),
        ],
    )
    assert detect_interrupt(graph, functions) is None


def test_interrupt_most_matchers_wins():
    def has_coupon():
        return True

    def has_upgrade():
        return True

    functions = {"has_coupon": has_coupon, "has_upgrade": has_upgrade}
    graph = Graph(
        states={},
        transitions=[],
        interrupts=[
            Interrupt(matchers=["has_coupon"], action="close_coupon"),
            Interrupt(matchers=["has_coupon", "has_upgrade"], action="close_all"),
        ],
    )
    result = detect_interrupt(graph, functions)
    assert result.action == "close_all"
