from contextvars import ContextVar

_context_var: ContextVar[dict] = ContextVar('easy_automation_context')


def get_context() -> dict:
    try:
        return _context_var.get()
    except LookupError:
        raise RuntimeError("context 尚未初始化，请先创建 StateMachine 实例")


def set_context(ctx: dict):
    _context_var.set(ctx)
