"""Base classes and interfaces for data processing pipelines.

This module defines the core pipeline abstractions that enable
building composable, testable data processing workflows.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, TypeVar

# Type variables for pipeline step inputs/outputs
TInput = TypeVar("TInput")
TOutput = TypeVar("TOutput")


class StepStatus(Enum):
    """Status of a pipeline step execution."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepResult[TOutput]:
    """Result of executing a pipeline step.

    Attributes:
        status: Execution status
        output: Output data from the step (None if failed/skipped)
        error: Error message if failed
        metadata: Additional metadata about the execution
        duration_seconds: How long the step took to execute
        started_at: When execution started
        completed_at: When execution completed
    """

    status: StepStatus
    output: TOutput | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    duration_seconds: float | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def succeeded(self) -> bool:
        """Check if the step succeeded."""
        return self.status == StepStatus.SUCCESS

    @property
    def failed(self) -> bool:
        """Check if the step failed."""
        return self.status == StepStatus.FAILED


@dataclass
class PipelineContext:
    """Context shared across all pipeline steps.

    Provides access to configuration, working directories, and
    shared state during pipeline execution.

    Attributes:
        config: Configuration dictionary
        work_dir: Working directory for temporary files
        output_dir: Directory for final outputs
        cache_dir: Directory for caching intermediate results
        dry_run: If True, don't actually perform destructive operations
        metadata: Additional metadata to pass between steps
    """

    config: dict[str, Any]
    work_dir: Path
    output_dir: Path
    cache_dir: Path | None = None
    dry_run: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Ensure directories exist."""
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)


class PipelineStep[TInput, TOutput](ABC):
    """Abstract base class for pipeline steps.

    Pipeline steps are composable units of work that:
    - Accept typed input
    - Produce typed output
    - Can validate their inputs
    - Provide clear error messages
    - Can be tested in isolation

    Example:
        class FetchTrailsStep(PipelineStep[None, gpd.GeoDataFrame]):
            def execute(self, context: PipelineContext, input_data: None) -> StepResult[gpd.GeoDataFrame]:
                # Download and return trail data
                trails = download_trails()
                return StepResult(
                    status=StepStatus.SUCCESS,
                    output=trails,
                    metadata={"trail_count": len(trails)}
                )
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for this step."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Brief description of what this step does."""
        pass

    @abstractmethod
    def execute(self, context: PipelineContext, input_data: TInput) -> StepResult[TOutput]:
        """Execute this pipeline step.

        Args:
            context: Pipeline execution context
            input_data: Input data from previous step

        Returns:
            StepResult containing the output or error information
        """
        pass

    def validate_input(self, input_data: TInput) -> list[str]:
        """Validate input data before execution.

        Args:
            input_data: Input data to validate

        Returns:
            List of validation errors (empty if valid)
        """
        return []

    def should_skip(self, context: PipelineContext, input_data: TInput) -> tuple[bool, str | None]:
        """Determine if this step should be skipped.

        Args:
            context: Pipeline execution context
            input_data: Input data

        Returns:
            Tuple of (should_skip, reason)
        """
        return False, None

    def cleanup(self, context: PipelineContext) -> None:  # noqa: B027 — an optional hook, not a contract
        """Clean up resources after execution.

        Called after execute() completes, regardless of success/failure.

        Args:
            context: Pipeline execution context
        """
        pass

    def __repr__(self) -> str:
        """String representation."""
        return f"{self.__class__.__name__}(name='{self.name}')"


class ConditionalStep(PipelineStep[TInput, TOutput]):
    """Base class for steps that may be conditionally skipped.

    Subclasses should override should_skip() to implement
    conditional logic.
    """

    pass


class RetryableStep(PipelineStep[TInput, TOutput]):
    """Base class for steps that support retries.

    Attributes:
        max_retries: Maximum number of retry attempts
        retry_delay_seconds: Delay between retries
        backoff_multiplier: Multiply delay by this factor after each retry
    """

    def __init__(
        self,
        max_retries: int = 3,
        retry_delay_seconds: float = 1.0,
        backoff_multiplier: float = 2.0,
    ) -> None:
        """Initialize retryable step.

        Args:
            max_retries: Maximum retry attempts
            retry_delay_seconds: Initial delay between retries
            backoff_multiplier: Backoff multiplier for exponential backoff
        """
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self.backoff_multiplier = backoff_multiplier

    @abstractmethod
    def execute_with_retry(self, context: PipelineContext, input_data: TInput) -> StepResult[TOutput]:
        """Execute with retry logic.

        Subclasses should implement their logic here.
        The execute() method will handle retries automatically.

        Args:
            context: Pipeline execution context
            input_data: Input data

        Returns:
            StepResult
        """
        pass

    def execute(self, context: PipelineContext, input_data: TInput) -> StepResult[TOutput]:
        """Execute with automatic retries.

        Args:
            context: Pipeline execution context
            input_data: Input data

        Returns:
            StepResult
        """
        import time

        attempt = 0
        delay = self.retry_delay_seconds

        while attempt <= self.max_retries:
            result = self.execute_with_retry(context, input_data)

            if result.succeeded or attempt == self.max_retries:
                if attempt > 0:
                    result.metadata["retry_attempts"] = attempt
                return result

            # Wait before retry
            if attempt < self.max_retries:
                time.sleep(delay)
                delay *= self.backoff_multiplier
                attempt += 1

        # Should never reach here, but just in case
        return StepResult(
            status=StepStatus.FAILED,
            error="Max retries exceeded",
            metadata={"retry_attempts": attempt},
        )
