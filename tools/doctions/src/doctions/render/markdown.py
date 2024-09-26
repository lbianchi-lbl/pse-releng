from contextlib import contextmanager
from functools import singledispatch, singledispatchmethod
import logging
from pathlib import Path
from typing import Iterable, Union, Any

from plum import dispatch

from ..models.core import dataclass
from ..models.actions import Workflow, Job, Step, RunShell, Checklist, Note
from . import document


_logger = logging.getLogger(__name__)

D = document.Directive


@dataclass
class Codeblock(document.Context):
    lang: str = "text"

    def before(self):
        yield D.empty_line
        yield f'```{self.lang}'

    def after(self):
        yield '```'
        yield D.empty_line


@dataclass
class Quoteblock(document.Element):
    content: str
    prefix: str = ''

    def __iter__(self):
        lines = self.content.splitlines()
        first_line = lines.pop(0)

        yield D.empty_line
        pfx = f'**{self.prefix}** ' if self.prefix else ''
        yield f'> {pfx} {first_line}'
        for line in lines:
            yield f'> {line}'
        yield D.empty_line


@dataclass
class BulletList(document.Context):
    parent: Any = None

    @property
    def is_sublist(self):
        return isinstance(self.parent, type(self))

    def before(self):
        yield D.indent if self.is_sublist else D.empty_line

    def after(self):
        yield D.dedent if self.is_sublist else D.empty_line


@dataclass
class Bullet(document.Context):
    text: str = ""
    marker: str = '-'

    def __iter__(self):
        yield f'{self.marker} {self.text}'

    @classmethod
    def with_checkbox(cls, text, checked=None):
        checkbox = '[ ]' if not checked else '[x]'
        return cls(
            text,
            marker=f'- {checkbox}'
        )


class BulletContext(document.Context):

    def before(self):
        yield D.indent

    def after(self):
        yield D.dedent


@dataclass
class Heading(document.Element):
    level: int
    text: str

    @property
    def prefix(self):
        return '#' * int(self.level)

    def __iter__(self):
        yield f'{self.prefix} {self.text}'
        yield D.empty_line


@dataclass
class Inline(document.Element):
    body: str

    def __iter__(self):
        # yield Directive.empty_line
        yield from self.body.splitlines()


@dataclass
class Paragraph(document.Element):
    body: str

    def __iter__(self):
        yield D.empty_line
        yield from self.body.splitlines()
        yield D.empty_line


class Document(document.Document):

    @contextmanager
    def bullet_list(self, factory=BulletList):
        bl = factory(parent=self.current_context)
        with self.context(bl) as ctx:
            yield ctx

    @singledispatchmethod
    def add(self, elem: document.Element):
        self.extend(elem)

    @add.register
    def for_directive(self, directive: document.Directive):
        self.append(directive)


@Document.add.register
def for_text(doc, text: str):
    doc.add(Inline(text))


@Document.add.register
def for_workflow(doc, workflow: Workflow):
    title = workflow.name or "Workflow"
    doc.add(Heading(1, title))
    for job_key, job in workflow.jobs.items():
        doc.add(job, key=job_key)
    doc.outputs['workflow.md'] = str(doc)


@Document.add.register
def for_job(doc, job: Job, key=""):
    title = job.name or key.capitalize()
    if not job.should_run:
        title = f'~~{title}~~ (N/A)'
    doc.add(Heading(2, title))
    if job.should_run:
        with doc.bullet_list():
            for step_idx, step in enumerate(job.steps):
                doc.add(step, step_idx)


@Document.add.register
def for_step(doc, step: Step, step_idx: int = None):
    step_num = step_idx + 1
    title = step.name or f'Step {step_num}'
    title = f'**{step_num}: {title}**'
    if not step.should_run:
        title = f'~~{title}~~ (N/A)'

    bullet = Bullet.with_checkbox(title, checked=not step.should_run)
    doc.add(bullet)

    if step.should_run:
        with doc.context(BulletContext()):
            doc.add(step.action)
            if note := step.note:
                _logger.debug(f'type(note)={type(note)}')
                doc.add(note)


@Document.add.register
def for_note(doc, note: Note):
    noteblock = Quoteblock(
        str(note),
        prefix='NOTE'
    )
    doc.add(noteblock)


@Document.add.register
def for_shell(doc, action: RunShell):
    with doc.context(Codeblock(lang='sh')):
        doc.add(action.body)


@Document.add.register
def for_checklist(doc, action: Checklist):
    for item in action:
        doc.add(item)


@Document.add.register
def for_checklist_item(doc, item: Checklist.Item):
    lines = str(item).splitlines()
    first_line = lines.pop(0)
    doc.add(Bullet.with_checkbox(first_line))
    if lines:
        doc.add(D.empty_line)
    with doc.context(BulletContext()):
        for line in lines:
            doc.add(line or Directive.empty_line)
