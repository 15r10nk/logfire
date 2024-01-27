from __future__ import annotations

import ast
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar, cast

import logfire

if TYPE_CHECKING:
    from logfire._main import Logfire


def exec_source(source: str, filename: str, module_name: str, globs: dict[str, Any], logfire: Logfire) -> None:
    """Execute a modified AST of the module's source code in the module's namespace.

    The modified AST wraps the body of every function definition in `with logfire.span(...):`.
    `logfire.span` is added to the module's namespace as `logfire_<uuid>`.
    The argument to `logfire.span` contains `module_name` and the qualified name of the current function.
    """
    logfire_name = f'logfire_{uuid.uuid4().hex}'
    globs[logfire_name] = logfire._fast_span  # type: ignore
    tree = rewrite_ast(source, filename, logfire_name, module_name, logfire)
    assert isinstance(tree, ast.Module)  # for type checking
    # dont_inherit=True is necessary to prevent the module from inheriting the __future__ import from this module.
    code = compile(tree, filename, 'exec', dont_inherit=True)
    exec(code, globs, globs)


def rewrite_ast(source: str, filename: str, logfire_name: str, module_name: str, logfire: Logfire) -> ast.AST:
    tree = ast.parse(source)
    transformer = Transformer(logfire_name, filename, module_name, logfire)
    return transformer.visit(tree)


@dataclass
class Transformer(ast.NodeTransformer):
    logfire_span_name: str
    filename: str
    module_name: str
    logfire: Logfire

    def __post_init__(self):
        # Names of functions and classes that we're currently inside,
        # so we can construct the qualified name of the current function.
        self.qualname_stack: list[str] = []

    def check_no_auto_trace(self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> bool:
        """Return true if the node has a `@no_auto_trace` or `@logfire.no_auto_trace` decorator."""
        return any(
            (
                isinstance(node, ast.Name)
                and node.id == no_auto_trace.__name__
                or (
                    isinstance(node, ast.Attribute)
                    and node.attr == no_auto_trace.__name__
                    and isinstance(node.value, ast.Name)
                    and node.value.id == logfire.__name__
                )
            )
            for node in node.decorator_list
        )

    def visit_ClassDef(self, node: ast.ClassDef):
        if self.check_no_auto_trace(node):
            return node

        self.qualname_stack.append(node.name)
        # We need to call generic_visit here to modify any functions defined inside the class.
        node = cast(ast.ClassDef, self.generic_visit(node))
        self.qualname_stack.pop()
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef):
        if self.check_no_auto_trace(node):
            return node

        self.qualname_stack.append(node.name)
        qualname = '.'.join(self.qualname_stack)
        self.qualname_stack.append('<locals>')
        # We need to call generic_visit here to modify any classes/functions nested inside.
        self.generic_visit(node)
        self.qualname_stack.pop()  # <locals>
        self.qualname_stack.pop()  # node.name

        msg, attributes = self.logfire._fast_span_attributes(  # type: ignore
            self.filename, self.module_name, qualname, node.lineno
        )
        attributes_stmt = ast.parse(repr(attributes)).body[0]
        assert isinstance(attributes_stmt, ast.Expr)
        attributes_node = attributes_stmt.value
        # Replace the body of the function with:
        #     with <logfire_span_name>('Calling ...'):
        #         <original body>
        span = ast.With(
            items=[
                ast.withitem(
                    context_expr=ast.Call(
                        func=ast.Name(id=self.logfire_span_name, ctx=ast.Load()),
                        args=[ast.Constant(value=msg), attributes_node],
                        keywords=[],
                    ),
                )
            ],
            body=node.body,
            type_comment=node.type_comment,
        )
        return ast.fix_missing_locations(
            ast.copy_location(
                type(node)(
                    name=node.name,
                    args=node.args,
                    body=[span],
                    decorator_list=node.decorator_list,
                    returns=node.returns,
                    type_comment=node.type_comment,
                ),
                node,
            )
        )

    visit_AsyncFunctionDef = visit_FunctionDef


T = TypeVar('T')


def no_auto_trace(x: T) -> T:
    """Decorator to prevent a function/class from being traced by `logfire.install_auto_tracing`.

    This is useful for small functions that are called very frequently and would generate too much noise.

    The decorator is detected at import time.
    Only `@no_auto_trace` or `@logfire.no_auto_trace` are supported.
    Renaming/aliasing either the function or module won't work.
    Neither will calling this indirectly via another function.

    Any decorated function, or any function defined anywhere inside a decorated function/class,
    will be completely ignored by `logfire.install_auto_tracing`.

    This decorator simply returns the argument unchanged, so there is zero runtime overhead.
    """
    return x
