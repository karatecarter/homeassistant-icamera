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
from homeassistant.helpers.entity_platform import current_platform
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.webhook import async_register

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

    platform = current_platform.get()
    platform.async_register_entity_service(
        "set_window_coordinates",
        {
            vol.Required("window_num"): cv.positive_int,
            vol.Required("x"): cv.positive_int,
            vol.Required("y"): cv.positive_int,
            vol.Required("x2"): cv.positive_int,
            vol.Required("y2"): cv.positive_int,
        },
        "async_set_motion_window_coordinates",
    )

    platform.async_register_entity_service(
        "set_window_name",
        {
            vol.Required("window_num"): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=4)
            ),
            vol.Required("name"): cv.string,
        },
        "async_set_motion_window_name",
    )

    platform.async_register_entity_service(
        "set_window_enabled",
        {
            vol.Required("window_num"): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=4)
            ),
            vol.Required("enabled"): cv.boolean,
        },
        "async_set_motion_window_enabled",
    )

    platform.async_register_entity_service(
        "set_window_sensitivity",
        {
            vol.Required("window_num"): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=4)
            ),
            vol.Required("sensitivity"): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=10)
            ),
        },
        "async_set_motion_window_sensitivity",
    )

    platform.async_register_entity_service(
        "set_window_threshold",
        {
            vol.Required("window_num"): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=4)
            ),
            vol.Required("threshold"): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=255)
            ),
        },
        "async_set_motion_window_threshold",
    )


class ICameraMotion(Camera):
    """Representation of a iCamera camera entity with motion detection."""

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
        self._windows = {
            1: None,
            2: None,
            3: None,
            4: None,
        }  # Store complete window objects

    def unauthorized(self):
        """Log camera unauthorized warning (callback function called from icamera-api)"""
        _LOGGER.warning(
            "Camera responded with an 401 Unauthorized error. Check you Username and Password (BOTH are case sensitive)"
        )

    def error(self, error_message: str):
        """LOG a warning message (callback function called from icamera-api)"""
        _LOGGER.warning(error_message)

    @property
    def state(self) -> str:  # pylint: disable=overridden-final-method
        """Returns motion state of camera"""
        # base object defines this property as "final", but camera motion state will not update without this
        # since base object defines state using "is_recording" and "is_streaming"
        return self._attr_state

    @property
    def device_info(self):
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.unique_id)
            },
            "configuration_url": self._camera.config_url,
            "name": "iCamera",
            "model": "iCamera",
            #            "sw_version": self.light.swversion,
        }

    @property
    def supported_features(self) -> int:
        return CameraEntityFeature.STREAM

    async def stream_source(self) -> str:
        """Return the source of the stream."""
        stream_source = await self._camera.stream_source()
        _LOGGER.debug("Getting stream source URL: %s", stream_source)
        return stream_source

    # def camera_image(self, width=None, height=None):
    #     return asyncio.run_coroutine_threadsafe(
    #         self.async_camera_image(), self.hass.loop
    #     ).result()

    #   @asyncio.coroutine
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

        attrs["stream_type1"] = self._camera._stream_type1
        attrs["stream_type2"] = self._camera._stream_type2
        attrs["stream_type3"] = self._camera._stream_type3
        attrs["h264_resolution"] = self._camera._h264_resolution
        attrs["mpeg4_resolution"] = self._camera._mpeg4_resolution
        attrs["jpeg_resolution"] = self._camera._jpeg_resolution

        # Add window data to attributes
        for window_num, window in self._windows.items():
            if window:
                attrs[f"window_{window_num}"] = {
                    "name": window._name,
                    "coordinates": {
                        "x": window._x,
                        "y": window._y,
                        "x2": window._x2,
                        "y2": window._y2,
                    },
                    "threshold": window._threshold,
                    "sensitivity": window._sensitivity,
                    "is_on": window._is_on,
                }

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
            session = async_get_clientsession(self.hass)
            await self.async_setup_webhook()  # this will register the webhook with Home Assistant, it will be called again from _camera_updated to set the camera's webhook url if necessary

            self.hass.async_create_task(
                self._camera.async_update_camera_parameters(session)
            )

        except (ClientError, Exception):  # pylint: disable=broad-except
            self._available = False
            _LOGGER.exception("Error")

    def _camera_updated(self):
        """Handle camera updates."""
        # AI Removed:
        # if self.entity_id != None:
        #     _LOGGER.debug("Camera updated")
        #     asyncio.run_coroutine_threadsafe(self.async_setup_webhook(), self.hass.loop)
        #     self.schedule_update_ha_state()
        #     self._available = True

        self._available = True
        # Update window data from camera if available
        for window_num in range(1, 5):
            window = self._camera.get_motion_window(window_num)
            if window:
                self._windows[window_num] = window
        self.async_write_ha_state()

    async def async_setup_webhook(self):
        callback_url = webhook.get_url(self.hass) + "/api/webhook/" + self.unique_id
        session = async_get_clientsession(self.hass)

        if self._camera.motion_callback_url != callback_url:
            _LOGGER.debug("Registering webhook - %s", callback_url)
            try:
                async_register(
                    self.hass,
                    DOMAIN,
                    "iCamera_motion",
                    self.unique_id,
                    partial(_handle_webhook, self.motion_trigger),
                )
            except Exception:  # pylint: disable=broad-except
                _LOGGER.debug("Webhook already set")

            if self.motion_detection_enabled:
                _LOGGER.debug("Setting camera callback URL - %s", callback_url)

                response = await self._camera.async_set_motion_callback_url(
                    session, callback_url
                )
                if not response:
                    _LOGGER.warning("Set Callback URL Failed")
            else:
                _LOGGER.info(
                    "Motion detection not enabled - camera callback URL not updated (webhook URL = %s)",
                    callback_url,
                )

    async def async_enable_motion_detection(self) -> None:
        return await self._camera.async_set_motion_detection_active(
            async_get_clientsession(self.hass), True
        )

    async def async_disable_motion_detection(self) -> None:
        return await self._camera.async_set_motion_detection_active(
            async_get_clientsession(self.hass), False
        )

    async def async_set_motion_window_coordinates(
        self, window_num: int, x: int, y: int, x2: int, y2: int
    ):
        """Set motion window coordinates."""
        async with async_get_clientsession(self.hass) as session:
            await self._camera.async_set_motion_window_coordinates(
                session, window_num, x, y, x2, y2
            )
            # Update the coordinates in the window object
            if self._windows[window_num] is None:
                # Create new window object if it doesn't exist
                window = ICameraMotionWindow(window_num)
                window.set_coordinates(x, y, x2, y2)
                self._windows[window_num] = window
            else:
                # Update existing window object
                self._windows[window_num].set_coordinates(x, y, x2, y2)
            self.async_write_ha_state()

    async def async_set_motion_window_name(self, window_num: int, name: str):
        """Set motion window name."""
        async with async_get_clientsession(self.hass) as session:
            await self._camera.async_set_motion_window_name(session, window_num, name)
            if self._windows[window_num]:
                self._windows[window_num].set_name(name)
            self.async_write_ha_state()

    async def async_set_motion_window_enabled(self, window_num: int, enabled: bool):
        """Enable or disable motion window."""
        async with async_get_clientsession(self.hass) as session:
            await self._camera.async_set_motion_window_active(
                session, window_num, enabled
            )
            if self._windows[window_num]:
                self._windows[window_num].set_is_on(enabled)
            self.async_write_ha_state()

    async def async_set_motion_window_sensitivity(
        self, window_num: int, sensitivity: int
    ):
        """Set motion window sensitivity."""
        async with async_get_clientsession(self.hass) as session:
            await self._camera.async_set_motion_window_sensitivity(
                session, window_num, sensitivity
            )
            if self._windows[window_num]:
                self._windows[window_num].set_sensitivity(sensitivity)
            self.async_write_ha_state()

    async def async_set_motion_window_threshold(self, window_num: int, threshold: int):
        """Set motion window threshold."""
        async with async_get_clientsession(self.hass) as session:
            await self._camera.async_set_motion_window_threshold(
                session, window_num, threshold
            )
            if self._windows[window_num]:
                self._windows[window_num].set_threshold(threshold)
            self.async_write_ha_state()
