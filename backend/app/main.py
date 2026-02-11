from __future__ import annotations

import ast
from collections import defaultdict
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI()

IO_CALL_NAMES = {
    "open",
    "print",
    "input",
    "read",
    "write",
    "read_text",
    "write_text",
    "read_bytes",
    "write_bytes",
}


class AtlasFile(BaseModel):
    path: str
    content: str


class AtlasRequest(BaseModel):
    files: list[AtlasFile] = Field(default_factory=list)


class AtlasNode(BaseModel):
    id: str
    file: str
    identifier: str
    kind: str
    start_line: int
    end_line: int
    tags: list[str]


class AtlasEdge(BaseModel):
    source: str
    target: str
    kind: str


class AtlasResponse(BaseModel):
    nodes: list[AtlasNode]
    edges: list[AtlasEdge]
    clusters: dict[str, list[str]]


def _line_range(node: ast.AST) -> tuple[int, int]:
    start = int(getattr(node, "lineno", 1) or 1)
    end = int(getattr(node, "end_lineno", start) or start)
    return start, end


def _make_id(file_path: str, kind: str, identifier: str, start_line: int, end_line: int) -> str:
    safe_identifier = identifier.replace(" ", "_")
    return f"{file_path}:{kind}:{safe_identifier}:{start_line}:{end_line}"


def _call_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _file_node(file_path: str, total_lines: int) -> AtlasNode:
    return AtlasNode(
        id=_make_id(file_path, "file", file_path, 1, max(1, total_lines)),
        file=file_path,
        identifier=file_path,
        kind="file",
        start_line=1,
        end_line=max(1, total_lines),
        tags=["file"],
    )


def _parse_python_file(file_path: str, content: str) -> tuple[list[AtlasNode], list[AtlasEdge]]:
    nodes: list[AtlasNode] = []
    edges: list[AtlasEdge] = []

    total_lines = len(content.splitlines())
    root_node = _file_node(file_path, total_lines)
    nodes.append(root_node)

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return nodes, edges

    def visit(node: ast.AST, parent_id: str) -> None:
        current_parent = parent_id

        if isinstance(node, ast.ClassDef):
            start, end = _line_range(node)
            atlas_node = AtlasNode(
                id=_make_id(file_path, "class", node.name, start, end),
                file=file_path,
                identifier=node.name,
                kind="class",
                start_line=start,
                end_line=end,
                tags=["class", "type"],
            )
            nodes.append(atlas_node)
            edges.append(AtlasEdge(source=parent_id, target=atlas_node.id, kind="contains"))
            current_parent = atlas_node.id

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start, end = _line_range(node)
            fn_kind = "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function"
            atlas_node = AtlasNode(
                id=_make_id(file_path, fn_kind, node.name, start, end),
                file=file_path,
                identifier=node.name,
                kind=fn_kind,
                start_line=start,
                end_line=end,
                tags=["function", "callable"],
            )
            nodes.append(atlas_node)
            edges.append(AtlasEdge(source=parent_id, target=atlas_node.id, kind="contains"))
            current_parent = atlas_node.id

        elif isinstance(node, (ast.For, ast.While, ast.AsyncFor)):
            start, end = _line_range(node)
            loop_kind = "loop"
            identifier = f"{node.__class__.__name__.lower()}@{start}"
            atlas_node = AtlasNode(
                id=_make_id(file_path, loop_kind, identifier, start, end),
                file=file_path,
                identifier=identifier,
                kind=loop_kind,
                start_line=start,
                end_line=end,
                tags=["loop", "iteration"],
            )
            nodes.append(atlas_node)
            edges.append(AtlasEdge(source=parent_id, target=atlas_node.id, kind="contains"))

        elif isinstance(node, ast.Try):
            start, end = _line_range(node)
            identifier = f"try@{start}"
            atlas_node = AtlasNode(
                id=_make_id(file_path, "exception", identifier, start, end),
                file=file_path,
                identifier=identifier,
                kind="exception",
                start_line=start,
                end_line=end,
                tags=["exception", "error_handling"],
            )
            nodes.append(atlas_node)
            edges.append(AtlasEdge(source=parent_id, target=atlas_node.id, kind="contains"))

        elif isinstance(node, ast.Call):
            name = _call_name(node)
            if name in IO_CALL_NAMES:
                start, end = _line_range(node)
                atlas_node = AtlasNode(
                    id=_make_id(file_path, "io_call", name, start, end),
                    file=file_path,
                    identifier=name,
                    kind="io_call",
                    start_line=start,
                    end_line=end,
                    tags=["io", "call"],
                )
                nodes.append(atlas_node)
                edges.append(AtlasEdge(source=parent_id, target=atlas_node.id, kind="uses"))

        for child in ast.iter_child_nodes(node):
            visit(child, current_parent)

    visit(tree, root_node.id)

    nodes.sort(key=lambda n: (n.file, n.start_line, n.end_line, n.kind, n.identifier, n.id))
    edges.sort(key=lambda e: (e.source, e.target, e.kind))
    return nodes, edges


def build_code_atlas(files: list[AtlasFile]) -> AtlasResponse:
    all_nodes: list[AtlasNode] = []
    all_edges: list[AtlasEdge] = []

    for file in sorted(files, key=lambda f: f.path):
        if file.path.endswith(".py"):
            nodes, edges = _parse_python_file(file.path, file.content)
            all_nodes.extend(nodes)
            all_edges.extend(edges)

    clusters: dict[str, list[str]] = defaultdict(list)
    for node in all_nodes:
        for tag in node.tags:
            clusters[tag].append(node.id)

    normalized_clusters = {
        key: sorted(value)
        for key, value in sorted(clusters.items(), key=lambda item: item[0])
    }

    return AtlasResponse(nodes=all_nodes, edges=all_edges, clusters=normalized_clusters)


@app.post("/api/code-atlas", response_model=AtlasResponse)
def code_atlas(payload: AtlasRequest) -> AtlasResponse:
    return build_code_atlas(payload.files)
