"""Agent interface (Phase 3)."""
from __future__ import annotations

from abc import ABC, abstractmethod


class Agent(ABC):
    @abstractmethod
    def act(self, observation: dict):
        """Return an action for the current observation."""

    def reset(self) -> None:
        """Called at the start of every run."""
