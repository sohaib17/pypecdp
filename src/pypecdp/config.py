"""Configuration model for launching Chromium/Chrome in pipe mode."""

from __future__ import annotations

import os
import pathlib
import tempfile
from dataclasses import dataclass, field

from .logger import logger


@dataclass
class Config:
    """Configuration for launching Chrome/Chromium with CDP pipe.

    Attributes:
        chrome_path: Path to Chrome/Chromium executable.
        user_data_dir: Path to user data directory. If None, a
            temporary directory will be created.
        headless: Whether to run in headless mode.
        extra_args: Additional command-line arguments to pass.
        switches: Dictionary of Chrome switches to enable.
        env: Environment variables to set for the browser process.
    """

    chrome_path: str = "chromium"
    user_data_dir: str | None = None
    headless: bool = True
    extra_args: list[str] = field(default_factory=list)
    switches: dict[str, str | None] = field(default_factory=dict)
    env: dict[str, str] = field(default_factory=dict)

    def ensure_user_data_dir(
        self,
    ) -> str:
        """Ensure user data directory exists and return its path.

        If user_data_dir is not set, creates a temporary directory.

        Returns:
            str: Path to the user data directory.
        """
        data_dir: str | None = self.user_data_dir
        if not data_dir:
            data_dir = os.path.join(tempfile.gettempdir(), ".pypecdp-profile")
            self.user_data_dir = data_dir
        pathlib.Path(data_dir).mkdir(parents=True, exist_ok=True)
        logger.debug("Using user_data_dir: %s", data_dir)
        return data_dir

    def build_argv(
        self,
    ) -> list[str]:
        """Build command-line arguments for Chrome launch.

        Constructs the full argument list including headless mode,
        pipe debugging, user data directory, switches, and extra args.

        Returns:
            list[str]: Complete list of command-line arguments.
        """
        argv: list[str] = []
        if self.headless and "--headless=new" not in self.extra_args:
            argv.append("--headless=new")

        argv.append("--remote-debugging-pipe")
        argv.append(f"--user-data-dir={self.ensure_user_data_dir()}")
        argv.extend(
            [
                "--no-first-run",
                "--no-default-browser-check",
                "--use-gl=angle",
                "--use-angle=swiftshader",
                "--disable-gpu",
            ]
        )

        for k, v in self.switches.items():
            if v is None:
                argv.append(f"--{k}")
            else:
                argv.append(f"--{k}={v}")

        argv.extend(self.extra_args)
        argv.append("about:blank")
        logger.debug("Built Chrome argv: %s", argv)
        return argv

    def build_env(
        self,
    ) -> dict[str, str]:
        """Build environment variables for Chrome process.

        Merges current environment with custom overrides.

        Returns:
            dict[str, str]: Complete environment variable mapping.
        """
        env: dict[str, str] = dict(os.environ)
        env.update(self.env)
        logger.debug("Built child env overrides: %s", self.env)
        return env


__all__ = ["Config"]
