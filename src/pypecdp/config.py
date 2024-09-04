"""Configuration model for launching Chromium/Chrome in pipe mode."""

from __future__ import annotations

import logging
import os
import pathlib
import tempfile
from dataclasses import dataclass, field

logger = logging.getLogger("pypecdp")


@dataclass
class Config:
    chrome_path: str = "chromium"
    user_data_dir: str | None = None
    headless: bool = True
    extra_args: list[str] = field(default_factory=list)
    switches: dict[str, str | None] = field(default_factory=dict)
    env: dict[str, str] = field(default_factory=dict)

    def ensure_user_data_dir(
        self,
    ):
        data_dir = self.user_data_dir
        if not data_dir:
            data_dir = os.path.join(tempfile.gettempdir(), ".pypecdp-profile")
            self.user_data_dir = data_dir
        pathlib.Path(data_dir).mkdir(parents=True, exist_ok=True)
        logger.debug("Using user_data_dir: %s", data_dir)
        return data_dir

    def build_argv(
        self,
    ):
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
    ):
        env = dict(os.environ)
        env.update(self.env)
        logger.debug("Built child env overrides: %s", self.env)
        return env
