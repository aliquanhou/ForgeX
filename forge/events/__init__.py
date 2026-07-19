"""Event Protocol — stable typed event schemas for Runtime ↔ Studio communication.

This is the contract between ForgeX Runtime and ForgeX-Studio.
All events emitted by the Runtime go through these typed schemas.

Studio should NEVER read RuntimeState directly.
Studio should ONLY consume events from this protocol.

v1.0 — frozen with ForgeX v0.5 LTS.
"""

from .protocol import (
    # Lifecycle
    TaskStartedEvent,
    TaskCompletedEvent,
    TaskFailedEvent,

    # Intent
    IntentClassifiedEvent,

    # Decision
    DecisionSelectedEvent,

    # Tool
    ToolStartedEvent,
    ToolCompletedEvent,
    ToolFailedEvent,
    ToolRejectedEvent,

    # World Model
    FactConfirmedEvent,
    WorldUpdatedEvent,

    # EVI
    EVIEvaluatedEvent,

    # Artifact
    ArtifactCreatedEvent,
    ArtifactStateChangedEvent,

    # Phase
    PhaseChangedEvent,

    # Error
    ErrorEvent,

    # Budget
    BudgetWarningEvent,
    BudgetExhaustedEvent,
)

__all__ = [
    "TaskStartedEvent",
    "TaskCompletedEvent",
    "TaskFailedEvent",
    "IntentClassifiedEvent",
    "DecisionSelectedEvent",
    "ToolStartedEvent",
    "ToolCompletedEvent",
    "ToolFailedEvent",
    "ToolRejectedEvent",
    "FactConfirmedEvent",
    "WorldUpdatedEvent",
    "EVIEvaluatedEvent",
    "ArtifactCreatedEvent",
    "ArtifactStateChangedEvent",
    "PhaseChangedEvent",
    "ErrorEvent",
    "BudgetWarningEvent",
    "BudgetExhaustedEvent",
]
