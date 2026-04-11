import json
from dataclasses import dataclass, field


@dataclass
class State:
    name: str
    matchers: list[str]


@dataclass
class Transition:
    from_state: str
    action: str
    possible_targets: list[str]


@dataclass
class Interrupt:
    matchers: list[str]
    action: str


@dataclass
class Graph:
    states: dict[str, State] = field(default_factory=dict)
    transitions: list[Transition] = field(default_factory=list)
    interrupts: list[Interrupt] = field(default_factory=list)


def load_graph(source) -> Graph:
    """从 JSON 文件路径或 dict 加载状态机图。加载时校验完整性。"""
    if isinstance(source, str):
        with open(source) as f:
            data = json.load(f)
    elif isinstance(source, dict):
        data = source
    else:
        raise TypeError(f"source 必须是文件路径(str)或 dict，得到: {type(source)}")

    states = {}
    for name, state_data in data.get("states", {}).items():
        if "matchers" not in state_data:
            raise ValueError(f"状态 {name} 缺少 matchers 字段")
        matchers = state_data["matchers"]
        if not matchers:
            raise ValueError(f"状态 {name} 的 matchers 不能为空")
        states[name] = State(name=name, matchers=matchers)

    transitions = []
    for i, t_data in enumerate(data.get("transitions", [])):
        for key in ("from", "action", "possible_targets"):
            if key not in t_data:
                raise ValueError(f"第 {i} 条 transition 缺少 {key} 字段")
        from_state = t_data["from"]
        action = t_data["action"]
        possible_targets = t_data["possible_targets"]
        if from_state not in states:
            raise ValueError(f"transition 的 from 状态不存在: {from_state}")
        for pt in possible_targets:
            if pt not in states:
                raise ValueError(f"transition 的 possible_target 状态不存在: {pt}")
        transitions.append(Transition(
            from_state=from_state,
            action=action,
            possible_targets=possible_targets,
        ))

    interrupts = []
    for i, i_data in enumerate(data.get("interrupts", [])):
        if "matchers" not in i_data or "action" not in i_data:
            raise ValueError(f"第 {i} 条 interrupt 缺少 matchers 或 action 字段")
        matchers = i_data["matchers"]
        if not matchers:
            raise ValueError("interrupt 的 matchers 不能为空")
        interrupts.append(Interrupt(
            matchers=matchers,
            action=i_data["action"],
        ))

    graph = Graph(states=states, transitions=transitions, interrupts=interrupts)
    return graph


def validate_graph_functions(graph: Graph, functions: dict[str, callable]):
    """校验图中引用的所有函数名是否存在于 functions dict 中。"""
    errors = []
    for name, state in graph.states.items():
        for m in state.matchers:
            if m not in functions:
                errors.append(f"状态 {name} 的 matcher 函数缺失: {m}")

    for t in graph.transitions:
        if t.action not in functions:
            errors.append(f"transition {t.from_state} 的 action 函数缺失: {t.action}")

    for interrupt in graph.interrupts:
        for m in interrupt.matchers:
            if m not in functions:
                errors.append(f"interrupt 的 matcher 函数缺失: {m}")
        if interrupt.action not in functions:
            errors.append(f"interrupt 的 action 函数缺失: {interrupt.action}")

    if errors:
        raise ValueError("状态机图校验失败:\n" + "\n".join(f"  - {e}" for e in errors))
