from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path

import tree_sitter
import tree_sitter_typescript
from pydantic import BaseModel

_MAX_FILE_BYTES = 2 * 1024 * 1024
_SKIP_SEGMENTS = frozenset({"node_modules", ".git", "dist", "build", "_nomap"})
_FUNCTION_KINDS = frozenset(
    {
        "function_declaration",
        "function_expression",
        "arrow_function",
        "method_definition",
        "generator_function_declaration",
        "generator_function",
    }
)

_LANGUAGE = tree_sitter.Language(tree_sitter_typescript.language_tsx())


class Function(BaseModel):
    id: str
    name: str
    path: str
    start_line: int
    end_line: int
    kind: str


class CallEdge(BaseModel):
    from_id: str
    callee_name: str
    path: str
    line: int


class FileResult(BaseModel):
    path: str
    functions: list[Function]
    edges: list[CallEdge]
    parse_errors: int


def _make_id(path: str, line: int, name: str, dedup_index: int) -> str:
    raw = (
        f"{path}:{line}:{name}:{dedup_index}"
        if dedup_index
        else f"{path}:{line}:{name}"
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _function_name(node: tree_sitter.Node, parent: tree_sitter.Node | None) -> str:
    if node.type in {
        "function_declaration",
        "generator_function_declaration",
        "method_definition",
    }:
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            return name_node.text.decode("utf-8", "replace")
    if node.type in {"arrow_function", "function_expression", "generator_function"}:
        # Bind back to LHS identifier for `const x = () => …` and `x = () => …`.
        if parent is not None:
            if parent.type == "variable_declarator":
                name_node = parent.child_by_field_name("name")
                if name_node is not None and name_node.type == "identifier":
                    return name_node.text.decode("utf-8", "replace")
            if parent.type == "assignment_expression":
                lhs = parent.child_by_field_name("left")
                if lhs is not None and lhs.type == "identifier":
                    return lhs.text.decode("utf-8", "replace")
            if parent.type == "pair":
                key = parent.child_by_field_name("key")
                if key is not None and key.type in {"property_identifier", "string"}:
                    return key.text.decode("utf-8", "replace").strip("'\"")
    return "<anonymous>"


def _callee_name(call_node: tree_sitter.Node) -> str | None:
    fn = call_node.child_by_field_name("function")
    if fn is None:
        return None
    if fn.type == "identifier":
        return fn.text.decode("utf-8", "replace")
    if fn.type == "member_expression":
        prop = fn.child_by_field_name("property")
        if prop is not None and prop.type in {"property_identifier", "identifier"}:
            return prop.text.decode("utf-8", "replace")
        return None
    return None


def _is_function_node(node: tree_sitter.Node) -> bool:
    return node.type in _FUNCTION_KINDS


def _walk_collect(
    root: tree_sitter.Node, rel: str
) -> tuple[list[Function], list[CallEdge], int]:
    functions: list[Function] = []
    edges: list[CallEdge] = []
    parse_errors = 0
    name_line_counts: dict[tuple[int, str], int] = defaultdict(int)
    fn_stack: list[str] = []

    # Iterative DFS with enter+leave events to maintain enclosing-function stack.
    stack: list[tuple[tree_sitter.Node, tree_sitter.Node | None, bool, bool]] = [
        (root, None, False, False)
    ]

    while stack:
        node, parent, entered, pushed_fn = stack.pop()

        if entered:
            if pushed_fn:
                fn_stack.pop()
            continue

        if node.type == "ERROR" or node.is_missing:
            parse_errors += 1

        pushed_here = False
        if _is_function_node(node):
            name = _function_name(node, parent)
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1
            key = (start_line, name)
            dedup_index = name_line_counts[key]
            name_line_counts[key] += 1
            fid = _make_id(rel, start_line, name, dedup_index)
            functions.append(
                Function(
                    id=fid,
                    name=name,
                    path=rel,
                    start_line=start_line,
                    end_line=end_line,
                    kind=node.type,
                )
            )
            fn_stack.append(fid)
            pushed_here = True

        if node.type == "call_expression":
            callee = _callee_name(node)
            if callee is not None:
                from_id = fn_stack[-1] if fn_stack else ""
                edges.append(
                    CallEdge(
                        from_id=from_id,
                        callee_name=callee,
                        path=rel,
                        line=node.start_point[0] + 1,
                    )
                )

        stack.append((node, parent, True, pushed_here))
        # Push children in reverse so DFS preorder matches source order.
        for i in range(node.child_count - 1, -1, -1):
            child = node.children[i]
            stack.append((child, node, False, False))

    return functions, edges, parse_errors


def extract_file(file_path: Path, sources_root: Path) -> FileResult:
    rel = file_path.relative_to(sources_root).as_posix()
    try:
        raw = file_path.read_bytes()
    except OSError:
        return FileResult(path=rel, functions=[], edges=[], parse_errors=1)
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        return FileResult(path=rel, functions=[], edges=[], parse_errors=1)

    parser = tree_sitter.Parser(_LANGUAGE)
    tree = parser.parse(raw)
    functions, edges, parse_errors = _walk_collect(tree.root_node, rel)
    return FileResult(
        path=rel,
        functions=functions,
        edges=edges,
        parse_errors=parse_errors,
    )


def extract_tree(
    sources_root: Path,
    exts: tuple[str, ...] = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"),
) -> list[FileResult]:
    results: list[FileResult] = []
    sources_root = sources_root.resolve()
    for path in sorted(sources_root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in exts:
            continue
        rel_parts = path.relative_to(sources_root).parts
        if any(p in _SKIP_SEGMENTS for p in rel_parts):
            continue
        try:
            if path.stat().st_size > _MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        results.append(extract_file(path, sources_root))
    return results
