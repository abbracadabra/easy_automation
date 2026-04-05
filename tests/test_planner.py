import pytest
from easy_automation.core.registry import register, clear_registry
from easy_automation.core.context import set_context
from easy_automation.core.graph import Graph, State, Transition, Interrupt
from easy_automation.core.planner import find_next_action, goto, GotoFailed, FallbackExhausted


@pytest.fixture(autouse=True)
def clean_registry():
    clear_registry()
    yield
    clear_registry()


# ============================================================
# find_next_action 测试
# ============================================================

class TestFindNextAction:
    def _simple_graph(self):
        """A -> B -> C 的简单图"""
        return Graph(
            states={
                "a": State("a", ["m_a"]),
                "b": State("b", ["m_b"]),
                "c": State("c", ["m_c"]),
            },
            transitions=[
                Transition("a", "go_b", ["b"]),
                Transition("b", "go_c", ["c"]),
            ],
            interrupts=[],
        )

    def test_direct_target(self):
        graph = self._simple_graph()
        assert find_next_action("a", "b", graph) == "go_b"

    def test_multi_hop(self):
        graph = self._simple_graph()
        # a -> b -> c，第一步应该是 go_b
        assert find_next_action("a", "c", graph) == "go_b"

    def test_no_path(self):
        graph = self._simple_graph()
        assert find_next_action("c", "a", graph) is None

    def test_excluded_states(self):
        """排除 b 后，a 到 c 无路"""
        graph = self._simple_graph()
        assert find_next_action("a", "c", graph, excluded_states={"b"}) is None

    def test_excluded_target_not_blocked(self):
        """即使 target 在 excluded 中，也应该能到达（target 不被排除）"""
        graph = self._simple_graph()
        assert find_next_action("a", "b", graph, excluded_states={"b"}) == "go_b"

    def test_branching_graph(self):
        """A 可以到 B 或 C，B 可以到 D，C 也可以到 D"""
        graph = Graph(
            states={
                "a": State("a", ["m"]),
                "b": State("b", ["m"]),
                "c": State("c", ["m"]),
                "d": State("d", ["m"]),
            },
            transitions=[
                Transition("a", "go_b", ["b"]),
                Transition("a", "go_c", ["c"]),
                Transition("b", "go_d_via_b", ["d"]),
                Transition("c", "go_d_via_c", ["d"]),
            ],
            interrupts=[],
        )
        # BFS 会找到 go_b 或 go_c（都是一跳到中间，两跳到 d）
        action = find_next_action("a", "d", graph)
        assert action in ("go_b", "go_c")

    def test_branching_with_exclusion(self):
        """排除 b 后，只能走 c"""
        graph = Graph(
            states={
                "a": State("a", ["m"]),
                "b": State("b", ["m"]),
                "c": State("c", ["m"]),
                "d": State("d", ["m"]),
            },
            transitions=[
                Transition("a", "go_b", ["b"]),
                Transition("a", "go_c", ["c"]),
                Transition("b", "go_d_via_b", ["d"]),
                Transition("c", "go_d_via_c", ["d"]),
            ],
            interrupts=[],
        )
        assert find_next_action("a", "d", graph, excluded_states={"b"}) == "go_c"

    def test_non_deterministic_transition(self):
        """一个 action 有多个 possible_targets"""
        graph = Graph(
            states={
                "a": State("a", ["m"]),
                "b": State("b", ["m"]),
                "c": State("c", ["m"]),
            },
            transitions=[
                Transition("a", "do_something", ["b", "c"]),
            ],
            interrupts=[],
        )
        assert find_next_action("a", "b", graph) == "do_something"
        assert find_next_action("a", "c", graph) == "do_something"


# ============================================================
# goto 测试
# ============================================================

class TestGoto:
    def test_already_at_target(self):
        """当前已经在目标状态"""
        @register()
        def m_a():
            return True

        graph = Graph(
            states={"a": State("a", ["m_a"])},
            transitions=[],
            interrupts=[],
        )
        set_context({})
        goto("a", graph)  # 不应该抛异常

    def test_simple_navigation(self):
        """A -> B 简单导航"""
        state_holder = {"current": "a"}

        @register()
        def m_a():
            return state_holder["current"] == "a"

        @register()
        def m_b():
            return state_holder["current"] == "b"

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
            interrupts=[],
        )
        set_context({})
        goto("b", graph)

    def test_multi_hop_navigation(self):
        """A -> B -> C 多跳导航"""
        state_holder = {"current": "a"}

        @register()
        def m_a():
            return state_holder["current"] == "a"

        @register()
        def m_b():
            return state_holder["current"] == "b"

        @register()
        def m_c():
            return state_holder["current"] == "c"

        @register()
        def go_b():
            state_holder["current"] = "b"

        @register()
        def go_c():
            state_holder["current"] = "c"

        graph = Graph(
            states={
                "a": State("a", ["m_a"]),
                "b": State("b", ["m_b"]),
                "c": State("c", ["m_c"]),
            },
            transitions=[
                Transition("a", "go_b", ["b"]),
                Transition("b", "go_c", ["c"]),
            ],
            interrupts=[],
        )
        set_context({})
        goto("c", graph)

    def test_interrupt_handling(self):
        """中断弹窗自动处理后继续导航"""
        state_holder = {"current": "a", "popup": True}

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
                Interrupt(matchers=["has_popup"], action="close_popup"),
            ],
        )
        set_context({})
        goto("b", graph)
        assert not state_holder["popup"]

    def test_non_deterministic_recovery(self):
        """动作结果不确定时，planner 重新规划"""
        call_count = {"go_b": 0}
        state_holder = {"current": "a"}

        @register()
        def m_a():
            return state_holder["current"] == "a"

        @register()
        def m_b():
            return state_holder["current"] == "b"

        @register()
        def go_b():
            call_count["go_b"] += 1
            # 前两次执行不成功（还在 a），第三次成功
            if call_count["go_b"] >= 3:
                state_holder["current"] = "b"

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
        goto("b", graph)
        assert call_count["go_b"] == 3

    def test_stuck_triggers_fallback(self):
        """卡在同一状态超过阈值触发 fallback"""
        state_holder = {"current": "a", "fallback_called": False}

        @register()
        def m_a():
            return state_holder["current"] == "a"

        @register()
        def m_b():
            return state_holder["current"] == "b"

        @register()
        def go_b():
            pass  # 永远不生效，卡在 a

        def my_fallback():
            state_holder["fallback_called"] = True
            state_holder["current"] = "b"  # fallback 后直接到 b

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
        goto("b", graph, max_consecutive=3, fallback_fn=my_fallback)
        assert state_holder["fallback_called"]

    def test_cycle_triggers_fallback(self):
        """死循环（A -> B -> A -> B ...）通过 entry_count 检测后 fallback"""
        state_holder = {"current": "a", "cycle_count": 0}

        @register()
        def m_a():
            return state_holder["current"] == "a"

        @register()
        def m_b():
            return state_holder["current"] == "b"

        @register()
        def m_c():
            return state_holder["current"] == "c"

        @register()
        def go_b():
            state_holder["current"] = "b"

        @register()
        def go_a():
            state_holder["current"] = "a"
            state_holder["cycle_count"] += 1

        def my_fallback():
            state_holder["current"] = "c"  # fallback 直接到目标

        graph = Graph(
            states={
                "a": State("a", ["m_a"]),
                "b": State("b", ["m_b"]),
                "c": State("c", ["m_c"]),
            },
            transitions=[
                Transition("a", "go_b", ["b"]),
                Transition("b", "go_a", ["a"]),  # 死循环：b 只能回 a
                Transition("b", "go_c_unreachable", ["c"]),  # 虽然有到 c 的路，但 go_a 会先被 BFS 选到
            ],
            interrupts=[],
        )

        # 重新构建：a->b 唯一，b->a 唯一（没有到 c 的路），只能循环
        graph2 = Graph(
            states={
                "a": State("a", ["m_a"]),
                "b": State("b", ["m_b"]),
                "c": State("c", ["m_c"]),
            },
            transitions=[
                Transition("a", "go_b", ["b"]),
                Transition("b", "go_a", ["a"]),
            ],
            interrupts=[],
        )
        set_context({})
        goto("c", graph2, max_entry=2, fallback_fn=my_fallback)

    def test_fallback_exhausted(self):
        """fallback 次数耗尽抛出 FallbackExhausted"""
        @register()
        def m_a():
            return True  # 永远在 a

        @register()
        def m_b():
            return False

        @register()
        def go_b():
            pass  # 不生效

        def my_fallback():
            pass  # fallback 也没用

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
        with pytest.raises(FallbackExhausted):
            goto("b", graph, max_consecutive=2, max_fallback=2, fallback_fn=my_fallback)

    def test_no_fallback_fn_raises(self):
        """需要 fallback 但未设置 fallback 函数"""
        @register()
        def m_a():
            return True

        @register()
        def m_b():
            return False

        @register()
        def go_b():
            pass

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
        with pytest.raises(GotoFailed, match="未设置 fallback"):
            goto("b", graph, max_consecutive=2)

    def test_context_used_by_action(self):
        """action 通过 contextvars 获取 context"""
        from easy_automation.core.context import get_context

        state_holder = {"current": "a"}

        @register()
        def m_a():
            return state_holder["current"] == "a"

        @register()
        def m_b():
            return state_holder["current"] == "b"

        @register()
        def go_b_with_context():
            ctx = get_context()
            ctx["visited"] = True
            state_holder["current"] = "b"

        graph = Graph(
            states={
                "a": State("a", ["m_a"]),
                "b": State("b", ["m_b"]),
            },
            transitions=[
                Transition("a", "go_b_with_context", ["b"]),
            ],
            interrupts=[],
        )
        ctx = {}
        set_context(ctx)
        goto("b", graph)
        assert ctx["visited"] is True
