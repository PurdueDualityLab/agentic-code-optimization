"""Configuration for workflow execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from config.base import SubSectionParser


@dataclass
class WorkflowConfig(SubSectionParser):
    """Workflow-level toggles."""

    SECTION: ClassVar[str] = "workflow"

    enable_benchmark: bool = True
