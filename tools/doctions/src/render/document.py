from contextlib import contextmanager
import enum
import logging
from pathlib import Path
from typing import Iterable, Union


_logger = logging.getLogger(__name__)


class Directive(enum.IntEnum):
    indent = 1
    empty_line = 0
    dedent = -indent


class Element:
    def __iter__(self) -> Iterable[Union[str, Directive]]:
        yield from []


class Context:
    
    def before(self):
        yield from []
    
    def after(self):
        yield from []


class Root(Context):
    pass


class Document:
    def __init__(self, data=None, **kwargs):
        self._lines = []
        self._context_stack = [Root()]
        self.data = data
        self.outputs = {}

    def append(self, line):
        self._lines.append(line)

    def extend(self, lines):
        self._lines.extend(lines)

    @property
    def current_context(self):
        return self._context_stack[-1]

    @contextmanager
    def context(self, ctx: Context):
        self.extend(ctx.before())
        # self.enter(elem, self.current_context)
        _logger.debug(f'switching from {self.current_context!r} to {ctx!r}')
        self._context_stack.append(ctx)

        yield self.current_context

        self._context_stack.pop(-1)
        _logger.debug(f'switching back to {self.current_context!r}')
        self.extend(ctx.after())

    @property
    def indented_lines(self):
        indent_char = '  '
        indent = 0
        previous = None

        for item in self._lines:
            if item in {Directive.indent, Directive.dedent}:
                indent += int(item); continue

            if item is Directive.empty_line:
                if previous is Directive.empty_line:
                    previous = item; continue
                indented = ''
            else:
                line = item
                indented = indent * indent_char + line

            previous = item
            yield indented.rstrip(' ')

    def __iter__(self):
        yield from self.indented_lines

    def __str__(self):
        return str.join('\n', self)

    def save_outputs(self, base_path: Path, overwrite=False):
        _logger.info(f'Saving {len(self.outputs)} items to {base_path}')
        base_path.mkdir(parents=True, exist_ok=True)
        for file_name, content in self.outputs.items():
            n_lines = content.count('\n')
            file_path = base_path / file_name
            if file_path.exists() and not overwrite:
                _logger.warning(f'path {file_path} exists, skipping')
            else:
                _logger.info(f'Saving {n_lines} lines to {file_path}')
                file_path.write_text(content)
