"""`python -m dbt_service` entrypoint: serve the sidecar on 0.0.0.0:$PORT."""

import uvicorn

from .app import app
from .config import Settings


def main() -> None:  # pragma: no cover
    settings = Settings()
    uvicorn.run(app, host="0.0.0.0", port=settings.port)


if __name__ == "__main__":  # pragma: no cover
    main()
