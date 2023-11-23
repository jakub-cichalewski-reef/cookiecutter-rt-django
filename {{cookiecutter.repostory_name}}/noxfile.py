from __future__ import annotations

import functools
import os
import subprocess
import tempfile
from pathlib import Path

import nox

CI = os.environ.get('CI') is not None

ROOT = Path('.')
PYTHON_VERSIONS = ['3.11']
PYTHON_DEFAULT_VERSION = PYTHON_VERSIONS[-1]
APP_ROOT = ROOT / 'app' / 'src'

nox.options.default_venv_backend = 'venv'
nox.options.stop_on_first_error = True
nox.options.reuse_existing_virtualenvs = True

# In CI, use Python interpreter provided by GitHub Actions
if CI:
    nox.options.force_venv_backend = 'none'


@functools.lru_cache
def _list_files() -> list[Path]:
    file_list = []
    for cmd in (
        ["git", "ls-files"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ):
        cmd_result = subprocess.run(cmd, check=True, text=True, capture_output=True)
        file_list.extend(cmd_result.stdout.splitlines())
    file_paths = [Path(p) for p in file_list]
    return file_paths


def list_files(suffix: str | None = None) -> list[Path]:
    """List all non-files not-ignored by git."""
    file_paths = _list_files()
    if suffix is not None:
        file_paths = [p for p in file_paths if p.suffix == suffix]
    return file_paths


def run_readable(session, mode="check"):
    session.run(
        'docker',
        'run',
        '--platform', 'linux/amd64',
        '--rm',
        '-v', f'{ROOT.absolute()}:/data',
        '-w', '/data',
        'ghcr.io/bobheadxi/readable:v0.5.0@sha256:423c133e7e9ca0ac20b0ab298bd5dbfa3df09b515b34cbfbbe8944310cc8d9c9',
        mode, '![.]**/*.md',
        external=True,
    )


def run_shellcheck(session, mode="check"):
    shellcheck_cmd = [
        "docker",
        "run",
        "--platform",
        "linux/amd64",  # while this image is multi-arch, we cannot use digest with multi-arch images
        "--rm",
        "-v",
        f"{ROOT.absolute()}:/mnt",
        "-w",
        "/mnt",
        "-q",
        "koalaman/shellcheck:0.9.0@sha256:a527e2077f11f28c1c1ad1dc784b5bc966baeb3e34ef304a0ffa72699b01ad9c",
    ]

    shellcheck_cmd.extend(list_files(suffix=".sh"))

    if mode == "fmt":
        with tempfile.NamedTemporaryFile(mode="w+") as diff_file:
            session.run(
                *shellcheck_cmd,
                "--format=diff",
                external=True,
                stdout=diff_file,
                success_codes=[0, 1],
            )
            diff_file.seek(0)
            diff = diff_file.read()
            if len(diff.splitlines()) > 1:  # ignore single-line message
                session.log("Applying shellcheck patch:\n%s", diff)
                subprocess.run(
                    ["patch", "-p1"],
                    input=diff,
                    text=True,
                    check=True,
                )

    session.run(*shellcheck_cmd, external=True)


@nox.session(name='format', python=PYTHON_DEFAULT_VERSION)
def format_(session):
    """Lint the code and apply fixes in-place whenever possible."""
    session.run('pip', 'install', '-e', '.[format]')
    session.run('ruff', 'check', '--fix', '.')
    run_shellcheck(session, mode="fmt")
    run_readable(session, mode="fmt")


@nox.session(python=PYTHON_DEFAULT_VERSION)
def lint(session):
    """Run linters in readonly mode."""
    session.run('pip', 'install', '-e', '.[lint]')
    session.run('ruff', 'check', '--diff', '.')
{%- if cookiecutter.ci_use_spellchecker == "y" %}
    session.run('codespell', '.')
{%- endif %}
    run_shellcheck(session, mode="check")
    run_readable(session, mode="check")


@nox.session(python=PYTHON_DEFAULT_VERSION)
def type_check(session):
    session.run('pip', 'install', '-e', '.[type_check]')
    with session.chdir(str(APP_ROOT)):
        session.run(
            'mypy',
            '--config-file', 'mypy.ini',
            '.',
            *session.posargs
        )


@nox.session(python=PYTHON_DEFAULT_VERSION)
def security_check(session):
    session.run('pip', 'install', 'bandit')
    with session.chdir(str(APP_ROOT)):
        session.run(
            'bandit',
            '--ini', 'bandit.ini',
            '-x', 'requirements_freeze.py',
            '-r',
            '.',
            *session.posargs
        )


@nox.session(python=PYTHON_VERSIONS)
def test(session):
    with session.chdir(str(APP_ROOT)):
        session.run(
            'pip', 'install', '-r', 'requirements.txt',
            'pytest',
            'pytest-django',
            'pytest-xdist',
            'ipdb',
            'freezegun',
        )
        session.run(
            'pytest',
            '-W', 'ignore::DeprecationWarning', '-s', '-x', '-vv',
            '-n', 'auto',
            '{{cookiecutter.django_project_name}}',
            *session.posargs,
        )
