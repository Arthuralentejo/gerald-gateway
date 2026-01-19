"""SQLAlchemy database models."""

from datetime import datetime, date
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


class DecisionModel(Base):
    """Database model for BNPL decisions."""

    __tablename__ = "bnpl_decisions"

    id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    requested_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credit_limit_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_granted_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    score_numeric: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_band: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )

    # Relationship to plan (one-to-one)
    plan: Mapped["PlanModel | None"] = relationship(
        "PlanModel",
        back_populates="decision",
        uselist=False,
    )


class PlanModel(Base):
    """Database model for repayment plans."""

    __tablename__ = "bnpl_plans"

    id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    decision_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("bnpl_decisions.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    total_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )

    # Relationships
    decision: Mapped["DecisionModel"] = relationship(
        "DecisionModel",
        back_populates="plan",
    )
    installments: Mapped[list["InstallmentModel"]] = relationship(
        "InstallmentModel",
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="InstallmentModel.due_date",
    )


class InstallmentModel(Base):
    """Database model for installment payments."""

    __tablename__ = "bnpl_installments"

    id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    plan_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("bnpl_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="scheduled",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )

    # Relationship
    plan: Mapped["PlanModel"] = relationship(
        "PlanModel",
        back_populates="installments",
    )
