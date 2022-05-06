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
from homeassistant.components.camera import Camera, SUPPORT_STREAM
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import (
    ConfigType,
    DiscoveryInfoType,
    HomeAssistantType,
    StateType,
)
from .const import DOMAIN

STATE_MOTION = "motion"
STATE_NO_MOTION = "no_motion"
STATE_IDLE = "idle"

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


class ICameraMotion(Camera):
    """Representation of a iCamera Motion sensor."""

    def __init__(self, hass: HomeAssistantType, id: str, config: dict):
        super().__init__()
        self._auth = aiohttp.BasicAuth(config["username"], config["password"])
        self._username = config["username"]
        self._password = config["password"]
        self._hostname = config["hostname"]
        self._httpport = config["http_port"]
        self._rtspport = config["rtsp_port"]
        self._motion_timeout = config["motion_timeout"]
        self._id = id
        self.hass = hass
        self._timer = None
        self._name = "icamera_" + self._hostname
        self._is_on = True
        self._available = False
        self._callback_url = ""
        self._stream_type = config["stream_type"]

        self._last_update = 0
        self._last_image = None
        self._last_motion = 0

        self._state = STATE_IDLE

        self._attrs: Dict[str, Any] = {}

        _LOGGER.debug("Sensor init - id=" + self._id)

    @property
    def supported_features(self) -> int:
        return SUPPORT_STREAM

    async def stream_source(self) -> str:
        """Return the source of the stream."""
        if self._stream_type == "RTSP":
            return f"rtsp://{self._hostname}:{str(self._rtspport)}/img/media.sav"
        else:
            return (
                "http://"
                + self._hostname
                + ":"
                + str(self._httpport)
                + "/img/video.mjpeg"
            )

    def camera_image(self, width=None, height=None):
        return asyncio.run_coroutine_threadsafe(
            self.async_camera_image(), self.hass.loop
        ).result()

    @asyncio.coroutine
    async def async_camera_image(self, width=None, height=None) -> bytes:
        """Return bytes of camera image."""
        hostaddress = f"http://{self._hostname}:{str(self._httpport)}/img/snapshot.cgi"

        session = async_get_clientsession(self.hass)
        response = await session.get(hostaddress, auth=self._auth)
        if response.status != 200:
            _LOGGER.warning("Get snapshot Failed")
        else:
            return await response.read()

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

    @property
    def motion_detection_enabled(self) -> bool:
        return True

    @property
    def extra_state_attributes(self):
        """Return the camera state attributes."""
        attrs = {}

        if self._last_motion:
            attrs["last_motion"] = self._last_motion

        if self._last_update:
            attrs["last_update"] = self._last_update

        return attrs

    @property
    def state(self) -> str:
        return self._state

    async def motion_trigger(self):
        _LOGGER.debug("Motion triggered")
        self._state = STATE_MOTION
        self._last_motion = datetime.now()
        if self._timer is not None:
            self._timer.cancel()
        self._timer = threading.Timer(self._motion_timeout, self.motion_end)
        self._timer.start()
        await self.async_update_ha_state()

    def motion_end(self):
        _LOGGER.debug("Motion ended")
        self._state = STATE_IDLE
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        self.schedule_update_ha_state()

    async def async_update(self):
        try:

            self._last_update = datetime.now()
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

        except (ClientError, Exception):
            self._available = False
            _LOGGER.exception("Error.")
