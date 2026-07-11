import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass

from basis_trade_agent.chat_tool import AgentRuntimeState, ChatTool
from basis_trade_agent.llm import GeminiLLM
from basis_trade_agent.prompts import USER_PROMPT

log = logging.getLogger(__name__)
MAX_TOOL_ITERATIONS = 10


@dataclass
class ChatEvent:
    eventType: str
    content: str


class ChatBot:
    def __init__(self, llm: GeminiLLM, tools: list[ChatTool]) -> None:
        self.llm = llm
        self.tools = tools
        self.history: list[ChatEvent] = []

    def execute(self, systemPrompt: str, runtimeState: AgentRuntimeState, userMessage: str) -> Iterator[str]:
        toolDescriptions = "\n".join(f"{tool.name}: {tool.description}\n  Parameters: {json.dumps(tool.paramsSchema.model_json_schema())}" for tool in self.tools)
        historyContext = "\n".join(f"{event.eventType}: {event.content}" for event in self.history[-20:]) or "(empty)"
        self.history.append(ChatEvent(eventType="user", content=userMessage))
        isComplete = False
        currentContext = ""
        lastMessage = None
        iterationCount = 0
        while not isComplete and iterationCount < MAX_TOOL_ITERATIONS:
            iterationCount += 1
            prompt = USER_PROMPT.format(historyContext=historyContext, tools=toolDescriptions, currentContext=currentContext.strip() or "(empty)", userMessage=userMessage)
            step = self.llm.get_next_step(systemPrompt=systemPrompt, prompt=prompt)
            isComplete = bool(step.get("isComplete", False))
            requestedToolName = step.get("tool")
            if requestedToolName:
                matchingTools = [tool for tool in self.tools if tool.name == requestedToolName]
                if not matchingTools:
                    currentContext += f"\nTool: unknown tool '{requestedToolName}'"
                    isComplete = False
                    continue
                tool = matchingTools[0]
                try:
                    params = tool.paramsSchema(**(step.get("args") or {}))
                except Exception as exception:  # noqa: BLE001
                    currentContext += f"\nTool: invalid arguments for '{requestedToolName}': {exception}"
                    isComplete = False
                    continue
                result = tool.execute(runtimeState=runtimeState, params=params)
                resultMessage = f"{requestedToolName} complete, result: {result}"
                yield f"[{requestedToolName}] {result}"
                currentContext += f"\nTool: {resultMessage}"
                isComplete = False
            elif step.get("message"):
                currentMessage = str(step["message"])
                if currentMessage == lastMessage:
                    log.warning("LLM repeated the same message, ending to prevent infinite loop")
                    isComplete = True
                    continue
                self.history.append(ChatEvent(eventType="agent", content=currentMessage))
                yield currentMessage
                lastMessage = currentMessage
            else:
                log.warning("LLM step did not contain tool or message")
                isComplete = True
