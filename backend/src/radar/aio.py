"""Event loop selection.

psycopg's async mode needs a selector event loop, and Windows defaults to the
proactor one. Linux containers are unaffected; this only matters when the
backend runs directly on a Windows machine during development.
"""

import asyncio
import selectors
import sys
from collections.abc import Coroutine
from typing import Any


def selector_loop() -> asyncio.AbstractEventLoop:
    """Loop factory, also usable as `uvicorn --loop radar.aio:selector_loop`."""
    return asyncio.SelectorEventLoop(selectors.SelectSelector())


def run[T](coroutine: Coroutine[Any, Any, T]) -> T:
    if sys.platform == "win32":
        return asyncio.run(coroutine, loop_factory=selector_loop)
    return asyncio.run(coroutine)
