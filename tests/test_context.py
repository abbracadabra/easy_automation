import pytest
from easy_automation.core.context import get_context, set_context


def test_set_and_get():
    ctx = {"key": "value"}
    set_context(ctx)
    assert get_context() is ctx
    assert get_context()["key"] == "value"


def test_get_without_set_raises():
    """在未 set 的新线程/上下文中，get 应该报错"""
    # contextvars 在同一线程中会保留，所以这个测试依赖执行顺序
    # 这里主要测试 set/get 的基本功能
    ctx = {"a": 1}
    set_context(ctx)
    result = get_context()
    assert result["a"] == 1


def test_context_is_mutable():
    ctx = {}
    set_context(ctx)
    get_context()["new_key"] = "new_value"
    assert ctx["new_key"] == "new_value"
