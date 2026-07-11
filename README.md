# Basis Trade Agent

## Goal

This agent automates a market-neutral cash-and-carry strategy by simultaneously holding spot crypto assets and matching short perpetual contracts to harvest high funding yields. By managing execution, position ratios, and margin thresholds in the background, it transforms a highly complex, manually intensive trading strategy into a hands-off yield product for users.

---

## Background

A **basis trade** (or cash-and-carry trade) is a delta-neutral strategy designed to capture structural inefficiencies in crypto derivatives markets without taking on directional price risk.

### Core Mechanics & Jargon

* **Delta-Neutral:** A state where a portfolio's net price exposure is zero. If you own $1,000 of spot Bitcoin (Long) and open a $1,000 Bitcoin perpetual contract (Short), a 10% market pump or dump results in a net $0 change in asset value because the gains on one side perfectly offset the losses on the other.
* **Funding Rates:** A recurring interest payment exchanged between long and short traders every hour (or block) to keep perpetual futures pegged to the underlying spot price. In bull markets, retail demand to go long pushes funding rates positive, meaning longs continuously pay shorts to maintain their positions.
* **Borrowing Rates / Pool Fees:** On decentralized, multi-asset liquidity venues (like GMX V2), shorting requires "borrowing" capital from liquidity pools. This introduces an hourly borrow fee that acts as a drag on yield.
* **Net Rate:** The true bottom line ($\text{Funding Rate} - \text{Borrowing Rate}$). This metric dictates if a trade is profitable.

### Collateral Ratios & Capital Efficiency

When deploying capital (e.g., $40), the choice of collateral alters capital efficiency and liquidation risk:

* **50/50 Split (USDC Margin):** $20 used to buy spot BTC, $20 USDC used as short margin. Safe from liquidation because the short collateral is stable, but only 50% capital efficient as only the perp side farms the funding rate.
* **100/0 Flip (Asset Margin):** All $40 used to buy spot BTC, which is then deposited directly as the short's margin collateral. Yield is earned on the full $40 (100% efficient). However, if BTC crashes, the dollar value of the collateral drops while the short size remains $40, causing **liquidation drift** where leverage spikes dangerously.
* **75/25 or 25/75 (Hybrid):** A mix of asset and stablecoin collateral used to capture higher efficiency while maintaining a structural margin cushion against market dips.

### Why Humans Do This Manually (and Why They Fail)

Traders manually execute basis trades to beat standard stablecoin lending rates, often pulling 10–20%+ annualized returns on what acts like a "synthetic stablecoin." However, manual management is operationally brutal:

1. **Leg-In/Leg-Out Friction:** Manually buying spot and opening a short takes time. In fast markets, slippage between the two orders can instantly wipe out weeks of yield. Swap fees and price impact must also be carefully calculated before entering.
2. **Funding Rate Volatility:** Funding rates are highly volatile. If the market flips bearish, funding can turn negative, meaning shorts start paying longs. Humans frequently leave trades open too long, bleeding capital.
3. **Margin Maintenance:** Sudden market crashes trigger immediate mathematical drift in 100/0 or 75/25 setups, requiring manual, high-stress rebalancing to avoid liquidation.
4. **Over-Trading / Fee Churn:** GMX funding-borrow net rates cross zero far more often than intuition suggests — observed 30-day BTC data crossed the line 6-7 times. Every full open+close round trip costs roughly 0.10-0.14% of position size in GMX position fees (0.05-0.07% open, 0.05-0.07% close) plus swap fees/slippage on the spot leg and L2 gas — on a $40 test position, roughly $0.15-$0.25 per round trip. A naive "close whenever the instantaneous rate goes negative" trigger reacting to every crossing burns far more in cumulative fees than it saves in avoided negative funding, and can wipe out an entire month's earned yield in a handful of round trips. Reacting to a smoothed (rolling-average) rate with separate, wider enter/exit thresholds (hysteresis) and a minimum hold time is required even for a "simple" binary gate — see Background Decision Loop.

---

## Product

### Initial User Configuration

The user interacts with the **Basis Trade Agent** via natural language text. The system parses the prompt into a structured configuration:

* **Inputs:** Starting capital (e.g., USDC amount), target asset (e.g., BTC), venue (e.g., GMX), minimum acceptable net yield threshold (e.g., 5% APR), and risk tolerance (Conservative/50-50 vs. Aggressive/100-0).

### Background Decision Loop

Once live, the agent operates as a continuous state-machine executing the following checks:

* **Yield Health:** Is a rolling time-weighted average (not the instantaneous) Net Rate above the user's minimum threshold, with separate, wider enter/exit thresholds (hysteresis) and a minimum hold time before exit, to avoid fee churn from reacting to every rate crossing?
* **Margin Health:** Is the current liquidation buffer safe relative to asset price movements?
* **Execution Equilibrium:** Are the notionals of the long leg and short leg perfectly matched, or has fee friction caused delta drift?

### Background Actions

* **Atomic Execution:** The agent bundles spot swaps and perp orders to execute entries and exits simultaneously, eliminating leg-in slippage.
* **Dynamic Rebalancing:** If a market drop threatens an asset-collateralized position (like a 100/0 setup), the agent automatically swaps a calculated portion of the asset back to USDC inside the margin account, shifting the ratio (e.g., to 75/25) to defend the liquidation price.
* **Automated Kill-Switch:** If the net funding velocity flips negative for a sustained period, the agent completely unwinds both legs atomically and parks the user's capital back into the stablecoin Vault Agent.

### Ongoing User Inputs & Reporting

* **Time-Forward Inputs:** The agent will ping the user via text only for macro changes—such as asking for permission to increase capital if margin buffers require external funds during unprecedented volatility, or asking if they want to lower their yield threshold during market-wide regime shifts.
* **Regular Reporting:** The agent provides simple, text-based daily or weekly updates detailing: Net Yield Earned, Current Capital Efficiency Ratio, Margin Health Status, and Total Fees Paid.

---

## Roadmap

### Phase 1: The Script (MVP) — implemented in this repo

* **User Flow:** The user manually inputs exact parameters into a basic configuration file.
* **Agent Background Flow:** A basic cron script loops every few minutes to check the GMX API. It calculates the net yield and reads position health. If parameters are met, it triggers hardcoded, simultaneous smart contract transactions to enter or exit. No active rebalancing occurs; it features a basic binary "stay open" or "close completely" logic gate based strictly on funding rates.

### Phase 2: Production Flow (Scale)

* **User Flow:** A seamless conversation interface where users text commands. The agent handles configuration derivation autonomously and asks for a simple transaction confirmation to start.
* **Agent Background Flow:** A robust, event-driven architecture utilizing event listeners on-chain and via DEX indexers. The background flow moves from a simple script to an active portfolio manager:
1. Continually ingests real-time funding, borrowing, and price feeds.
2. Runs mathematical optimization models to dynamically shift collateral mixes (e.g., smoothly sliding between 100/0 and 50/50 as volatility fluctuates).
3. Integrates fallback safety routines that utilize pre-approved flash loans or liquidity routing to protect margin balances during extreme network congestion or exchange degradation.

---

## Running Phase 1

This project uses [direnv](https://direnv.net/): `.envrc` (gitignored, not committed) holds `BASIS_TRADE_WALLET_PRIVATE_KEY_ENCRYPTED`, `ARBITRUM_RPC_URL`, and `GEMINI_API_KEY` directly as `export` statements — there is no `.env` file. `BASIS_TRADE_WALLET_PRIVATE_KEY_ENCRYPTED` must be the Fernet-encrypted output of `yieldseeker-app/api/scripts/generate_evm_private_key.py` (not a raw hex key) — `wallet.py` decrypts it with a hardcoded password matching that script's convention.

```bash
make install                     # uv sync --active
cp config.example.yaml config.yaml   # fill in real parameters
make main                        # background trading loop: uv run --active main.py --config config.yaml
```

`make lint` / `make lint-fix` run ruff; `make test` runs pytest. See `scripts/probe_gmx_data.py` for a standing debug utility that dumps live GMX market/funding/position data for the configured chain.

### Talking to the agent

`make agent` (`uv run --active agent.py`) starts an interactive CLI chat session backed by Gemini, using the same hand-rolled REST + JSON-tool-call pattern as `yieldseeker-app/api`'s `GeminiLLM`/`ChatBot` (no native Gemini function-calling SDK). It's read-only with respect to trading — it never places orders — but it can:

* Answer questions about the agent wallet's current ETH/USDC/target-asset balances (`get_wallet_holdings`) and its currently open GMX position, if any (`get_current_position`) — current state only, no history.
* Read the current trading config (`get_config`).
* Update trading parameters in `config.yaml` on request (`update_config`) — e.g. "raise my minimum yield to 8%" or "switch to aggressive mode". Comments in `config.yaml` are preserved; invalid values are rejected without touching the file. The running `make main` loop picks up config changes on its next restart.

`chain` and `targetAssetSymbol` can't be changed via chat (that requires re-resolving the GMX market and restarting the loop).

### Recording a demo

`demo.py` is a bounded, one-shot variant of `main.py`: it runs preflight checks, watches the live GMX net rate every `pollIntervalSeconds`, and — the moment a real entry signal fires — opens one real position and exits with a summary (tx links + position size/mark/liquidation price), instead of looping forever like `main.py`. Good for a recording since it has a natural end point.

```bash
uv run --active python demo.py --config config.yaml
```

To get a reliable, fast entry during a recording session:

1. Send a small amount of **USDC** (not the target asset — the agent buys/converts it itself) plus a little ETH for gas to the agent wallet (`demo.py` prints the wallet's Arbiscan link on startup).
2. Copy `config.demo.example.yaml` to `config.yaml` (or pass `--config config.demo.example.yaml` directly) — it sets a small `startingCapitalUsdc` matching a small test deposit, an `enterNetYieldAprPercent` near zero so it clears whatever the live rate currently is, and a short `pollIntervalSeconds` so it doesn't sit idle on camera. Nothing about execution is simulated — it still submits real signed transactions to real GMX V2 contracts on Arbitrum mainnet.
3. After `demo.py` reports the position opened, run `make agent` and ask "what's my current position?" — a good second beat for the recording, showing the conversational agent introspecting the same live on-chain state `demo.py` just created.
