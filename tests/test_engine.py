import pytest
from easy_automation.core.registry import register, clear_registry
from easy_automation.core.context import get_context
from easy_automation.core.engine import StateMachine


@pytest.fixture(autouse=True)
def clean_registry():
    clear_registry()
    yield
    clear_registry()


def test_end_to_end_didi_like_flow():
    """端到端测试：模拟滴滴租车比价的简化流程

    流程：home -> rental_page -> car_list -> rental_page -> home -> my_page -> settings -> logged_out
    中间可能出现 coupon 弹窗（interrupt 处理）
    """
    state_holder = {"current": "home", "coupon_visible": False, "coupon_closed_count": 0}

    # --- matchers ---
    @register()
    def is_home():
        return state_holder["current"] == "home"

    @register()
    def is_rental_page():
        return state_holder["current"] == "rental"

    @register()
    def is_car_list():
        return state_holder["current"] == "car_list"

    @register()
    def is_my_page():
        return state_holder["current"] == "my"

    @register()
    def is_settings():
        return state_holder["current"] == "settings"

    @register()
    def is_logged_out():
        return state_holder["current"] == "logged_out"

    @register()
    def has_coupon():
        return state_holder["coupon_visible"]

    # --- actions ---
    @register()
    def click_rental():
        state_holder["current"] = "rental"
        # 进入租车页时可能弹 coupon
        state_holder["coupon_visible"] = True

    @register()
    def fill_and_search():
        ctx = get_context()
        # 模拟使用 context 中的数据
        assert "pickup" in ctx
        state_holder["current"] = "car_list"

    @register()
    def go_back_to_rental():
        state_holder["current"] = "rental"

    @register()
    def go_back_to_home():
        state_holder["current"] = "home"

    @register()
    def click_my():
        state_holder["current"] = "my"

    @register()
    def click_settings():
        state_holder["current"] = "settings"

    @register()
    def do_logout():
        state_holder["current"] = "logged_out"

    @register()
    def close_coupon():
        state_holder["coupon_visible"] = False
        state_holder["coupon_closed_count"] += 1

    # --- graph ---
    graph_data = {
        "states": {
            "home": {"matchers": ["is_home"]},
            "rental": {"matchers": ["is_rental_page"]},
            "car_list": {"matchers": ["is_car_list"]},
            "my": {"matchers": ["is_my_page"]},
            "settings": {"matchers": ["is_settings"]},
            "logged_out": {"matchers": ["is_logged_out"]},
        },
        "transitions": [
            {"from": "home", "action": "click_rental", "possible_targets": ["rental"]},
            {"from": "rental", "action": "fill_and_search", "possible_targets": ["car_list"]},
            {"from": "car_list", "action": "go_back_to_rental", "possible_targets": ["rental"]},
            {"from": "rental", "action": "go_back_to_home", "possible_targets": ["home"]},
            {"from": "home", "action": "click_my", "possible_targets": ["my"]},
            {"from": "my", "action": "click_settings", "possible_targets": ["settings"]},
            {"from": "settings", "action": "do_logout", "possible_targets": ["logged_out"]},
        ],
        "interrupts": [
            {"matchers": ["has_coupon"], "action": "close_coupon"},
        ],
    }

    machine = StateMachine(graph_data, context={"pickup": "地点A", "dropoff": "地点B"})
    machine.validate()

    # 导航到租车页（会触发 coupon interrupt）
    machine.goto("rental")
    assert state_holder["current"] == "rental"

    # 设置搜索条件后导航到报价列表
    machine.goto("car_list")
    assert state_holder["current"] == "car_list"

    # 返回首页
    machine.goto("home")
    assert state_holder["current"] == "home"

    # 走退出登录流程
    machine.goto("logged_out")
    assert state_holder["current"] == "logged_out"

    # coupon 被自动处理过
    assert state_holder["coupon_closed_count"] >= 1


def test_target_state_not_exist():
    @register()
    def m():
        return True

    graph_data = {
        "states": {"a": {"matchers": ["m"]}},
        "transitions": [],
        "interrupts": [],
    }
    machine = StateMachine(graph_data)
    with pytest.raises(ValueError, match="目标状态不存在"):
        machine.goto("nonexistent")
