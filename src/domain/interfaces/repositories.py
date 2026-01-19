"""Repository interfaces for data persistence."""

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from src.domain.entities import Decision, Plan


class DecisionRepository(ABC):
    """
    Abstract repository for Decision persistence.

    Implementations may use PostgreSQL, in-memory storage, etc.
    """

    @abstractmethod
    async def save(self, decision: Decision) -> Decision:
        """
        Persist a decision.

        Args:
            decision: The decision to save

        Returns:
            The saved decision with any generated fields populated
        """
        ...

    @abstractmethod
    async def get_by_id(self, decision_id: UUID) -> Optional[Decision]:
        """
        Retrieve a decision by ID.

        Args:
            decision_id: The decision's unique identifier

        Returns:
            The decision if found, None otherwise
        """
        ...

    @abstractmethod
    async def get_by_user_id(
        self,
        user_id: str,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Decision]:
        """
        Retrieve decisions for a user.

        Args:
            user_id: The user's identifier
            limit: Maximum number of decisions to return
            offset: Number of decisions to skip

        Returns:
            List of decisions, ordered by created_at descending
        """
        ...


class PlanRepository(ABC):
    """
    Abstract repository for Plan persistence.

    Implementations may use PostgreSQL, in-memory storage, etc.
    """

    @abstractmethod
    async def save(self, plan: Plan) -> Plan:
        """
        Persist a plan with its installments.

        Args:
            plan: The plan to save

        Returns:
            The saved plan with any generated fields populated
        """
        ...

    @abstractmethod
    async def get_by_id(self, plan_id: UUID) -> Optional[Plan]:
        """
        Retrieve a plan by ID.

        Args:
            plan_id: The plan's unique identifier

        Returns:
            The plan if found, None otherwise
        """
        ...

    @abstractmethod
    async def get_by_user_id(self, user_id: str) -> List[Plan]:
        """
        Retrieve all plans for a user.

        Args:
            user_id: The user's identifier

        Returns:
            List of plans for the user
        """
        ...
