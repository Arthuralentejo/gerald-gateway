# Gerald Gateway

BNPL Approval & Credit-Limit Service

---

## Quick Start

```bash
# Start everything with Docker
make docker-up

# Or run locally
cp .env.example .env
poetry install --with dev
make db-up
make run-dev
```

**Endpoints:**
- API: http://localhost:8000
- Swagger Docs: http://localhost:8000/docs
- Health: http://localhost:8000/v1/health

**Run Tests:**
```bash
make test          # 64 unit tests
make coverage      # with coverage report
```

---

## Technical Choices

### Why Clean Architecture?

I chose Clean Architecture to demonstrate separation of concerns and testability:

```
src/
├── domain/           # Pure business logic, no dependencies
├── application/      # Use cases, orchestration
├── infrastructure/   # Database, HTTP clients
├── presentation/     # FastAPI routes
└── service/scoring/  # Risk algorithm (isolated module)
```

**Benefits:**
- The scoring algorithm (`src/service/scoring/`) is completely independent - no FastAPI, no SQLAlchemy, just pure Python. This makes it trivial to unit test.
- Swapping PostgreSQL for another database only requires changing `infrastructure/repositories/`.
- The domain layer defines interfaces; infrastructure implements them.

**Trade-off:** More boilerplate than a simple FastAPI app, but scales better and is easier to test.

### Why These Dependencies?

| Dependency | Reason |
|------------|--------|
| **FastAPI** | Async support, automatic OpenAPI docs, Pydantic validation |
| **SQLAlchemy 2.0** | Async support with `asyncpg`, type hints, mature ORM |
| **Pydantic v2** | Fast validation, good error messages, settings management |
| **structlog** | Structured JSON logging for production observability |
| **httpx** | Async HTTP client with timeout/retry support |

### Database Design

Three tables with straightforward relationships:

```
decisions (1) ──── (1) plans (1) ──── (N) installments
```

I used UUIDs as primary keys for distributed-system friendliness, though auto-increment would work fine for this scale.

---

## Risk Scoring Algorithm

### The Core Insight

Gerald's business model is unusual: **zero fees means defaults are pure losses**. Unlike traditional lenders who profit from interest on risky borrowers, Gerald only wins when users successfully repay. This shifts the risk calculus toward being more selective.

### Three-Factor Model

| Factor | Weight | Why This Weight |
|--------|--------|-----------------|
| **NSF Count** | 35% | Most direct predictor - past payment failures predict future ones |
| **Income/Spend Ratio** | 35% | Forward-looking sustainability indicator |
| **Avg Daily Balance** | 30% | Financial cushion, but less predictive than behavior |

**Formula:**
```
Score = (ADB_Score × 0.30) + (Ratio_Score × 0.35) + (NSF_Score × 0.35)
```

Each factor is normalized to 0-100, then weighted. Final score maps to credit limits:

| Score | Limit | Rationale |
|-------|-------|-----------|
| 0-29 | $0 (Decline) | Expected default rate too high |
| 30-44 | $100 | Starter tier, limited exposure |
| 45-59 | $200 | Low risk |
| 60-74 | $300 | Moderate |
| 75-84 | $400 | Good |
| 85-94 | $500 | Very good |
| 95-100 | $600 | Excellent (cap) |

### Key Decisions

**Why allow 1-2 NSFs?**
- Many legitimate users have timing mismatches (payday vs. bill due date)
- Strict zero-tolerance would reject otherwise good customers
- Pattern (3+ NSFs) matters more than isolated incidents

**Why $100 minimum, not lower?**
- $50 is too small for meaningful purchases
- Lower limits have higher operational cost per dollar lent
- $100 is enough to test user behavior without major exposure

**Thin File Handling:**
- <10 transactions or <30 days = thin file
- Clean thin file → $100 starter (include underbanked users)
- Thin file with any NSF → decline (can't offset negative signal with limited data)

**Gig Worker Adjustment:**
- Irregular income ≠ insufficient income
- If income consistency is low but overall ratio is healthy (>1.2), add +10 points
- Prevents unfair penalization of Uber drivers, freelancers, etc.

---

## Code Organization

### Scoring Module (`src/service/scoring/`)

Intentionally isolated from the web framework:

```python
# Pure functions, easy to test
from src.service.scoring import make_decision

decision = make_decision(
    user_id="user_123",
    amount_requested_cents=30000,
    transactions=transactions
)
```

Files:
- `models.py` - Data classes (Transaction, Decision)
- `risk_factors.py` - Calculate ADB, ratio, NSF count
- `risk_score.py` - Normalize factors to 0-100 scores
- `credit_limit.py` - Map score to dollar limit
- `thin_file.py` - Edge case handling
- `decision.py` - Orchestrates the above

### API Layer (`src/presentation/`)

Standard FastAPI patterns:
- Pydantic schemas for request/response validation
- Dependency injection for services
- Middleware for error handling and request context

### Infrastructure (`src/infrastructure/`)

- **Repositories:** Abstract database access behind interfaces
- **Clients:** HTTP clients with retry logic and exponential backoff

---

## Testing Strategy

### Unit Tests (64 tests)

Located in `tests/unit/`, these test the scoring module:

1. **Risk factor calculations** - ADB, ratio, NSF count with various edge cases
2. **Scoring functions** - Boundary conditions, normalization
3. **Credit limit mapping** - All tiers, edge cases
4. **Thin file handling** - Clean vs. NSF thin files
5. **End-to-end decisions** - Healthy user, risky user, edge cases

### Integration Tests

Located in `tests/integration/`, these test the full API:

1. **Decision API** (`test_decision_api.py`)
   - `test_user_good_approval` - Happy path approval with plan
   - `test_user_overdraft_decline` - Users with NSFs are declined
   - `test_user_highutil_capped_to_limit` - Requested amount capped to credit limit
   - `test_user_thin_file` - Thin file policy handling

2. **Persistence** (`test_persistence.py`)
   - `test_plan_retrieval` - GET /v1/plan/{plan_id} returns correct schedule
   - `test_decision_history` - GET /v1/decision/history shows audit trail

3. **Resilience** (`test_resilience.py`)
   - `test_bank_api_failure` - Returns 503 on upstream failure
   - `test_webhook_failure_does_not_block_decision` - Decisions succeed even if webhook fails

4. **Metrics** (`test_metrics.py`)
   - `test_metrics_incremented` - Counters and gauges are updated
   - `test_metrics_endpoint_returns_prometheus_format` - /metrics returns valid format

### Running Tests

```bash
make test              # Run all tests (unit + integration)
make test-unit         # Run unit tests only
make test-integration  # Run integration tests only
make test-fast         # Stop on first failure
make coverage          # Run tests with coverage report
```

The scoring module has high coverage because it's pure functions - no mocking needed.

---

## What I'd Do Differently

### With More Time

1. **Property-based testing** - Use Hypothesis for scoring edge cases
2. **Load testing** - Verify performance under concurrent requests
3. **End-to-end tests with real PostgreSQL** - Current integration tests use SQLite in-memory

### With More Data

1. **Recency weighting** - Recent NSFs should matter more than old ones
2. **ML model** - Train on actual default outcomes to optimize weights
3. **Feature expansion** - Add transaction categories, merchant types

### Production Considerations

1. **Caching** - Cache Bank API responses (they're 90-day windows)
2. **Circuit breaker** - For Bank API failures
3. **Rate limiting** - Prevent abuse
4. **Audit logging** - Compliance requirement for financial decisions

---

## Project Structure

```
gerald-gateway/
├── src/
│   ├── main.py                 # FastAPI app entry point
│   ├── core/                   # Config, dependencies, logging
│   ├── domain/                 # Entities, interfaces, exceptions
│   ├── application/            # Services, DTOs
│   ├── infrastructure/         # Repositories, HTTP clients
│   ├── presentation/           # Routes, schemas, middleware
│   └── service/scoring/        # Risk algorithm (isolated)
├── tests/
│   ├── unit/                   # 64 unit tests for scoring module
│   └── integration/            # API integration tests
│       ├── test_decision_api.py
│       ├── test_persistence.py
│       ├── test_resilience.py
│       └── test_metrics.py
├── Makefile                    # Development commands
├── docker-compose.yml          # PostgreSQL + App
├── Dockerfile                  # Production image
└── pyproject.toml              # Dependencies
```

---

## Make Commands

```bash
make help           # Show all commands

# Testing
make test              # Run all tests (unit + integration)
make test-unit         # Run unit tests only
make test-integration  # Run integration tests only
make test-fast         # Stop on first failure
make coverage          # Generate coverage report

# Development
make lint           # Check code quality
make format         # Format code

# Docker
make docker-up      # Start app + database
make docker-down    # Stop services
make docker-logs    # View logs

# Local
make run            # Run server with hot reload
make db-up          # Start PostgreSQL only
```

---

## API Examples

**Request a decision:**
```bash
curl -X POST http://localhost:8000/v1/decision \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user_123", "amount_cents_requested": 30000}'
```

**Response (approved):**
```json
{
  "approved": true,
  "credit_limit_cents": 40000,
  "amount_granted_cents": 30000,
  "plan_id": "550e8400-e29b-41d4-a716-446655440000",
  "decision_factors": {
    "avg_daily_balance": 850.00,
    "income_ratio": 1.45,
    "nsf_count": 1,
    "risk_score": 72
  }
}
```

**Response (declined):**
```json
{
  "approved": false,
  "credit_limit_cents": 0,
  "amount_granted_cents": 0,
  "plan_id": null,
  "decision_factors": {
    "avg_daily_balance": -50.00,
    "income_ratio": 0.75,
    "nsf_count": 4,
    "risk_score": 18
  }
}
```

---

## Questions & Answers

### 1. How would Product diagnose an approval rate drop?

**Scenario:** Approval rate drops from 35% to 25%. Is it a bug or legitimate user quality change?

**Diagnostic approach:**

1. **Check score distribution shift**
   - Pull histogram of composite scores before/after the drop
   - If the entire distribution shifted left → user quality changed
   - If distribution is bimodal or has gaps → likely a bug

2. **Compare individual factor distributions**
   ```sql
   -- Compare ADB, ratio, NSF distributions
   SELECT
     date_trunc('day', created_at) as day,
     avg(score_numeric) as avg_score,
     percentile_cont(0.5) WITHIN GROUP (ORDER BY score_numeric) as median
   FROM bnpl_decisions
   GROUP BY 1
   ORDER BY 1;
   ```
   - If one factor (e.g., NSF) spiked while others stayed flat → investigate that factor
   - If all factors shifted proportionally → user quality change

3. **Segment by acquisition channel**
   - Did the drop correlate with a new marketing campaign?
   - Are users from a specific source (referral, paid ads) driving the change?

4. **Check upstream data quality**
   - Is the Bank API returning incomplete transaction data?
   - Are there parsing errors in the transaction processor?
   - Check `bank_fetch_failures_total` metric for spikes

5. **Review recent code changes**
   - Any deploys in the 24h before the drop?
   - Check git history for scoring logic changes

**Quick triage:** If approval rate dropped but average score of *approved* users stayed the same, it's likely a threshold issue. If average score dropped across all users, it's a user quality or data issue.

---

### 2. What would change for higher-income users?

If Gerald pivoted to target higher-income users instead of paycheck-to-paycheck:

**Scoring changes:**

| Parameter | Current (Low-Income) | Higher-Income |
|-----------|---------------------|---------------|
| `SCORING_ADB_LOW_THRESHOLD` | $100 | $500 |
| `SCORING_ADB_MODERATE_THRESHOLD` | $500 | $2,000 |
| `SCORING_ADB_GOOD_THRESHOLD` | $1,500 | $5,000 |
| `SCORING_WEIGHT_ADB` | 0.30 | 0.20 |
| `SCORING_WEIGHT_NSF` | 0.35 | 0.25 |
| Max credit limit | $600 | $2,000+ |

**Rationale:**
- Higher-income users have larger balances, so thresholds must scale up
- NSF events are rarer and more significant for this segment (over-index on them)
- ADB becomes less predictive (most will have "good" balances)
- Higher limits make sense since average transaction sizes are larger

**New factors to consider:**
- Debt-to-income ratio (they may have mortgages, car payments)
- Credit utilization patterns
- Savings rate (income - spending) / income

**Business model implications:**
- Higher limits = higher default exposure per user
- May need credit bureau data to maintain <5% default rate
- Cornerstore revenue per user likely higher (larger baskets)

---

### 3. How would you explain a decline to a frustrated user?

**Principles:**
- Be specific enough to be actionable
- Don't reveal exact thresholds (prevents gaming)
- Provide a path forward
- Acknowledge their frustration

**Example response:**

> "We reviewed your recent banking activity and aren't able to approve you at this time. This decision was based on factors like recent overdrafts, the balance between your income and spending, and your account history length.
>
> **What you can do:**
> - Avoid overdrafts for the next 30 days
> - Ensure regular deposits are visible in your connected account
> - You can reapply in 30 days
>
> We know this is frustrating. Our goal is to set you up for success, and approving credit you can't comfortably repay wouldn't help either of us."

**What we expose in the API:**
```json
{
  "decision_factors": {
    "avg_daily_balance": -50.00,  // "Your balance has been low"
    "income_ratio": 0.75,         // "Spending exceeded income"
    "nsf_count": 4,               // "Recent overdrafts"
    "risk_score": 18              // Internal use only
  }
}
```

Support can use `decision_factors` to give specific guidance without revealing scoring thresholds.

---

### 4. Business Math: Break-even analysis

**Given:**
- Cornerstore revenue per approved user: $50
- Default rate: 3%
- Average credit limit: $300 (assumption based on our tiers)

**Question:** What's the break-even approval rate?

**Analysis:**

First, let's understand the economics per approved user:

```
Revenue per approved user     = $50 (Cornerstore margin)
Expected loss per user        = Default Rate × Average Limit
                              = 3% × $300
                              = $9

Net revenue per approved user = $50 - $9 = $41
```

Since net revenue per approved user is positive ($41), **any approval rate > 0% is profitable** at these assumptions.

**The real question is: at what default rate do we break even?**

```
Break-even: Revenue = Expected Loss
$50 = Default Rate × $300
Default Rate = $50 / $300 = 16.7%
```

**Interpretation:**
- Our target 3% default rate provides a **$41 margin per user** (82% of Cornerstore revenue retained)
- We could tolerate up to **16.7% default rate** before losing money
- The 5% default ceiling in requirements gives us **$35 margin per user** (70% retained)

**Sensitivity analysis:**

| Default Rate | Loss per User | Net Revenue | Margin |
|--------------|---------------|-------------|--------|
| 1% | $3 | $47 | 94% |
| 3% | $9 | $41 | 82% |
| 5% | $15 | $35 | 70% |
| 10% | $30 | $20 | 40% |
| 16.7% | $50 | $0 | 0% (break-even) |

**Why this matters for approval rate decisions:**

If we're too conservative (low approval rate), we leave money on the table. If we're too aggressive, defaults eat our margin. The optimal point is where marginal revenue from one more approval equals marginal loss from increased defaults.

With our current model targeting 40% approval and <5% default, we expect:
```
Per 100 applicants:
- 40 approved
- 40 × $35 net = $1,400 total margin
- vs. rejecting everyone = $0
```

---

### 5. How would the model change with more data?

**With 6 months of transaction history (instead of 90 days):**

```python
# Recency weighting - recent behavior matters more
def weighted_nsf_count(transactions, days=180):
    recent_weight = 2.0   # Last 30 days
    mid_weight = 1.0      # 30-90 days
    old_weight = 0.5      # 90-180 days

    # Weight NSFs by recency
    weighted_count = sum(
        recent_weight if days_ago < 30 else
        mid_weight if days_ago < 90 else
        old_weight
        for t in transactions if t.nsf
    )
    return weighted_count
```

**Benefits:**
- Detect recovery patterns (was struggling, now stable)
- Seasonal income patterns (tax refunds, bonuses)
- More confident thin-file identification
- Trend analysis (improving vs. deteriorating)

---

**With credit bureau data:**

| New Factor | Weight | Rationale |
|------------|--------|-----------|
| Credit score | 25% | Proven predictor across industries |
| Credit utilization | 15% | High utilization = higher risk |
| Payment history | 20% | Broader view than bank NSFs alone |
| Account age | 5% | Longer history = more stable |

**Adjusted weights:**
```python
# With bureau data, reduce reliance on bank-only signals
SCORING_WEIGHT_ADB = 0.15      # Was 0.30
SCORING_WEIGHT_RATIO = 0.20    # Was 0.35
SCORING_WEIGHT_NSF = 0.15      # Was 0.35
SCORING_WEIGHT_BUREAU = 0.50   # New
```

**Benefits:**
- Approve thin-file users with good credit history
- Catch users with NSFs at *other* banks
- Industry-standard risk signal

---

**With rent/utility payment history:**

This is especially valuable for Gerald's demographic (underbanked users who may lack traditional credit):

```python
# Alternative credit data
def score_alternative_credit(rent_payments, utility_payments):
    """
    On-time rent/utility payments are strong positive signals
    for users without traditional credit history.
    """
    on_time_rate = (on_time_payments / total_payments)

    if on_time_rate >= 0.95:
        return 90  # Excellent
    elif on_time_rate >= 0.85:
        return 70  # Good
    elif on_time_rate >= 0.75:
        return 50  # Fair
    else:
        return 30  # Poor
```

**Benefits:**
- Include responsible renters who lack credit cards
- Reduce thin-file decline rate
- Fairer to users without traditional banking relationships
- Aligns with Gerald's mission to serve underbanked users

---

## Configuration

All scoring parameters are configurable via environment variables:

```bash
# Core thresholds
SCORING_APPROVAL_THRESHOLD=30
SCORING_THIN_FILE_LIMIT_CENTS=10000

# Factor weights (must sum to 1.0)
SCORING_WEIGHT_ADB=0.30
SCORING_WEIGHT_RATIO=0.35
SCORING_WEIGHT_NSF=0.35

# Credit limit tiers (JSON)
SCORING_CREDIT_LIMIT_TIERS_JSON=[[0,29,0],[30,44,10000],[45,59,20000],[60,74,30000],[75,84,40000],[85,94,50000],[95,100,60000]]
```

See `.env.example` for all available settings.

---

## Local Monitoring Dashboard

A Grafana + Prometheus stack is included for local monitoring and development visualization.

### Running the Dashboard

```bash
# Start the monitoring stack
docker compose -f docker-compose.monitoring.yml up -d

# Access the dashboards
# Grafana: http://localhost:3000 (admin/admin)
# Prometheus: http://localhost:9091
```

Make sure the main application is running (`make run-dev` or `make docker-up`) so Prometheus can scrape metrics from `localhost:8000/metrics`.

### Dashboard Panels

The **Gerald BNPL Dashboard** has two sections:

#### Business Metrics
| Panel | Description |
|-------|-------------|
| **Approval Rate** | Percentage of decisions resulting in approval (gauge) |
| **Average Credit Limit** | Mean credit limit for approved users in dollars |
| **Decisions by Outcome** | Time series showing approved vs declined decisions |
| **Credit Limit Distribution** | Breakdown of approved limits by tier ($100-$600) |

#### Engineering Metrics
| Panel | Description |
|-------|-------------|
| **Decision Latency (p95)** | 95th percentile response time for `/v1/decision` endpoint |
| **Bank API Health** | Success rate of Bank API calls (should be >99%) |
| **Webhook Delivery** | Success vs failure count for webhook notifications |

### Interpreting the Metrics

- **Approval Rate ~40%**: Target is 40% approval with <5% default. Significant drops may indicate user quality changes or bugs.
- **Decision Latency <200ms**: Most latency comes from Bank API calls. If p95 exceeds 500ms, check upstream connectivity.
- **Bank API Health >99%**: The system includes retry logic with exponential backoff. Persistent failures indicate upstream issues.
- **Credit Limit Distribution**: Healthy distribution should show spread across tiers. Clustering at $100 may indicate thin-file heavy traffic.

### Stopping the Dashboard

```bash
docker compose -f docker-compose.monitoring.yml down

# To remove stored data as well
docker compose -f docker-compose.monitoring.yml down -v
```
