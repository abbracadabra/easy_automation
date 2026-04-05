from easy_automation.core.context import set_context
from easy_automation.core.graph import load_graph, validate_graph_functions
from easy_automation.core.planner import goto


class StateMachine:
    def __init__(self, source, context: dict = None):
        """创建状态机实例。

        Args:
            source: JSON 文件路径(str) 或状态机图 dict
            context: 初始上下文变量
        """
        self.context = context or {}
        set_context(self.context)
        self.graph = load_graph(source)
        self._fallback_fn = None

    def validate(self):
        """校验图中引用的所有函数是否已注册。建议在所有 @register 完成后调用。"""
        validate_graph_functions(self.graph)

    def set_fallback(self, fn):
        """设置 fallback 函数，在卡死或死循环时调用。"""
        self._fallback_fn = fn

    def goto(
        self,
        target: str,
        max_steps: int = 50,
        max_entry: int = 3,
        max_consecutive: int = 5,
        max_fallback: int = 3,
    ):
        """导航到目标状态。

        Args:
            target: 目标状态名
            max_steps: 最大循环步数
            max_entry: 单个状态最大进入次数，超过后寻路时排除该状态
            max_consecutive: 连续停留同一状态的最大次数，超过后触发 fallback
            max_fallback: 最大 fallback 次数，超过后抛出异常
        """
        set_context(self.context)
        goto(
            target=target,
            graph=self.graph,
            max_steps=max_steps,
            max_entry=max_entry,
            max_consecutive=max_consecutive,
            max_fallback=max_fallback,
            fallback_fn=self._fallback_fn,
        )
