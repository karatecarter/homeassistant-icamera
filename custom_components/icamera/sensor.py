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
from homeassistant.components.sensor import PLATFORM_SCHEMA, Se
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import (
    ConfigType,
    DiscoveryInfoType,
    HomeAssistantType,
    StateType,
)
from .const import DOMAIN

DEPENDENCIES = ("webhook",)


async def _handle_webhook(action, hass, webhook_id, request):
    """Handle incoming webhook."""

    _LOGGER.debug("Motion detection webhook")
    _LOGGER.debug(str(webhook_id))

    result = {
        "platform": "webhook",
        "webhook_id": webhook_id,
    }

    if "json" in request.headers.get(hdrs.CONTENT_TYPE, ""):
        result["json"] = await request.json()
    else:
        result["data"] = await request.post()

    result["query"] = request.query

    hass.async_run_job(action)


_LOGGER = logging.getLogger(__name__)


# SCAN_INTERVAL = timedelta(minutes=1)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Setup sensors from a config entry created in the integrations UI."""
    _LOGGER.debug("async_setup_entry")
    config = hass.data[DOMAIN][config_entry.entry_id]

    sensors = [ICameraMotion(hass, config_entry.entry_id, config)]
    async_add_entities(sensors, update_before_add=True)


class ICameraMotion(SensorEntity):
    """Representation of a iCamera Motion sensor."""

    def __init__(self, hass: HomeAssistantType, id: str, config: dict):
        super().__init__()
        self._auth = aiohttp.BasicAuth(config["username"], config["password"])
        self._hostname = config["hostname"]
        self._httpport = config["http_port"]
        self._rtspport = config["rtsp_port"]
        self._motion_timeout = config["motion_timeout"]
        self._id = id
        self.hass = hass
        self._timer = None
        self._name = "icamera_" + self._hostname + "_ias_zone"
        self._state = "idle"
        self._available = False
        self._callback_url = ""

        self._attrs: Dict[str, Any] = {}

        _LOGGER.debug("Sensor init - id=" + self._id)

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
    def native_value(self) -> StateType:
        return self._state

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        return self._attrs

    async def motion_trigger(self):
        _LOGGER.warning("Motion triggered")
        self._state = "motion"
        if self._timer is not None:
            self._timer.cancel()
        self._timer = threading.Timer(self._motion_timeout, self.motion_end)
        self._timer.start()
        await self.async_update_ha_state()

    def motion_end(self):
        _LOGGER.warning("Motion ended")
        self._state = "idle"
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        self.schedule_update_ha_state()

    async def async_update(self):
        try:
            if self.entity_id is not None:
                callback_url = urllib.parse.quote(
                    "http://192.168.1.139:8123/api/webhook/" + self.unique_id,
                    safe="'",
                )
                if self._callback_url != callback_url:
                    _LOGGER.debug("Setting callback URL")

                    try:
                        self.hass.components.webhook.async_register(
                            DOMAIN,
                            "iCamera_motion",
                            self.unique_id,
                            partial(_handle_webhook, self.motion_trigger),
                        )
                    except Exception:
                        _LOGGER.debug("Webhook already set")

                    hostaddress = (
                        "http://"
                        + self._hostname
                        + ":"
                        + str(self._httpport)
                        + "/adm/set_group.cgi?group=HTTP_NOTIFY&http_notify=1&http_url="
                        + callback_url
                    )

                    session = async_get_clientsession(self.hass)
                    response = await session.get(hostaddress, auth=self._auth)
                    if response.status != 200:
                        _LOGGER.warning("Set Callback URL Failed")
                    else:
                        self._callback_url = callback_url
                self._available = True
            else:
                _LOGGER.debug("Entity ID is None")

        except (ClientError, Exception):
            self._available = False
            _LOGGER.exception("Error.")
