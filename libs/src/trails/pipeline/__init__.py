"""Pipeline interfaces and base classes for trail data processing."""

from .base import PipelineContext, PipelineStep, StepResult, StepStatus

__all__ = [
    "PipelineContext",
    "PipelineStep",
    "StepResult",
    "StepStatus",
]
