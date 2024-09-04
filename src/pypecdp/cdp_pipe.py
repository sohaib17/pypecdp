"""Pipe transport for the Chrome DevTools Protocol (CDP)."""

import asyncio
import contextlib
import logging
import os

from .config import Config

logger = logging.getLogger("pypecdp")


async def launch_chrome_with_pipe(
    config,
):
    chrome_path = config.chrome_path
    argv = config.build_argv()
    env = config.build_env()

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
    logger.debug("Chrome argv: %s", argv)

    proc = await asyncio.create_subprocess_exec(
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

    loop = asyncio.get_running_loop()

    reader = asyncio.StreamReader()
    r_proto = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(
        lambda: r_proto, os.fdopen(c2p_r, "rb", buffering=0)
    )

    w_transport, _ = await loop.connect_write_pipe(
        asyncio.Protocol, os.fdopen(p2c_w, "wb", buffering=0)
    )

    class _Writer:

        def write(self, data: bytes) -> None:
            w_transport.write(data)

        async def drain(self) -> None:
            await asyncio.sleep(0)

        def close(self) -> None:
            w_transport.close()

    writer = _Writer()
    logger.info("Chrome launched (pid=%s)", proc.pid)
    return proc, reader, writer
