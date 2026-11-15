from dataclasses import FrozenInstanceError

import pytest

from harness.config import ConfigurationError, HarnessConfig


def test_default_configuration_is_valid(config_factory):
    config_factory().validate()


@pytest.mark.parametrize("field,value", [("app_name", "  "), ("description", "")])
def test_required_fields_cannot_be_empty(config_factory, field, value):
    config = config_factory(**{field: value})
    with pytest.raises(ConfigurationError):
        config.validate()


@pytest.mark.parametrize("value", ["false", 0, None])
def test_docker_selection_must_be_boolean(config_factory, value):
    with pytest.raises(ConfigurationError, match="yes/no value"):
        config_factory(uses_docker=value).validate()


def test_configuration_is_immutable(config_factory):
    config = config_factory()
    with pytest.raises(FrozenInstanceError):
        config.app_name = "Changed"
