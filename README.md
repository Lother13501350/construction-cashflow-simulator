# Construction Cash Flow Simulator

Model a contractor's month-by-month cash position on a construction project and
see how payment terms change the money you need to borrow.

Payment delays, retention and advance payments decide how long a contractor
carries project costs before the owner pays. This tool takes a cost-loaded
schedule and a set of payment terms, simulates borrowing and interest month by
month, and reports the funding gap, the peak loan balance and the total
financing cost for each scenario, so payment terms can be compared before a
contract is signed.

![Loan balance under three payment scenarios](output/fig_loan_balance.png)

## Features

- **Item-level cost loading**: allocate the cost and contract price of each
  estimate item to months from its progress plan, with an optional payment lag
  per item.
- **Separate cost, billing and cash tracking**: certified billing is never
  counted as cash; receipts arrive only after the payment delay.
- **Retention and advance payments**: retention is withheld from every
  certified payment and released in a chosen month; an advance payment is
  recovered as a share of each certified payment, capped at the unrecovered
  balance.
- **Borrowing and interest**: shortfalls are borrowed, interest accrues
  monthly, unpaid interest is capitalised, and surplus cash repays the loan.
- **Scenario comparison**: run any number of payment scenarios against the same
  project and get a summary table, monthly ledgers and charts.
- **Built-in checks**: every run verifies that cash is conserved and that
  retention and advance payments are fully settled.

## Quick start

Requires Python 3.10 or later.

```bash
git clone https://github.com/Lother13501350/construction-cashflow-simulator.git
cd construction-cashflow-simulator
python -m venv .venv
```

Activate the environment and install dependencies:

```powershell
# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux
source .venv/bin/activate
```

```bash
pip install -r requirements.txt
python src/run.py
```

This runs every scenario in `data/scenarios.csv` against the sample project and
writes the results to `output/`. To explore the results interactively, open
`main.ipynb` with Jupyter and run all cells:

```bash
jupyter notebook main.ipynb
```

## Usage

### 1. Describe the project

**`data/items.csv`**: one row per estimate item.

| Column | Type | Description |
|---|---|---|
| `item_id` | int | Unique item identifier |
| `name` | str | Item description |
| `category` | str | Grouping label, for reporting only |
| `cost` | number | Contractor's cost to perform the item |
| `contract_price` | number | Amount billable to the owner for the item |
| `cost_pay_lag` | int ≥ 0 | Months between doing the work and paying for it (0 = paid at the start of the same month) |

**`data/progress.csv`**: one row per item, one column per month (`M1`, `M2`,
…). Each value is the fraction of the item completed in that month. Each row
must sum to 1; the loader rejects the file otherwise and names the offending
items.

### 2. Define payment scenarios

**`data/scenarios.csv`**: one row per scenario.

| Column | Example | Description |
|---|---|---|
| `scenario` | `A_延遲2月` | Scenario name, also used in output file names |
| `payment_delay` | `2` | Months from certification to receipt (received at month end) |
| `retention_rate` | `0.05` | Share of each certified payment withheld as retention |
| `retention_release_month` | `15` | Month in which all retention is released (month end) |
| `advance_rate` | `0.10` | Advance payment as a share of the total contract price, received before work starts (month 0) |
| `advance_recovery_rate` | `0.10` | Share of each certified payment deducted to recover the advance |
| `initial_cash` | `0` | Cash on hand at month 0 |
| `annual_rate` | `0.06` | Annual interest rate on borrowing |

Add a row to compare another scenario; no code changes are needed.

### 3. Run

```bash
python src/run.py
```

### Output

| File | Content |
|---|---|
| `output/summary.csv` | One row per scenario: maximum funding gap, peak loan balance, total interest, ending cash and ending loan |
| `output/ledger_<scenario>.csv` | Monthly ledger: costs paid, certified billing, retention, advance recovery, receipts, borrowing, interest, repayment, loan and cash balances |
| `output/item_cost_incurred.csv` | Cost allocated to each item and month |
| `output/item_certified_billing.csv` | Certified billing for each item and month |
| `output/fig_cumulative_cashflow.png` | Cumulative cash flow, excluding interest |
| `output/fig_loan_balance.png` | Loan balance over time |
| `output/fig_s_curve.png` | Cumulative cost and billing S-curves |

## How it works

Time runs in whole months. Month 0 is the period before work starts, when an
advance payment, if any, is received. Every month then follows the same
sequence:

1. **Start of month**: pay the costs due. If cash is short, borrow the
   difference.
2. **During the month**: interest accrues on the loan balance at
   `annual_rate / 12`.
3. **End of month**: receive the payments due, pay the month's interest
   (borrowing any shortfall, which accrues interest from the next month), and
   use the remaining cash to repay the loan.

Work certified in month *t* is received at the end of month
*t* + `payment_delay`, net of retention and advance recovery:

```
received = certified − certified × retention_rate − advance recovery
advance recovery = min(certified × advance_recovery_rate, unrecovered advance)
```

All retention is released at the end of `retention_release_month`. The
simulation runs until every cost has been paid and every receipt, including
retention, has arrived.

### Metrics

| Metric | Definition |
|---|---|
| Maximum funding gap | Largest value of cumulative costs paid minus cumulative receipts minus initial cash, measured after each start-of-month payment. Excludes interest. |
| Peak loan balance | Largest loan balance reached, including capitalised interest. |
| Total interest | Sum of monthly interest charges. |
| Ending cash / ending loan | Balances at the end of the final month. |

The gap between the maximum funding gap and the peak loan balance is the
interest capitalised up to the peak.

## Example results

The sample project is a three-storey reinforced-concrete house with 30
estimate items: NT$10,000,000 contract price, NT$9,000,000 cost, completed in
month 9, with 5% retention released in month 15 and borrowing at 6% a year.

| Payment terms | Max funding gap | Peak loan | Total interest |
|---|---:|---:|---:|
| Paid 2 months after certification | 3,690,498 | 3,785,932 | 129,213 |
| Paid 1 month after certification | 2,592,998 | 2,648,321 | 82,956 |
| Paid after 2 months, with a 10% advance | 3,249,393 | 3,313,824 | 93,545 |

Paying one month sooner cuts the peak loan by 30%; a 10% advance payment cuts
it by 12.5%.

The sample data is synthetic and does not describe a real project. It is
generated by `src/make_case.py`; running that script overwrites the files in
`data/`.

## Validation

### Automated tests

```bash
python -m pytest
```

The suite includes two small projects whose expected results were calculated
by hand (the working is written out in each test's docstring), along with
tests for the advance recovery cap, payment lags, input validation, and
conservation checks on the sample project.

### Independent spreadsheet check

`validation/` rebuilds the same model as an Excel workbook in which every
monthly value is a spreadsheet formula, then compares Excel's results with the
Python results cell by cell. For the sample project, all 576 compared values
match, with a maximum difference of about 2 × 10⁻¹² (floating-point rounding
only).

Recalculating the workbook requires Microsoft Excel on Windows:

```powershell
python validation/build_excel_check.py
powershell -ExecutionPolicy Bypass -File validation/recalc_excel.ps1
python validation/compare.py
```

The comparison is written to `validation/comparison_monthly.csv` and
`validation/comparison_summary.csv`.

## Project structure

```
├── data/            Input files: items, progress plan, payment scenarios
├── output/          Generated results and charts
├── src/
│   ├── cashflow.py      Simulation engine
│   ├── run.py           Command-line entry point
│   ├── make_case.py     Sample data generator
│   └── make_notebook.py Notebook generator
├── tests/           pytest suite
├── validation/      Excel cross-check and comparison scripts
├── main.ipynb       Interactive walkthrough
└── requirements.txt
```

## Limitations

- Monthly resolution: costs and receipts are assumed to fall at the start or
  end of a month.
- No interest is earned on positive cash balances.
- A single interest rate with no credit limit.
- The contract price is fixed; change orders are not modelled.
- Retention is released in a single month.

## Roadmap

- Activity-based schedule input (start month and duration), with a comparison
  of early-start and late-start schedules
- Sensitivity analysis across payment delay, retention rate and interest rate
- Per-item payment terms for subcontractors and suppliers

## Contributing

- Run `python -m pytest` before every commit.
- Write commit messages in English following
  [Conventional Commits](https://www.conventionalcommits.org/), for example
  `feat(engine): add interest on positive cash balances`.
- Keep each commit to one logical change.
