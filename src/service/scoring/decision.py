"""Main decision-making logic combining all risk factors."""

from typing import List
import uuid

from .models import Transaction, DecisionFactors, Decision
from .risk_factors import (
    calculate_avg_daily_balance,
    calculate_income_spend_ratio,
    count_nsf_events,
    calculate_income_consistency,
)
from .risk_score import calculate_risk_score
from .credit_limit import score_to_credit_limit_cents
from .thin_file import handle_thin_file


def make_decision(
    transactions: List[Transaction],
    amount_requested_cents: int,
    generate_plan_id: bool = True,
) -> Decision:
    """Analyze transactions and return a credit decision."""
    if not transactions:
        return Decision(
            approved=False,
            credit_limit_cents=0,
            amount_granted_cents=0,
            plan_id=None,
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
        amount_granted_cents = min(amount_requested_cents, credit_limit_cents) if approved else 0

        avg_daily_balance = calculate_avg_daily_balance(transactions)
        income_ratio = calculate_income_spend_ratio(transactions)
        nsf_count = count_nsf_events(transactions)

        return Decision(
            approved=approved,
            credit_limit_cents=credit_limit_cents,
            amount_granted_cents=amount_granted_cents,
            plan_id=str(uuid.uuid4()) if approved and generate_plan_id else None,
            decision_factors=DecisionFactors(
                avg_daily_balance=round(avg_daily_balance, 2),
                income_ratio=round(income_ratio, 2),
                nsf_count=nsf_count,
                risk_score=0 if not approved else 30,
            ),
        )

    avg_daily_balance = calculate_avg_daily_balance(transactions)
    income_ratio = calculate_income_spend_ratio(transactions)
    nsf_count = count_nsf_events(transactions)
    income_consistency = calculate_income_consistency(transactions)

    risk_score = calculate_risk_score(
        avg_daily_balance=avg_daily_balance,
        income_spend_ratio=income_ratio,
        nsf_count=nsf_count,
        income_consistency=income_consistency,
    )

    credit_limit_cents = score_to_credit_limit_cents(risk_score)
    approved = credit_limit_cents > 0
    amount_granted_cents = min(amount_requested_cents, credit_limit_cents) if approved else 0

    return Decision(
        approved=approved,
        credit_limit_cents=credit_limit_cents,
        amount_granted_cents=amount_granted_cents,
        plan_id=str(uuid.uuid4()) if approved and generate_plan_id else None,
        decision_factors=DecisionFactors(
            avg_daily_balance=round(avg_daily_balance, 2),
            income_ratio=round(income_ratio, 2) if income_ratio != float('inf') else 999.99,
            nsf_count=nsf_count,
            risk_score=risk_score,
        ),
    )


def explain_decision(decision: Decision) -> str:
    """Generate human-readable explanation of a decision."""
    factors = decision.decision_factors

    lines = []

    if not decision.approved:
        lines.append("Decision: DECLINED")
    else:
        lines.append(f"Decision: APPROVED (${decision.credit_limit_cents / 100:.0f} limit)")

    lines.append(f"Risk Score: {factors.risk_score}/100")
    lines.append("")
    lines.append("Contributing Factors:")

    if factors.avg_daily_balance < 0:
        lines.append(f"  - Average balance: ${factors.avg_daily_balance:.2f} (NEGATIVE - high risk)")
    elif factors.avg_daily_balance < 100:
        lines.append(f"  - Average balance: ${factors.avg_daily_balance:.2f} (low cushion)")
    elif factors.avg_daily_balance < 500:
        lines.append(f"  - Average balance: ${factors.avg_daily_balance:.2f} (moderate cushion)")
    else:
        lines.append(f"  - Average balance: ${factors.avg_daily_balance:.2f} (healthy cushion)")

    if factors.income_ratio < 0.8:
        lines.append(f"  - Income/spend ratio: {factors.income_ratio:.2f} (spending exceeds income)")
    elif factors.income_ratio < 1.0:
        lines.append(f"  - Income/spend ratio: {factors.income_ratio:.2f} (near break-even)")
    elif factors.income_ratio < 1.3:
        lines.append(f"  - Income/spend ratio: {factors.income_ratio:.2f} (sustainable)")
    else:
        lines.append(f"  - Income/spend ratio: {factors.income_ratio:.2f} (healthy margin)")

    if factors.nsf_count == 0:
        lines.append(f"  - NSF events: {factors.nsf_count} (excellent)")
    elif factors.nsf_count <= 2:
        lines.append(f"  - NSF events: {factors.nsf_count} (minor concern)")
    else:
        lines.append(f"  - NSF events: {factors.nsf_count} (significant concern)")

    return "\n".join(lines)
