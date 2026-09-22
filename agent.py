"""
agent.py

This file is where calls to the LLM and agent tool calls 
will be made.
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from tools import get_accounts

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

# list of tools usable by agent
TOOL_FUNCTIONS = {
    "get_accounts": get_accounts,
}

TOOL_DEFINITIONS = [
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


def execute_tool(name: str, arguments: dict) -> dict:
    """Validate a requested call and execute an allowed Python function."""

    # check if requested tool exists
    if name not in TOOL_FUNCTIONS:
        raise ValueError(f"Unknown tool: {name}")
    
    # check if arguments are in the right format
    if not isinstance(arguments, dict):
        raise ValueError("Tool arguments must be a dictionary.")
    
    # check if get_accounts was given extra arguments
    if name == "get_accounts" and arguments:
        raise ValueError("get_accounts accepts only an empty dictionary.")

    # TODO: delete this print
    print(f"Tool: {name}, arguments: {arguments}")

    # get tool and run it with arguments
    tool_function = TOOL_FUNCTIONS[name]
    return tool_function(**arguments)


def run_agent(message: str) -> str:
    """Send a question, handle tool calls, and return the final answer."""

    # create client and add instructions and user message
    client = create_client()
    messages = [
        {"role": "system", "content": AGENT_INSTRUCTIONS},
        {"role": "user", "content": message},
    ]
    
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
            return assistant_message.content or ""

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

            # check if arguments are in the right format
            if not isinstance(arguments, dict):
                raise ValueError("Tool arguments must be a dictionary.")
            # check if get_accounts was given extra arguments
            if name == "get_accounts" and arguments:
                raise ValueError("get_accounts accepts only an empty dictionary.")

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
