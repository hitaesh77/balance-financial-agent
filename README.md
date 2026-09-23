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

## Run locally

Use Python 3.10 or newer. In PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Create a `.env` file in the project root with your API key:

```text
OPENAI_API_KEY=your_api_key_here
```

Then run:

```powershell
python main.py
```

Ask a financial question, or type `exit` to finish. Conversation history is kept in memory until you exit. Tool calls are printed so you can see how the answer was produced.
An API key with available API quota is required to use the assistant.

Run `python tools.py` for local tool examples or `python data_access.py` to
inspect the mock records. These commands do not make API requests.

## Project structure

- `data/`: fictional financial records stored as JSON.
- `data_access.py`: reads the JSON files.
- `tools.py`: filters records and calculates financial results.
- `agent.py`: the home for model instructions and tool-call orchestration.
- `main.py`: the interactive command-line interface.

Amounts are stored in integer cents. Account balances are snapshots that already
include completed purchases; budget spending is calculated from transactions.
API keys belong in environment variables and must never be committed.
