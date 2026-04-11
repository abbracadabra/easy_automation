from __future__ import annotations

import logging
from collections import defaultdict, deque
from typing import Optional

from easy_automation.core.cache import reset_snapshot_cache
from easy_automation.core.detector import detect_interrupt, detect_state
from easy_automation.core.graph import Graph

logger = logging.getLogger(__name__)


class GotoFailed(Exception):
    pass


class FallbackExhausted(Exception):
    pass


def find_next_action(
    current: str,
    target: str,
    graph: Graph,
    excluded_states: Optional[set[str]] = None,
) -> Optional[str]:
    """BFS 寻路，返回从 current 到 target 最短路径的第一步 action。
    excluded_states 中的状态不作为中间节点考虑。
    返回 None 表示无路可走。
    """
    excluded = excluded_states or set()

    adj = defaultdict(list)
    for t in graph.transitions:
        for pt in t.possible_targets:
            adj[t.from_state].append((t.action, pt))

    queue = deque([(current, None)])
    visited = {current}

    while queue:
        state, first_action = queue.popleft()
        for action, next_state in adj[state]:
            if next_state in visited:
                continue
            if next_state in excluded and next_state != target:
                continue
            fa = first_action or action
            if next_state == target:
                return fa
            visited.add(next_state)
            queue.append((next_state, fa))

    return None


def goto(
    target: str,
    graph: Graph,
    functions: dict[str, callable],
    max_steps: int = 50,
    max_entry: int = 3,
    max_consecutive: int = 5,
    max_fallback: int = 3,
    fallback_fn: Optional[callable] = None,
):
    if target not in graph.states:
        raise ValueError(f"目标状态不存在: {target}")

    entry_count: dict[str, int] = defaultdict(int)
    consecutive_same = 0
    last_state = None
    fallback_count = 0

    def do_fallback(reason: str):
        nonlocal fallback_count, entry_count, consecutive_same, last_state
        fallback_count += 1
        logger.warning(f"触发 fallback (第 {fallback_count} 次): {reason}")
        if fallback_count > max_fallback:
            raise FallbackExhausted(
                f"fallback 次数超过上限 {max_fallback}，最后原因: {reason}"
            )
        if fallback_fn is None:
            raise GotoFailed(
                f"需要 fallback 但未设置 fallback 函数，原因: {reason}"
            )
        fallback_fn()
        entry_count = defaultdict(int)
        consecutive_same = 0
        last_state = None

    for step in range(max_steps):
        reset_snapshot_cache()

        current = detect_state(graph, functions)

        if current != last_state:
            entry_count[current] += 1
            consecutive_same = 1
            last_state = current
            logger.debug(f"步骤 {step}: 进入状态 {current} (第 {entry_count[current]} 次)")
        else:
            consecutive_same += 1
            logger.debug(f"步骤 {step}: 仍在状态 {current} (连续第 {consecutive_same} 次)")

        if consecutive_same >= max_consecutive:
            do_fallback(f"连续 {consecutive_same} 次停留在 {current}")
            continue

        interrupt = detect_interrupt(graph, functions)
        if interrupt:
            logger.debug(f"步骤 {step}: 处理中断，执行 {interrupt.action}")
            try:
                action_fn = functions[interrupt.action]
                action_fn()
            except Exception as e:
                logger.warning(f"interrupt action {interrupt.action} 执行异常: {e}")
            continue

        if current == target:
            logger.info(f"到达目标状态 {target}，共 {step + 1} 步")
            return

        excluded = {s for s, c in entry_count.items() if c > max_entry}
        action_name = find_next_action(current, target, graph, excluded)

        if action_name is None:
            do_fallback(f"从 {current} 到 {target} 无可用路径")
            continue

        logger.debug(f"步骤 {step}: 从 {current} 执行 {action_name}")
        try:
            action_fn = functions[action_name]
            action_fn()
        except Exception as e:
            logger.warning(f"action {action_name} 执行异常: {e}")

    raise GotoFailed(f"在 {max_steps} 步内未能到达 {target}")
