import re
from textwrap import dedent

import pytest

from sync_pre_commit_lock.pre_commit_config import PreCommitHook, PreCommitRepo
from sync_pre_commit_lock.shell import ShellPrinter, Verbosity, use_color


@pytest.fixture(params=[True, False])
def is_tty(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> bool:
    value = request.param
    monkeypatch.setattr("sys.stdout.isatty", lambda: value)
    return value


def test_enable_colors_on_tty(is_tty: bool) -> None:
    assert use_color() == is_tty


@pytest.mark.usefixtures("is_tty")
def test_force_color(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FORCE_COLOR", "1")
    assert use_color() is True


@pytest.mark.usefixtures("is_tty")
def test_no_color(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    assert use_color() is False


@pytest.mark.usefixtures("is_tty")
def test_no_color_precedance_over_force_color(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.setenv("NO_COLOR", "1")
    assert use_color() is False


RE_ANSI = re.compile(r"\x1b[^m]*m")


def normalize(txt: str) -> str:
    """
    Remove ANSI escapes and surrounding whitespaces.

    Make assertions works with colors, aka with `-s` option.
    """
    return RE_ANSI.sub("", txt).strip()


@pytest.mark.parametrize(
    "verbosity,with_prefix,expected_out,expected_err",
    [
        # QUIET verbosity - nothing show except errors
        pytest.param(Verbosity.QUIET, True, "", "[sync-pre-commit-lock] error", id="quiet-with-prefix"),
        pytest.param(Verbosity.QUIET, False, "", "error", id="quiet-without-prefix"),
        # NORMAL verbosity - shows info, success, warning, error (but not debug)
        pytest.param(
            Verbosity.NORMAL,
            True,
            """
            [sync-pre-commit-lock] info
            [sync-pre-commit-lock] multiline
            [sync-pre-commit-lock] success
            [sync-pre-commit-lock] warning
            """,
            "[sync-pre-commit-lock] error",
            id="normal-with-prefix",
        ),
        pytest.param(Verbosity.NORMAL, False, "info\nmultiline\nsuccess\nwarning", "error", id="normal-without-prefix"),
        # # DEBUG verbosity - shows all levels
        pytest.param(
            Verbosity.DEBUG,
            True,
            """
            [sync-pre-commit-lock] debug
            [sync-pre-commit-lock] info
            [sync-pre-commit-lock] multiline
            [sync-pre-commit-lock] success
            [sync-pre-commit-lock] warning
            """,
            "[sync-pre-commit-lock] error",
            id="debug-with-prefix",
        ),
        pytest.param(
            Verbosity.DEBUG, False, "debug\ninfo\nmultiline\nsuccess\nwarning", "error", id="debug-without-prefix"
        ),
    ],
)
def test_shell_print_levels_and_verbosity(
    capsys: pytest.CaptureFixture[str],
    verbosity: Verbosity,
    with_prefix: bool,
    expected_out: str,
    expected_err: str,
) -> None:
    printer = ShellPrinter(with_prefix=with_prefix, verbosity=verbosity)

    printer.debug("debug")
    printer.info("info\nmultiline")
    printer.success("success")
    printer.warning("warning")
    printer.error("error")

    captured = capsys.readouterr()

    assert normalize(captured.out) == dedent(expected_out).strip()
    assert normalize(captured.err) == dedent(expected_err).strip()


def test_shell_printer_list_success(capsys: pytest.CaptureFixture[str]) -> None:
    printer = ShellPrinter()

    printer.list_updated_packages(
        {
            "package": (
                PreCommitRepo("https://repo1.local/test", "rev1", [PreCommitHook("hook")]),
                PreCommitRepo("https://repo1.local/test", "rev2", [PreCommitHook("hook")]),
            )
        }
    )
    captured = capsys.readouterr()

    expected = "[sync-pre-commit-lock] ✔ https://repo1.local/test \t rev1 -> rev2"
    assert normalize(captured.out) == expected


def test_shell_printer_list_success_additional_dependency(capsys: pytest.CaptureFixture[str]) -> None:
    printer = ShellPrinter()

    printer.list_updated_packages(
        {
            "package": (
                PreCommitRepo("https://repo1.local/test", "rev1", [PreCommitHook("hook", ["dep"])]),
                PreCommitRepo("https://repo1.local/test", "rev1", [PreCommitHook("hook", ["dep==0.1.2"])]),
            )
        }
    )
    captured = capsys.readouterr()

    expected = dedent("""
    [sync-pre-commit-lock] ✔ https://repo1.local/test
    [sync-pre-commit-lock]   └ hook
    [sync-pre-commit-lock]     └ dep \t * -> 0.1.2
    """).strip()

    assert normalize(captured.out) == expected


@pytest.mark.parametrize(
    "with_prefix,expected",
    [
        pytest.param(
            True,
            """
[sync-pre-commit-lock] ✔ https://repo1.local/test \t rev1 -> rev2
[sync-pre-commit-lock]   ├ 1st-hook
[sync-pre-commit-lock]   │ └ other \t 0.42 -> 3.4.5
[sync-pre-commit-lock]   └ 2nd-hook
[sync-pre-commit-lock]     ├ dep \t * -> 0.1.2
[sync-pre-commit-lock]     └ other \t >=0.42 -> 3.4.5
            """,
            id="with-prefix",
        ),
        pytest.param(
            False,
            """
✔ https://repo1.local/test \t rev1 -> rev2
  ├ 1st-hook
  │ └ other \t 0.42 -> 3.4.5
  └ 2nd-hook
    ├ dep \t * -> 0.1.2
    └ other \t >=0.42 -> 3.4.5
            """,
            id="without-prefix",
        ),
    ],
)
def test_shell_printer_list_success_repo_with_multiple_hooks_and_additional_dependency(
    capsys: pytest.CaptureFixture[str], with_prefix: bool, expected: str
) -> None:
    printer = ShellPrinter(with_prefix=with_prefix)

    printer.list_updated_packages(
        {
            "package": (
                PreCommitRepo(
                    repo="https://repo1.local/test",
                    rev="rev1",
                    hooks=[
                        PreCommitHook("1st-hook", ["dep==0.1.2", "other==0.42"]),
                        PreCommitHook("2nd-hook", ["dep", "other>=0.42"]),
                    ],
                ),
                PreCommitRepo(
                    repo="https://repo1.local/test",
                    rev="rev2",
                    hooks=[
                        PreCommitHook("1st-hook", ["dep==0.1.2", "other==3.4.5"]),
                        PreCommitHook("2st-hook", ["dep==0.1.2", "other==3.4.5"]),
                    ],
                ),
            )
        }
    )
    captured = capsys.readouterr()

    assert normalize(captured.out) == expected.strip()


def test_shell_printer_list_success_renamed_repository(capsys: pytest.CaptureFixture[str]) -> None:
    printer = ShellPrinter()

    printer.list_updated_packages(
        {
            "package": (
                PreCommitRepo("https://old.repo.local/test", "rev1", [PreCommitHook("hook")]),
                PreCommitRepo("https://new.repo.local/test", "rev2", [PreCommitHook("hook")]),
            ),
        }
    )
    captured = capsys.readouterr()

    expected = "[sync-pre-commit-lock] ✔ https://{old -> new}.repo.local/test \t rev1 -> rev2"
    assert normalize(captured.out) == expected
