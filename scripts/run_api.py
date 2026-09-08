"""Developer CLI for the inference API (M09).

Follows the repository's ``scripts/run_*.py`` conventions. Starts a
local uvicorn server bound to the configured host/port. Research/paper
only — no execution code exists in this service.
"""

from __future__ import annotations

import argparse
import json
import sys

import uvicorn

from src.config.loader import load_config


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Start the local Finance AI inference API (research mode)."
    )
    parser.add_argument("--host", default=None, help="Bind host (default: config api.host)")
    parser.add_argument(
        "--port", type=int, default=None, help="Bind port (default: config api.port)"
    )
    parser.add_argument("--env", default=None, help="Environment overlay (development/production)")
    args = parser.parse_args()

    environment = args.env or None
    config = load_config(environment) if environment else load_config()
    if config.api.mode not in ("research", "paper"):
        print(
            json.dumps({"status": "FAILED", "error": "api.mode 'live' is not implemented"}),
            file=sys.stderr,
        )
        return 2
    host = args.host or config.api.host
    port = args.port or config.api.port
    print(
        json.dumps(
            {
                "status": "STARTING",
                "host": host,
                "port": port,
                "mode": config.api.mode,
                "api_version": "v1",
            }
        )
    )
    uvicorn.run("src.api.app:get_app", host=host, port=port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
