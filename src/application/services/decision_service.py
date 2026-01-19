"""Decision service - orchestrates the BNPL decision use case."""

from datetime import date, timedelta
from uuid import UUID

import structlog

from src.domain.entities import Decision, DecisionFactors, Plan, Installment
from src.domain.exceptions import (
    DecisionNotFoundException,
    InvalidDecisionRequestException,
)
from src.domain.interfaces import (
    BankAPIClient,
    DecisionRepository,
    PlanRepository,
    LedgerWebhookClient,
)
from src.application.dto import DecisionRequest, DecisionResponse, DecisionHistoryResponse
from src.service.scoring.models import Transaction as ScoringTransaction
from src.service.scoring.models import TransactionType as ScoringTxnType
from src.service.scoring import (
    calculate_avg_daily_balance,
    calculate_income_spend_ratio,
    count_nsf_events,
    calculate_income_consistency,
    calculate_risk_score,
    score_to_credit_limit_cents,
    handle_thin_file,
)

logger = structlog.get_logger(__name__)


class DecisionService:
    """
    Application service for BNPL decision use cases.
    """

    NUM_INSTALLMENTS = 4
    DAYS_BETWEEN_INSTALLMENTS = 14

    def __init__(
        self,
        decision_repository: DecisionRepository,
        plan_repository: PlanRepository,
        bank_client: BankAPIClient,
        ledger_client: LedgerWebhookClient,
    ):
        self._decision_repo = decision_repository
        self._plan_repo = plan_repository
        self._bank_client = bank_client
        self._ledger_client = ledger_client

    async def make_decision(self, request: DecisionRequest) -> DecisionResponse:
        """
        Process a BNPL decision request.

        Args:
            request: The decision request with user_id and amount

        Returns:
            DecisionResponse with approval status and details

        Raises:
            InvalidDecisionRequestException: If request validation fails
            BankAPIException: If bank API fails
            UserNotFoundException: If user doesn't exist
        """
        errors = request.validate()
        if errors:
            raise InvalidDecisionRequestException("; ".join(errors))

        log = logger.bind(
            user_id=request.user_id,
            amount_requested=request.amount_cents_requested,
        )
        log.info("decision_requested")

        transactions = await self._bank_client.get_transactions(request.user_id)
        log.info("transactions_fetched", count=len(transactions))

        domain_transactions = self._convert_transactions(transactions)

        decision = self._calculate_decision(
            user_id=request.user_id,
            amount_requested=request.amount_cents_requested,
            transactions=domain_transactions,
        )

        # Persist decision first (plan has FK to decision)
        await self._decision_repo.save(decision)

        # If approved, create and persist repayment plan
        if decision.approved:
            plan = self._create_plan(
                user_id=request.user_id,
                decision_id=decision.id,
                amount_cents=decision.amount_granted_cents,
            )

            # Update decision with plan ID
            decision.plan_id = plan.id

            # Persist plan (after decision exists)
            await self._plan_repo.save(plan)

            log.info(
                "plan_created",
                plan_id=str(plan.id),
                num_installments=len(plan.installments),
            )

            # Send webhook asynchronously (fire and forget)
            await self._ledger_client.send_plan_created(plan)

        log.info(
            "decision_made",
            approved=decision.approved,
            credit_limit=decision.credit_limit_cents,
            amount_granted=decision.amount_granted_cents,
            risk_score=decision.decision_factors.risk_score,
        )

        return DecisionResponse.from_entity(decision)

    async def get_decision_history(
        self,
        user_id: str,
        limit: int = 10,
    ) -> DecisionHistoryResponse:
        """
        Get decision history for a user.

        Args:
            user_id: The user's identifier
            limit: Maximum number of decisions to return

        Returns:
            DecisionHistoryResponse with list of decisions
        """
        decisions = await self._decision_repo.get_by_user_id(user_id, limit=limit)
        return DecisionHistoryResponse.from_entities(user_id, decisions)

    async def get_decision_by_id(self, decision_id: UUID) -> Decision:
        """
        Get a specific decision by ID.

        Args:
            decision_id: The decision's unique identifier

        Returns:
            The decision entity

        Raises:
            DecisionNotFoundException: If decision not found
        """
        decision = await self._decision_repo.get_by_id(decision_id)
        if decision is None:
            raise DecisionNotFoundException(str(decision_id))
        return decision

    def _convert_transactions(self, transactions) -> list:
        """Convert API transactions to scoring module format if needed."""
        # The transactions from bank client are already in the correct format
        # This method exists for potential future transformations

        return [
            ScoringTransaction(
                date=t.date,
                amount_cents=t.amount_cents,
                balance_cents=t.balance_cents,
                type=ScoringTxnType(t.type.value),
                nsf=t.nsf,
                description=t.description,
            )
            for t in transactions
        ]

    def _calculate_decision(
        self,
        user_id: str,
        amount_requested: int,
        transactions: list,
    ) -> Decision:
        """
        Calculate the risk-based decision.

        Uses the scoring module to evaluate creditworthiness.
        """
        if not transactions:
            return Decision(
                user_id=user_id,
                approved=False,
                credit_limit_cents=0,
                amount_requested_cents=amount_requested,
                amount_granted_cents=0,
                decision_factors=DecisionFactors(
                    avg_daily_balance=0.0,
                    income_ratio=0.0,
                    nsf_count=0,
                    risk_score=0,
                ),
            )

        thin_file_result = handle_thin_file(transactions)

        if thin_file_result is not None:
            approved, credit_limit_cents = thin_file_result
            amount_granted = min(amount_requested, credit_limit_cents) if approved else 0

            avg_daily_balance = calculate_avg_daily_balance(transactions)
            income_ratio = calculate_income_spend_ratio(transactions)
            nsf_count = count_nsf_events(transactions)

            return Decision(
                user_id=user_id,
                approved=approved,
                credit_limit_cents=credit_limit_cents,
                amount_requested_cents=amount_requested,
                amount_granted_cents=amount_granted,
                decision_factors=DecisionFactors(
                    avg_daily_balance=round(avg_daily_balance, 2),
                    income_ratio=round(income_ratio, 2),
                    nsf_count=nsf_count,
                    risk_score=30 if approved else 0,
                ),
            )

        avg_daily_balance = calculate_avg_daily_balance(transactions)
        income_ratio = calculate_income_spend_ratio(transactions)
        nsf_count = count_nsf_events(transactions)
        income_consistency = calculate_income_consistency(transactions)

        # Calculate composite risk score
        risk_score = calculate_risk_score(
            avg_daily_balance=avg_daily_balance,
            income_spend_ratio=income_ratio,
            nsf_count=nsf_count,
            income_consistency=income_consistency,
        )

        # Map score to credit limit
        credit_limit_cents = score_to_credit_limit_cents(risk_score)
        approved = credit_limit_cents > 0
        amount_granted = min(amount_requested, credit_limit_cents) if approved else 0

        # Handle infinite ratio for serialization
        display_ratio = 999.99 if income_ratio == float("inf") else income_ratio

        return Decision(
            user_id=user_id,
            approved=approved,
            credit_limit_cents=credit_limit_cents,
            amount_requested_cents=amount_requested,
            amount_granted_cents=amount_granted,
            decision_factors=DecisionFactors(
                avg_daily_balance=round(avg_daily_balance, 2),
                income_ratio=round(display_ratio, 2),
                nsf_count=nsf_count,
                risk_score=risk_score,
            ),
        )

    def _create_plan(
        self,
        user_id: str,
        decision_id: UUID,
        amount_cents: int,
    ) -> Plan:
        """
        Create a repayment plan with 4 bi-weekly installments.

        Args:
            user_id: The user's identifier
            decision_id: The associated decision ID
            amount_cents: Total amount to be repaid

        Returns:
            A Plan with 4 installments
        """
        plan = Plan(
            user_id=user_id,
            decision_id=decision_id,
            total_cents=amount_cents,
        )

        # Calculate installment amounts (handle rounding)
        base_amount = amount_cents // self.NUM_INSTALLMENTS
        remainder = amount_cents % self.NUM_INSTALLMENTS

        # Create installments
        start_date = date.today() + timedelta(days=self.DAYS_BETWEEN_INSTALLMENTS)

        for i in range(self.NUM_INSTALLMENTS):
            # Add remainder to first installment
            inst_amount = base_amount + (remainder if i == 0 else 0)

            due_date = start_date + timedelta(days=i * self.DAYS_BETWEEN_INSTALLMENTS)

            installment = Installment(
                plan_id=plan.id,
                due_date=due_date,
                amount_cents=inst_amount,
            )
            plan.installments.append(installment)

        return plan
