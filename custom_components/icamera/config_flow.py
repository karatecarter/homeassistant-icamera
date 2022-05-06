import base64
import json
from copy import deepcopy
import logging
from typing import Any, Dict, Optional

import aiohttp
from homeassistant import config_entries, core
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_NAME, CONF_PATH, CONF_URL
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_registry import (
    async_entries_for_config_entry,
    async_get_registry,
)
import voluptuous as vol

from .const import DOMAIN
#
#

CONF_SCHEMA = vol.Schema(
    {
        vol.Required("hostname", "Hostname/IP Address"): cv.string,
        vol.Required("http_port", "HTTP Port", 80): cv.positive_int,
        vol.Required("rtsp_port", "RTSP Port", 554): cv.positive_int,
        vol.Required("username", "Camera Username (Case Sensitive)", "administrator"): cv.string,
        vol.Required("password", "Camera Password (Case Sensitive)"): cv.string,
        vol.Required("stream_type", "Type of video stream", "RTSP"): cv.string,
        vol.Required("motion_timeout", "Motion Timeout", 5): cv.positive_int
    }
)
#


_LOGGER = logging.getLogger(__name__)

class ICameraCustomConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """iCamera Custom config flow."""

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None):
        """Invoked when a user initiates a flow via the user interface."""
        errors: Dict[str, str] = {}

        if user_input is not None:

            try:
                hostaddress = "http://" + user_input["hostname"] + ":" + str(user_input["http_port"]) + "/adm/log.cgi"
                session = async_get_clientsession(self.hass)
                response = await session.get(hostaddress, auth=aiohttp.BasicAuth(user_input["username"], user_input["password"]))
                if response.status != 200:
                    errors["base"] = "auth"

            except Exception:
                errors["base"] = "auth"
            if not errors:
                # Input is valid, set data.
                # self.data = user_input
                return self.async_create_entry(title="iCamera", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=CONF_SCHEMA, errors=errors
        )

#     @staticmethod
#     @callback
#     def async_get_options_flow(config_entry):
#         """Get the options flow for this handler."""
#         return OptionsFlowHandler(config_entry)
#
#
# class OptionsFlowHandler(config_entries.OptionsFlow):
#     """Handles options flow for the component."""
#
#     def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
#         self.config_entry = config_entry
#
#     async def async_step_init(
#         self, user_input: Dict[str, Any] = None
#     ) -> Dict[str, Any]:
#         """Manage the options for the custom component."""
#         errors: Dict[str, str] = {}
#         # Grab all configured repos from the entity registry so we can populate the
#         # multi-select dropdown that will allow a user to remove a repo.
#         entity_registry = await async_get_registry(self.hass)
#         entries = async_entries_for_config_entry(
#             entity_registry, self.config_entry.entry_id
#         )
#         # Default value for our multi-select.
#         all_repos = {e.entity_id: e.original_name for e in entries}
#         repo_map = {e.entity_id: e for e in entries}
#
#         if user_input is not None:
#             updated_repos = deepcopy(self.config_entry.data[CONF_REPOS])
#
#             # Remove any unchecked repos.
#             removed_entities = [
#                 entity_id
#                 for entity_id in repo_map.keys()
#                 if entity_id not in user_input["repos"]
#             ]
#             for entity_id in removed_entities:
#                 # Unregister from HA
#                 entity_registry.async_remove(entity_id)
#                 # Remove from our configured repos.
#                 entry = repo_map[entity_id]
#                 entry_path = entry.unique_id
#                 updated_repos = [e for e in updated_repos if e["path"] != entry_path]
#
#             if user_input.get(CONF_PATH):
#                 # Validate the path.
#                 access_token = self.hass.data[DOMAIN][self.config_entry.entry_id][
#                     CONF_ACCESS_TOKEN
#                 ]
#                 try:
#                     await validate_path(user_input[CONF_PATH], access_token, self.hass)
#                 except ValueError:
#                     errors["base"] = "invalid_path"
#
#                 if not errors:
#                     # Add the new repo.
#                     updated_repos.append(
#                         {
#                             "path": user_input[CONF_PATH],
#                             "name": user_input.get(CONF_NAME, user_input[CONF_PATH]),
#                         }
#                     )
#
#             if not errors:
#                 # Value of data will be set on the options property of our config_entry
#                 # instance.
#                 return self.async_create_entry(
#                     title="",
#                     data={CONF_REPOS: updated_repos},
#                 )
#
#         options_schema = vol.Schema(
#             {
#                 vol.Optional("repos", default=list(all_repos.keys())): cv.multi_select(
#                     all_repos
#                 ),
#                 vol.Optional(CONF_PATH): cv.string,
#                 vol.Optional(CONF_NAME): cv.string,
#             }
#         )
#         return self.async_show_form(
#             step_id="init", data_schema=options_schema, errors=errors
