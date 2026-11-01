"""Adversarial suite, layer 1: the language.

Action code that tries what has always got out of a restricted ``exec``:
walking from a literal to ``object.__subclasses__()``, a function's
``__globals__``, a builtin's ``__self__``, a format string that reads
attributes, a generator's frame, a traceback's frame, ``import``, ``eval``,
``open``. Each must be refused before it runs (``kind == "refused"``) or fail
when it runs, and none may return a marker held by the executor or the run's
secrets. The same attempts are also run in the child with the policy layer off
in ``test_sandbox_adversarial_process.py``: layer 1 is not what keeps the
secrets safe.
"""

import pytest

from sandbox import policy
from tests.sandbox_support import needs_confinement, run

SENTINEL = "SENTINEL-THE-EXECUTOR-KEY-0123456789"
SECRET_VALUE = "SECRET-VALUE-OF-THIS-RUN-987654"

ESCAPES = {
    "subclasses": "x = ().__class__.__bases__[0].__subclasses__()",
    "function_globals": "x = log.__globals__",
    "api_function_globals": "x = get_form.__globals__",
    "closure": "x = send_data_webhook.__closure__",
    "code_object": "x = log.__code__",
    "builtin_self": "x = print.__self__",
    "format_attribute_read": "x = '{0.__globals__}'.format(log)",
    "format_map": "x = '{a.__globals__}'.format_map({'a': log})",
    "getattr_name": "x = getattr(log, '__glob' + 'als__')",
    "dunder_import": "x = __import__('os')",
    "import": "import os",
    "import_from": "from os import environ",
    "eval": "x = eval('1')",
    "exec": "exec('x = 1')",
    "compile": "x = compile('1', 'a', 'eval')",
    "open": "x = open('/etc/passwd')",
    "type_walk": "x = type(log).__mro__",
    "vars": "x = vars()",
    "globals": "x = globals()",
    "locals": "x = locals()",
    "dir": "x = dir(log)",
    "generator_frame": "x = (i for i in []).gi_frame.f_back.f_globals",
    "traceback_frame": (
        "try:\n    1 / 0\nexcept Exception as e:\n"
        "    x = e.__traceback__.tb_frame.f_globals"
    ),
    "traceback_without_dunder": (
        "try:\n    1 / 0\nexcept Exception as e:\n    x = e.with_traceback"
        "\n    y = e.tb_frame"
    ),
    "lambda_globals": "x = (lambda: 0).__globals__",
    "class_statement": "class A:\n    pass",
    "class_with_metaclass": "class A(metaclass=type):\n    pass",
    "fullwidth_underscores": "x = log.＿＿globals＿＿",
    "builtins_name": "x = __builtins__",
    "build_class": "x = __build_class__",
    "async": "async def f():\n    pass",
    "yield": "def f():\n    yield 1",
    "str_subclasses": "x = str.__subclasses__()",
    "json_function_globals": "x = json.dumps.__globals__",
    "random_class": "x = random.__init__.__globals__",
    "http_exception_class": "x = HTTPException.__init__.__globals__",
    "decorator_trick": "@log.__globals__.get\ndef f():\n    pass",
    "match_attribute": ("match 1:\n    case log.__globals__:\n        pass"),
}


@pytest.mark.parametrize("name", sorted(ESCAPES))
def test_the_policy_refuses_every_usual_escape(name):
    with pytest.raises(policy.PolicyViolation):
        policy.check_source(ESCAPES[name])


@needs_confinement
@pytest.mark.parametrize("name", sorted(ESCAPES))
def test_in_the_sandbox_each_escape_is_refused_and_leaks_nothing(name, monkeypatch):
    monkeypatch.setenv("AES_HEX_KEY", SENTINEL)
    outcome = run(
        ESCAPES[name] + "\nlog('REACHED-THE-END')",
        {"secret_names": ["Token"], "parameters": {"Mode": "x"}},
    )
    assert outcome.error is not None
    assert outcome.error["kind"] == "refused"
    assert "REACHED-THE-END" not in outcome.log
    assert SENTINEL not in repr(outcome)


@needs_confinement
@pytest.mark.parametrize(
    "name", ["os", "sys", "socket", "subprocess", "settings", "crypto", "httpx"]
)
def test_modules_and_settings_are_simply_not_there(name):
    outcome = run(f"x = {name}")
    assert outcome.error["kind"] == "error"
    assert outcome.error["class"] == "NameError"


@needs_confinement
def test_the_run_data_is_only_what_was_sent():
    outcome = run(
        "log(str(get_parameter('Mode')))\n"
        "log(str(sorted(get_secrets())))\n"
        "log(str(get_response()))",
        {
            "parameters": {"Mode": "fast"},
            "secret_names": ["Token"],
            "response": {"answers": {"q": "A"}},
        },
    )
    assert outcome.error is None
    assert outcome.log == ["fast", "['Token']", "{'answers': {'q': 'A'}}"]


@needs_confinement
def test_a_secret_is_a_name_never_a_value():
    # the value is not sent to the child at all (the data has the names only);
    # the code can print the handle, not what it stands for
    outcome = run(
        "s = get_secret('Token')\n"
        "log(str(s))\nlog(repr(s))\nlog(f'{s}')\nlog(str(get_secrets()))\n"
        "try:\n    log(json.dumps(s))\nexcept Exception as e:\n    log('TypeError' if isinstance(e, TypeError) else 'other')\n"
        "try:\n    log(s + 'x')\nexcept Exception as e:\n    log('TypeError' if isinstance(e, TypeError) else 'other')\n"
        "log(str(get_secret('Missing')))\n",
        {"secret_names": ["Token"]},
    )
    assert outcome.error is None
    assert SECRET_VALUE not in repr(outcome)
    assert outcome.log[0] == "<secret Token>"
    assert outcome.log[3] == "{'Token': <secret Token>}"
    assert outcome.log[4:] == ["TypeError", "TypeError", "None"]


@needs_confinement
def test_ordinary_action_code_still_runs():
    code = """
rows = [{"title": q["title"], "answer": q["answer"]} for q in get_simple_form_response()]
total = sum(len(r["answer"]) for r in rows)
def label(row):
    return f"{row['title']}={row['answer']}"
log(', '.join(sorted(label(r) for r in rows)))
log(str(total))
log(json.dumps({"n": len(rows)}))
log(str(random(7).randint(1, 1)))
try:
    raise HTTPException(409, "already")
except HTTPException as e:
    log("caught:" + str(e))
"""
    outcome = run(
        code,
        {
            "simple_response": [
                {"title": "Q1", "answer": "yes"},
                {"title": "Q2", "answer": "no"},
            ]
        },
    )
    assert outcome.error is None, outcome.error
    assert outcome.log == ["Q1=yes, Q2=no", "5", '{"n": 2}', "1", "caught:already"]


@needs_confinement
def test_what_the_code_needs_is_loaded_before_the_filesystem_goes():
    # nothing can be imported once the child is confined: the usual codecs,
    # unseeded randomness and json are loaded first
    outcome = run(
        "log(str('é'.encode('latin-1')))\nlog(str('é'.encode('utf-16')))\n"
        "log(str(0 <= random().random() < 1))\nlog(json.dumps({'é': 1}))"
    )
    assert outcome.error is None, outcome.error
    assert outcome.log == [
        "b'\\xe9'",
        "b'\\xff\\xfe\\xe9\\x00'",
        "True",
        '{"\\u00e9": 1}',
    ]


@needs_confinement
def test_a_code_that_loops_forever_or_recurses_ends():
    outcome = run("def f():\n    return f()\nf()")
    assert outcome.error["class"] == "RecursionError"
    outcome = run("while True:\n    pass", cpu_seconds=1, timeout_seconds=15)
    assert outcome.error["kind"] in ("cpu_limit", "timeout", "killed")


@needs_confinement
def test_a_huge_allocation_ends_with_a_memory_error():
    outcome = run("x = 'a' * (1 << 31)", memory_mb=128)
    assert outcome.error["kind"] == "memory"


def test_source_limits():
    with pytest.raises(policy.PolicyViolation):
        policy.check_source("x = 1\n" * 20_000)  # too many nodes
    with pytest.raises(policy.PolicyViolation):
        policy.check_source("# " + "a" * 70_000)
    with pytest.raises(policy.PolicyViolation):
        policy.check_source("x = (")
    with pytest.raises(policy.PolicyViolation):
        policy.check_source("(" * 400 + ")" * 400)  # too deep to parse
