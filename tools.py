"""
tools.py

This file contains the tools that the financial agent I am 
building will have access to. For example, getting user
budgets, bank accoutn balances, transaction data, etc...
"""

from datetime import date, timedelta
from data_access import load_accounts, load_budgets, load_transactions

# Fixed date for mock dataset, not curr date
DEMO_DATE = date(2026, 9, 22)

# Helper functions
def _period_start(period: str) -> date:
    """Find the inclusive start date; weeks begin on Monday."""

    if period == "today":
        return DEMO_DATE
    if period == "this_week":
        return DEMO_DATE - timedelta(days=DEMO_DATE.weekday())
    if period == "this_month":
        return DEMO_DATE.replace(day=1)
    if period == "last_month":
        return (DEMO_DATE.replace(day=1) - timedelta(days=1)).replace(day=1)
    
    raise ValueError("Use today, this_week, this_month, or last_month.")


def _category_error(category: str) -> dict | None:
    """Recognize categories found in either budgets or transactions."""

    categories = set()
    for record in load_budgets():
        categories.add(record["category"])

    for record in load_transactions():
        categories.add(record["category"])

    if category not in categories:
        return {
            "error": f"Unknown category: {category}",
            "available_categories": sorted(categories),
        }
    return None

# Tools
def get_accounts() -> dict:
    """Return individual account balances and their combined total."""

    accounts = load_accounts()

    total_balance_cents = sum(
        account["balance_cents"] for account in accounts
    )

    return {
        "accounts": accounts,
        "total_balance_cents": total_balance_cents,
        "currency": "USD",
    }

def get_recent_transactions(category: str | None = None, limit: int = 5) -> dict:
    """Return the latest completed purchases, optionally filtered by category."""

    # check if limit of recent transaction is possible
    if type(limit) is not int or limit < 1:
        return {"error": "limit must be a positive integer."}

    # check if category exists if requested
    if category is not None:
        category = category.strip().lower()
        error = _category_error(category)
        if error:
            return error

    # get transactions and sort
    transactions = [
        transaction for transaction in load_transactions()
        if date.fromisoformat(transaction["date"]) <= DEMO_DATE
        and (category is None or transaction["category"] == category)
    ]
    transactions.sort(key=lambda transaction: transaction["date"], reverse=True)

    return {
        "transactions": transactions[:limit],
        "as_of_date": DEMO_DATE.isoformat(),
        "currency": "USD",
    }

def get_spending(category: str, period: str = "this_month") -> dict:
    """Sum recorded purchases within an inclusive date range."""

    category = category.strip().lower()
    error = _category_error(category)
    if error:
        return error

    try:
        start = _period_start(period)
    except ValueError as error:
        return {"error": str(error)}

    end = DEMO_DATE
    if period == "last_month":
        end = DEMO_DATE.replace(day=1) - timedelta(days=1)

    transactions = [
        transaction for transaction in load_transactions()
        if transaction["category"] == category
        and start <= date.fromisoformat(transaction["date"]) <= end
    ]
    return {
        "category": category,
        "period": period,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "spent_cents": sum(item["amount_cents"] for item in transactions),
        "transaction_count": len(transactions),
        "currency": "USD",
    }

def get_budget(category: str) -> dict:
    """Return this month's limit, recorded spending, and remaining budget."""
    category = category.strip().lower()
    month = DEMO_DATE.strftime("%Y-%m")
    budget = next(
        (item for item in load_budgets()
         if item["category"] == category and item["month"] == month),
        None,
    )
    if budget is None:
        return {"error": f"No budget found for {category} in {month}."}

    spending = get_spending(category, "this_month")
    if "error" in spending:
        return spending
    return {
        "category": category,
        "month": month,
        "as_of_date": DEMO_DATE.isoformat(),
        "limit_cents": budget["limit_cents"],
        "spent_cents": spending["spent_cents"],
        "remaining_cents": budget["limit_cents"] - spending["spent_cents"],
        "currency": "USD",
    }


if __name__ == "__main__":
    import json

    examples = {
        "Accounts": get_accounts(),
        "Recent purchases": get_recent_transactions(),
        "Dining this week": get_spending("dining", "this_week"),
        "Dining budget": get_budget("dining"),
        "Unknown category": get_budget("groceries"),
    }
    for name, result in examples.items():
        print(f"\n{name}")
        print(json.dumps(result, indent=2))
