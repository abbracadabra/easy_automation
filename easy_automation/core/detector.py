from __future__ import annotations

import logging

from easy_automation.core.graph import Graph

logger = logging.getLogger(__name__)


def detect_state(graph: Graph, functions: dict[str, callable]) -> str:
    """按定义顺序匹配状态，第一个所有 matcher 都通过的状态胜出。"""
    for name, state in graph.states.items():
        try:
            matchers = [functions[m] for m in state.matchers]
            if all(m() for m in matchers):
                return name
        except Exception as e:
            logger.warning(f"matcher 执行异常，视为不匹配: {e}")

    return "unknown"
