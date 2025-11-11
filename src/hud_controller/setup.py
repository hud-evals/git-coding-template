import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .manual_dinit import ServiceLoader, SimpleDinit

logger = logging.getLogger(__name__)

TEST_MODE = os.environ.get("MCP_TESTING_MODE", "1") in ["1", "true"]

if TEST_MODE:
    # xfce starts quickly on our computer, but not in test
    XFCE_STARTUP_DELAY = 5
    CHROMIUM_STARTUP_DELAY = 3
else:
    # in test mode, we need to wait for the computer to start
    XFCE_STARTUP_DELAY = 30
    CHROMIUM_STARTUP_DELAY = 5


async def start_dinit():
    logger.info("Starting dinit")
    loader = ServiceLoader(Path("/etc/dinit.d"))
    services = loader.load_all()
    engine = SimpleDinit(services)
    engine.start("boot")


def start_dinit_script():
    """Entry point for the start_dinit script."""
    asyncio.run(start_dinit())


async def default_setup(template: dict[str, Any]) -> None:
    """Default setup function that initializes the environment for coding tasks."""
    logger.info(f"=== ENVIRONMENT SETUP DEBUG ===")
    logger.info(f"Template: {template}")


    # Start dinit services
    await start_dinit()
    logger.info("Services started successfully")

    # Wait for XFCE to fully start before setting up Chromium
    logger.info(f"Waiting {XFCE_STARTUP_DELAY} seconds for XFCE to start...")
    await asyncio.sleep(XFCE_STARTUP_DELAY)


def git_setup(base_commit: str, repo_path: str = "/home/ubuntu/ClickHouse") -> None:
    """Setup function for git-based tasks that resets the repository to a baseline commit."""
    logger.info(f"=== GIT SETUP DEBUG ===")
    logger.info(f"Base commit: {base_commit}")
    logger.info(f"Repo path: {repo_path}")

    if not base_commit:
        logger.error("No base commit specified")
        raise ValueError("base commit is required for git setup")

    # Add safe directory to avoid dubious ownership errors
    logger.info(f"Adding {repo_path} as safe directory")
    subprocess.run(
        ["git", "config", "--global", "--add", "safe.directory", repo_path],
        capture_output=True,
        text=True,
    )

    logger.info(f"Resetting repository at {repo_path} to commit {base_commit}")

    # Reset the repository to the baseline commit
    # Use hard reset to ensure clean state
    result = subprocess.run(
        ["git", "reset", "--hard", base_commit],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        logger.error(f"Failed to reset to base commit: {result.stderr}")
        raise RuntimeError(f"Git reset failed: {result.stderr}")

    logger.info(f"Successfully reset to commit {base_commit}")

    # Clean any untracked files
    result = subprocess.run(
        ["git", "clean", "-fdx"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        logger.warning(f"Git clean had issues: {result.stderr}")
    else:
        logger.info("Repository cleaned successfully")
