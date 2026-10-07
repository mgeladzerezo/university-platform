"""Print the OpenAPI schema: `python -m app.openapi > ../frontend/openapi.json`.

The frontend generates its API types from this file, so the two cannot drift
without the type check failing.
"""

import json
import sys
from types import SimpleNamespace

from app.config import Settings
from app.main import create_app


def main() -> None:
    app = create_app(SimpleNamespace(settings=Settings()), session_factory=None)
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    json.dump(app.openapi(), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
