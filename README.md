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

**64 unit tests** covering:

1. **Risk factor calculations** - ADB, ratio, NSF count with various edge cases
2. **Scoring functions** - Boundary conditions, normalization
3. **Credit limit mapping** - All tiers, edge cases
4. **Thin file handling** - Clean vs. NSF thin files
5. **End-to-end decisions** - Healthy user, risky user, edge cases

```bash
make test           # Run all tests
make coverage       # See coverage report
make test-fast      # Stop on first failure
```

The scoring module has high coverage because it's pure functions - no mocking needed.

---

## What I'd Do Differently

### With More Time

1. **Integration tests** - Test the full API with a real database
2. **Property-based testing** - Use Hypothesis for scoring edge cases
3. **Load testing** - Verify performance under concurrent requests

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
│   └── unit/                   # 64 unit tests
├── Makefile                    # Development commands
├── docker-compose.yml          # PostgreSQL + App
├── Dockerfile                  # Production image
└── pyproject.toml              # Dependencies
```

---

## Make Commands

```bash
make help           # Show all commands

# Development
make test           # Run tests
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
