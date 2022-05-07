# from functools import partial
#
# from aiohttp import hdrs
#
# from .const import DOMAIN
#
from homeassistant.helpers import entity_registry as er
import threading
import urllib.parse

import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession


import asyncio
from functools import partial

import voluptuous as vol
import logging
from aiohttp import ClientError, hdrs

# import pandas as pd
from homeassistant import config_entries, core
from datetime import datetime, date
import sys
from datetime import timedelta
from typing import Any, Callable, Dict, Optional
from homeassistant.components.switch import SwitchEntity
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity, EntityCategory
from homeassistant.helpers.typing import (
    ConfigType,
    DiscoveryInfoType,
    HomeAssistantType,
    StateType,
)
from .const import DOMAIN


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Setup sensors from a config entry created in the integrations UI."""
    _LOGGER.debug("async_setup_entry")
    config = hass.data[DOMAIN][config_entry.entry_id]

    sensors = [ICameraEmailSwitch(hass, config_entry.entry_id, config)]
    async_add_entities(sensors, update_before_add=True)


class ICameraEmailSwitch(SwitchEntity):
    """Representation of an iCamera email switch."""

    def __init__(self, hass: HomeAssistantType, id: str, config: dict):
        super().__init__()
        self._auth = aiohttp.BasicAuth(config["username"], config["password"])
        self._username = config["username"]
        self._password = config["password"]
        self._hostname = config["hostname"]
        self._httpport = config["http_port"]
        self._id = id
        self.hass = hass
        self._name = "Send Email on Motion"
        self._is_on = True
        self._available = True

        self._last_update = 0

        self._attrs: Dict[str, Any] = {}

        _LOGGER.debug("Sensor init - id=" + self._id)

    @property
    def device_info(self):
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.unique_id)
            },
            # "name": "iCamera",
            # "manufacturer": "Dan",
            #            "model": self.light.productname,
            #            "sw_version": self.light.swversion,
        }

    @property
    def entity_category(self) -> EntityCategory:
        return EntityCategory.CONFIG

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self._id

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def is_on(self) -> bool:
        return self._is_on

    async def async_set_state(self, on: bool) -> None:
        on_string = "0"
        if on:
            on_string = "1"

        hostaddress = (
            "http://"
            + self._hostname
            + ":"
            + str(self._httpport)
            + "/adm/set_group.cgi?group=EVENT&event_interval=0&event_mt=email:"
            + on_string
        )

        session = async_get_clientsession(self.hass)
        response = await session.get(hostaddress, auth=self._auth)
        if response.status != 200:
            _LOGGER.warning("Set email switch failed")
        else:
            self._is_on = on

    async def async_turn_off(self, **kwargs: Any) -> None:
        return await self.async_set_state(False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        return await self.async_set_state(True)

    async def async_turn_toggle(self, **kwargs: Any) -> None:
        return await self.async_set_state(not self._is_on)

    async def async_update(self):
        self._available = True
