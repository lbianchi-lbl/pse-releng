import enum
import logging
from pathlib import Path
import signal
import subprocess
from typing import Optional, List

import oyaml as yaml
import typer

from doctions.models.actions import WorkflowSpec
from doctions.releng.actions import Contexts
from doctions.render import markdown
# from doctions.render import notebook

app = typer.Typer()


_logger = logging.getLogger(__name__)


class Renderer(str, enum.Enum):
    ipynb = "ipynb"
    md = "md"

    def create(self, *args, **kwargs):
        return {
            # self.ipynb: notebook.Notebook,
            self.md: markdown.Document,
        }[self](*args, **kwargs)


def get_release(ctx: Contexts, tag: Optional[str] = None):
    if tag:
        return ctx.releases[tag]
    by_version_asc = sorted(ctx.releases.values(), key=lambda r: r._ver)
    latest = by_version_asc[-1]
    return latest


@app.command()
def run(
        workflow: Path,
        tag: Optional[str] = None,
        contexts: Optional[Path] = None,
        output_path: Optional[Path] = None,
        renderer: Optional[List[Renderer]] = [Renderer.md],
        env: Optional[List[str]] = None,
        overwrite: Optional[bool] = False,
    ):
    logging.basicConfig(level=logging.INFO)

    wf_path = Path(workflow).resolve()
    ctx_path = Path(contexts or wf_path.parent / 'contexts.yml')
    output_path = Path(output_path or ctx_path.with_suffix('')).resolve()

    ctx = Contexts.from_yaml(ctx_path)
    ctx.release = ctx.release or get_release(ctx, tag)

    spec = WorkflowSpec(path=wf_path)
    workflow = spec.dispatch(**dict(ctx))

    for r_spec in renderer:
        renderer = r_spec.create(data=ctx, env=env)
        renderer.add(workflow)
        renderer.save_outputs(output_path, overwrite=overwrite)


def run_to_update(
        runspec: Path,
        sep: str = "*" * 20,
    ):
    runspec = yaml.safe_load(runspec.read_text())
    for to_update in runspec["update"]:
        _logger.info(sep + f" Running {to_update}")
        run(**to_update)


@app.command()
def watch(
        to_monitor: Path,
        runspec: Path,
        mkdocs_dir: Optional[Path] = None,
    ):
    import watchgod
    _logger.info(f"Monitoring for changes in {to_monitor}")
    if mkdocs_dir:
        args = [
            "mkdocs", "serve",
            "--dev-addr", "localhost:9999",
        ]
        popen = subprocess.Popen(
            args,
            cwd=mkdocs_dir.resolve(),
        )
    try:
        watchgod.run_process(
            to_monitor,
            run_to_update,
            args=(runspec,),
            watcher_cls=watchgod.DefaultWatcher,
        )
    except KeyboardInterrupt:
        _logger.info("CTRL+C received, exiting...")
    finally:
        popen.send_signal(signal.SIGQUIT)
        popen.wait(timeout=2)
        return


if __name__ == '__main__':
    app([
        "examples/workflows/release.yml",
        "--contexts", "examples/data/proteuslib.yml",
        "--output-path", "~/lbl/reltech/docs/docs/releases/proteuslib",
        "--overwrite",
    ])
