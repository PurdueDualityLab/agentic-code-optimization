"""Agent module for the multi-agent code optimization system."""

import logging
from pathlib import Path

from agents.base import BaseAgent

# Initialize logging when module is imported
_log_dir = Path.cwd() / "logs"
logger = logging.getLogger(__name__)
logger.info("Agent module initialized with logging")

__all__ = [
    "BaseAgent",
]
