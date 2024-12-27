"""Config flow for Hello World integration."""
from __future__ import annotations

import logging
from typing import Any
from collections.abc import Mapping
from ipaddress import ip_address as ip

import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.core import HomeAssistant

from .cyberiot_intelligent import CyberiotApollo

from homeassistant.core import callback
from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.util.network import is_ip_address as is_ip

from .const import DOMAIN, SERIAL_NUMBER

_LOGGER = logging.getLogger(__name__)

HTTP_SUFFIX = "._http._tcp.local."
DEFAULT_PORT = 80

DATA_SCHEMA = vol.Schema({("serial_number"): str})


async def validate_input(hass: HomeAssistant, data: dict) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    if len(data["serial_number"]) < 3:
        raise InvalidHost
    apollo = CyberiotApollo(hass, data["serial_number"])
    result = await apollo.check_connection()
    if not result:
        raise CannotConnect

    return {"title": data["serial_number"]}


class ApolloFlowHandler(ConfigFlow, domain=DOMAIN):
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self) -> None:
        """Initialize the apollo config flow."""
        self.discovered_conf: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidHost:
                errors["host"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        host = discovery_info.host
        serial_number = discovery_info.name.removesuffix(HTTP_SUFFIX)
        return await self.async_step_confirm_discovery(host, serial_number)

    def _async_get_existing_entry(self, serial_number: str):
        """See if we already have a configured NAS with this MAC address."""
        for entry in self._async_current_entries():
            if serial_number in [
                name.removesuffix(HTTP_SUFFIX) for name in entry.data.get(SERIAL_NUMBER, [])
            ]:
                return entry
        return None

    async def async_step_confirm_discovery(
        self, host: str, serial_number: str
    ) -> ConfigFlowResult:
        """Handle discovery confirm."""
        await self.async_set_unique_id(serial_number)
        existing_entry = self._async_get_existing_entry(serial_number)
        self._abort_if_unique_id_configured()

        if (
            existing_entry
            and is_ip(existing_entry.data[CONF_HOST])
            and is_ip(host)
            and existing_entry.data[CONF_HOST] != host
            and ip(existing_entry.data[CONF_HOST]).version == ip(host).version
        ):
            _LOGGER.debug(
                "Update host from '%s' to '%s' for NAS '%s' via discovery",
                existing_entry.data[CONF_HOST],
                host,
                existing_entry.unique_id,
            )
            self.hass.config_entries.async_update_entry(
                existing_entry,
                data={**existing_entry.data, CONF_HOST: host},
            )
            return self.async_abort(reason="reconfigure_successful")

        if existing_entry:
            return self.async_abort(reason="already_configured")

        self.discovered_conf = {
            CONF_NAME: serial_number,
            CONF_HOST: host,
            SERIAL_NUMBER: serial_number
        }
        self.context["title_placeholders"] = self.discovered_conf
        return await self.async_step_link()

    async def async_step_link(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Link a config entry from discovery."""
        step = "link"
        if not user_input:
            pass
            # return self._show_form(step)
        # _LOGGER.debug("------------------discovered_conf:{}, user_input:{}".format(self.discovered_conf, user_input))
        # user_input = {**self.discovered_conf, **user_input}
        user_input = self.discovered_conf
        return await self.async_validate_input_create_entry(user_input, step_id=step)

    async def async_validate_input_create_entry(
        self, user_input: dict[str, Any], step_id: str
    ) -> ConfigFlowResult:
        """Process user input and create new or update existing config entry."""
        host = user_input[CONF_HOST]
        port = user_input.get(CONF_PORT)
        serial_number = user_input.get(SERIAL_NUMBER)

        if not port:
            port = DEFAULT_PORT

        errors = {}
        if errors:
            return
            # return self._show_form(step_id, user_input, errors)

        # unique_id should be serial for services purpose
        # existing_entry = await self.async_set_unique_id(serial, raise_on_progress=False)

        config_data = {
            CONF_HOST: host,
            CONF_PORT: port,
            CONF_NAME: serial_number,
            SERIAL_NUMBER: serial_number
        }

        # if existing_entry:
        #     reason = (
        #         "reauth_successful" if self.reauth_conf else "reconfigure_successful"
        #     )
        #     return self.async_update_reload_and_abort(
        #         existing_entry, data=config_data, reason=reason
        #     )

        return self.async_create_entry(title=serial_number or host, data=config_data)

    @callback
    def async_create_entry(  # type: ignore[override]
        self,
        *,
        title: str,
        data: Mapping[str, Any],
        description: str | None = None,
        description_placeholders: Mapping[str, str] | None = None,
        options: Mapping[str, Any] | None = None,
    ):
        """Finish config flow and create a config entry."""
        result = super().async_create_entry(
            title=title,
            data=data,
            description=description,
            description_placeholders=description_placeholders,
        )

        result["options"] = options or {}

        return result


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidHost(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid hostname."""
