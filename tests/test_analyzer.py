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
        assert [finding.exception_name for finding in self.report.findings] == ["ValueError"]
        assert self.report.findings[0].path == ("load_value", "read_number", "parse_number")
        assert [call.name for call in self.report.unresolved_calls] == ["open", "int"]

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
    assert library_node.summary_source == "library"
    assert library_node.escaping_exceptions == [
        "ConnectionError",
        "RequestException",
        "Timeout",
        "TooManyRedirects",
    ]
    assert report.unresolved_calls == []


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
