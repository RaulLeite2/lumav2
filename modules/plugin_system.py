from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class PluginDescriptor:
    name: str
    root_path: Path
    config_module: str
    services_module: str
    commands_module: str
    events_module: str


class PluginSystem:
    """Simple internal plugin registry for discoverable module boundaries."""

    def __init__(self, base_path: Path):
        self.base_path = base_path

    def discover(self) -> list[PluginDescriptor]:
        descriptors: list[PluginDescriptor] = []
        if not self.base_path.exists():
            return descriptors

        for child in sorted(self.base_path.iterdir()):
            if not child.is_dir():
                continue

            name = child.name
            descriptors.append(
                PluginDescriptor(
                    name=name,
                    root_path=child,
                    config_module=f"modules.{name}.config",
                    services_module=f"modules.{name}.services",
                    commands_module=f"modules.{name}.commands",
                    events_module=f"modules.{name}.events",
                )
            )

        return descriptors
