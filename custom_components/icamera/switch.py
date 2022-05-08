# from functools import partial
#
# from aiohttp import hdrs
#
# from .const import DOMAIN
#
import logging
from typing import Any

# import pandas as pd
from homeassistant import config_entries, core
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.typing import HomeAssistantType

from . import cameras
from .const import DOMAIN
from .icamera_api import ICameraApi, ICameraMotionWindow

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Setup sensors from a config entry created in the integrations UI."""
    _LOGGER.debug("async_setup_entry")

    camera = cameras[config_entry.entry_id]
    sensors = [
        ICameraEmailSwitch(hass, config_entry.entry_id, camera),
        ICameraMotionWindowSwitch(hass, config_entry.entry_id, 1, camera),
        ICameraMotionWindowSwitch(hass, config_entry.entry_id, 2, camera),
        ICameraMotionWindowSwitch(hass, config_entry.entry_id, 3, camera),
        ICameraMotionWindowSwitch(hass, config_entry.entry_id, 4, camera),
    ]
    async_add_entities(sensors, update_before_add=True)


class ICameraEmailSwitch(SwitchEntity):
    """Representation of an iCamera email switch."""

    def __init__(
        self, hass: HomeAssistantType, uniqueid: str, camera: ICameraApi
    ) -> None:
        super().__init__()
        self._camera = camera
        self._id = uniqueid
        self.hass = hass
        self._attr_name = "Send Email on Motion"
        self._attr_available = False
        self._camera.subscribe_to_updates(self._camera_updated)

        log_string = f"Sensor init - id={self._id}"
        _LOGGER.debug(log_string)

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
    def entity_category(self) -> EntityCategory:
        return EntityCategory.CONFIG

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self._id

    @property
    def is_on(self) -> bool:
        return self._camera.send_email_on_motion

    async def async_set_state(self, on: bool) -> None:
        response = await self._camera.async_set_email_on_motion(
            async_get_clientsession(self.hass), on
        )

        if not response:
            _LOGGER.warning("Set email switch failed")

    async def async_turn_off(self, **kwargs: Any) -> None:
        return await self.async_set_state(False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        return await self.async_set_state(True)

    async def async_turn_toggle(self, **kwargs: Any) -> None:
        return await self.async_set_state(not self._camera.send_email_on_motion)

    async def async_update(self):
        session = async_get_clientsession(self.hass)
        await self._camera.async_update_camera_parameters(session)

        self._attr_available = True

    def _camera_updated(self):
        if self.entity_id != None:
            self.schedule_update_ha_state()


class ICameraMotionWindowSwitch(SwitchEntity):
    def __init__(
        self,
        hass: HomeAssistantType,
        uniqueid: str,
        window_num: int,
        camera: ICameraApi,
    ) -> None:
        super().__init__()
        self._camera = camera
        self._device_id = uniqueid
        self._id = uniqueid + ".switch.motion" + str(window_num)
        self.hass = hass
        self._window_num = window_num
        self._attr_name = "Motion Detection Window " + str(window_num)
        self._attr_available = False
        self._camera.subscribe_to_updates(self._camera_updated)

    @property
    def entity_category(self) -> EntityCategory:
        return EntityCategory.CONFIG

    @property
    def device_info(self):
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self._device_id)
            }
        }

    @property
    def unique_id(self) -> str:
        return self._id

    @property
    def _window(self) -> ICameraMotionWindow:
        return self._camera.get_motion_window(self._window_num)

    @property
    def is_on(self) -> bool:
        return self._window.is_on

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "name": self._window.name,
            "coordinates": self._window.coordinates,
            "threshold": self._window.threshold,
            "sensitivity": self._window.sensitivity,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        return await self._camera.async_set_motion_window_active(
            async_get_clientsession(self.hass), self._window_num, True
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        return await self._camera.async_set_motion_window_active(
            async_get_clientsession(self.hass), self._window_num, False
        )

    async def async_toggle(self, **kwargs: Any) -> None:
        return await self._camera.async_set_motion_window_active(
            async_get_clientsession(self.hass), self._window_num, not self.is_on
        )

    async def async_update(self) -> None:
        await self._camera.async_update_camera_parameters(
            async_get_clientsession(self.hass)
        )
        self._attr_available = True

    def _camera_updated(self):
        if self.entity_id != None:
            self.schedule_update_ha_state()
