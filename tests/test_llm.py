import json

import pytest
import requests

from basis_trade_agent.llm import GeminiLLM


class MockGeminiHttpResponse:
    def __init__(self, jsonBody: dict) -> None:
        self.jsonBody = jsonBody

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.jsonBody


def make_gemini_response_body(payload: dict) -> dict:
    fencedText = f"```json\n{json.dumps(payload)}\n```"
    return {"candidates": [{"content": {"parts": [{"text": fencedText}]}}]}


def test_get_next_step_parses_fenced_json_response(monkeypatch: pytest.MonkeyPatch) -> None:
    expectedStep = {"message": "hello", "tool": None, "args": {}, "isComplete": True}
    postCalls = []
    def mock_post(url, json, timeout):
        postCalls.append({"url": url, "json": json, "timeout": timeout})
        return MockGeminiHttpResponse(make_gemini_response_body(expectedStep))
    monkeypatch.setattr("basis_trade_agent.llm.requests.post", mock_post)
    llm = GeminiLLM(apiKey="test-key", modelId="gemini-test")
    result = llm.get_next_step(systemPrompt="system", prompt="user")
    assert result == expectedStep
    assert len(postCalls) == 1
    assert "test-key" in postCalls[0]["url"]


def test_get_next_step_raises_clear_error_on_unparseable_json(monkeypatch: pytest.MonkeyPatch) -> None:
    responseBody = {"candidates": [{"content": {"parts": [{"text": "this is not json"}]}}]}
    monkeypatch.setattr("basis_trade_agent.llm.requests.post", lambda url, json, timeout: MockGeminiHttpResponse(responseBody))
    llm = GeminiLLM(apiKey="test-key", modelId="gemini-test")
    with pytest.raises(ValueError, match="Could not parse JSON"):
        llm.get_next_step(systemPrompt="system", prompt="user")


def test_get_next_step_retries_on_request_exception_then_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    callCount = 0
    def mock_post(url, json, timeout):
        nonlocal callCount
        callCount += 1
        raise requests.RequestException("connection reset")
    monkeypatch.setattr("basis_trade_agent.llm.requests.post", mock_post)
    monkeypatch.setattr("basis_trade_agent.llm.time.sleep", lambda seconds: None)
    llm = GeminiLLM(apiKey="test-key", modelId="gemini-test")
    with pytest.raises(RuntimeError, match="failed after 5 attempts"):
        llm.get_next_step(systemPrompt="system", prompt="user")
    assert callCount == 5
    assert callCount > 1
