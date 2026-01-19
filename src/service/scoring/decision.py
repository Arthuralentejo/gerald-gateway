"""
Decision Engine for Gerald BNPL Approval Engine.

This module orchestrates the complete decision-making process:
1. Check for thin file (special handling)
2. Calculate risk factors from transaction history
3. Generate composite risk score
4. Map score to credit limit
5. Build and return the final decision

This is the main entry point for the scoring module.
"""

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
    """
    Make a BNPL approval decision based on transaction history.

    This is the main entry point for the scoring module. It:
    1. Handles thin-file users with a special policy
    2. Calculates all risk factors from transactions
    3. Generates a composite risk score
    4. Maps the score to a credit limit
    5. Returns a complete Decision object

    Decision Logic:
        - Thin file with NSF: Decline (insufficient positive data)
        - Thin file clean: Approve with $100 starter limit
        - Standard file: Score-based approval with graduated limits

    Amount Granted:
        The amount_granted is the minimum of:
        - amount_requested_cents (what the user asked for)
        - credit_limit_cents (what they qualify for)

    Args:
        transactions: List of bank transactions (90-day history)
        amount_requested_cents: Amount the user is requesting
        generate_plan_id: Whether to generate a plan ID (True for production)

    Returns:
        Decision object with approval status, limits, and factors
    """
    # Handle empty transaction list
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

    # Check for thin file first
    thin_file_result = handle_thin_file(transactions)

    if thin_file_result is not None:
        approved, credit_limit_cents = thin_file_result
        amount_granted_cents = min(amount_requested_cents, credit_limit_cents) if approved else 0

        # Still calculate factors for transparency (even though not used for decision)
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
                risk_score=0 if not approved else 30,  # Thin file doesn't use score
            ),
        )

    # Standard scoring path
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
    """
    Generate a human-readable explanation of a decision.

    This can be used for:
    - Logging and debugging
    - Support team reference
    - (Potentially) User-facing explanations

    Args:
        decision: The decision to explain

    Returns:
        Human-readable explanation string
    """
    factors = decision.decision_factors

    lines = []

    if not decision.approved:
        lines.append("Decision: DECLINED")
    else:
        lines.append(f"Decision: APPROVED (${decision.credit_limit_cents / 100:.0f} limit)")

    lines.append(f"Risk Score: {factors.risk_score}/100")
    lines.append("")
    lines.append("Contributing Factors:")

    # ADB explanation
    if factors.avg_daily_balance < 0:
        lines.append(f"  - Average balance: ${factors.avg_daily_balance:.2f} (NEGATIVE - high risk)")
    elif factors.avg_daily_balance < 100:
        lines.append(f"  - Average balance: ${factors.avg_daily_balance:.2f} (low cushion)")
    elif factors.avg_daily_balance < 500:
        lines.append(f"  - Average balance: ${factors.avg_daily_balance:.2f} (moderate cushion)")
    else:
        lines.append(f"  - Average balance: ${factors.avg_daily_balance:.2f} (healthy cushion)")

    # Income ratio explanation
    if factors.income_ratio < 0.8:
        lines.append(f"  - Income/spend ratio: {factors.income_ratio:.2f} (spending exceeds income)")
    elif factors.income_ratio < 1.0:
        lines.append(f"  - Income/spend ratio: {factors.income_ratio:.2f} (near break-even)")
    elif factors.income_ratio < 1.3:
        lines.append(f"  - Income/spend ratio: {factors.income_ratio:.2f} (sustainable)")
    else:
        lines.append(f"  - Income/spend ratio: {factors.income_ratio:.2f} (healthy margin)")

    # NSF explanation
    if factors.nsf_count == 0:
        lines.append(f"  - NSF events: {factors.nsf_count} (excellent)")
    elif factors.nsf_count <= 2:
        lines.append(f"  - NSF events: {factors.nsf_count} (minor concern)")
    else:
        lines.append(f"  - NSF events: {factors.nsf_count} (significant concern)")

    return "\n".join(lines)
