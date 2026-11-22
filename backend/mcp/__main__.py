# vendored-from: internal-upstream
# upstream-path: tlx/mcp_server/__main__.py
# upstream-sha:  83cae232b94e7998ef543c72e8e7302617d438a0
# imported-on:   2026-05-22
# license:       proprietary — see upstream repo
# modifications: none

"""Entrypoint: `python -m mcp_server`."""
from __future__ import annotations

import asyncio

from kernel import Kernel
from kernel.config import load_config
from mcp_server.server import run


async def main() -> None:
    cfg = load_config()
    kernel = await Kernel.boot(config=cfg, surface="mcp")
    try:
        await run(kernel)
    finally:
        kernel.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
