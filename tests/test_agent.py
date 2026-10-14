"""Tests for agent.py tool-call handling using a scripted fake client. No API requests."""

import json
from types import SimpleNamespace

import pytest

import agent
import eval as evaluation


class FakeMessage:
    """Stands in for the SDK's assistant message object."""

    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls

    def model_dump(self, exclude_none=True):
        data = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            data["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.function.name, "arguments": call.function.arguments},
                }
                for call in self.tool_calls
            ]
        return {key: value for key, value in data.items() if value is not None}


def tool_call(call_id, name, arguments):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=arguments))


@pytest.mark.parametrize("arguments", ["null", "[]", '"text"', "42"])
def test_parse_tool_call_rejects_non_object_json_arguments(arguments):
    call = tool_call("c1", "get_accounts", arguments)
    with pytest.raises(ValueError, match="JSON object"):
        agent.parse_tool_call(call)


def test_parse_tool_call_preserves_unicode_and_treats_empty_arguments_as_object():
    unicode_call = tool_call("c1", "get_transactions", '{"category": "caf\u00e9"}')
    empty_call = tool_call("c2", "get_accounts", "")
    assert agent.parse_tool_call(unicode_call) == ("get_transactions", {"category": "caf\u00e9"})
    assert agent.parse_tool_call(empty_call) == ("get_accounts", {})


def fake_client(*replies):
    """Return a client whose create() hands back each scripted reply in order."""
    replies = list(replies)
    sent = []

    def create(**kwargs):
        sent.append(json.loads(json.dumps(kwargs["messages"])))
        message = replies.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return client, sent


def tool_results(messages):
    return [json.loads(m["content"]) for m in messages if m["role"] == "tool"]


@pytest.fixture
def use_client(monkeypatch):
    def install(*replies):
        client, sent = fake_client(*replies)
        monkeypatch.setattr(agent, "create_client", lambda: client)
        return sent
    return install


# validation

def test_validation_rejects_unknown_tool():
    with pytest.raises(ValueError, match="Unknown tool"):
        agent.validate_tool_arguments("transfer_money", {})


@pytest.mark.parametrize("days", [0, 366, "7", 2.5, True])
def test_validation_rejects_bad_days(days):
    with pytest.raises(ValueError):
        agent.validate_tool_arguments("get_upcoming_expenses", {"days": days})


def test_validation_allows_null_goal():
    agent.validate_tool_arguments("get_savings_goals", {"goal": None})


def test_every_definition_has_a_function():
    names = {tool["function"]["name"] for tool in agent.TOOL_DEFINITIONS}
    assert names == set(agent.TOOL_FUNCTIONS)


# run_agent loop

def test_tool_result_reaches_model(use_client):
    sent = use_client(
        FakeMessage(tool_calls=[tool_call("c1", "get_safe_to_spend", "{}")]),
        FakeMessage(content="You can spend $223.01."),
    )
    assert agent.run_agent("how much can I spend?") == "You can spend $223.01."
    assert tool_results(sent[1])[0]["safe_to_spend_cents"] == 22301


def test_unknown_tool_is_returned_as_error_not_raised(use_client):
    sent = use_client(
        FakeMessage(tool_calls=[tool_call("c1", "delete_account", "{}")]),
        FakeMessage(content="Sorry, I can't do that."),
    )
    assert agent.run_agent("delete my account") == "Sorry, I can't do that."
    assert "Unknown tool" in tool_results(sent[1])[0]["error"]


def test_bad_json_and_bad_arguments_let_model_retry(use_client):
    sent = use_client(
        FakeMessage(tool_calls=[
            tool_call("c1", "get_upcoming_expenses", "{not json"),
            tool_call("c2", "get_upcoming_expenses", '{"days": 0}'),
        ]),
        FakeMessage(tool_calls=[tool_call("c3", "get_upcoming_expenses", '{"days": 7}')]),
        FakeMessage(content="$56.99 due this week."),
    )
    assert agent.run_agent("bills this week?") == "$56.99 due this week."
    first, second = tool_results(sent[1])
    assert "Invalid JSON" in first["error"]
    assert "days" in second["error"]
    assert tool_results(sent[2])[-1]["total_due_cents"] == 5699


def test_history_keeps_conversation(use_client):
    use_client(FakeMessage(content="Hi!"), FakeMessage(content="Still here."))
    history = []
    agent.run_agent("hello", history)
    agent.run_agent("you there?", history)
    roles = [m["role"] for m in history]
    assert roles == ["system", "user", "assistant", "user", "assistant"]


def test_verbose_prints_tool_calls(use_client, capsys):
    use_client(
        FakeMessage(tool_calls=[tool_call("c1", "get_savings_goals", '{"goal": "spring"}')]),
        FakeMessage(content="done"),
    )
    agent.run_agent("spring break goal?", verbose=True)
    assert "[tool] get_savings_goals" in capsys.readouterr().out


def test_stops_after_max_iterations(use_client):
    use_client(*[FakeMessage(tool_calls=[tool_call(f"c{i}", "get_accounts", "{}")]) for i in range(10)])
    with pytest.raises(RuntimeError, match="maximum"):
        agent.run_agent("loop forever")


# eval scoring helpers

def test_extract_amounts_handles_dollars_and_commas():
    assert evaluation.extract_amounts("You owe $1,026.99, not $50.") == [1026.99, 50.0]


def test_check_answer_amounts_and_keywords():
    case = {"amounts": [223.01], "keywords": ["can't", "cannot"]}
    assert evaluation.check_answer(case, "You can’t, only $223.01 is safe.")
    assert not evaluation.check_answer(case, "Sure, you have $1,250.00.")


def test_check_tools_expects_none_for_refusals():
    assert evaluation.check_tools([], [])
    assert not evaluation.check_tools([], ["get_accounts"])
    assert evaluation.check_tools(["get_spending", "get_budget"], ["get_budget"])


# cli error messages

def test_quota_errors_are_told_apart_from_rate_limits():
    from main import describe_rate_limit

    def error(code=None, error_type=None):
        return SimpleNamespace(code=code, type=error_type)

    assert "out of credit" in describe_rate_limit(error("credit_balance_exhausted"))
    assert "out of credit" in describe_rate_limit(error(error_type="insufficient_quota"))
    assert "Too many requests" in describe_rate_limit(error("rate_limit_exceeded", "requests"))
