from easy_automation import StateMachine


def is_home():
    return True


functions = {"is_home": is_home}

machine = StateMachine(
    {"states": {"home": {"matchers": ["is_home"]}}, "transitions": []},
    functions=functions,
)
machine.validate()
