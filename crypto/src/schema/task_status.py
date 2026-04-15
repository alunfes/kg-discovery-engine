"""Task and experiment run status enumerations."""

from enum import Enum


class TaskStatus(Enum):
    """Status of a pipeline task or run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SecrecyLevel(Enum):
    """Information secrecy classification.

    Determines whether a hypothesis card can be shared externally.
    Higher secrecy = higher direct alpha potential = must not be shared.
    """

    PRIVATE_ALPHA = "private_alpha"
    INTERNAL_WATCHLIST = "internal_watchlist"
    SHAREABLE_STRUCTURE = "shareable_structure"
    DISCARD = "discard"


class ValidationStatus(Enum):
    """Epistemic state of a hypothesis.

    Cards begin as UNTESTED; validation is updated by the eval pipeline.
    DECAYED is set externally when the market regime changes.
    """

    UNTESTED = "untested"
    WEAKLY_SUPPORTED = "weakly_supported"
    REPRODUCED = "reproduced"
    INVALIDATED = "invalidated"
    DECAYED = "decayed"
