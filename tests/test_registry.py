import pytest
from easy_automation.core.registry import register, get_function, clear_registry


@pytest.fixture(autouse=True)
def clean_registry():
    clear_registry()
    yield
    clear_registry()


def test_register_and_get():
    @register()
    def my_func():
        return 42

    fn = get_function("my_func")
    assert fn() == 42


def test_register_with_custom_name():
    @register("custom_name")
    def my_func():
        return 99

    fn = get_function("custom_name")
    assert fn() == 99

    with pytest.raises(KeyError):
        get_function("my_func")


def test_get_unregistered_raises():
    with pytest.raises(KeyError, match="函数未注册"):
        get_function("nonexistent")


def test_duplicate_register_raises():
    @register()
    def dup_func():
        pass

    with pytest.raises(ValueError, match="函数名已注册"):
        @register()
        def dup_func():
            pass
