# Input Data Formats

This directory holds the canonical seed/test fixtures for Portfolio Copilot, and
this README documents the format of every input the system ingests so you can
supply your own data.

There are **two input shapes**, because the data lands in two stores:

| Input | Format | Loaded into | Fixture(s) here |
|---|---|---|---|
| **Account transactions** | **CSV** | BigQuery (`portfolio_copilot.<table>`) | `chase_transactions.csv`, `checking_transactions.csv` |
| **Holdings** | JSON | Firestore (`holdings/<user_id>`) | `holdings.json` |
| **Liabilities** | JSON | Firestore (`liabilities/<user_id>`) | `liabilities.json` |
| **Investment Policy Statement (IPS)** | JSON | Firestore (`ips/<ips_id>_v<version>`) | `ips.json` |

> Only **transactions** use CSV. Holdings, liabilities, and the IPS are JSON
> documents (Firestore stores documents, not tabular rows). The JSON files here
> double as the `*.json` fixtures validated against [`/schemas`](../schemas)
> during loading — those schema files are the source of truth; this README is
> the human-readable explanation.

Load everything with:

```bash
./scripts/load_test_data.sh <PROJECT_ID> <REGION>
# validate the fixtures against the schemas without uploading:
python3 scripts/load_test_data.py --dry-run
```

See [`install/README.md`](../install/README.md) for the full setup flow.

---

## 1. Account transactions — CSV

Transaction history for spending and cash-flow analysis (categorization, savings
rate, reserve months, anomaly detection). Loaded into BigQuery so the Spending
Analysis skill can run NL-to-SQL queries over it; every query is scoped to the
caller's `user_id`.

**Where it goes:** BigQuery dataset `portfolio_copilot`, table
`checking_transactions` (default) or `chase_transactions`. `setup_bigquery.sh`
creates both tables; `load_test_data.py` loads a CSV with `WRITE_TRUNCATE`
(replace) using an explicit schema — the CSV is **not** autodetected, so column
order and the header row matter.

**File rules:**
- UTF-8, comma-separated, **one header row** (it is skipped on load).
- Columns must appear in the order below.

**Columns**

| # | Column | Type | Required | Notes |
|---|---|---|---|---|
| 1 | `user_id` | STRING | ✅ | Owner of the row. Queries are filtered by this; it scopes every user's data. |
| 2 | `transaction_date` | DATE | ✅ | `YYYY-MM-DD`. |
| 3 | `amount` | FLOAT64 | ✅ | Signed. **Positive = income/inflow, negative = expense/outflow.** |
| 4 | `description` | STRING | optional | Raw description from the statement (may be blank). |
| 5 | `raw_category` | STRING | optional | The institution's own category, pre-normalization (may be blank). |
| 6 | `normalized_category` | STRING | ✅ | Category in the app's standard taxonomy (see below). |

> `account_type` appears in [`account-transaction.schema.json`](../schemas/account-transaction.schema.json)
> but is **not** a column of the BigQuery transactions table — pick the table
> (`checking_transactions` vs `chase_transactions`) to represent the account
> instead. Keep the CSV to the six columns above.

**Normalized category taxonomy.** `normalized_category` is stored as a free
string, but Spending Analysis expects the app's standard set. Use `income` for
inflows; everything else is an outflow:

```
income · housing · utilities · groceries · dining · transportation ·
entertainment · subscriptions · healthcare · travel · shopping ·
transfers · fees · other
```

**Example** (`chase_transactions.csv`):

```csv
user_id,transaction_date,amount,description,raw_category,normalized_category
demo_user,2026-05-01,6000.00,EMPLOYER PAYROLL DIRECT DEP,Income,income
demo_user,2026-05-02,-2000.00,MAIN STREET APARTMENTS RENT,Mortgage & Rent,housing
demo_user,2026-05-05,-150.00,CITY POWER & WATER,Utilities,utilities
demo_user,2026-05-08,-245.50,WHOLE FOODS MARKET #102,Groceries,groceries
demo_user,2026-05-12,-15.00,NETFLIX.COM STREAMING,Entertainment,subscriptions
```

---

## 2. Liabilities — JSON

Current debts (credit cards, mortgage, loans). Current-state, **not** versioned —
overwritten as balances change. Self-reported (a transaction feed shows
payments, not balances or APRs), captured during onboarding. Stored at Firestore
`liabilities/<user_id>`. Schema: [`liabilities.schema.json`](../schemas/liabilities.schema.json).

**Top level:** `user_id` (string), `as_of` (RFC 3339 date-time), `liabilities`
(array), `total_liabilities_usd` (number — sum of balances).

**Each liability** — required: `liability_id`, `type`, `balance_usd`,
`minimum_payment_usd`.

| Field | Type | Notes |
|---|---|---|
| `liability_id` | string | Stable id, e.g. `liab_cc_001`. |
| `type` | enum | `credit_card` · `mortgage` · `auto_loan` · `student_loan` · `heloc` · `other`. |
| `description` | string | e.g. `"Chase Sapphire Reserve"`. |
| `balance_usd` | number ≥ 0 | Outstanding balance. |
| `interest_rate_percent` | number ≥ 0 | APR. Absent from transaction data — must be self-reported. |
| `minimum_payment_usd` | number ≥ 0 | Minimum monthly payment. |

```json
{
  "user_id": "demo_user",
  "as_of": "2026-08-01T00:00:00Z",
  "liabilities": [
    {
      "liability_id": "liab_cc_001",
      "type": "credit_card",
      "description": "Chase Sapphire Reserve",
      "balance_usd": 4500,
      "interest_rate_percent": 24.99,
      "minimum_payment_usd": 150
    }
  ],
  "total_liabilities_usd": 4500
}
```

---

## 3. Holdings — JSON

Current portfolio positions. Current-state, overwritten as holdings change.
Stored at Firestore `holdings/<user_id>`. Schema:
[`holdings.schema.json`](../schemas/holdings.schema.json).

**Top level:** `user_id` (string), `as_of` (RFC 3339 date-time), `positions`
(array), `cash_usd` (number), `total_value_usd` (number — Σ position
`market_value_usd` + `cash_usd`; the denominator for drift and concentration
checks).

**Each position** — required: `ticker`, `quantity`, `asset_class`,
`market_value_usd`.

| Field | Type | Notes |
|---|---|---|
| `ticker` | string | e.g. `VTI`. |
| `quantity` | number ≥ 0 | Shares/units held. |
| `asset_class` | string | **Must match one of the IPS's `target_allocation` asset classes** or drift comparison has nothing to compare against (e.g. `Equity`, `Bonds`, `Crypto`). |
| `market_value_usd` | number ≥ 0 | Current market value of the position. |
| `account_type` | enum | `taxable` · `retirement`. |

```json
{
  "user_id": "demo_user",
  "as_of": "2026-08-01T00:00:00Z",
  "positions": [
    { "ticker": "VTI", "quantity": 400, "asset_class": "Equity", "market_value_usd": 110000, "account_type": "taxable" },
    { "ticker": "BND", "quantity": 400, "asset_class": "Bonds", "market_value_usd": 35000, "account_type": "taxable" }
  ],
  "cash_usd": 20000,
  "total_value_usd": 165000
}
```

---

## 4. Investment Policy Statement (IPS) — JSON

The reference policy the whole system plans against. Normally produced by the
Goals & Onboarding interview, but a seed fixture (`ips.json`) lets you preload
one. **Versioned/append-only** — a change creates a new version; the old one is
marked `superseded`, never edited in place. Stored at Firestore
`ips/<ips_id>_v<version>` (e.g. `ips/ips_demo_001_v1`). Schema:
[`ips.schema.json`](../schemas/ips.schema.json), explained field-by-field in
[`docs/spec/03-contracts.md`](../docs/spec/03-contracts.md).

Key fields: `ips_id`, `user_id`, `version`, `status` (`active`/`superseded`),
`risk_tolerance`, `time_horizon_years`, `goals[]`, `liquidity_needs`,
`target_allocation[]` (asset-class **bands** with `target_percent` /
`min_percent` / `max_percent`), and `constraints` (`concentration_limit_percent`,
`excluded_tickers`, `excluded_sectors`). See `ips.json` for a complete example.

---

## Validating your data

`load_test_data.py` validates every JSON fixture against its schema before
loading, and loads the transactions CSV with a fixed BigQuery schema. To check
your JSON documents without touching GCP:

```bash
python3 scripts/load_test_data.py --dry-run
```

The [`/schemas`](../schemas) JSON Schema files are the source of truth; if a
field here and a schema ever disagree, the schema wins — fix this README.
