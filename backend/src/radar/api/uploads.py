"""Uploads that arrive as the raw request body."""

from fastapi import HTTPException, Request, status


async def read_limited(request: Request, limit: int, too_large: str) -> bytes:
    """Read the upload, refusing it as soon as it exceeds the limit.

    The declared length is checked first, but it is only a claim: the stream
    is counted as well, so a client that lies about the size is cut off too.
    """
    refusal = HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail=too_large)
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > limit:
        raise refusal
    chunks: list[bytes] = []
    received = 0
    async for chunk in request.stream():
        received += len(chunk)
        if received > limit:
            raise refusal
        chunks.append(chunk)
    return b"".join(chunks)
