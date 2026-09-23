"""
agent.py

This file is where calls to the LLM and agent tool calls 
will be made.
"""

import json
import os
from inspect import signature
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from tools import DEMO_DATE, get_accounts, get_budget, get_spending, get_recent_transactions

AGENT_INSTRUCTIONS = """
You are Balance, a financial assistant working with fictional demo data.
Use tools for factual claims about the user's finances. Never invent values.
All money responses in tool results is in cents, format it as dollars in your answer. 
THAT IS IMPORTANT, ENSURE THAT YOU UNDERSTAND RESULTS ARE IN CENTS, AND YOU HAVE TO CONVERT TO DOLLARS.
Combined account balances include savings and are not automatically spendable.
If data is missing or a tool returns an error, explain that clearly.
You cannot transfer money or change financial records.
Keep answers concise. And sound conversational, the target user is genz.
""".strip()
AGENT_INSTRUCTIONS += f"\nUse {DEMO_DATE.isoformat()} as today's date for this demo. Weeks begin Monday."

# list of tools usable by agent
TOOL_FUNCTIONS = {
    "get_accounts": get_accounts,
    "get_budget": get_budget,
    "get_spending": get_spending,
    "get_recent_transactions": get_recent_transactions,
}

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_budget",
            "description": "Get a category's monthly budget limit, spending so far, and remaining amount in cents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Spending category, such as dining or clothing."},
                },
                "required": ["category"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_spending",
            "description": "Get recorded spending in cents for a category and period relative to the demo date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Spending category, such as dining or clothing."},
                    "period": {
                        "type": "string",
                        "enum": ["today", "this_week", "this_month", "last_month"],
                        "description": "Defaults to this_month. Weeks start Monday.",
                    },
                },
                "required": ["category"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_transactions",
            "description": "List completed purchases newest first, optionally filtered by category. Amounts are in cents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": ["string", "null"], "description": "Omit or use null to include all categories."},
                    "limit": {"type": "integer", "minimum": 1, "description": "Maximum purchases to return; defaults to 5."},
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_accounts",
            "description": "Gets user's individual account balance and their combined total",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
]


def create_client():
    """Configure the chosen provider's SDK using an environment variable."""

    # Load local settings without replacing existing environment variables.
    load_dotenv(Path(__file__).resolve().parent / ".env")

    # get api key from environment
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()

    # check if api key exists
    if not api_key:
        raise ValueError("Set OPENAI_API_KEY in the project .env file or environment before creating the client.")
    
    # create client with api key
    return OpenAI(api_key=api_key)


def validate_tool_arguments(name: str, arguments: dict) -> None:
    """Check names, required arguments, and types before calling a tool."""

    # check if requested tool exists
    if name not in TOOL_FUNCTIONS:
        raise ValueError(f"Unknown tool: {name}")
    
    # check if arguments are in the right format
    if not isinstance(arguments, dict):
        raise ValueError("Tool arguments must be a dictionary.")
    
    try:
        signature(TOOL_FUNCTIONS[name]).bind(**arguments)
    except TypeError as exc:
        raise ValueError(f"Invalid arguments for {name}: {exc}") from exc

    if "category" in arguments:
        category = arguments["category"]
        if not (name == "get_recent_transactions" and category is None):
            if not isinstance(category, str) or not category.strip():
                raise ValueError("category must be a non-empty string.")
    if "period" in arguments and arguments["period"] not in (
        "today", "this_week", "this_month", "last_month"
    ):
        raise ValueError("Unsupported spending period.")
    if "limit" in arguments:
        limit = arguments["limit"]
        if type(limit) is not int or limit < 1:
            raise ValueError("limit must be a positive integer.")


def execute_tool(name: str, arguments: dict) -> dict:
    """Validate a requested call and execute an allowed Python function."""
    validate_tool_arguments(name, arguments)

    # Show tool calls as evidence for the demo.
    # print(f"Tool: {name}, arguments: {arguments}")

    # get tool and run it with arguments
    tool_function = TOOL_FUNCTIONS[name]
    return tool_function(**arguments)


def run_agent(message: str, history: list[dict] | None = None) -> str:
    """Send a question, handle tool calls, and return the final answer."""

    # Work on a copy so a failed request does not damage the session history.
    client = create_client()
    messages = list(history) if history else [
        {"role": "system", "content": AGENT_INSTRUCTIONS},
    ]
    messages.append({"role": "user", "content": message})
    
    # limit how many times agent can request a response
    max_iterations = 10
    for _ in range(max_iterations):
        # send messages and available tools to model
        response = client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            messages=messages,
            tools=TOOL_DEFINITIONS,
        )
        # return answer if model does not need any tools
        assistant_message = response.choices[0].message
        if not assistant_message.tool_calls:
            answer = assistant_message.content or ""
            messages.append({"role": "assistant", "content": answer})
            if history is not None:
                history[:] = messages
            return answer

        # check all requested tools before running them
        parsed_tool_calls = []
        for tool_call in assistant_message.tool_calls:
            # check if requested tool exists
            name = tool_call.function.name
            if name not in TOOL_FUNCTIONS:
                raise ValueError(f"Unknown tool: {name}")

            # convert tool arguments from json
            try:
                arguments = json.loads(tool_call.function.arguments)
            except (json.JSONDecodeError, TypeError) as exc:
                raise ValueError(f"Invalid JSON arguments for tool: {name}") from exc

            validate_tool_arguments(name, arguments)

            parsed_tool_calls.append((tool_call.id, name, arguments))

        # save model response and add results from each tool
        messages.append(assistant_message.model_dump(exclude_none=True))
        for call_id, name, arguments in parsed_tool_calls:
            result = execute_tool(name, arguments)
            messages.append({
                "role": "tool",
                "tool_call_id": call_id,
                "content": json.dumps(result),
            })

    # stop if agent reaches limit without a final answer
    raise RuntimeError(f"Agent exceeded the maximum of {max_iterations} iterations.")


if __name__ == "__main__":
    print(run_agent(input("Ask Balance a question: ")))
