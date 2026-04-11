from __future__ import annotations

import logging
from typing import Any, Optional

from easy_automation.core.graph import Graph, Interrupt

logger = logging.getLogger(__name__)


def _match_best(
    candidates: list[tuple[Any, list[str]]],
    functions: dict[str, callable],
) -> Any:
    """通用匹配逻辑：对每个候选项执行其 matchers，全部通过才算命中，命中项中 matcher 数量最多的胜出。

    Args:
        candidates: [(item, matcher_names), ...]
        functions: 函数名 -> callable 映射

    Returns:
        命中的 item，或 None
    """
    matched = []
    for item, matcher_names in candidates:
        try:
            matchers = [functions[m] for m in matcher_names]
            if all(m() for m in matchers):
                matched.append((item, len(matcher_names)))
        except Exception as e:
            logger.warning(f"matcher 执行异常，视为不匹配: {e}")

    if not matched:
        return None

    matched.sort(key=lambda x: -x[1])

    if len(matched) > 1 and matched[0][1] == matched[1][1]:
        logger.warning(
            f"多个候选项 matcher 数量相同，结果可能不确定: {matched[0][0]}, {matched[1][0]}"
        )

    return matched[0][0]


def detect_state(graph: Graph, functions: dict[str, callable]) -> str:
    candidates = [
        (name, state.matchers)
        for name, state in graph.states.items()
    ]
    result = _match_best(candidates, functions)
    return result if result is not None else "unknown"


def detect_interrupt(graph: Graph, functions: dict[str, callable]) -> Optional[Interrupt]:
    candidates = [
        (interrupt, interrupt.matchers)
        for interrupt in graph.interrupts
    ]
    return _match_best(candidates, functions)
