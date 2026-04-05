_registry: dict[str, callable] = {}


def register(name: str = None):
    def decorator(fn):
        key = name or fn.__name__
        if key in _registry:
            raise ValueError(f"函数名已注册: {key}")
        _registry[key] = fn
        return fn
    return decorator


def get_function(name: str) -> callable:
    if name not in _registry:
        raise KeyError(f"函数未注册: {name}")
    return _registry[name]


def clear_registry():
    _registry.clear()
