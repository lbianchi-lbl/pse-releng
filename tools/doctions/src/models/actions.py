import logging
from pathlib import Path
from pprint import pprint
from typing import Any, Union, List, Dict, Iterable

import jinja2
import oyaml as yaml

from .core import Model, dataclass, validator


_logger = logging.getLogger(__name__)


REGISTERED_ACTIONS = {}


class Action(Model):

    def __init_subclass__(cls, action_name=None, **kwargs):
        super().__init_subclass__(**kwargs)
        REGISTERED_ACTIONS[action_name or cls.__name__] = cls
    

class RunShell(Action):
    body: str

    def __str__(self):
        return str(self.body)

    def __iter__(self):
        yield from self.body.splitlines()


class Checklist(Action, action_name="checklist"):
    @dataclass
    class Item:
        content: str

        def __str__(self):
            return str(self.content)

    items: List[str] = None

    def __iter__(self):
        for item in self.items:
            yield self.Item(item)


class Note(Model):
    __root__: str

    def __str__(self):
        return str(self.__root__)


@dataclass
class Condition:
    input_spec: Union[str, bool] = None
    outcome: bool = None
    eval_result: Any = None

    def __post_init__(self):
        if self.input_spec in {True, False}:
            self.outcome = self.input_spec

    def __bool__(self):
        return self.outcome

    def evaluate(self, context: dict):
        _logger.debug(f'Evaluating "{self}" with context={context["release"].dict()}')
        self.eval_result = eval(str(self.input_spec), dict(context))
        self.outcome = bool(self.eval_result)
        return self.outcome

    def __str__(self):
        return f'{self.input_spec}: {self.outcome}'


class ComplicatedSkippable(Model):
    if_: str = None
    condition: Condition = None

    class Config:
        fields = {'if_': 'if'}
        
    def evaluate_condition(self, data) -> bool:
        if self.condition is None:
            self.condition = Condition(self.if_)
        self.condition.evaluate(data)
        return bool(self.condition)


class Skippable(Model):
    should_run: bool = True

    @validator('should_run', always=True, pre=True)
    def convert_to_bool(cls, val: Any):
        return bool(val)

    class Config:
        fields = {'should_run': 'if'}


class Step(Skippable):
    name: str = None
    uses: str = None
    action_opts: Dict[str, Any] = None
    run: str = None
    note: Note = None

    class Config:
        fields = {
            'action_opts': 'with',
            'note': 'x-note',
            'comment': 'x-comment',
        }

    @property
    def action(self):
        if self.uses is None:
            return RunShell(body=self.run)
        action_cls = REGISTERED_ACTIONS[self.uses]
        _logger.debug(f'self.action_opts={self.action_opts}')
        return action_cls(**self.action_opts)


class Job(Skippable):
    steps: List[Step]
    name: str = None


class Workflow(Model):
    name: str = None
    env: dict = None
    jobs: Dict[str, Job]


class Triggers(Model):
    anchor_path: Path = Path('.')
    update: List[Path] = None

    @validator('update', always=True)
    def resolve_paths(cls, paths: Iterable[Path], values):
        return [
            (values['anchor_path'] / p).resolve()
            for p in paths
        ]


# class WorkflowRun(Model):
#     workflow: Workflow
#     contexts


class WorkflowSpec(Model):
    path: Path = None

    @property
    def source(self) -> str:
        return self.path.read_text()

    @property
    def template(self) -> jinja2.Template:
        return jinja2.Template(
            self.source,
            variable_start_string=r'${{',
            variable_end_string=r'}}',
            block_start_string=r'${%',
            block_end_string=r'%}',
            finalize=str,
        )

    def load(self, text: str):
        data = yaml.safe_load(text)
        # Stupid YAML
        data['on'] = data.pop(True, {})
        return data

    @property
    def data(self):
        return self.load(self.source)

    @property
    def triggers(self):
        return Triggers(
            anchor_path=self.path.resolve(),
            **self.data.get('on', {})
        )

    def dispatch(self, **kwargs) -> Workflow:
        rendered = self.template.render(**kwargs)
        # pprint(rendered)
        wf_data = self.load(rendered)
        # pprint(wf_data)
        return Workflow(**wf_data)
