from __future__ import annotations

import sys

from .application import MoniApplication


def main() -> int:
    app = MoniApplication(sys.argv)
    return app.start()


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
