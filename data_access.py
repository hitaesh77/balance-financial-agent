import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"

# helper functions
def _load_json(filename: str) -> list[dict]:
    """Read a JSON file containing a list of records."""
    
    with (DATA_DIR / filename).open(encoding="utf-8") as file:
        return json.load(file)

# exposed functions
def load_accounts() -> list[dict]:
    """Load all account records."""
    return _load_json("accounts.json")

def load_budgets() -> list[dict]:
    """Load all account records."""
    return _load_json("budgets.json")

def load_transactions() -> list[dict]:
    """Load all account records."""
    return _load_json("transactions.json")

if __name__ == "__main__":
    # main used for testing the functions in this file
    
    for name, loader in [
        ("Accounts", load_accounts),
        ("Budgets", load_budgets),
        ("Transactions", load_transactions),
    ]:
        records = loader()
        print(f"\n{name}: {len(records)} records")
        print(json.dumps(records, indent=2))