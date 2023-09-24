"""Adds config flow for LightSwitch."""
from __future__ import annotations
from typing import Any, Mapping

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_ENTITY_ID, Platform
from homeassistant.helpers import selector, entity_registry as er
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
    SchemaFlowMenuStep,
    wrapped_entity_config_entry_title,
)

from .const import DOMAIN, CONF_SWITCH_ENTITY_ID

CONFIG_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
    "user": SchemaFlowFormStep(
        vol.Schema(
            {
                vol.Required(CONF_ENTITY_ID): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=Platform.LIGHT),
                ),
                vol.Required(CONF_SWITCH_ENTITY_ID): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=Platform.SWITCH),
                ),
            }
        )
    )
}


class LightSwitchFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Config flow for LightSwitch."""

    config_flow = CONFIG_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title and hide the wrapped entity if registered."""
        # Hide the wrapped entry if registered
        registry = er.async_get(self.hass)
        entity_entry = registry.async_get(options[CONF_ENTITY_ID])
        if entity_entry is not None and not entity_entry.hidden:
            registry.async_update_entity(
                options[CONF_ENTITY_ID], hidden_by=er.RegistryEntryHider.INTEGRATION
            )

        return wrapped_entity_config_entry_title(self.hass, options[CONF_ENTITY_ID])
