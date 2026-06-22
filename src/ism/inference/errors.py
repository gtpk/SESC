from __future__ import annotations

from ism.inference.contracts import ErrorKind


def classify_exception(error: BaseException) -> ErrorKind:
    message = str(error).casefold()
    if isinstance(error, MemoryError) or "out of memory" in message or "cuda oom" in message:
        return ErrorKind.OUT_OF_MEMORY
    if isinstance(error, (TimeoutError, ConnectionError)):
        return ErrorKind.TRANSIENT
    if isinstance(error, ValueError):
        return ErrorKind.VALIDATION
    return ErrorKind.FATAL
