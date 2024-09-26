import logging
import os
from pathlib import Path
from typing import Dict, List

import jinja2

from doctions.models.core import Model, validator
from doctions.models.actions import Action, WorkflowSpec
from doctions.releng.release import Release
from doctions.releng.project import Project
from doctions.render import markdown


_logger = logging.getLogger(__name__)


class Summary(Action, action_name="summary"):
    content: str = None
    release: Release = None
    format: str = "markdown"

    @property
    def project(self) -> Project:
        return self.release.project

    @property
    def input_text_to_use(self):
        choices = {
            'action argument': (self, "content"),
            'release': (self.release, "summary"),
            'project': (self.project, "summary"),
        }
        for whence, (obj, attrname) in choices.items():
            text = getattr(obj, attrname, None)
            if text:
                _logger.info(f'Using release notes from {whence}')
                return text
        raise ValueError(
            f'None of the following choices contained valid text: {choices}'
        )

    @property
    def jinja_template(self):
        return jinja2.Template(self.input_text_to_use)

    @property
    def release_data(self):
        return self.release.dict()

    @property
    def text(self):
        # print(self.release_data)
        return self.jinja_template.render(**self.release_data)

    def __str__(self):
        return str(self.notes_text)


@markdown.Document.add.register
def for_summary(doc, action: Summary):
    action.release = doc.data.release
    text = action.text
    fmt = action.format
    doc.add(f"Summary text (in `{fmt}`):")
    with doc.context(markdown.Codeblock(lang=fmt)):
        doc.add(text)
    if fmt == "markdown":
        doc.add("---")
        doc.add(text)
        doc.add("---")


class CreateGithubRelease(Action, action_name="github-release"):
    release: Release = None
    notes: str = None
    write_file: bool = False

    @property
    def project(self) -> Project:
        return self.release.project

    @property
    def input_text_to_use(self):
        choices = {
            'action argument': self.notes,
            'release data': self.release.notes,
            'project template': self.project.release_notes,
        }
        for whence, text in choices.items():
            if text:
                _logger.info(f'Using release notes from {whence}')
                return text
        raise ValueError(
            f'None of the following choices contained valid text: {choices}'
        )

    @property
    def jinja_template(self):
        return jinja2.Template(self.input_text_to_use)

    @property
    def release_data(self):
        return self.release.dict()

    @property
    def notes_text(self):
        # print(self.release_data)
        return self.jinja_template.render(**self.release_data)

    def __str__(self):
        return str(self.notes_text)

    @property
    def notes_file_name(self):
        return f'release-notes-{self.release.tag}.md'

    @property
    def repo_full_name(self):
        return self.release.project.github.full_name

    @property
    def command(self):
        rel = self.release
        q = lambda s: f'"{s}"'
        args = [
            'gh', 'release', 'create', q(rel.tag),
            '--repo', q(self.repo_full_name),
            '--target', q(rel.branch_name),
            '--title', q(rel.notes_title),
            '--notes-file', q(self.notes_file_name),
        ]
        if rel.is_candidate:
            args.append('--prerelease')
        args.append('--draft')

        return str.join(' ', [str(a) for a in args])


class Contexts(Model):
    project: Project
    release: Release = None
    releases: Dict[str, Release] = None

    @validator('releases')
    def set_project(cls, releases, values):
        for key, rel in releases.items():
            rel.tag = str(key)
            rel.project = values['project']
        return releases


def _get_shell_command_to_write_text_to_file(text: str, dest: os.PathLike) -> str:
    return f"""cat <<'EOF' > {dest}\n{text}\nEOF"""


@markdown.Document.add.register
def for_release(doc, action: CreateGithubRelease):
    action.release = doc.data.release
    # print(f'action.release_data={action.release_data}')
    md_content = str(action.notes_text)
    doc.add(f'Copy and paste the following release notes into a file named `{action.notes_file_name}`:')
    with doc.context(markdown.Codeblock(lang='markdown')):
        doc.add(md_content)
    doc.add(f'Or, run the following shell command to create the file in the local directory:')
    with doc.context(markdown.Codeblock(lang="sh")):
        cmd = _get_shell_command_to_write_text_to_file(md_content, action.notes_file_name)
        doc.add(cmd)
    doc.add('Run this command to create a draft release using the `gh` CLI tool')
    with doc.context(markdown.Codeblock(lang="sh")):
        doc.add(action.command)
    if action.write_file:
        doc.outputs[action.notes_file_name] = md_content
        # path = Path(action.notes_file_name).resolve()
        # path.write_text(rendered)
        # _logger.info(f'GitHub release notes written to file {path}')


def main():
    base_path = Path.home() / 'lbl' / 'mkrelease' / 'tools' / 'ccsi'
    ctx = Contexts.from_yaml(base_path / 'contexts.yml')
    spec = WorkflowSpec(path=base_path / 'workflow.yml', contexts_data=dict(ctx))
    wf = spec.workflow
    


if __name__ == '__main__':
    main()
