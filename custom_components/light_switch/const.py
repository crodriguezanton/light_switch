"""Constants for light_switch."""
from logging import Logger, getLogger
from typing import Final


LOGGER: Logger = getLogger(__package__)

NAME = "Light Switch"
DOMAIN = "light_switch"
VERSION = "0.0.0"

CONF_SWITCH_ENTITY_ID: Final = "switch_entity_id"
