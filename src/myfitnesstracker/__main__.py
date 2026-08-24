"""Allow ``python -m myfitnesstracker`` to run the project CLI."""

from __future__ import annotations

from .cli import main


if __name__ == "__main__":
    raise SystemExit(main())
