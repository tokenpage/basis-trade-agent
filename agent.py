import logging
import os
from pathlib import Path

from eth_defi.gmx.config import GMXConfig

from basis_trade_agent.chat_bot import ChatBot
from basis_trade_agent.chat_tool import AgentRuntimeState
from basis_trade_agent.config import load_config
from basis_trade_agent.gmx_client import GmxClient, resolve_market_and_tokens
from basis_trade_agent.llm import GeminiLLM
from basis_trade_agent.prompts import SYSTEM_PROMPT
from basis_trade_agent.tools import GetConfigTool, GetCurrentPositionTool, GetRecentActivityTool, GetWalletHoldingsTool, UpdateConfigTool
from basis_trade_agent.wallet import load_wallet_context

CHAT_MODEL_ID = "gemini-2.5-flash"


def build_runtime_state(configPath: Path) -> tuple[AgentRuntimeState, str]:
    config = load_config(configPath)
    walletContext = load_wallet_context()
    readConfig = GMXConfig(walletContext.web3)
    marketTokens = resolve_market_and_tokens(readConfig, config.targetAssetSymbol)
    gmxClient = GmxClient(readConfig=readConfig, writeConfig=readConfig)
    runtimeState = AgentRuntimeState(walletContext=walletContext, gmxClient=gmxClient, marketTokens=marketTokens, configPath=configPath)
    systemPrompt = SYSTEM_PROMPT.format(targetAssetSymbol=config.targetAssetSymbol, chain=config.chain)
    return runtimeState, systemPrompt


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
    configPath = Path(os.environ.get("BASIS_TRADE_CONFIG_PATH", "config.yaml"))
    runtimeState, systemPrompt = build_runtime_state(configPath)
    geminiApiKey = os.environ["GEMINI_API_KEY"]
    llm = GeminiLLM(apiKey=geminiApiKey, modelId=CHAT_MODEL_ID)
    tools = [GetConfigTool(), UpdateConfigTool(), GetWalletHoldingsTool(), GetCurrentPositionTool(), GetRecentActivityTool()]
    chatBot = ChatBot(llm=llm, tools=tools)
    print(f"Basis Trade Agent ready. Wallet: {runtimeState.walletContext.account.address}. Market: {runtimeState.marketTokens.marketSymbol}. Ctrl+D to exit.")
    while True:
        try:
            userMessage = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not userMessage:
            continue
        for outputLine in chatBot.execute(systemPrompt=systemPrompt, runtimeState=runtimeState, userMessage=userMessage):
            print(outputLine)


if __name__ == "__main__":
    main()
