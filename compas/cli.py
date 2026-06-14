"""Command-line entrypoint: ``compas`` / ``python -m compas``.

Starts the local-first dashboard with Uvicorn. Pass ``--reload`` for
development, or set ``COMPAS_*`` environment variables to point at a real
Navigate catalog.
"""

from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="compas", description=__doc__)
    parser.add_argument("--host", default="127.0.0.1",
                        help="bind host (default 127.0.0.1, local-first)")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args(argv)

    import uvicorn

    uvicorn.run("compas.main:app", host=args.host, port=args.port,
                reload=args.reload)


if __name__ == "__main__":
    main()
