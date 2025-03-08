"""Select entities for iCamera."""

from __future__ import annotations

from typing import Final

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import cameras
from .icamera_api import ICameraApi
from .const import DOMAIN

RESOLUTION_OPTIONS: Final = ["160x120", "320x240", "640x480", "1280x720"]
RESOLUTION_VALUES: Final = {
    "160x120": "1",
    "320x240": "2",
    "640x480": "3",
    "1280x720": "4",
}

STREAM_TYPES: Final = [
    SelectEntityDescription(
        key="h264_resolution",
        translation_key="h264_resolution",
        options=RESOLUTION_OPTIONS,
        entity_category=EntityCategory.CONFIG,
    ),
    SelectEntityDescription(
        key="mpeg4_resolution",
        translation_key="mpeg4_resolution",
        options=RESOLUTION_OPTIONS,
        entity_category=EntityCategory.CONFIG,
    ),
    SelectEntityDescription(
        key="jpeg_resolution",
        translation_key="jpeg_resolution",
        options=RESOLUTION_OPTIONS,
        entity_category=EntityCategory.CONFIG,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select entities for iCamera."""
    camera = cameras[config_entry.entry_id]
    async_add_entities(
        IcameraStreamResolutionSelect(camera, description, config_entry.entry_id)
        for description in STREAM_TYPES
    )


class IcameraStreamResolutionSelect(SelectEntity):
    """Select entity for stream resolution settings."""

    def __init__(
        self, camera: ICameraApi, description: SelectEntityDescription, uniqueid: str
    ) -> None:
        """Initialize the select entity."""
        super().__init__()
        self.entity_description = description
        self._id = f"{uniqueid}_{description.key}"
        self._device_id = uniqueid
        self._attr_name = description.key
        self._camera = camera

    @property
    def unique_id(self) -> str:
        return self._id

    @property
    def current_option(self) -> str | None:
        """Return the current resolution option."""
        resolution = None
        if self.entity_description.key == "h264_resolution":
            resolution = self._camera._h264_resolution
        elif self.entity_description.key == "mpeg4_resolution":
            resolution = self._camera._mpeg4_resolution
        elif self.entity_description.key == "jpeg_resolution":
            resolution = self._camera._jpeg_resolution
        return resolution if resolution in RESOLUTION_OPTIONS else None

    @property
    def device_info(self):
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self._device_id)
            }
        }

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        stream_type = self.entity_description.key.split("_")[0].upper()
        value = RESOLUTION_VALUES[option]
        return await self._camera.async_set_stream_resolution(
            async_get_clientsession(self.hass), stream_type, value
        )
