from contextvars import ContextVar

_frame_cache_var: ContextVar[dict] = ContextVar('easy_automation_frame_cache') # 当前帧的cache


def get_frame_cache() -> dict:
    try:
        return _frame_cache_var.get()
    except LookupError:
        raise RuntimeError("snapshot cache 尚未初始化，请先调用 StateMachine.goto()")


def reset_snapshot_cache():
    _frame_cache_var.set({})
