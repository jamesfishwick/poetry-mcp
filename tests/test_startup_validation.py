"""Coverage for the startup tag-validation helper.

`_run_startup_tag_validation` was extracted from main() so the startup path can
be tested directly. It must:
  - run validation only when config enables it,
  - read the ValidationResult via attributes (a prior version dict-subscripted
    the model and raised),
  - never let a validation failure escape (startup must not be blocked).
"""

from unittest.mock import AsyncMock, Mock, patch

import poetry_mcp.server as server_module
from poetry_mcp.models.results import ValidationResult


def _config(enabled: bool):
    return Mock(validation=Mock(auto_validate_on_sync=enabled))


def _result(valid: bool, invalid_tags=None):
    invalid_tags = invalid_tags or []
    return ValidationResult(
        success=valid,
        valid=valid,
        invalid_tags=invalid_tags,
        violations_count=len(invalid_tags),
        affected_poems=[{"id": "p", "title": "P", "invalid_tags": invalid_tags}]
        if invalid_tags
        else [],
        total_poems_checked=3,
        total_tags_checked=5,
        valid_tags=["water"],
    )


def test_returns_none_and_skips_when_disabled():
    validate = Mock(fn=AsyncMock())
    with (
        patch("poetry_mcp.config.get_config", return_value=_config(False)),
        patch.object(server_module, "validate_poem_tags", validate),
    ):
        assert server_module._run_startup_tag_validation() is None
    validate.fn.assert_not_called()


def test_runs_and_returns_result_when_valid():
    result = _result(valid=True)
    validate = Mock(fn=AsyncMock(return_value=result))
    with (
        patch("poetry_mcp.config.get_config", return_value=_config(True)),
        patch.object(server_module, "validate_poem_tags", validate),
    ):
        out = server_module._run_startup_tag_validation()
    validate.fn.assert_called_once()
    assert out is result
    assert out.valid is True


def test_handles_invalid_result_via_attributes():
    # More than five invalid tags exercises the "... and N more" branch, and
    # attribute access here is exactly what the dict-subscript bug broke.
    tags = [f"bad{i}" for i in range(7)]
    validate = Mock(fn=AsyncMock(return_value=_result(valid=False, invalid_tags=tags)))
    with (
        patch("poetry_mcp.config.get_config", return_value=_config(True)),
        patch.object(server_module, "validate_poem_tags", validate),
    ):
        out = server_module._run_startup_tag_validation()
    assert out.valid is False
    assert out.violations_count == 7


def test_swallows_validation_error_and_returns_none():
    validate = Mock(fn=AsyncMock(side_effect=RuntimeError("boom")))
    with (
        patch("poetry_mcp.config.get_config", return_value=_config(True)),
        patch.object(server_module, "validate_poem_tags", validate),
    ):
        # Must not raise: startup can't be blocked by validation.
        assert server_module._run_startup_tag_validation() is None
