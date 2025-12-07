"""Button platform for Elegoo printer."""

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.elegoo_printer.coordinator import ElegooDataUpdateCoordinator
from custom_components.elegoo_printer.data import ElegooPrinterConfigEntry
from custom_components.elegoo_printer.definitions import (
    PRINTER_FDM_BUTTONS,
    ElegooPrinterButtonEntityDescription,
)
from custom_components.elegoo_printer.entity import ElegooPrinterEntity

from .const import (
    LOGGER,
    CONF_DEFAULT_UPLOAD_PATH,
    CONF_DEFAULT_START_WHEN_DONE,
    CONF_DEFAULT_START_FILENAME,
)

if TYPE_CHECKING:
    from custom_components.elegoo_printer.websocket.client import ElegooPrinterClient


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    config_entry: ElegooPrinterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """
    Asynchronously sets up Elegoo printer button entities in Home Assistant.

    Creates and adds a button entity for pausing the current print job
    if the connected printer is identified as an FDM model.
    """
    coordinator: ElegooDataUpdateCoordinator = config_entry.runtime_data.coordinator

    LOGGER.debug(f"Adding {len(PRINTER_FDM_BUTTONS)} button entities")
    for description in PRINTER_FDM_BUTTONS:
        async_add_entities(
            [ElegooSimpleButton(coordinator, description)], update_before_add=True
        )

    # Add optional control buttons (Upload Default, Start Default Filename)
    async_add_entities(
        [
            ElegooUploadDefaultFileButton(coordinator),
            ElegooStartDefaultFilenameButton(coordinator),
            ElegooStartLastUploadedButton(coordinator),
        ],
        update_before_add=True,
    )


class ElegooSimpleButton(ElegooPrinterEntity, ButtonEntity):
    """Representation of an Elegoo printer pause button."""

    def __init__(
        self,
        coordinator: ElegooDataUpdateCoordinator,
        description: ElegooPrinterButtonEntityDescription,
    ) -> None:
        """
        Initialize an Elegoo printer pause button entity with the given data coordinator.

        Configures the entity's unique ID, display name, and icon.
        """  # noqa: E501
        super().__init__(coordinator)
        self.entity_description: ElegooPrinterButtonEntityDescription = description
        self._elegoo_printer_client: ElegooPrinterClient = (
            coordinator.config_entry.runtime_data.api.client
        )
        # Set a unique ID and a friendly name for the entity
        self._attr_unique_id = coordinator.generate_unique_id(
            self.entity_description.key
        )
        self._attr_name = f"{description.name}"

    async def async_press(self) -> None:
        """
        Asynchronously presses the button.

        Calls the printer's action function and requests a state refresh.
        """
        await self.entity_description.action_fn(self._elegoo_printer_client)
        await self.coordinator.async_request_refresh()

    @property
    def available(self) -> bool:
        """Return whether the button entity is currently available."""
        if not super().available:
            return False
        return self.entity_description.available_fn(self._elegoo_printer_client)


class ElegooUploadDefaultFileButton(ElegooPrinterEntity, ButtonEntity):
    """Uploads a default file defined in Options and optionally starts print."""

    def __init__(self, coordinator: ElegooDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.generate_unique_id("upload_default_file")
        self._attr_name = "Upload Default File"

    async def async_press(self) -> None:
        entry = self.coordinator.config_entry
        settings = {**(entry.data or {}), **(entry.options or {})}
        path = settings.get(CONF_DEFAULT_UPLOAD_PATH)
        start_when_done = bool(settings.get(CONF_DEFAULT_START_WHEN_DONE, False))
        api = entry.runtime_data.api
        if not path:
            LOGGER.warning("No default_upload_path set in Options")
            return
        await api.async_upload_file(path, start_when_done=start_when_done)
        await self.coordinator.async_request_refresh()

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        entry = self.coordinator.config_entry
        settings = {**(entry.data or {}), **(entry.options or {})}
        path = settings.get(CONF_DEFAULT_UPLOAD_PATH)
        # Upload currently only supported for MQTT transport
        client = entry.runtime_data.api.client
        return bool(path) and getattr(client, "upload_file_from_path", None) is not None


class ElegooStartDefaultFilenameButton(ElegooPrinterEntity, ButtonEntity):
    """Starts a print using a default filename from Options."""

    def __init__(self, coordinator: ElegooDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.generate_unique_id("start_default_filename")
        self._attr_name = "Start Default Filename"

    async def async_press(self) -> None:
        entry = self.coordinator.config_entry
        settings = {**(entry.data or {}), **(entry.options or {})}
        filename = settings.get(CONF_DEFAULT_START_FILENAME)
        api = entry.runtime_data.api
        if not filename:
            LOGGER.warning("No default_start_filename set in Options")
            return
        await api.async_start_print(filename)
        await self.coordinator.async_request_refresh()

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        entry = self.coordinator.config_entry
        settings = {**(entry.data or {}), **(entry.options or {})}
        filename = settings.get(CONF_DEFAULT_START_FILENAME)
        return bool(filename)


class ElegooStartLastUploadedButton(ElegooPrinterEntity, ButtonEntity):
    """Starts the last successfully uploaded file."""

    def __init__(self, coordinator: ElegooDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.generate_unique_id("start_last_uploaded")
        self._attr_name = "Start Last Uploaded"

    async def async_press(self) -> None:
        api = self.coordinator.config_entry.runtime_data.api
        filename = api.printer_data.last_uploaded_filename
        if not filename:
            LOGGER.warning("No last uploaded filename available")
            return
        await api.async_start_print(filename)
        await self.coordinator.async_request_refresh()

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        api = self.coordinator.config_entry.runtime_data.api
        return bool(api.printer_data.last_uploaded_filename)
