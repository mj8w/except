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
        assert "Call tree:" in captured.out
        assert "- call load_value (line 19), def line " in captured.out
        assert "  - call read_number" in captured.out
        assert "    - unresolved call open" in captured.out
        assert "    - call parse_number" in captured.out
        assert "      - raises ValueError" in captured.out
