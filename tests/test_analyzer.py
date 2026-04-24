from __future__ import annotations

from pathlib import Path

import pytest

from except_tool.analyzer import ModuleAnalyzer
from except_tool.analyzer import native_exceptions_for_line


@pytest.fixture(scope="class")
def sample_report_context(request: pytest.FixtureRequest, sample_module_path: Path) -> None:
    """Attach a shared analyzer instance and report to the test class."""

    analyzer = ModuleAnalyzer(sample_module_path)
    request.cls.analyzer = analyzer
    request.cls.report = analyzer.analyze_statement(19)


@pytest.mark.usefixtures("sample_report_context")
class TestModuleAnalyzer:
    analyzer = None
    report = None

    def test_analyze_statement_reports_the_target_assignment(self) -> None:
        assert self.report.statement_line == 19
        assert self.report.statement_source == 'value = load_value("config.txt")'

    def test_analyze_statement_collects_findings_and_unresolved_calls(self) -> None:
        assert [finding.exception_name for finding in self.report.findings] == [
            "FileNotFoundError",
            "OSError",
            "ValueError",
            "TypeError",
            "ValueError",
        ]
        assert self.report.findings[2].path == ("load_value", "read_number", "parse_number")
        assert self.report.findings[-1].path == (
            "load_value",
            "read_number",
            "parse_number",
            "int",
        )
        assert self.report.unresolved_calls == []

    def test_analyze_statement_builds_a_call_tree(self) -> None:
        root = self.report.call_tree[0]

        assert root.name == "load_value"
        assert root.resolved is True
        assert root.children[0].name == "read_number"
        assert root.children[0].children[0].name == "open"
        assert root.children[0].children[0].resolved is False
        assert root.children[0].children[1].name == "parse_number"
        assert [finding.exception_name for finding in root.children[0].children[1].findings] == [
            "ValueError"
        ]


def test_analyze_statement_resolves_imported_library_summaries(requests_module_path) -> None:
    report = ModuleAnalyzer(requests_module_path).analyze_statement(9)
    root = report.call_tree[0]
    library_node = root.children[0]

    assert root.name == "fetch_status"
    assert library_node.name == "requests.get"
    assert library_node.summary_source == "library summary"
    assert library_node.escaping_exceptions == [
        "ConnectionError",
        "RequestException",
        "Timeout",
        "TooManyRedirects",
    ]
    assert report.unresolved_calls == []


def test_analyze_statement_can_descend_into_python_stdlib_source(json_module_path) -> None:
    report = ModuleAnalyzer(json_module_path).analyze_statement(8)
    root = report.call_tree[0]
    library_node = root.children[0]

    assert root.name == "parse_payload"
    assert library_node.name == "json.loads"
    assert library_node.resolved is True
    assert library_node.summary_source == "stdlib source"
    assert library_node.definition_line == 299
    assert "JSONDecodeError" in library_node.escaping_exceptions
    assert "TypeError" in library_node.escaping_exceptions


def test_analyze_statement_reports_builtin_summaries_without_unresolved_calls(
    sample_module_path,
) -> None:
    report = ModuleAnalyzer(sample_module_path).analyze_statement(19)
    open_node = report.call_tree[0].children[0].children[0]
    int_node = report.call_tree[0].children[0].children[1].children[0]

    assert open_node.name == "open"
    assert open_node.summary_source == "builtin summary"
    assert open_node.escaping_exceptions == ["FileNotFoundError", "OSError"]
    assert int_node.name == "int"
    assert int_node.summary_source == "builtin summary"
    assert int_node.escaping_exceptions == ["TypeError", "ValueError"]
    assert report.unresolved_calls == []


def test_analyze_statement_reports_stdlib_method_summaries(pathlib_module_path) -> None:
    report = ModuleAnalyzer(pathlib_module_path).analyze_statement(9)
    root = report.call_tree[0]
    summary_node = root.children[1]

    assert root.name == "read_config"
    assert summary_node.name == "pathlib.Path.read_text"
    assert summary_node.summary_source == "stdlib summary"
    assert summary_node.escaping_exceptions == [
        "FileNotFoundError",
        "OSError",
        "UnicodeDecodeError",
    ]


class TestNativeExceptionsForLine:
    def test_reports_builtin_call_exceptions(self) -> None:
        assert native_exceptions_for_line('value = int(payload["count"])') == [
            "IndexError",
            "KeyError",
            "TypeError",
            "ValueError",
        ]

    def test_reports_operator_exceptions(self) -> None:
        assert native_exceptions_for_line("ratio = total / count") == [
            "TypeError",
            "ZeroDivisionError",
        ]

    def test_accepts_return_statement_lines(self) -> None:
        assert native_exceptions_for_line("return max(values)") == ["TypeError", "ValueError"]
