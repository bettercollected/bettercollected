"""Shared by the marker script and the guard test: which repository methods write?

A method writes if its body awaits a Beanie write call (save/insert/delete/
update/... on a document or query), or if it calls another write method of the
same repository via ``self.`` — that inner call runs on the concrete Mongo
instance and would never reach the mirror, so the outer method must be routed
as a write itself.
"""

import ast, pathlib

WRITE_CALLS = {
    "save",
    "insert",
    "insert_many",
    "insert_one",
    "replace",
    "replace_one",
    "delete",
    "delete_all",
    "delete_many",
    "delete_one",
    "update",
    "update_many",
    "update_all",
    "update_one",
    "upsert",
    "set",
    "inc",
    "save_changes",
    "find_one_and_update",
    "create",
}


def classify(repositories_dir):
    """-> {(file, class, method): (is_write, reasons)} for public methods."""
    out = {}
    for p in sorted(pathlib.Path(repositories_dir).glob("*.py")):
        if p.name == "__init__.py":
            continue
        tree = ast.parse(p.read_text())
        for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
            methods = {
                n.name: n
                for n in cls.body
                if isinstance(n, (ast.AsyncFunctionDef, ast.FunctionDef))
            }
            direct, self_calls = {}, {}
            for name, fn in methods.items():
                writes, calls = set(), set()
                for node in ast.walk(fn):
                    if (
                        isinstance(node, ast.Await)
                        and isinstance(node.value, ast.Call)
                        and isinstance(node.value.func, ast.Attribute)
                    ):
                        if node.value.func.attr in WRITE_CALLS:
                            writes.add(node.value.func.attr)
                    if (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "self"
                    ):
                        calls.add(node.func.attr)
                direct[name], self_calls[name] = writes, calls
            # transitive closure over self-calls
            is_write = {n: bool(w) for n, w in direct.items()}
            changed = True
            while changed:
                changed = False
                for n, cs in self_calls.items():
                    if not is_write[n] and any(is_write.get(c) for c in cs):
                        is_write[n] = True
                        changed = True
            for name, fn in methods.items():
                if name.startswith("_"):
                    continue
                reasons = sorted(direct[name]) + [
                    f"self.{c}" for c in sorted(self_calls[name]) if is_write.get(c)
                ]
                out[(p.name, cls.name, name)] = (
                    is_write[name],
                    reasons,
                    fn.lineno,
                    [ast.unparse(d) for d in fn.decorator_list],
                )
    return out


from pathlib import Path

REPOSITORIES = Path(__file__).resolve().parents[3] / "backend" / "app" / "repositories"


def test_every_repository_method_that_writes_is_marked_write_op():
    """The RoutingRepository mirrors only methods marked @write_op. A write that
    is not marked runs on the primary store alone and silently drifts the
    mirror — so this is checked from the source, not from convention."""
    result = classify(REPOSITORIES)
    unmarked = sorted(
        f"{cls}.{method} (writes via {', '.join(reasons)})"
        for (file, cls, method), (is_write, reasons, _, decorators) in result.items()
        if is_write and not any("write_op" in d for d in decorators)
    )
    assert unmarked == [], "mark these with @write_op:\n  " + "\n  ".join(unmarked)


def test_reads_are_not_marked_write_op():
    result = classify(REPOSITORIES)
    over_marked = sorted(
        f"{cls}.{method}"
        for (file, cls, method), (is_write, reasons, _, decorators) in result.items()
        if not is_write and any("write_op" in d for d in decorators)
    )
    assert over_marked == [], "these are reads; drop @write_op:\n  " + "\n  ".join(
        over_marked
    )


def test_the_classifier_sees_the_whole_repository_layer():
    result = classify(REPOSITORIES)
    assert len(result) > 150 and sum(1 for v in result.values() if v[0]) > 60
