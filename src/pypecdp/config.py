"""Configuration model for launching Chromium/Chrome in pipe mode."""

from __future__ import annotations

import os
import pathlib
import shutil
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
        clean_data_dir: Whether to remove existing user data directory before
            starting. Defaults to True. Set to False to preserve cookies,
            cache, and other browser state between runs.
        headless: Whether to run in headless mode.
        extra_args: Additional command-line arguments to pass.
        ignore_default_args: List of default args to ignore.
        env: Environment variables to set for the browser process.

    Example:
        >>> config = Config(
        ...     chrome_path="chromium",
        ...     clean_data_dir=False,  # Preserve profile
        ...     headless=True
        ... )
    """

    chrome_path: str = "chromium"
    user_data_dir: str | None = None
    clean_data_dir: bool = True
    headless: bool = True
    extra_args: list[str] = field(default_factory=list)
    ignore_default_args: list[str] | None = None
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
        if self.clean_data_dir and os.path.exists(data_dir):
            shutil.rmtree(data_dir)
        pathlib.Path(data_dir).mkdir(parents=True, exist_ok=True)
        logger.debug("Using user_data_dir: %s", data_dir)
        return data_dir

    def build_argv(
        self,
    ) -> list[str]:
        """Build command-line arguments for Chrome launch.

        Constructs the full argument list including headless mode,
        pipe debugging, user data directory, and extra args.
        Filters out arguments specified in ignore_default_args.

        Returns:
            list[str]: Complete list of command-line arguments.
        """
        argv: list[str] = []
        if self.headless and "--headless=new" not in self.extra_args:
            argv.append("--headless=new")
        argv.append("--remote-debugging-pipe")
        argv.append(f"--user-data-dir={self.ensure_user_data_dir()}")
        # Define default arguments
        default_args = [
            "--accept-lang=en-US",
            "--no-first-run",
            "--no-default-browser-check",
            "--use-gl=angle",
            "--use-angle=swiftshader",
            "--disable-gpu",
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process",
        ]
        # Filter out ignored default args
        if self.ignore_default_args:
            filtered_args = []
            for arg in default_args:
                # Check if the arg (or its base without value) should be ignored
                arg_base = arg.split("=", maxsplit=1)[0]
                should_ignore = False
                for ignore_arg in self.ignore_default_args:
                    # Support both "arg-name" and "--arg-name" formats
                    if arg_base in (ignore_arg, f"--{ignore_arg}"):
                        should_ignore = True
                        break
                if not should_ignore:
                    filtered_args.append(arg)
            argv.extend(filtered_args)
        else:
            argv.extend(default_args)
        # Append extra user args
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
