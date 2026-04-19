# Easy Automation 实现设计方案

## 设计原则

1. **平台无关** — 框架不感知任何 UI 驱动（Playwright/Appium/UIAutomator2），不定义 page/driver，用户自己管理
2. **JSON 是结构，代码是行为** — 状态机图是纯数据，所有行为通过函数名引用到用户代码
3. **有序匹配规则** — state 按定义顺序匹配：全部 matcher 通过即命中，先匹配先返回
4. **反应式循环** — planner 每步执行后重新观测，不假设动作结果
5. **隐式 context** — 通过 `contextvars` 提供全局可访问的 context，matcher/action 函数无参数
6. **框架只做导航调度** — 不管设备操作层，不管页面内元素交互，只负责状态间的路径规划和容错

## 核心思想

传统 UI 自动化用线性代码，每一步都要写大量 if-else 处理各种意外情况。本框架将这些分支逻辑收敛为：

- 一张状态机图（定义所有可能的状态和转移关系）
- 一个反应式 planner（自动寻路、观测、重新规划）

用例只表达业务意图（"从 A 到 B"），不处理中间的意外和分支。

## 防死循环与容错机制

这是框架最关键的容错设计，解决三类问题：

### 三类问题

| 问题 | 表现 | 检测方式 |
|---|---|---|
| 卡死 | 连续多次 iteration 停留在同一个 state（包括 unknown） | consecutive_same >= M |
| 死循环 | 在多个 state 之间反复绕圈，无法到达目标 | 所有可选 next state 的 entry_count 都 > N |
| 不可恢复 | fallback 多次后仍然无法到达目标 | fallback_count > X |

### 状态计数规则

**entry_count[state]：** 记录每个 state 的进入次数。只在状态切换时才 +1（从一个 state 变到另一个 state）。停留在同一个 state 不计入 entry，因为停留不代表路径上的循环。

**consecutive_same：** 记录连续停留在同一个 state 的 iteration 次数。切换到新 state 后重置为 1。

**fallback_count：** 整个 goto 期间的 fallback 累计次数，不重置。

**作用域：** entry_count、consecutive_same、fallback_count 都只在一次 goto 调用内生效，下一次 goto 全部清零。

### Planner 循环

```
goto(target):
    entry_count = {}
    consecutive_same = 0
    last_state = None
    fallback_count = 0

    loop (max_steps):
        1. 检测当前 state

        2. 更新计数：
           如果 current != last_state:
               entry_count[current] += 1
               consecutive_same = 1
               last_state = current
           否则:
               consecutive_same += 1

        3. 卡死检测：
           如果 consecutive_same >= M → 触发 fallback

        4. 当前 == 目标？→ 结束

        5. BFS 寻路（排除 entry_count > N 的 next state）

        6. 有路 → 执行 action
           无路（所有 next state 都超限）→ 触发 fallback

    fallback 逻辑：
        fallback_count += 1
        如果 fallback_count > X → throw error
        执行用户自定义 fallback 函数
        重置 entry_count
        重置 consecutive_same
        重置 last_state
        continue 回到循环顶部
```

### BFS 寻路（带排除）

```python
def find_next_action(current, target, graph, excluded_states):
    """BFS 寻路，excluded_states 中的状态不作为 next state 考虑"""
    adj = defaultdict(list)
    for t in graph.transitions:
        for pt in t.possible_targets:
            adj[t.from_state].append((t.action, pt))

    queue = deque([(current, None)])
    visited = {current}
    while queue:
        state, first_action = queue.popleft()
        for action, next_state in adj[state]:
            if next_state in visited or next_state in excluded_states:
                continue
            fa = first_action or action
            if next_state == target:
                return fa
            visited.add(next_state)
            queue.append((next_state, fa))

    return None  # 无路可走
```

## 模块划分

```
easy_automation/
├── core/
│   ├── context.py        # contextvars 管理
│   ├── registry.py       # 函数注册表（matcher/action 函数名 -> 函数对象）
│   ├── graph.py          # 状态机图的加载与数据结构
│   ├── detector.py       # 状态检测（按定义顺序，先匹配先返回）
│   ├── planner.py        # BFS 寻路 + 反应式循环 + 防死循环 + fallback
│   └── engine.py         # StateMachine 入口类，组装以上模块
├── tests/
│   ├── test_context.py
│   ├── test_registry.py
│   ├── test_detector.py
│   ├── test_planner.py   # 重点：死循环、卡死、fallback 场景的测试
│   └── test_engine.py    # 端到端测试（用 mock 函数模拟 UI）
└── examples/
    └── mock_demo.py      # 用 mock 函数演示完整流程，不依赖任何 UI 驱动
```

## 关键实现点

### 1. Context（contextvars）

```python
from contextvars import ContextVar

_context_var: ContextVar[dict] = ContextVar('easy_automation_context')

def get_context() -> dict:
    return _context_var.get()

def set_context(ctx: dict):
    _context_var.set(ctx)
```

### 2. 函数注册表（装饰器）

```python
_registry: dict[str, callable] = {}

def register(name: str = None):
    def decorator(fn):
        key = name or fn.__name__
        _registry[key] = fn
        return fn
    return decorator

def get_function(name: str) -> callable:
    if name not in _registry:
        raise KeyError(f"函数未注册: {name}")
    return _registry[name]
```

### 3. 状态机图（数据结构 + 加载时校验）

```python
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
class Graph:
    states: dict[str, State]
    transitions: list[Transition]
```

加载时校验：函数名是否已注册、from_state 是否存在于 states、possible_targets 是否存在于 states。启动时报错而非运行时报错。需要高优先级处理的状态（如弹窗关闭）作为普通 state 放在 states 最前面，通过 transitions 的 possible_targets 连接到所有可能的后续状态。

### 4. 状态检测（有序匹配）

按 states 定义顺序依次检测，第一个所有 matcher 都通过的 state 胜出。需要高优先级处理的状态（如弹窗）放在 states 最前面。

### 5. Engine（入口类）

```python
class StateMachine:
    def __init__(self, graph_path: str, context: dict = None):
        self.context = context or {}
        set_context(self.context)
        self.graph = load_graph(graph_path)

    def goto(self, target: str, max_steps: int = 50,
             max_entry: int = 3, max_consecutive: int = 5,
             max_fallback: int = 3):
        set_context(self.context)
        goto(target, self.graph, max_steps,
             max_entry, max_consecutive, max_fallback,
             self.fallback_fn)

    def set_fallback(self, fn):
        self.fallback_fn = fn
```

## 设计决策记录

| 决策 | 选择 | 原因 |
|---|---|---|
| matcher/action 函数签名 | 无参数，通过 contextvars 获取 context | 简洁，避免每个函数都传参 |
| 状态匹配优先级 | 按定义顺序，先匹配先返回 | 简单直观，用户通过排列顺序控制优先级 |
| 同一个 from→to 只允许一个 action | 是 | 保持简单，多 action 增加复杂度但收益不大 |
| detect_state 返回 unknown 时 | 纳入 consecutive_same 计数，由卡死检测处理 | 不单独处理，统一机制 |
| 页面内等待策略 | 框架不管，用户在 matcher/action 里自己处理 | 平台无关原则 |
| fallback 时是否重置 entry_count | 重置 | 给 planner 全新机会，fallback_count 兜底防无限重启 |
