import pytest
from easy_automation.core.context import get_context
from easy_automation.core.engine import StateMachine


def test_end_to_end_didi_like_flow():
    """端到端测试：模拟滴滴租车比价的简化流程

    流程：home -> rental_page -> car_list -> rental_page -> home -> my_page -> settings -> logged_out
    中间可能出现 coupon 弹窗（优先级状态处理）
    """
    state_holder = {"current": "home", "coupon_visible": False, "coupon_closed_count": 0}

    def is_home():
        return state_holder["current"] == "home"

    def is_rental_page():
        return state_holder["current"] == "rental"

    def is_car_list():
        return state_holder["current"] == "car_list"

    def is_my_page():
        return state_holder["current"] == "my"

    def is_settings():
        return state_holder["current"] == "settings"

    def is_logged_out():
        return state_holder["current"] == "logged_out"

    def has_coupon():
        return state_holder["coupon_visible"]

    def click_rental():
        state_holder["current"] = "rental"
        state_holder["coupon_visible"] = True

    def fill_and_search():
        ctx = get_context()
        assert "pickup" in ctx
        state_holder["current"] = "car_list"

    def go_back_to_rental():
        state_holder["current"] = "rental"

    def go_back_to_home():
        state_holder["current"] = "home"

    def click_my():
        state_holder["current"] = "my"

    def click_settings():
        state_holder["current"] = "settings"

    def do_logout():
        state_holder["current"] = "logged_out"

    def close_coupon():
        state_holder["coupon_visible"] = False
        state_holder["coupon_closed_count"] += 1

    functions = {
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
        "close_coupon": close_coupon,
    }

    graph_data = {
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
            {"from": "has_coupon", "action": "close_coupon",
             "possible_targets": ["home", "rental", "car_list", "my", "settings", "logged_out"]},
            {"from": "home", "action": "click_rental", "possible_targets": ["rental"]},
            {"from": "rental", "action": "fill_and_search", "possible_targets": ["car_list"]},
            {"from": "car_list", "action": "go_back_to_rental", "possible_targets": ["rental"]},
            {"from": "rental", "action": "go_back_to_home", "possible_targets": ["home"]},
            {"from": "home", "action": "click_my", "possible_targets": ["my"]},
            {"from": "my", "action": "click_settings", "possible_targets": ["settings"]},
            {"from": "settings", "action": "do_logout", "possible_targets": ["logged_out"]},
        ],
    }

    machine = StateMachine(graph_data, functions=functions, context={"pickup": "地点A", "dropoff": "地点B"})
    machine.validate()

    machine.goto("rental")
    assert state_holder["current"] == "rental"

    machine.goto("car_list")
    assert state_holder["current"] == "car_list"

    machine.goto("home")
    assert state_holder["current"] == "home"

    machine.goto("logged_out")
    assert state_holder["current"] == "logged_out"

    assert state_holder["coupon_closed_count"] >= 1


def test_target_state_not_exist():
    def m():
        return True

    functions = {"m": m}
    graph_data = {
        "states": {"a": {"matchers": ["m"]}},
        "transitions": [],
    }
    machine = StateMachine(graph_data, functions=functions)
    with pytest.raises(ValueError, match="目标状态不存在"):
        machine.goto("nonexistent")
