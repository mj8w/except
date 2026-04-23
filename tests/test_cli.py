from __future__ import annotations

import pytest

from except_tool import cli


@pytest.mark.usefixtures("sample_module_test_context")
class TestCli:
    project_root = None
    sample_module_path = None

    def test_main_reports_local_raise_and_unresolved_open_call(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.chdir(self.project_root)
        monkeypatch.setattr("sys.argv", ["except", str(self.sample_module_path), "19"])

        exit_code = cli.main()
        captured = capsys.readouterr()

        assert exit_code == 0
        assert 'Statement at line 19: value = load_value("config.txt")' in captured.out
        assert "ValueError via load_value -> read_number -> parse_number" in captured.out
        assert "open via load_value -> read_number -> open" in captured.out

    def test_main_can_render_tree_output(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.chdir(self.project_root)
        monkeypatch.setattr(
            "sys.argv", ["except", str(self.sample_module_path), "19", "--format", "tree"]
        )

        exit_code = cli.main()
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "Call tree" in captured.out
        assert "Exceptions" in captured.out
        assert "load_value" in captured.out
        assert "read_number" in captured.out
        assert "open" in captured.out
        assert "FileNotFoundError, OSError" in captured.out
        assert "[raises ValueError]" in captured.out


def test_main_renders_swallowed_exceptions_in_tree_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    project_root,
    caught_exception_module_path,
) -> None:
    monkeypatch.chdir(project_root)
    monkeypatch.setattr(
        "sys.argv", ["except", str(caught_exception_module_path), "14", "--format", "tree"]
    )

    exit_code = cli.main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "wrapper" in captured.out
    assert "leaf" in captured.out
    assert "wrapper" in captured.out and "[swallows ValueError]" in captured.out
    assert "leaf" in captured.out and "ValueError; [raises ValueError]" in captured.out


def test_main_can_analyze_a_module_that_imports_requests(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    project_root,
    requests_module_path,
) -> None:
    monkeypatch.chdir(project_root)
    monkeypatch.setattr("sys.argv", ["except", str(requests_module_path), "9"])

    exit_code = cli.main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert 'Statement at line 9: return fetch_status("https://example.com")' in captured.out
    assert "Potential exceptions (implicit operations):" in captured.out
    assert "ConnectionError via fetch_status -> requests.get" in captured.out
    assert "RequestException via fetch_status -> requests.get" in captured.out
    assert "Unresolved calls:" not in captured.out


def test_main_renders_library_summaries_in_tree_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    project_root,
    requests_module_path,
) -> None:
    monkeypatch.chdir(project_root)
    monkeypatch.setattr("sys.argv", ["except", str(requests_module_path), "9", "--format", "tree"])

    exit_code = cli.main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "fetch_status" in captured.out
    assert "requests.get" in captured.out
    assert "ConnectionError, RequestException, Timeout, TooManyRedirects" in captured.out
    assert "[library summary]" in captured.out
