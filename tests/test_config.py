"""Tests for Config class."""

import os
import tempfile
from pathlib import Path

import pytest

from pypecdp.config import Config


class TestConfig:
    """Test suite for Config class."""

    def test_default_config(self) -> None:
        """Test Config with default values."""
        config = Config()

        assert config.chrome_path == "chromium"
        assert config.user_data_dir is None
        assert config.headless is True
        assert config.extra_args == []
        assert config.ignore_default_args is None
        assert config.env == {}

    def test_custom_config(self) -> None:
        """Test Config with custom values."""
        config = Config(
            chrome_path="/usr/bin/google-chrome",
            user_data_dir="/tmp/test-profile",
            headless=False,
            extra_args=["--no-sandbox", "--disable-gpu"],
            ignore_default_args=["disable-gpu"],
            env={"LANG": "en_US.UTF-8"},
        )

        assert config.chrome_path == "/usr/bin/google-chrome"
        assert config.user_data_dir == "/tmp/test-profile"
        assert config.headless is False
        assert config.extra_args == ["--no-sandbox", "--disable-gpu"]
        assert config.ignore_default_args == ["disable-gpu"]
        assert config.env == {"LANG": "en_US.UTF-8"}

    def test_ensure_user_data_dir_creates_temp(self) -> None:
        """Test that ensure_user_data_dir creates temp directory."""
        config = Config()

        data_dir = config.ensure_user_data_dir()

        assert data_dir is not None
        assert ".pypecdp-profile" in data_dir
        assert config.user_data_dir == data_dir
        assert Path(data_dir).exists()

    def test_ensure_user_data_dir_uses_existing(self) -> None:
        """Test that ensure_user_data_dir uses existing directory."""
        test_dir = "/tmp/test-pypecdp-profile"
        config = Config(user_data_dir=test_dir)

        data_dir = config.ensure_user_data_dir()

        assert data_dir == test_dir
        assert config.user_data_dir == test_dir

    def test_build_argv_headless(self) -> None:
        """Test build_argv includes headless mode."""
        config = Config(headless=True)

        argv = config.build_argv()

        assert "--headless=new" in argv
        assert "--remote-debugging-pipe" in argv
        assert any("--user-data-dir=" in arg for arg in argv)
        assert "about:blank" in argv

    def test_build_argv_not_headless(self) -> None:
        """Test build_argv without headless mode."""
        config = Config(headless=False)

        argv = config.build_argv()

        assert "--headless=new" not in argv
        assert "--remote-debugging-pipe" in argv

    def test_build_argv_extra_args(self) -> None:
        """Test build_argv includes extra arguments."""
        config = Config(extra_args=["--no-sandbox", "--disable-dev-shm-usage"])

        argv = config.build_argv()

        assert "--no-sandbox" in argv
        assert "--disable-dev-shm-usage" in argv

    def test_build_argv_ignore_default_args(self) -> None:
        """Test build_argv respects ignore_default_args."""
        config = Config(ignore_default_args=["disable-gpu"])

        argv = config.build_argv()

        # Should not contain --disable-gpu
        assert not any("--disable-gpu" in arg for arg in argv)

    def test_build_argv_ignore_default_args_with_prefix(self) -> None:
        """Test ignore_default_args works with -- prefix."""
        config = Config(ignore_default_args=["--disable-gpu"])

        argv = config.build_argv()

        assert not any("--disable-gpu" in arg for arg in argv)

    def test_build_argv_default_args_included(self) -> None:
        """Test build_argv includes expected default arguments."""
        config = Config()

        argv = config.build_argv()

        assert "--accept-lang=en-US" in argv
        assert "--no-first-run" in argv
        assert "--no-default-browser-check" in argv
        assert any("--disable-blink-features" in arg for arg in argv)

    def test_build_env(self) -> None:
        """Test build_env merges environment variables."""
        config = Config(env={"CUSTOM_VAR": "value", "LANG": "en_US.UTF-8"})

        env = config.build_env()

        # Should include custom vars
        assert env["CUSTOM_VAR"] == "value"
        assert env["LANG"] == "en_US.UTF-8"

        # Should also include existing environment
        assert "PATH" in env or "USERPROFILE" in env or "HOME" in env

    def test_build_env_empty(self) -> None:
        """Test build_env with no custom variables."""
        config = Config()

        env = config.build_env()

        # Should be a copy of os.environ
        assert len(env) > 0
        assert env == dict(os.environ)
