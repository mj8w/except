from __future__ import annotations

import pytest

from except_tool.analyzer import ModuleAnalyzer


@pytest.mark.xfail(
    reason="Analyzer does not yet infer implicit exceptions from subscripts and builtins.",
    strict=True,
)
def test_analyze_statement_detects_value_error_and_type_error_from_key_lookup(
    implicit_exception_module_path,
) -> None:
    report = ModuleAnalyzer(implicit_exception_module_path).analyze_statement(7)

    assert [finding.exception_name for finding in report.findings] == ["TypeError", "ValueError"]


def test_analyze_statement_omits_exception_caught_lower_in_call_tree(
    caught_exception_module_path,
) -> None:
    report = ModuleAnalyzer(caught_exception_module_path).analyze_statement(14)

    assert report.findings == []
    assert report.call_tree[0].escaping_exceptions == []
    assert report.call_tree[0].swallowed_exceptions == ["ValueError"]
    assert report.call_tree[0].children[0].escaping_exceptions == ["ValueError"]
