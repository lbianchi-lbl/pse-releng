import calendar
from typing import Optional, List, Dict

from urlpath import URL

from doctions.models.core import Model, dataclass


class Service(Model):
    base_url: URL = URL('https://example.com')
    class Config:
        arbitrary_types_allowed = True


class GitHub(Service):
    org: str
    name: str
    base_url: URL = URL('https://github.com')
    default_branch: str = "main"

    @property
    def full_name(self):
        return f'{self.org}/{self.name}'

    @property
    def url(self):
        return self.base_url / self.org / self.name

    @property
    def branches_url(self):
        return self.url / 'branches'

    @property
    def ssh_target(self):
        return f'git@github.com:{self.full_name}.git'

    @property
    def releases_url(self):
        return self.url / 'releases'

    @property
    def compare_url(self):
        return self.url / 'compare'


class ReadTheDocs(Service):
    slug: str
    project_name: str
    base_url: URL = URL('https://www.readthedocs.org')

    @property
    def project_url(self):
        return self.base_url / 'projects' / self.slug

    @property
    def builds_url(self):
        return self.project_url / 'builds'

    @property
    def versions_url(self):
        return self.project_url / 'versions'

    @property
    def version_url(self):
        return self.base_url / 'dashboard' / self.slug / 'version'

    @property
    def url(self):
        return URL(f'https://{self.slug}.readthedocs.org')


@dataclass
class PythonDistribution:
    name: str = ""
    default_python_version: str = ""
    test_commands: List[str] = None
    pypi_user: str = "__token__"

    @property
    def smoke_test_command(self):
        if self.test_commands:
            return self.test_commands[0]


class ReleaseCycle(Model):
    year: int
    month: int
    series: str = None

    @property
    def month_name(self):
        return calendar.month_name[self.month]

    @property
    def month_abbr(self):
        return calendar.month_abbr[self.month]

    def __str__(self):
        return f'{self.year} {self.month_abbr}'


class Releasing(Model):
    cycles: Dict[str, ReleaseCycle] = None
    notes_template: str = None


class Project(Model):
    id: str
    name: str = None
    github: GitHub = None
    readthedocs: ReadTheDocs = None
    python: PythonDistribution = None
    releasing: Releasing = None
    extra: Dict = None

    @property
    def git_clone_target_https(self):
        return self.github.url

    @property
    def git_clone_target_ssh(self):
        return self.github.ssh_target

    @property
    def git_push_remote(self):
        return self.github.ssh_target

    @property
    def git_clone_default_dir_name(self):
        return self.github.url.stem

    @property
    def git_clone_target(self):
        return self.git_clone_target_ssh

    @property
    def git_clone_command(self):
        return f'git clone {self.git_clone_target} && cd {self.git_clone_default_dir_name}'

    @property
    def release_notes(self) -> str:
        return self.releasing.notes_template