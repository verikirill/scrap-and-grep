"""Start the browser once while the image is built.

Camoufox writes its runtime font configuration to its cache on the first
launch; the container's file system is read-only, so that happens here.
"""

import asyncio

from radar_browser.render import Renderer


async def _warm() -> None:
    renderer = Renderer(tabs=1)
    await renderer.start()
    await renderer.close()


if __name__ == "__main__":
    asyncio.run(_warm())
