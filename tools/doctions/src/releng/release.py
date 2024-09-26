from typing import List, Dict, Union

import packaging.version as pkgver
from pydantic import Field

from doctions.models.core import Model, dataclass
from .project import Project, ReleaseCycle



class ReleaseHighlight(Model):
    __root__ = str

    def __str__(self):
        return str(__root__)


class Release(Model):
    tag: str = "X.Y.Z"
    next_dev_version_tag: str = ""
    project: Project = None
    notes: str = None
    highlights: List[Union[str, ReleaseHighlight]] = Field(default_factory=list)
    highlights_text: str = ""
    extra: Dict = None
    refs_to_cherrypick: List[str] = []
    release_branch: str = ""

    @property
    def _ver(self):
        return pkgver.Version(self.tag)

    @property
    def major(self):
        return self._ver.major

    @property
    def minor(self):
        return self._ver.minor

    @property
    def patch(self):
        return self._ver.micro

    @property
    def candidate(self) -> Union[int, None]:
        pre = self._ver.pre
        if pre:
            pfx, num = pre
            return num
        return None

    @property
    def series(self):
        return f'{self.major}.{self.minor}'

    @property
    def cycle(self) -> ReleaseCycle:
        return self.project.releasing.cycles.get(self.series)

    @property
    def is_first_in_cycle(self):
        return self.patch == 0 and self.candidate == 0

    @property
    def is_candidate(self):
        return self.candidate is not None

    @property
    def is_patch(self):
        return self.patch >= 1

    @property
    def is_final(self):
        return not self.is_candidate

    @property
    def version_qualifier(self):
        return "candidate" if self.is_candidate else "final"

    def __str__(self):
        return self.tag

    @property
    def branch_name(self):
        return self.release_branch or f'{self.major}.{self.minor}_rel'

    @property
    def clone_branch_command(self):
        url = self.project.github.url
        return f'git clone --depth 1 --branch "{self.branch_name}" {url} && cd {url.stem}'

    @property
    def clone_tag_command(self):
        url = self.project.github.url
        return f'git clone --depth 1 --branch "{self.tag}" {url} && cd {url.stem}'

    @property
    def notes_title(self):
        "Title used for release notes"
        s = []
        # if self.cycle:
        #     s += [str(self.cycle)]
        s += [str(self.series)]
        if self.is_patch:
            s += ["Patch"]
        s += ["Release"]
        if self.is_candidate:
            s += [f"Candidate #{self.candidate}"]
        return " ".join(s)

    @property
    def github_release_url(self):
        return self.project.github.releases_url / 'tag' / self.tag

    @property
    def github_release_edit_url(self):
        return self.project.github.releases_url / 'edit' / self.tag

    @property
    def github_compare_url(self):
        "URL to compare commits on the default branch relative to the current state of the release branch"
        gh = self.project.github
        return  gh.compare_url / f'{self.branch_name}...{gh.default_branch}'

    @property
    def github_archive_url(self):
        return self.project.github.url / 'archive' / f'{self.tag}.zip'

    @property
    def docs_url(self):
        return self.project.readthedocs.url / 'en' / self.tag

    @property
    def docs_builds_url(self):
        return self.project.readthedocs.builds_url

    @property
    def docs_version_url(self):
        # https://readthedocs.org/dashboard/MYPROJECT/version/3.10.0/edit/
        return self.project.readthedocs.version_url / self.tag / 'edit'

    @property
    def pypi_target(self):
        s = self.project.python.name
        return f'{s}=={self.tag}'

    @property
    def pypi_url(self):
        name = self.project.python.name
        return f"https://pypi.org/project/{name}/{self.tag}/"
