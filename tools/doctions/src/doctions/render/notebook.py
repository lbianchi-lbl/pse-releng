from contextlib import contextmanager
from functools import singledispatchmethod
import nbformat as nbf
import os

from ..models.actions import Workflow, Job, Step, RunShell, Checklist, Note
from . import document, markdown as md 



class Notebook(document.Document):
    def __init__(self, data=None, env=None):
        self._nb = nbf.v4.new_notebook()
        self.data = data
        self.outputs = {}

        if env:
            self.create_env_cell(env)

    def create_env_cell(self, env_spec: list):
        pairs = []
        for key_or_pair in env_spec:
            if key_or_pair in os.environ:
                key = key_or_pair
                val = os.environ[key]
                pairs.append(f'{key}="{val}"')
            else:
                pairs.append(key_or_pair)

        self.add(
            RunShell(
                body=str.join('\n', 
                [f'export {pair}' for pair in pairs])
            )
        )

    def __str__(self):
        return nbf.writes(self._nb)

    @property
    def metadata(self):
        return self._nb["metadata"]

    def append(self, cell):
        self._nb["cells"].append(cell)

    def extend(self, cells):
        self._nb["cells"].extend(cells)

    @singledispatchmethod
    def add(self, obj):
        doc = md.Document(data=self.data)
        doc.add(obj)
        self.add(doc)

    @add.register
    def for_markdown(self, doc: md.Document):
        self.append(
            nbf.v4.new_markdown_cell(str(doc))
        )

    @add.register
    def for_code(self, code: RunShell):
        self.append(
            nbf.v4.new_code_cell(code.body.strip())
        )

    @contextmanager
    def cell(self):
        doc = md.Document()
        yield doc
        self.add(doc)


@Notebook.add.register
def workflow(nb, workflow: Workflow):
    title = workflow.name or "Workflow"
    nb.add(md.Heading(1, title))
    for job_key, job in workflow.jobs.items():
        nb.add(job, key=job_key)
    nb.outputs['workflow.ipynb'] = str(nb)


@Notebook.add.register
def job(nb, job: Job, key=""):
    title = job.name or key.capitalize()
    nb.add(md.Heading(2, title))
    for step_idx, step in enumerate(job.steps):
        nb.add(step, step_idx)


@Notebook.add.register
def step(nb, step: Step, step_idx=0):
    step_num = step_idx + 1
    title = step.name or f'Step {step_num}'
    title = f'**{step_num}: {title}**'
    should_run = step.should_run
    if not should_run:
        title = f'~~{title}~~(should_run: False)'
    nb.add(md.Heading(4, title))
    if should_run:
        nb.add(step.action)
        if step.note:
            nb.add(step.note)


@Notebook.add.register
def note(nb, note: Note):
    nb.add(
        md.Quoteblock(
            str(note),
            prefix=f'NOTE'
        )
    )
