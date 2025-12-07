"""Platform for selecting Elegoo printer options."""

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.elegoo_printer.sdcp.models.enums import PrinterType

from .coordinator import ElegooDataUpdateCoordinator
from .definitions import (
    PRINTER_SELECT_TYPES,
    PRINTER_FILE_SELECT,
    ElegooPrinterDynamicSelectEntityDescription,
    ElegooPrinterSelectEntityDescription,
)
from .entity import ElegooPrinterEntity


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Asynchronously sets up Elegoo printer select entities in Home Assistant."""
    coordinator: ElegooDataUpdateCoordinator = config_entry.runtime_data.coordinator
    printer_type = coordinator.config_entry.runtime_data.api.printer.printer_type

    entities = []
    if printer_type == PrinterType.FDM:
        for description in PRINTER_SELECT_TYPES:
            entities.append(ElegooPrintSpeedSelect(coordinator, description))

    # Add storage file select for all printer types
    for description in PRINTER_FILE_SELECT:
        entities.append(ElegooPrintFileSelect(coordinator, description))

    if entities:
        async_add_entities(entities, update_before_add=True)


class ElegooPrintSpeedSelect(ElegooPrinterEntity, SelectEntity):
    """Representation of an Elegoo printer select entity."""

    def __init__(
        self,
        coordinator: ElegooDataUpdateCoordinator,
        description: ElegooPrinterSelectEntityDescription,
    ) -> None:
        """Initialize an Elegoo printer select entity."""
        super().__init__(coordinator)
        self.entity_description: ElegooPrinterSelectEntityDescription = description
        self._api = None  # Initialize _api to None

        self._attr_unique_id = coordinator.generate_unique_id(description.key)
        self._attr_name = description.name
        self._attr_options = description.options

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self._api = self.coordinator.config_entry.runtime_data.api

    @property
    def current_option(self) -> None:
        """Returns the current selected option."""
        if self.coordinator.data:
            return self.entity_description.current_option_fn(self.coordinator.data)
        return None

    async def async_select_option(self, option: str) -> None:
        """Asynchronously selects an option."""
        value = self.entity_description.options_map.get(option)
        if self._api:
            await self.entity_description.select_option_fn(self._api, value)
            if self.coordinator.data:
                self.coordinator.async_set_updated_data(self.coordinator.data)
            self.async_write_ha_state()


class ElegooPrintFileSelect(ElegooPrinterEntity, SelectEntity):
    """Representation of a dynamic file selection for starting prints."""

    def __init__(
        self,
        coordinator: ElegooDataUpdateCoordinator,
        description: ElegooPrinterDynamicSelectEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description: ElegooPrinterDynamicSelectEntityDescription = (
            description
        )
        self._api = None
        self._attr_unique_id = coordinator.generate_unique_id(description.key)
        self._attr_name = description.name

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._api = self.coordinator.config_entry.runtime_data.api
        # Fetch file list on first add
        try:
            await self._api.async_get_file_list()
            await self.coordinator.async_request_refresh()
        except Exception as e:  # noqa: BLE001
            self.coordinator.logger.warning("Failed to fetch initial file list: %s", e)

    @property
    def options(self) -> list[str]:
        if self.coordinator.data:
            return self.entity_description.options_fn(self.coordinator.data)
        return []

    @property
    def current_option(self) -> str | None:
        if self.coordinator.data:
            return self.entity_description.current_option_fn(self.coordinator.data)
        return None

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        if self.coordinator.data:
            return self.entity_description.available_fn(self.coordinator.data)
        return False

    async def async_select_option(self, option: str) -> None:
        if self._api:
            await self.entity_description.select_option_fn(self._api, option)
            await self.coordinator.async_request_refresh()
            self.async_write_ha_state()
