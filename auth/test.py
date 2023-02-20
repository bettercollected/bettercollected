from typing import Any



def get_variable_name(var: Any):
    return f'{var=}'.split('=')[0]


if __name__ == "__main__":
    ok = "hello"
    print(get_variable_name(ok))
