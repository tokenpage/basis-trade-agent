from pathlib import Path
from types import SimpleNamespace

from basis_trade_agent.chat_bot import MAX_TOOL_ITERATIONS, ChatBot
from basis_trade_agent.chat_tool import AgentRuntimeState


def make_runtime_state() -> AgentRuntimeState:
    return AgentRuntimeState(walletContext=SimpleNamespace(), gmxClient=SimpleNamespace(), marketTokens=SimpleNamespace(), configPath=Path("/dev/null"))


def test_execute_yields_message_and_stops_when_no_tool_is_requested(mock_gemini_llm, mock_echo_tool) -> None:
    llm = mock_gemini_llm([{"message": "Answer", "tool": None, "isComplete": True}])
    chatBot = ChatBot(llm=llm, tools=[mock_echo_tool()])
    events = list(chatBot.execute(systemPrompt="system", runtimeState=make_runtime_state(), userMessage="hi"))
    assert events == ["Answer"]
    assert len(llm.calls) == 1


def test_execute_dispatches_tool_call_then_yields_final_message(mock_gemini_llm, mock_echo_tool) -> None:
    tool = mock_echo_tool(resultText="echoed")
    llm = mock_gemini_llm([
        {"tool": "mock_echo", "args": {"text": "ping"}, "isComplete": False},
        {"message": "Done", "tool": None, "isComplete": True},
    ])
    chatBot = ChatBot(llm=llm, tools=[tool])
    events = list(chatBot.execute(systemPrompt="system", runtimeState=make_runtime_state(), userMessage="hi"))
    assert events == ["[mock_echo] echoed", "Done"]
    assert tool.executeInnerCalls == [{"text": "ping"}]
    assert len(llm.calls) == 2


def test_execute_respects_max_tool_iterations_cap(mock_gemini_llm, mock_echo_tool) -> None:
    tool = mock_echo_tool()
    responses = [{"tool": "mock_echo", "args": {"text": str(index)}, "isComplete": False} for index in range(MAX_TOOL_ITERATIONS + 5)]
    llm = mock_gemini_llm(responses)
    chatBot = ChatBot(llm=llm, tools=[tool])
    events = list(chatBot.execute(systemPrompt="system", runtimeState=make_runtime_state(), userMessage="hi"))
    assert len(llm.calls) == MAX_TOOL_ITERATIONS
    assert len(events) == MAX_TOOL_ITERATIONS
    assert len(tool.executeInnerCalls) == MAX_TOOL_ITERATIONS


def test_execute_stops_on_repeated_identical_message(mock_gemini_llm, mock_echo_tool) -> None:
    llm = mock_gemini_llm([
        {"message": "Hi there", "tool": None, "isComplete": False},
        {"message": "Hi there", "tool": None, "isComplete": False},
    ])
    chatBot = ChatBot(llm=llm, tools=[mock_echo_tool()])
    events = list(chatBot.execute(systemPrompt="system", runtimeState=make_runtime_state(), userMessage="hi"))
    assert events == ["Hi there"]
    assert len(llm.calls) == 2
