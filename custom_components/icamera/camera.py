# from functools import partial
#
# from aiohttp import hdrs
#
# from .const import DOMAIN
#
from homeassistant.components import webhook
from . import cameras
from .icamera_api import ICameraApi
import threading
from homeassistant.helpers.aiohttp_client import async_get_clientsession


import asyncio
from functools import partial

import logging
from aiohttp import ClientError, hdrs

# import pandas as pd
from homeassistant import config_entries, core
from datetime import datetime
from typing import Any
from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.helpers.typing import HomeAssistantType
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
    camera = cameras[config_entry.entry_id]

    sensors = [
        ICameraMotion(
            hass,
            config_entry.entry_id,
            camera,
            config["motion_timeout"],
        )
    ]
    async_add_entities(sensors, update_before_add=True)


class ICameraMotion(Camera):
    """Representation of a iCamera Motion sensor."""

    def __init__(
        self,
        hass: HomeAssistantType,
        uniqueid: str,
        camera: ICameraApi,
        motion_timeout: int,
    ) -> None:
        super().__init__()
        self._camera = camera
        self._camera.set_unathorized_callback(self.unauthorized)
        self._camera.subscribe_to_updates(self._camera_updated)
        self._is_on = True
        self._motion_timeout = motion_timeout
        self._id = uniqueid
        self.hass = hass
        self._timer = None
        self._name = "icamera_" + self._camera._hostname
        self._hostname = self._camera._hostname
        self._available = False

        self._last_motion = 0
        self._last_image = 0

        self._attr_state = STATE_IDLE

        self._attrs: dict[str, Any] = {}

        log_string = f"Sensor init - id={self._id}"
        _LOGGER.debug(log_string)

    def unauthorized(self):
        _LOGGER.warning(
            "Camera responded with an 401 Unauthorized error. Check you Username and Password (BOTH are case sensitive)"
        )

    def error(self, error_message: str):
        _LOGGER.warning(error_message)

    @property
    def state(self) -> str:
        return self._attr_state

    @property
    def device_info(self):
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.unique_id)
            },
            "configuration_url": self._camera.config_url,
            "default_name": "iCamera",
            "model": "iCamera",
            #            "sw_version": self.light.swversion,
        }

    @property
    def supported_features(self) -> int:
        return CameraEntityFeature.STREAM

    async def stream_source(self) -> str:
        """Return the source of the stream."""
        stream_source = await self._camera.stream_source()
        _LOGGER.debug("Getting stream source URL")
        return stream_source

    # def camera_image(self, width=None, height=None):
    #     return asyncio.run_coroutine_threadsafe(
    #         self.async_camera_image(), self.hass.loop
    #     ).result()

    @asyncio.coroutine
    async def async_camera_image(self, width=None, height=None) -> bytes:
        """Return bytes of camera image."""
        image = await self._camera.async_camera_image(
            async_get_clientsession(self.hass), width, height
        )
        self._last_image = datetime.now()
        return image

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
        return self._camera.is_motion_detection_enabled

    @property
    def extra_state_attributes(self):
        """Return the camera state attributes."""
        attrs = {}

        if self._last_motion:
            attrs["last_motion"] = self._last_motion
        if self._last_image:
            attrs["last_image"] = self._last_image

        attrs["last_update"] = self._camera.last_updated

        return attrs

    async def motion_trigger(self):
        _LOGGER.debug("Motion triggered")
        self._attr_state = STATE_MOTION
        self._last_motion = datetime.now()
        if self._timer is not None:
            self._timer.cancel()
        self._timer = threading.Timer(self._motion_timeout, self.motion_end)
        self._timer.start()
        await self.async_update_ha_state()

    def motion_end(self):
        _LOGGER.debug("Motion ended")
        self._attr_state = STATE_IDLE
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        self.schedule_update_ha_state()

    async def async_update(self):
        _LOGGER.debug("async_update")
        try:

            callback_url = webhook.get_url(self.hass) + "/api/webhook/" + self.unique_id
            session = async_get_clientsession(self.hass)

            if self._camera.motion_callback_url != callback_url:
                _LOGGER.debug("Registering webhook - " + callback_url)
                try:
                    self.hass.components.webhook.async_register(
                        DOMAIN,
                        "iCamera_motion",
                        self.unique_id,
                        partial(_handle_webhook, self.motion_trigger),
                    )
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.debug("Webhook already set")

                if not __debug__:
                    _LOGGER.debug("Setting camera callback URL - " + callback_url)

                    response = await self._camera.async_set_motion_callback_url(
                        session, callback_url
                    )
                    if not response:
                        _LOGGER.warning("Set Callback URL Failed")
                else:
                    _LOGGER.info(
                        "Debug mode - camera callback URL not updated (webhook URL = "
                        + callback_url
                        + ")"
                    )
            self.hass.async_create_task(
                self._camera.async_update_camera_parameters(session)
            )

        except (ClientError, Exception):  # pylint: disable=broad-except
            self._available = False
            _LOGGER.exception("Error")

    def _camera_updated(self):
        if self.entity_id != None:
            _LOGGER.debug("Camera updated")
            self.schedule_update_ha_state()
            self._available = True

    async def async_enable_motion_detection(self) -> None:
        return await self._camera.async_set_motion_detection_active(
            async_get_clientsession(self.hass), True
        )

    async def async_disable_motion_detection(self) -> None:
        return await self._camera.async_set_motion_detection_active(
            async_get_clientsession(self.hass), False
        )
