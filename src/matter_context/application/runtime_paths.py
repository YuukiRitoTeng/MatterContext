"""Runtime storage locations, intentionally outside the source checkout."""

from dataclasses import dataclass
import os
from pathlib import Path
import sys


@dataclass(frozen=True, slots=True)
class RuntimePaths:
    config: Path
    data: Path
    attachments: Path
    cache: Path
    diagnostics: Path

    @classmethod
    def for_current_platform(cls) -> "RuntimePaths":
        """Resolve platform conventions, optionally overridden for deployment."""
        if sys.platform.startswith("win"):
            config_base = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
            data_base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
            cache_base = data_base
        elif sys.platform == "darwin":
            config_base = Path.home() / "Library/Application Support"
            data_base = config_base
            cache_base = Path.home() / "Library/Caches"
        else:
            config_base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
            data_base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
            cache_base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))

        name = "MatterContext"
        config = Path(os.environ.get("MATTER_CONTEXT_CONFIG_DIR", config_base / name))
        data = Path(os.environ.get("MATTER_CONTEXT_DATA_DIR", data_base / name))
        cache = Path(os.environ.get("MATTER_CONTEXT_CACHE_DIR", cache_base / name))
        diagnostics = Path(os.environ.get("MATTER_CONTEXT_DIAGNOSTICS_DIR", data / "diagnostics"))
        attachments = Path(os.environ.get("MATTER_CONTEXT_ATTACHMENTS_DIR", data / "attachments"))
        return cls(
            config=config,
            data=data,
            attachments=attachments,
            cache=cache,
            diagnostics=diagnostics,
        )

    @classmethod
    def isolated(cls, root: Path) -> "RuntimePaths":
        """Provide deterministic, repository-independent test locations."""
        root = Path(root)
        return cls(
            config=root / "config",
            data=root / "data",
            attachments=root / "data" / "attachments",
            cache=root / "cache",
            diagnostics=root / "diagnostics",
        )

    def ensure_exists(self) -> "RuntimePaths":
        for directory in (self.config, self.data, self.attachments, self.cache, self.diagnostics):
            directory.mkdir(parents=True, exist_ok=True)
        return self
