# Balance Financial Agent

A small Python prototype for Balance, our senior design budgeting assistant.
The project explores LLM tool calling: a model chooses a financial tool,
Python runs it against mock data, and the model explains the result.

The assistant is designed around everyday questions like "How much do I have
left for dining?" and "What are my recent purchases?" Python tools retrieve
account balances, filter transactions, and calculate spending and remaining
budgets. Financial answers should come from those results.

Everything uses fictional JSON data. There are no bank connections or money
transfers. Date based tools use September 22, 2026 as a fixed demo date.

## Run the local tools

Use Python 3.10 or newer. In PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python tools.py
```

This prints example tool results. Run `python data_access.py` to inspect the
loaded records. These local tools use Python's standard library.

## Project structure

- `data/`: fictional financial records stored as JSON.
- `data_access.py`: reads the JSON files.
- `tools.py`: filters records and calculates financial results.
- `agent.py`: the home for model instructions and tool-call orchestration.
- `main.py`: the intended entry point for the command-line interface.

Amounts are stored in integer cents. Account balances are snapshots that already
include completed purchases; budget spending is calculated from transactions.
API keys belong in environment variables and must never be committed.
