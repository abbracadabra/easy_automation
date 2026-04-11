"""
Mock Demo: 模拟滴滴租车比价流程

不依赖任何 UI 驱动，用内存状态模拟页面切换，演示框架完整能力：
- 多状态导航
- 优先级状态自动处理弹窗（如 coupon 弹窗放在 states 最前面）
- context 传递业务数据
- 非确定性转移（action 可能失败）
- fallback 机制
"""
import logging
import random

from easy_automation import StateMachine, get_context

logging.basicConfig(level=logging.DEBUG, format="%(name)s - %(message)s")

# ============================================================
# 模拟 UI 状态
# ============================================================
ui = {
    "current_page": "home",
    "coupon_visible": False,
    "logged_in": True,
}


# ============================================================
# Matchers
# ============================================================
def is_home():
    return ui["current_page"] == "home"

def is_rental_page():
    return ui["current_page"] == "rental"

def is_car_list():
    return ui["current_page"] == "car_list"

def is_my_page():
    return ui["current_page"] == "my"

def is_settings():
    return ui["current_page"] == "settings"

def is_logged_out():
    return ui["current_page"] == "login"

def has_coupon():
    return ui["coupon_visible"]


# ============================================================
# Actions
# ============================================================
def click_rental():
    ui["current_page"] = "rental"
    if random.random() < 0.3:
        ui["coupon_visible"] = True

def fill_and_search():
    ctx = get_context()
    print(f"  [action] 搜索: {ctx['pickup']} -> {ctx['dropoff']}")
    if random.random() < 0.2:
        print("  [action] 搜索失败，页面未跳转")
        return
    ui["current_page"] = "car_list"

def go_back_to_rental():
    ui["current_page"] = "rental"

def go_back_to_home():
    ui["current_page"] = "home"

def click_my():
    ui["current_page"] = "my"

def click_settings():
    ui["current_page"] = "settings"

def do_logout():
    ui["current_page"] = "login"
    ui["logged_in"] = False

def login_new_account():
    ctx = get_context()
    account = ctx["accounts"].pop(0)
    print(f"  [action] 登录新账号: {account}")
    ui["current_page"] = "home"
    ui["logged_in"] = True

def close_coupon():
    print("  [action] 关闭领券弹窗")
    ui["coupon_visible"] = False


# ============================================================
# Functions dict
# ============================================================
FUNCTIONS = {
    "is_home": is_home,
    "is_rental_page": is_rental_page,
    "is_car_list": is_car_list,
    "is_my_page": is_my_page,
    "is_settings": is_settings,
    "is_logged_out": is_logged_out,
    "has_coupon": has_coupon,
    "click_rental": click_rental,
    "fill_and_search": fill_and_search,
    "go_back_to_rental": go_back_to_rental,
    "go_back_to_home": go_back_to_home,
    "click_my": click_my,
    "click_settings": click_settings,
    "do_logout": do_logout,
    "login_new_account": login_new_account,
    "close_coupon": close_coupon,
}


# ============================================================
# 状态机图
# ============================================================
GRAPH = {
    "states": {
        "has_coupon": {"matchers": ["has_coupon"]},
        "home": {"matchers": ["is_home"]},
        "rental": {"matchers": ["is_rental_page"]},
        "car_list": {"matchers": ["is_car_list"]},
        "my": {"matchers": ["is_my_page"]},
        "settings": {"matchers": ["is_settings"]},
        "logged_out": {"matchers": ["is_logged_out"]},
    },
    "transitions": [
        {"from": "has_coupon", "action": "close_coupon", "possible_targets": ["home", "rental", "car_list", "my", "settings"]},
        {"from": "home", "action": "click_rental", "possible_targets": ["rental"]},
        {"from": "rental", "action": "fill_and_search", "possible_targets": ["car_list", "rental"]},
        {"from": "car_list", "action": "go_back_to_rental", "possible_targets": ["rental"]},
        {"from": "rental", "action": "go_back_to_home", "possible_targets": ["home"]},
        {"from": "home", "action": "click_my", "possible_targets": ["my"]},
        {"from": "my", "action": "click_settings", "possible_targets": ["settings"]},
        {"from": "settings", "action": "do_logout", "possible_targets": ["logged_out"]},
        {"from": "logged_out", "action": "login_new_account", "possible_targets": ["home"]},
    ],
}


# ============================================================
# Fallback
# ============================================================
def my_fallback():
    print("  [fallback] 重置 App 状态")
    ui["current_page"] = "home"
    ui["coupon_visible"] = False


# ============================================================
# 测试用例
# ============================================================
def main():
    pairs = [
        {"pickup": "杭州东站", "dropoff": "西湖"},
        {"pickup": "萧山机场", "dropoff": "钱江新城"},
        {"pickup": "武林广场", "dropoff": "滨江"},
    ]
    accounts = ["account_2", "account_3"]

    machine = StateMachine(GRAPH, functions=FUNCTIONS, context={
        "accounts": accounts,
    })
    machine.set_fallback(my_fallback)
    machine.validate()

    results = []
    for i, pair in enumerate(pairs):
        print(f"\n{'='*50}")
        print(f"第 {i+1} 个: {pair['pickup']} -> {pair['dropoff']}")
        print(f"{'='*50}")

        machine.context["pickup"] = pair["pickup"]
        machine.context["dropoff"] = pair["dropoff"]

        machine.goto("rental")
        machine.goto("car_list")

        results.append({
            "pickup": pair["pickup"],
            "dropoff": pair["dropoff"],
            "price": f"¥{random.randint(100, 500)}",
        })
        print(f"  [结果] {results[-1]}")

    print(f"\n{'='*50}")
    print("退出登录")
    print(f"{'='*50}")
    machine.goto("logged_out")

    print(f"\n\n最终结果:")
    for r in results:
        print(f"  {r['pickup']} -> {r['dropoff']}: {r['price']}")


if __name__ == "__main__":
    main()
