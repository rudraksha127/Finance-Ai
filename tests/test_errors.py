"""Tests for src/core/errors.py — foundational exception hierarchy."""

import pytest

from src.core.errors import ConfigError, FinanceAIError, StorageError, ValidationError


def test_base_error_carries_message_and_context():
    error = FinanceAIError("boom", context={"key": "value"})
    assert str(error) == "boom"
    assert error.message == "boom"
    assert error.context == {"key": "value"}


def test_base_error_defaults_context_to_empty_dict():
    assert FinanceAIError("boom").context == {}


@pytest.mark.parametrize(
    "error_type",
    [ConfigError, ValidationError, StorageError],
)
def test_specific_errors_are_finance_ai_errors(error_type):
    error = error_type("problem")
    assert isinstance(error, FinanceAIError)
    assert isinstance(error, Exception)
    assert error.message == "problem"


def test_error_categories_are_distinct():
    assert ConfigError.__name__ == "ConfigError"
    assert ValidationError.__name__ == "ValidationError"
    assert StorageError.__name__ == "StorageError"
    # Distinct categories: a config error is never a validation error.
    assert not issubclass(ConfigError, ValidationError)


def test_can_raise_and_catch_specific_error():
    with pytest.raises(ConfigError, match="bad config"):
        raise ConfigError("bad config")
