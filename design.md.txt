# Easy Automation - 非确定性状态机设计

## 概述

传统 UI 自动化使用线性脚本：步骤1 -> 步骤2 -> 步骤3。任何意外情况（弹窗、网络错误、加载延迟）都会导致整个流程崩溃。

本框架使用**非确定性状态机** + **反应式 Planner** 来解决这个问题。核心思路：

- 将所有可能的 UI 状态和转移定义为一张图
- Planner 读取这张图，观测当前状态，动态规划到目标状态的路径
- 每个动作执行后，结果是不确定的 — Planner 重新观测、重新规划

测试用例只表达**业务意图**（"到A页面，再到B页面"），不涉及实现细节（"点这个按钮，等3秒，填那个输入框"）。

---

## 状态机结构

状态机由四部分组成：

```
StateMachine = States + Transitions + Interrupts + Context
```

### 图定义（JSON）

```json
{
  "states": { ... },
  "transitions": [ ... ],
  "interrupts": [ ... ]
}
```

---

## 状态（States）

一个状态代表一个可识别的 UI 场景（如"登录页"、"商品列表"、"订单确认页"）。

每个状态有一个名称和一组 **matcher 函数名**。所有 matcher 都返回 `True`，该状态才算被匹配。

```json
{
  "states": {
    "login_page": {
      "matchers": ["is_login_url", "has_login_form"]
    },
    "home_page": {
      "matchers": ["is_home_url", "has_dashboard"]
    },
    "product_detail": {
      "matchers": ["is_product_url", "has_product_info"]
    },
    "product_detail_with_cart": {
      "matchers": ["is_product_url", "has_product_info", "has_cart_popup"]
    }
  }
}
```

matcher 函数用 Python 实现：

```python
# matchers.py
def is_login_url(page, context):
    return "/login" in page.url

def has_login_form(page, context):
    return page.locator("#login-form").is_visible()

def is_home_url(page, context):
    return "/home" in page.url

def has_dashboard(page, context):
    return page.locator(".dashboard").is_visible()

def is_product_url(page, context):
    return "/product" in page.url

def has_product_info(page, context):
    return page.locator(".product-detail").is_visible()

def has_cart_popup(page, context):
    return page.locator(".cart-popup").is_visible()
```

### 状态匹配规则

检测当前状态时：

1. 对所有状态的 matcher 逐一求值
2. 只有**全部** matcher 返回 `True` 的状态才是候选
3. 候选中 **matcher 数量最多的胜出**

```python
def detect_state(page, context, states):
    matched = []
    for name, state in states.items():
        matchers = [get_function(m) for m in state["matchers"]]
        if all(m(page, context) for m in matchers):
            matched.append((name, len(matchers)))

    matched.sort(key=lambda x: -x[1])
    return matched[0][0] if matched else "unknown"
```

**为什么"matcher 数量多的优先"：** 如果 `product_detail`（2个 matcher）和 `product_detail_with_cart`（3个 matcher）同时匹配，更具体的状态（有购物车弹窗的）自动胜出。不需要手动管理优先级或权重。

---

## 转移（Transitions）

一条转移定义：从某个状态，执行某个动作，可能到达的下一个状态。

关键点在于转移是**非确定性的** — 执行一个动作后，可能到达多个不同的状态。

```json
{
  "transitions": [
    {
      "from": "login_page",
      "action": "do_login",
      "possible_targets": ["home_page", "captcha_page", "login_page"]
    },
    {
      "from": "home_page",
      "action": "click_product",
      "possible_targets": ["product_detail"]
    },
    {
      "from": "product_detail",
      "action": "click_buy",
      "possible_targets": ["order_confirm", "login_page"]
    }
  ]
}
```

动作函数用 Python 实现：

```python
# actions.py
def do_login(page, context):
    page.fill("#username", context["username"])
    page.fill("#password", context["password"])
    page.click("#login-btn")

def click_product(page, context):
    name = context["target_product"]
    page.locator(f".product-item:has-text('{name}')").click()

def click_buy(page, context):
    page.click(".buy-btn")
```

---

## 中断（Interrupts）

### 为什么需要中断

在真实 App 中，弹窗几乎可以在任何页面出现：领券弹窗、升级提示、权限请求、广告浮层等。

如果没有中断机制，你需要为每个页面定义带弹窗的状态：`pageA_with_coupon`、`pageB_with_coupon`、`pageC_with_coupon`... 以及对应的转移。假设有 10 个页面和 3 种弹窗，就可能多出 30 个状态和 30 条转移。

中断机制通过定义**全局处理器**来解决这个问题，在正常状态匹配之前优先检查。

### 定义

```json
{
  "interrupts": [
    {
      "matchers": ["has_coupon_popup"],
      "action": "close_coupon"
    },
    {
      "matchers": ["has_upgrade_dialog"],
      "action": "dismiss_upgrade"
    },
    {
      "matchers": ["has_permission_popup"],
      "action": "allow_permission"
    },
    {
      "matchers": ["has_coupon_popup", "has_upgrade_dialog"],
      "action": "close_all_popups"
    }
  ]
}
```

### 中断匹配规则

与状态匹配规则一致：所有 matcher 必须通过，**matcher 数量最多的优先**。

这能处理多个弹窗同时出现的情况。例如，领券弹窗和升级提示同时弹出，`["has_coupon_popup", "has_upgrade_dialog"]`（2个 matcher）优先于单独的处理器（各1个 matcher）。

```python
def detect_interrupt(page, context, interrupts):
    matched = []
    for interrupt in interrupts:
        matchers = [get_function(m) for m in interrupt["matchers"]]
        if all(m(page, context) for m in matchers):
            matched.append((interrupt, len(matchers)))

    matched.sort(key=lambda x: -x[1])
    return matched[0][0] if matched else None
```

---

## 上下文变量（Context）

Context 是一个字典，贯穿整个执行过程。动作函数可以读取和写入。

**变量有两个来源：**

1. **外部传入** — 调用方在执行前提供
2. **运行时产生** — 动作在执行过程中提取并写回

```python
# 外部传入
machine.run(
    target_state="product_detail",
    context={
        "target_product": "iPhone 16",
        "username": "test_user",
        "password": "123456",
    }
)
```

```python
# 运行时产生 — 动作写入 context
def extract_order_id(page, context):
    context["order_id"] = page.locator(".order-id").text_content()
```

所有 matcher 和 action 函数的签名统一为 `(page, context)`，可以自由读写共享的 context。

---

## Planner

Planner 是运行时引擎。它读取状态机图，观测当前 UI 状态，通过反应式循环导航到目标状态。

```python
def goto(target_state, page, context, graph, max_steps=50):
    for step in range(max_steps):
        # 1. 优先检查中断
        interrupt = detect_interrupt(page, context, graph["interrupts"])
        if interrupt:
            action = get_function(interrupt["action"])
            action(page, context)
            continue  # 处理完中断后重新观测

        # 2. 检测当前状态
        current = detect_state(page, context, graph["states"])

        # 3. 到达目标？
        if current == target_state:
            return True

        # 4. 在图上找从当前状态到目标状态的下一步动作
        action = find_next_action(current, target_state, graph["transitions"])
        action_fn = get_function(action)
        action_fn(page, context)

        # 5. 回到循环顶部重新观测（因为结果是不确定的）

    raise TimeoutError(f"在 {max_steps} 步内未能到达 {target_state}")
```

`find_next_action` 函数在转移图上搜索从当前状态到目标状态的路径，返回下一步要执行的动作。执行后，Planner **不假设**到达了预期状态 — 它重新观测、重新规划。

---

## 自动化用例 Demo

### Demo 1：滴滴租车比价

**场景：** 从滴滴 App 采集 1000+ 个取车-还车地点组合的租车报价。每 100 个组合后切换新账号。

#### 状态机图

```json
{
  "states": {
    "didi_home": {
      "matchers": ["is_didi_home"]
    },
    "rental_page": {
      "matchers": ["is_rental_page"]
    },
    "car_list": {
      "matchers": ["is_car_list"]
    },
    "my_page": {
      "matchers": ["is_my_page"]
    },
    "settings_page": {
      "matchers": ["is_settings_page"]
    },
    "logged_out": {
      "matchers": ["is_login_page"]
    }
  },
  "transitions": [
    {
      "from": "didi_home",
      "action": "click_rental_entry",
      "possible_targets": ["rental_page"]
    },
    {
      "from": "rental_page",
      "action": "fill_and_search",
      "possible_targets": ["car_list"]
    },
    {
      "from": "car_list",
      "action": "go_back",
      "possible_targets": ["rental_page"]
    },
    {
      "from": "rental_page",
      "action": "go_back",
      "possible_targets": ["didi_home"]
    },
    {
      "from": "didi_home",
      "action": "click_my",
      "possible_targets": ["my_page"]
    },
    {
      "from": "my_page",
      "action": "click_settings",
      "possible_targets": ["settings_page"]
    },
    {
      "from": "settings_page",
      "action": "scroll_and_logout",
      "possible_targets": ["logged_out"]
    },
    {
      "from": "logged_out",
      "action": "login_new_account",
      "possible_targets": ["didi_home"]
    }
  ],
  "interrupts": [
    {
      "matchers": ["has_coupon_popup"],
      "action": "close_coupon"
    }
  ]
}
```

说明：领券弹窗可能出现在任何页面（首页、租车页、我的页面）。一条 interrupt 定义即可全局处理，不需要 `didi_home_with_coupon`、`rental_page_with_coupon` 等额外状态。

#### Matchers

```python
def is_didi_home(page, context):
    return page.locator(".home-func-matrix").is_visible()

def is_rental_page(page, context):
    return page.locator(".rental-pickup-input").is_visible()

def is_car_list(page, context):
    return page.locator(".car-price-list").is_visible()

def is_my_page(page, context):
    return page.locator(".my-profile-header").is_visible()

def is_settings_page(page, context):
    return page.locator(".settings-list").is_visible()

def is_login_page(page, context):
    return page.locator(".login-form").is_visible()

def has_coupon_popup(page, context):
    return page.locator(".coupon-modal").is_visible()
```

#### Actions

```python
def click_rental_entry(page, context):
    page.locator(".home-func-matrix").locator("text=滴滴租车").click()

def close_coupon(page, context):
    page.locator(".coupon-modal .close-btn").click()

def fill_and_search(page, context):
    page.locator(".rental-pickup-input").fill(context["pickup"])
    page.locator(".rental-dropoff-input").fill(context["dropoff"])
    page.locator(".rental-start-time").fill(context["start_time"])
    page.locator(".rental-end-time").fill(context["end_time"])
    page.locator(".btn-search-car").click()

def go_back(page, context):
    page.locator(".nav-back").click()

def click_my(page, context):
    page.locator("text=我的").click()

def click_settings(page, context):
    page.locator("text=设置").click()

def scroll_and_logout(page, context):
    page.locator(".settings-list").evaluate("el => el.scrollTo(0, el.scrollHeight)")
    page.locator("text=退出登录").click()
    page.locator("text=确认").click()

def login_new_account(page, context):
    account = context["accounts"].pop(0)
    page.locator(".phone-input").fill(account["phone"])
    page.locator(".verify-btn").click()
    page.locator(".code-input").fill(account["code"])
    page.locator(".login-btn").click()
```

#### 测试用例

```python
def test_didi_rental_price_comparison():
    machine = StateMachine(graph, page)
    pairs = load_pairs()        # 1000+ 取车-还车地点组合
    accounts = load_accounts()  # 多个账号
    results = []

    machine.context["accounts"] = accounts

    for i, pair in enumerate(pairs):
        # 每 100 个组合切换账号
        if i > 0 and i % 100 == 0:
            machine.goto("logged_out")
            machine.goto("didi_home")

        # 导航到租车页并填写搜索条件
        machine.goto("rental_page")
        machine.context["pickup"] = pair["pickup"]
        machine.context["dropoff"] = pair["dropoff"]
        machine.context["start_time"] = pair["start"]
        machine.context["end_time"] = pair["end"]

        # 导航到报价列表
        machine.goto("car_list")

        # 提取报价数据（直接操作页面，不是状态切换）
        page.locator(".sort-by-price").click()
        items = page.locator(".car-item").all()[:100]
        for item in items:
            results.append({
                "pickup": pair["pickup"],
                "dropoff": pair["dropoff"],
                "car": item.locator(".car-name").text_content(),
                "price": item.locator(".car-price").text_content(),
            })

    save_results(results)
```

### Demo 2：京东商品价格查询

**场景：** 在京东 App 搜索茅台，找到带"自营"标签、卖家为"京东超市白酒自营专区"的商品及价格。

#### 状态机图

```json
{
  "states": {
    "jd_home": {
      "matchers": ["is_jd_home"]
    },
    "search_input": {
      "matchers": ["is_search_input_focused"]
    },
    "search_results": {
      "matchers": ["is_search_results"]
    }
  },
  "transitions": [
    {
      "from": "jd_home",
      "action": "click_search_box",
      "possible_targets": ["search_input"]
    },
    {
      "from": "search_input",
      "action": "type_and_search",
      "possible_targets": ["search_results"]
    }
  ],
  "interrupts": []
}
```

#### Matchers & Actions

```python
def is_jd_home(page, context):
    return page.locator(".jd-home-banner").is_visible()

def is_search_input_focused(page, context):
    return page.locator(".search-input:focus").is_visible()

def is_search_results(page, context):
    return page.locator(".product-list").is_visible()

def click_search_box(page, context):
    page.locator(".search-box").click()

def type_and_search(page, context):
    page.locator(".search-input").fill(context["keyword"])
    page.locator(".search-btn").click()
```

#### 测试用例

```python
def test_jd_maotai_price():
    machine = StateMachine(graph, page)
    machine.context["keyword"] = "茅台"

    # 导航到搜索结果页
    machine.goto("search_results")

    # 筛选并提取（直接操作页面）
    items = page.locator(".product-item").all()
    for item in items:
        is_self_operated = item.locator(".tag-self").is_visible()
        seller = item.locator(".seller-name").text_content()
        if is_self_operated and "京东超市白酒自营专区" in seller:
            print({
                "name": item.locator(".product-name").text_content(),
                "price": item.locator(".product-price").text_content(),
            })
            break
```

---

## 总结

| 组件 | 存储形式 | 实现形式 |
|---|---|---|
| 状态（States） | JSON（名称 + matcher 函数名列表） | Python matcher 函数 |
| 转移（Transitions） | JSON（from + action 名称 + possible_targets） | Python action 函数 |
| 中断（Interrupts） | JSON（matcher 函数名列表 + action 名称） | Python matcher/action 函数 |
| 上下文（Context） | 运行时字典 | 由 matcher 和 action 读写 |
| 规划器（Planner） | 框架代码 | 反应式 观测-决策-执行 循环 |

**设计原则：**

1. **JSON 是结构，代码是行为** — JSON 存储图的拓扑关系，Python 函数处理所有复杂逻辑
2. **matcher 数量多的优先** — 状态和中断匹配使用同一规则：所有 matcher 必须通过，候选中 matcher 最多的胜出
3. **中断处理全局弹窗** — 避免跨页面 UI 元素导致的状态爆炸
4. **非确定性转移** — 每个动作可能导向多个状态，Planner 每步都重新观测
5. **Context 传递变量** — 共享可变字典，支持外部传入和运行时提取
