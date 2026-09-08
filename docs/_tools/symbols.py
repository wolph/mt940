"""Collect owned Python definitions for the documentation inventory."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class Symbol:
    """An owned definition and the canonical anchor documenting it."""

    name: str
    anchor: str
    kind: str
    documented: bool


def collect(package: Path) -> dict[str, Symbol]:
    """Collect owned definitions, excluding repeated overload declarations.

    Returns:
        Definitions keyed by their qualified names, including relative aliases.
    """
    symbols: dict[str, Symbol] = {}
    aliases: dict[str, str] = {}
    for path in sorted(package.rglob('*.py')):
        parts: list[str] = list(
            path.relative_to(package.parent).with_suffix('').parts
        )
        if parts[-1] == '__init__':
            _ = parts.pop()
        module: str = '.'.join(parts)
        source: str = path.read_text(encoding='utf-8')
        tree: ast.Module = ast.parse(source)
        symbols[module] = Symbol(
            module, module, 'module', bool(ast.get_docstring(tree))
        )
        _collect_body(tree.body, module, source, symbols)
        parent: str = (
            module if path.stem == '__init__' else module.rsplit('.', 1)[0]
        )
        aliases.update(_relative_imports(tree, module, parent))
    for name, imported in aliases.items():
        target: str = imported
        visited: set[str] = {name}
        while target in aliases and target not in visited:
            visited.add(target)
            target = aliases[target]
        if name not in symbols and target in symbols:
            original: Symbol = symbols[target]
            symbols[name] = Symbol(
                name, original.anchor, 'alias', original.documented
            )
    return symbols


def _relative_imports(
    tree: ast.Module, module: str, parent: str
) -> dict[str, str]:
    """Identify package-local aliases without importing the package.

    Returns:
        Qualified import names mapped to their defining names.
    """
    aliases: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or not node.level:
            continue
        parts: list[str] = parent.split('.')
        prefix: str = '.'.join(parts[: len(parts) - node.level + 1])
        origin: str = f'{prefix}.{node.module}' if node.module else prefix
        for imported in node.names:
            aliases[f'{module}.{imported.asname or imported.name}'] = (
                f'{origin}.{imported.name}'
            )
    return aliases


def _is_overload(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Recognise both imported and qualified overload decorators.

    Returns:
        Whether the declaration is an overload stub.
    """
    return any(
        (isinstance(item, ast.Name) and item.id == 'overload')
        or (isinstance(item, ast.Attribute) and item.attr == 'overload')
        for item in node.decorator_list
    )


def _commented(node: ast.AST, source: str) -> bool:
    """Recognise Sphinx attribute comments immediately above a definition.

    Returns:
        Whether the preceding comment block contains an attribute description.
    """
    lines: list[str] = source.splitlines()
    number: int = getattr(node, 'lineno', 1) - 2
    while number >= 0 and lines[number].lstrip().startswith('#'):
        if lines[number].lstrip().startswith('#:'):
            return True
        number -= 1
    return False


def _assignment_names(
    node: ast.Assign | ast.AnnAssign, *, instance_only: bool = False
) -> list[str]:
    """Get names and instance attributes, including unpacked assignments.

    Returns:
        Names declared by the assignment, excluding indexed assignments.
    """
    targets: list[ast.expr] = (
        list(node.targets) if isinstance(node, ast.Assign) else [node.target]
    )
    names: list[str] = []
    while targets:
        target: ast.expr = targets.pop()
        if isinstance(target, ast.Name) and not instance_only:
            names.append(target.id)
        elif (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == 'self'
        ):
            names.append(target.attr)
        elif isinstance(target, (ast.Tuple, ast.List)):
            targets.extend(target.elts)
        elif isinstance(target, ast.Starred):
            targets.append(target.value)
    return names


def _collect_attributes(
    body: list[ast.stmt], scope: str, source: str, symbols: dict[str, Symbol]
) -> None:
    """Record module/class attributes, with their owning scope as fallback."""
    context: str = '\n'.join(
        node.value.value
        for node in body
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )
    for index, node in enumerate(body):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        following: ast.stmt | None = (
            body[index + 1] if index + 1 < len(body) else None
        )
        literal: bool = (
            isinstance(following, ast.Expr)
            and isinstance(following.value, ast.Constant)
            and isinstance(following.value.value, str)
        )
        for name in _assignment_names(node):
            full: str = f'{scope}.{name}'
            previous: Symbol | None = symbols.get(full)
            documented: bool = (
                _commented(node, source)
                or literal
                or bool(re.search(rf'\b{re.escape(name)}\b', context))
                or bool(previous and previous.documented)
            )
            owner: Symbol = symbols[scope]
            anchor: str = full if owner.kind == 'module' else scope
            symbols[full] = Symbol(full, anchor, 'attribute', documented)


def _collect_body(
    body: list[ast.stmt],
    scope: str,
    source: str,
    symbols: dict[str, Symbol],
    enclosing_function: str = '',
) -> None:
    """Walk owned definitions, mapping closures to the enclosing callable."""
    if not enclosing_function:
        _collect_attributes(body, scope, source, symbols)
    for node in body:
        if not isinstance(
            node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            for child in ast.iter_child_nodes(node):
                if isinstance(
                    child, (ast.stmt, ast.ExceptHandler, ast.match_case)
                ):
                    children: list[ast.stmt] = (
                        [child]
                        if isinstance(child, ast.stmt)
                        else list(child.body)
                    )
                    _collect_body(
                        children, scope, source, symbols, enclosing_function
                    )
            continue
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef)
        ) and _is_overload(node):
            continue
        name: str = f'{scope}.{node.name}'
        kind: str = 'class' if isinstance(node, ast.ClassDef) else 'function'
        anchor: str = enclosing_function or name
        symbols[name] = Symbol(
            name, anchor, kind, bool(ast.get_docstring(node))
        )
        nested_anchor: str = '' if isinstance(node, ast.ClassDef) else anchor
        _collect_body(node.body, name, source, symbols, nested_anchor)
        if isinstance(node, ast.ClassDef):
            _collect_instance_attributes(node, name, source, symbols)


def _collect_instance_attributes(
    node: ast.ClassDef, scope: str, source: str, symbols: dict[str, Symbol]
) -> None:
    """Record self attributes and their class or constructor descriptions."""
    context: str = '\n'.join(
        ast.get_docstring(item) or ''
        for item in [node, *node.body]
        if isinstance(
            item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        )
    )
    methods: list[ast.FunctionDef | ast.AsyncFunctionDef] = [
        item
        for item in node.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    for item in (child for method in methods for child in ast.walk(method)):
        if not isinstance(item, (ast.Assign, ast.AnnAssign)):
            continue
        for name in _assignment_names(item, instance_only=True):
            full: str = f'{scope}.{name}'
            previous: Symbol | None = symbols.get(full)
            documented: bool = (
                _commented(item, source)
                or bool(re.search(rf'\b{re.escape(name)}\b', context))
                or bool(previous and previous.documented)
            )
            symbols[full] = Symbol(full, scope, 'attribute', documented)
