import pytest
from easy_automation.core.registry import register, clear_registry
from easy_automation.core.graph import Graph, State, Interrupt
from easy_automation.core.detector import detect_state, detect_interrupt


@pytest.fixture(autouse=True)
def clean_registry():
    clear_registry()
    yield
    clear_registry()


def test_detect_single_state():
    @register()
    def always_true():
        return True

    graph = Graph(
        states={"page_a": State(name="page_a", matchers=["always_true"])},
        transitions=[],
        interrupts=[],
    )
    assert detect_state(graph) == "page_a"


def test_detect_unknown_when_no_match():
    @register()
    def always_false():
        return False

    graph = Graph(
        states={"page_a": State(name="page_a", matchers=["always_false"])},
        transitions=[],
        interrupts=[],
    )
    assert detect_state(graph) == "unknown"


def test_most_matchers_wins():
    @register()
    def check_url():
        return True

    @register()
    def check_element():
        return True

    @register()
    def check_popup():
        return True

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
    assert detect_state(graph) == "page_a_with_popup"


def test_partial_match_not_candidate():
    """只有部分 matcher 通过的状态不是候选"""
    @register()
    def is_true():
        return True

    @register()
    def is_false():
        return False

    graph = Graph(
        states={
            "page_a": State(name="page_a", matchers=["is_true"]),
            "page_b": State(name="page_b", matchers=["is_true", "is_false"]),
        },
        transitions=[],
        interrupts=[],
    )
    # page_b 有一个 matcher 失败，只有 page_a 是候选
    assert detect_state(graph) == "page_a"


def test_detect_interrupt():
    @register()
    def has_popup():
        return True

    graph = Graph(
        states={},
        transitions=[],
        interrupts=[
            Interrupt(matchers=["has_popup"], action="close_popup"),
        ],
    )
    result = detect_interrupt(graph)
    assert result is not None
    assert result.action == "close_popup"


def test_detect_no_interrupt():
    @register()
    def has_popup():
        return False

    graph = Graph(
        states={},
        transitions=[],
        interrupts=[
            Interrupt(matchers=["has_popup"], action="close_popup"),
        ],
    )
    assert detect_interrupt(graph) is None


def test_interrupt_most_matchers_wins():
    @register()
    def has_coupon():
        return True

    @register()
    def has_upgrade():
        return True

    graph = Graph(
        states={},
        transitions=[],
        interrupts=[
            Interrupt(matchers=["has_coupon"], action="close_coupon"),
            Interrupt(matchers=["has_coupon", "has_upgrade"], action="close_all"),
        ],
    )
    result = detect_interrupt(graph)
    assert result.action == "close_all"
