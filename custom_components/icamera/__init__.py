from .icamera_api import ICameraApi
from homeassistant import core, config_entries
import logging

from .const import DOMAIN


_LOGGER = logging.getLogger(__name__)

cameras: dict[str, ICameraApi] = {}


async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Set up platform from a ConfigEntry."""
    _LOGGER.debug("async_setup_entry")
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    cameras[entry.entry_id] = create_camera_with_config(entry.data)

    # Forward the setup to the sensor platform.
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "camera")
    )
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "switch")
    )
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "select")
    )
    return True


def create_camera_with_config(config: dict) -> ICameraApi:
    return ICameraApi(
        config["hostname"],
        config["http_port"],
        config["rtsp_port"],
        config["username"],
        config["password"],
    )
