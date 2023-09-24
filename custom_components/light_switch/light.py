"""Light support for switch entities."""
from __future__ import annotations

from typing import Any
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.entity_platform import AddEntitiesCallback


from homeassistant.components import switch, light
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_MAX_MIREDS,
    ATTR_MIN_MIREDS,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_TRANSITION,
    ATTR_XY_COLOR,
    ATTR_EFFECT_LIST,
    ATTR_EFFECT,
    ATTR_COLOR_MODE,
    ATTR_FLASH,
    ATTR_WHITE,
    ATTR_SUPPORTED_COLOR_MODES,
    LightEntity,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    CONF_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)

from .const import CONF_SWITCH_ENTITY_ID

_LOGGER = logging.getLogger(__name__)

FORWARDED_ATTRIBUTES = frozenset(
    {
        ATTR_BRIGHTNESS,
        ATTR_COLOR_TEMP,
        ATTR_EFFECT,
        ATTR_FLASH,
        ATTR_HS_COLOR,
        ATTR_RGB_COLOR,
        ATTR_RGBW_COLOR,
        ATTR_RGBWW_COLOR,
        ATTR_TRANSITION,
        ATTR_WHITE,
        ATTR_XY_COLOR,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize Light Switch config entry."""
    registry = er.async_get(hass)
    entity_id = er.async_validate_entity_id(
        registry, config_entry.options[CONF_ENTITY_ID]
    )
    wrapped_switch = registry.async_get(entity_id)
    device_id = wrapped_switch.device_id if wrapped_switch else None

    async_add_entities(
        [
            LightSwitch(
                entity_id,
                config_entry.title,
                config_entry.options[CONF_ENTITY_ID],
                config_entry.options[CONF_SWITCH_ENTITY_ID],
            )
        ]
    )


# class NotALightSwitch(BaseToggleEntity, LightEntity):
#     """Represents a Switch as a Light."""

#     _attr_color_mode = ColorMode.ONOFF
#     _attr_supported_color_modes = {ColorMode.ONOFF}


class LightSwitch(LightEntity):
    """Representation of a light group."""

    _attr_available = False
    _attr_icon = "mdi:lightbulb"
    _attr_max_mireds = 500
    _attr_min_mireds = 154
    _attr_should_poll = False

    def __init__(
        self,
        unique_id: str | None,
        name: str,
        light_entity_id: list[str],
        switch_entity_id: str | None,
    ) -> None:
        """Initialize a light group."""
        self._light_entity_id = light_entity_id
        self._switch_entity_id = switch_entity_id

        self._attr_name = name
        self._attr_extra_state_attributes = {
            ATTR_ENTITY_ID: [light_entity_id, switch_entity_id]
        }
        self._attr_unique_id = unique_id

    @property
    def should_poll(self) -> bool:
        """Disable polling for group."""
        return False

    # async def async_added_to_hass(self) -> None:
    #     """Register listeners."""

    #     async def _update_at_start(_):
    #         self.async_update_group_state()
    #         self.async_write_ha_state()

    #     self.async_on_remove(start.async_at_start(self.hass, _update_at_start))

    @callback
    def async_defer_or_update_ha_state(self) -> None:
        """Only update once at start."""
        if not self.hass.is_running:
            return

        self.async_update_group_state()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        @callback
        def async_state_changed_listener(event: Event) -> None:
            """Handle child updates."""
            self.async_set_context(event.context)
            self.async_defer_or_update_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._switch_entity_id, self._light_entity_id],
                async_state_changed_listener,
            )
        )

        await super().async_added_to_hass()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Forward the turn_on command to all lights in the light group."""
        light_data = {
            key: value for key, value in kwargs.items() if key in FORWARDED_ATTRIBUTES
        }
        light_data[ATTR_ENTITY_ID] = self._light_entity_id
        switch_data = {ATTR_ENTITY_ID: self._switch_entity_id}

        switch_state = self.hass.states.get(self._switch_entity_id)

        _LOGGER.debug(
            "Forwarded turn_on command to switch (%s): %s",
            switch_state.state,
            switch_data,
        )
        _LOGGER.debug(
            "Forwarded turn_on command to lights: %s",
            light_data,
        )

        if switch_state.state != STATE_ON:
            await self.hass.services.async_call(
                switch.DOMAIN,
                SERVICE_TURN_ON,
                switch_data,
                blocking=True,
                context=self._context,
            )

        await self.hass.services.async_call(
            light.DOMAIN,
            SERVICE_TURN_ON,
            light_data,
            blocking=True,
            context=self._context,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Forward the turn_off command to all lights in the light group."""
        data = {ATTR_ENTITY_ID: self._switch_entity_id}

        if ATTR_TRANSITION in kwargs:
            data[ATTR_TRANSITION] = kwargs[ATTR_TRANSITION]

        await self.hass.services.async_call(
            switch.DOMAIN,
            SERVICE_TURN_OFF,
            data,
            blocking=True,
            context=self._context,
        )

    @callback
    def async_update_group_state(self) -> None:
        """Query all members and determine the light group state."""

        switch_state = self.hass.states.get(self._switch_entity_id)
        light_state = self.hass.states.get(self._light_entity_id)

        states = [switch_state, light_state]

        _LOGGER.debug("Switch State %s", switch_state.as_dict())
        _LOGGER.debug("Light State %s", light_state.as_dict())

        valid_state = all(
            state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
            for state in [switch_state, light_state]
        )

        if not valid_state:
            # Set as unknown if any / all member is unknown or unavailable
            self._attr_is_on = None
        else:
            # self._attr_is_on = all(state.state == STATE_ON for state in states)
            self._attr_is_on = switch_state.state == STATE_ON

        self._attr_available = all(state.state != STATE_UNAVAILABLE for state in states)
        self._attr_brightness = light_state.attributes.get(ATTR_BRIGHTNESS)

        self._attr_hs_color = light_state.attributes.get(ATTR_HS_COLOR)

        self._attr_rgb_color = light_state.attributes.get(ATTR_RGB_COLOR)

        self._attr_rgbw_color = light_state.attributes.get(ATTR_RGBW_COLOR)

        self._attr_rgbww_color = light_state.attributes.get(ATTR_RGBWW_COLOR)

        self._attr_xy_color = light_state.attributes.get(ATTR_XY_COLOR)

        self._attr_color_temp = light_state.attributes.get(ATTR_COLOR_TEMP)

        self._attr_min_mireds = light_state.attributes.get(ATTR_MIN_MIREDS)

        self._attr_max_mireds = light_state.attributes.get(ATTR_MAX_MIREDS)

        self._attr_effect_list = light_state.attributes.get(ATTR_EFFECT_LIST)
        # all_effect_lists = list(find_state_attributes(states, ATTR_EFFECT_LIST))
        # if all_effect_lists:
        #     # Merge all effects from all effect_lists with a union merge.
        #     self._attr_effect_list = list(set().union(*all_effect_lists))
        #     self._attr_effect_list.sort()
        #     if "None" in self._attr_effect_list:
        #         self._attr_effect_list.remove("None")
        #         self._attr_effect_list.insert(0, "None")

        self._attr_effect = light_state.attributes.get(ATTR_EFFECT)
        # all_effects = list(find_state_attributes(on_states, ATTR_EFFECT))
        # if all_effects:
        #     # Report the most common effect.
        #     effects_count = Counter(itertools.chain(all_effects))
        #     self._attr_effect = effects_count.most_common(1)[0][0]

        self._attr_color_mode = light_state.attributes.get(ATTR_COLOR_MODE)
        # all_color_modes = list(find_state_attributes(on_states, ATTR_COLOR_MODE))
        # if all_color_modes:
        #     # Report the most common color mode, select brightness and onoff last
        #     color_mode_count = Counter(itertools.chain(all_color_modes))
        #     if ColorMode.ONOFF in color_mode_count:
        #         color_mode_count[ColorMode.ONOFF] = -1
        #     if ColorMode.BRIGHTNESS in color_mode_count:
        #         color_mode_count[ColorMode.BRIGHTNESS] = 0
        #     self._attr_color_mode = color_mode_count.most_common(1)[0][0]

        self._attr_supported_color_modes = light_state.attributes.get(
            ATTR_SUPPORTED_COLOR_MODES
        )
        # all_supported_color_modes = list(
        #     find_state_attributes(states, ATTR_SUPPORTED_COLOR_MODES)
        # )
        # if all_supported_color_modes:
        #     # Merge all color modes.
        #     self._attr_supported_color_modes = cast(
        #         set[str], set().union(*all_supported_color_modes)
        #     )

        self._attr_supported_features = light_state.attributes.get(
            ATTR_SUPPORTED_FEATURES
        )
        # for support in find_state_attributes(states, ATTR_SUPPORTED_FEATURES):
        #     # Merge supported features by emulating support for every feature
        #     # we find.
        #     self._attr_supported_features |= support
        # # Bitwise-and the supported features with the GroupedLight's features
        # # so that we don't break in the future when a new feature is added.
        # self._attr_supported_features &= SUPPORT_GROUP_LIGHT
