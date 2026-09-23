"""
main.py

This file is the cli interface to call the agent.
"""

from openai import APIError, AuthenticationError, RateLimitError
from agent import run_agent


def main() -> None:
    print("Balance Financial Assistant")
    print("Fictional demo data. Conversation is remembered until you exit.")
    print("Type exit or quit to finish.\n")

    history: list[dict] = []

    while True:
        try:
            message = input("You: ").strip()
            if message.lower() in {"exit", "quit"}:
                break
            if not message:
                continue

            try:
                answer = run_agent(message, history)
                print(f"Balance: {answer or 'No answer returned. Please try again.'}\n")
            except AuthenticationError:
                print("Balance: Authentication failed. Check OPENAI_API_KEY in .env.\n")
            except RateLimitError:
                print("Balance: The API reported a rate or quota limit. Check API usage or try later.\n")
            except APIError:
                print("Balance: The API request failed. Check your connection and try again.\n")
            except (ValueError, RuntimeError):
                print("Balance: Could not complete the request. Check your API key setup or try rephrasing.\n")
            except (OSError, KeyError, TypeError):
                print("Balance: Could not read or process the financial data. Check the local JSON files.\n")
        except (EOFError, KeyboardInterrupt):
            print()
            break

    print("Goodbye!")


if __name__ == "__main__":
    main()
