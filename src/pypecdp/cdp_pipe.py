"""Pipe transport for the Chrome DevTools Protocol (CDP)."""

import asyncio
import contextlib
import os
from asyncio.subprocess import Process
from importlib.util import find_spec

from .config import Config
from .logger import logger

_POSIX = find_spec("posix") is not None


class _Writer:
    """Custom writer for CDP pipe communication.

    Attributes:
        _transport: The underlying asyncio WriteTransport.
    """

    def __init__(self, transport: asyncio.WriteTransport) -> None:
        """Initialize the writer.

        Args:
            transport: The asyncio WriteTransport to wrap.
        """
        self._transport = transport

    def write(self, data: bytes) -> None:
        """Write data to the transport.

        Args:
            data: The bytes to write to the transport.
        """
        self._transport.write(data)

    async def drain(self) -> None:
        """Drain the transport (no-op for pipe)."""
        await asyncio.sleep(0)

    def close(self) -> None:
        """Close the transport."""
        self._transport.close()


async def launch_chrome_with_pipe_posix(
    config: Config,
) -> tuple[Process, asyncio.StreamReader, _Writer]:
    """Launch Chrome with pipe-based CDP communication.

    Creates bidirectional pipes for Chrome DevTools Protocol
    communication, launches the Chrome process with appropriate file
    descriptors, and returns async reader/writer for CDP messages.

    Args:
        config: Configuration object with Chrome path and arguments.

    Returns:
        tuple: A tuple containing:
            - proc: The Chrome subprocess object.
            - reader: AsyncIO StreamReader for reading CDP messages.
            - writer: Custom writer object for sending CDP messages.
    """
    chrome_path: str = config.chrome_path
    argv: list[str] = config.build_argv()
    env: dict[str, str] = config.build_env()

    # Parent <-> Child pipes:
    # parent writes (p2c_w) -> child reads on FD 3
    p2c_r, p2c_w = os.pipe()
    # child writes on FD 4 -> parent reads (c2p_r)
    c2p_r, c2p_w = os.pipe()

    for fd in (p2c_r, c2p_w):
        os.set_inheritable(fd, True)

    def _preexec() -> None:
        os.dup2(p2c_r, 3)
        os.dup2(c2p_w, 4)
        if p2c_r not in (3, 4):
            with contextlib.suppress(OSError):
                os.close(p2c_r)
        if c2p_w not in (3, 4):
            with contextlib.suppress(OSError):
                os.close(c2p_w)

    logger.info("Launching Chrome at %s with %d args", chrome_path, len(argv))

    proc: Process = await asyncio.create_subprocess_exec(
        chrome_path,
        *argv,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,  # avoid pipe backpressure deadlock
        preexec_fn=_preexec,
        pass_fds=(3, 4),
        env=env,
    )

    with contextlib.suppress(OSError):
        os.close(p2c_r)
    with contextlib.suppress(OSError):
        os.close(c2p_w)

    loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()

    reader: asyncio.StreamReader = asyncio.StreamReader(limit=2**30)
    r_proto: asyncio.StreamReaderProtocol = asyncio.StreamReaderProtocol(
        reader
    )
    await loop.connect_read_pipe(
        lambda: r_proto, os.fdopen(c2p_r, "rb", buffering=0)
    )

    w_transport, _ = await loop.connect_write_pipe(
        asyncio.Protocol, os.fdopen(p2c_w, "wb", buffering=0)
    )

    writer = _Writer(w_transport)
    logger.info("Chrome launched (pid=%s)", proc.pid)
    return proc, reader, writer


if _POSIX:
    launch_chrome_with_pipe = launch_chrome_with_pipe_posix
else:
    raise NotImplementedError("Pipe transport is only implemented for POSIX.")


__all__ = ["launch_chrome_with_pipe"]
