from __future__ import annotations

from pathlib import Path

from backend.pillars.sast.callgraph_native import (
    CallEdge,
    FileResult,
    Function,
    extract_file,
    extract_tree,
)


def _write(tmp_path: Path, name: str, src: str) -> Path:
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(src, encoding="utf-8")
    return p


def test_function_declaration(tmp_path: Path) -> None:
    f = _write(tmp_path, "foo.js", "function add(a, b) { return a + b; }\n")
    result = extract_file(f, tmp_path)

    assert isinstance(result, FileResult)
    assert result.path == "foo.js"
    assert result.parse_errors == 0
    assert len(result.functions) == 1
    fn = result.functions[0]
    assert fn.name == "add"
    assert fn.kind == "function_declaration"
    assert fn.start_line == 1
    assert result.edges == []


def test_arrow_function(tmp_path: Path) -> None:
    # Arrow functions bound to a `variable_declarator` get the LHS identifier as
    # their name — this matches how a human reading the file would refer to it.
    f = _write(tmp_path, "arr.js", "const g = (x) => x * 2;\n")
    result = extract_file(f, tmp_path)

    assert result.parse_errors == 0
    assert len(result.functions) == 1
    fn = result.functions[0]
    assert fn.kind == "arrow_function"
    assert fn.name == "g"


def test_method_definition_and_call(tmp_path: Path) -> None:
    src = "class Foo { bar() { this.baz(); } baz() {} }\n"
    f = _write(tmp_path, "klass.js", src)
    result = extract_file(f, tmp_path)

    assert result.parse_errors == 0
    names = sorted(fn.name for fn in result.functions)
    assert names == ["bar", "baz"]
    assert all(fn.kind == "method_definition" for fn in result.functions)

    assert len(result.edges) == 1
    edge = result.edges[0]
    assert edge.callee_name == "baz"

    bar = next(fn for fn in result.functions if fn.name == "bar")
    assert edge.from_id == bar.id


def test_nested_function_scopes(tmp_path: Path) -> None:
    src = (
        "function a() {\n"
        "  function b() {\n"
        "    c();\n"
        "  }\n"
        "  b();\n"
        "}\n"
    )
    f = _write(tmp_path, "nest.js", src)
    result = extract_file(f, tmp_path)

    assert result.parse_errors == 0
    a = next(fn for fn in result.functions if fn.name == "a")
    b = next(fn for fn in result.functions if fn.name == "b")

    b_to_c = next(e for e in result.edges if e.callee_name == "c")
    assert b_to_c.from_id == b.id
    assert b_to_c.from_id != a.id

    a_to_b = next(e for e in result.edges if e.callee_name == "b")
    assert a_to_b.from_id == a.id


def test_extract_tree_walks_dir(tmp_path: Path) -> None:
    _write(tmp_path / "src", "a.ts", "function alpha() {}\n")
    _write(tmp_path / "src/util", "b.ts", "function beta() {}\n")
    _write(tmp_path, "notes.txt", "hello\n")
    _write(tmp_path / "node_modules" / "pkg", "skip.ts", "function nope() {}\n")

    results = extract_tree(tmp_path)
    assert len(results) == 2
    paths = sorted(r.path for r in results)
    assert paths == ["src/a.ts", "src/util/b.ts"]


def test_tsx_with_jsx_parses(tmp_path: Path) -> None:
    src = "const App = () => <div onClick={() => log()}>hi</div>;\n"
    f = _write(tmp_path, "App.tsx", src)
    result = extract_file(f, tmp_path)

    assert result.parse_errors == 0
    arrows = [fn for fn in result.functions if fn.kind == "arrow_function"]
    assert len(arrows) >= 1
    # The inline arrow inside onClick calls `log` — make sure that survived too.
    assert any(e.callee_name == "log" for e in result.edges)


def test_call_via_member_expression(tmp_path: Path) -> None:
    src = "function x() { obj.foo.bar(); }\n"
    f = _write(tmp_path, "mem.js", src)
    result = extract_file(f, tmp_path)

    assert result.parse_errors == 0
    assert len(result.edges) == 1
    assert result.edges[0].callee_name == "bar"
    x = next(fn for fn in result.functions if fn.name == "x")
    assert result.edges[0].from_id == x.id


def test_parse_error_does_not_crash(tmp_path: Path) -> None:
    f = _write(tmp_path, "broken.js", "function broken(\n")
    result = extract_file(f, tmp_path)

    assert isinstance(result, FileResult)
    assert result.parse_errors > 0
    # Sanity: also exercise the pydantic models stay importable.
    _ = Function, CallEdge
