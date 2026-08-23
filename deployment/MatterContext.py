"""Frozen executable entry point that makes the src layout importable to Nuitka."""

from pathlib import Path
import sys


SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SOURCE_ROOT))

from matter_context.ui.application import main


if __name__ == "__main__":
    raise SystemExit(main())
