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
* Report the live GMX net funding/borrow rate versus your configured enter/exit thresholds, and explain why the agent has or hasn't entered a trade (`get_market_rate`) — fetched fresh from GMX on every call, not cached or estimated.
* Read the current trading config (`get_config`).
* Show the most recent approval/order activity the live main loop recorded, including explorer links (`get_recent_activity`).
* Update trading parameters in `config.yaml` on request (`update_config`) — e.g. "raise my minimum yield to 8%" or "switch to aggressive mode". Comments in `config.yaml` are preserved; invalid values are rejected without touching the file. The running `make main` loop picks up config changes on its next cycle.

`chain` and `targetAssetSymbol` can't be changed via chat while `main.py` is already running (that requires re-resolving the GMX market and restarting the loop).

### Talking to the deployed worker

`bta.yieldseeker.xyz` (the landing page) and `bta-api.yieldseeker.xyz`'s co-located `basis-trade-agent-worker` container run continuously on the app box against `/home/ec2-user/basis-trade-agent-shared/config.yaml` (see `.github/workflows/api-deploy.yml`), independently of anything running locally. To have a live conversation that updates that *same* deployed worker's config (rather than a local file it never reads), SSH onto the app box and run `agent.py` in a one-off container against the same shared volume:

```bash
ssh ys-appbox
docker run --rm -it \
  --volume /home/ec2-user/basis-trade-agent-shared:/app/shared \
  --env BASIS_TRADE_CONFIG_PATH=/app/shared/config.yaml \
  --env-file ~/.basis-trade-agent-api.vars \
  ghcr.io/tokenpage/basis-trade-agent-api:latest \
  uv run --active python agent.py
```

This reuses the exact same deployed image and code path as the always-on worker — it's not a separate implementation. The container exits and is removed (`--rm`) when you `Ctrl+D`; the worker container itself is untouched and keeps running throughout.

**Important:** this shares one real wallet with any local `make main` run using the same `.envrc`. Never run a local loop and the deployed worker against the same wallet at the same time — they can race on the same position/nonces. Check `docker ps` on the app box first if unsure whether the worker is already live.

### Recording a demo

The demo flow is two terminals using the real agent and the real main loop — not a separate execution path.

1. Fund the wallet with a small amount of **USDC** (not WBTC — `main.py` always starts from USDC and buys/converts the asset itself) plus a little ETH for gas on Arbitrum.
2. Run the prep script once to put `config.yaml` into a demo-friendly state and confirm the wallet is flat:

```bash
uv run --active python prepare_demo.py --config config.yaml --starting-capital-usdc 5
```

3. In **Terminal 1**, start the conversational agent:

```bash
make agent
```

Use this exact runbook on camera:
- `what are my current holdings?`
- `what's my current position?`
- `set starting capital to 5 dollars`
- `set my minimum net yield to 0.01 percent`
- `set my hysteresis band to 0.02 percent`
- `set my smoothing window to 0.02 hours`
- `set my poll interval to 15 seconds`
- `show me my current config`

4. In **Terminal 2**, start the live loop:

```bash
make main
```

What you should see:
- first, a `reloaded config from disk` log line proving `main.py` picked up what you changed conversationally without a restart;
- then per-cycle rate logs (real cadence is dictated by GMX API/oracle latency — typically a few minutes between cycles in practice, not the configured `pollIntervalSeconds`, which only sets a minimum floor after each cycle finishes);
- then, when the live smoothed GMX net rate clears the very low demo threshold, `action=enter` and real signed GMX tx hashes.

5. After the position opens, go back to **Terminal 1** and ask:
- `what's my current position?`
- `what are my current holdings?`
- `show me the recent activity`

That gives you a complete before/after story in one recording: conversational config changes → live loop reacts → real on-chain position exists → conversational agent introspects the result.

### Alternative demo script (net yield currently unfavorable)

Real GMX funding/borrow rates move on their own schedule and are sometimes genuinely negative for the short side (`get_market_rate` / the loop's own `instantaneousApr` log both show the real number — see the "Talking to the agent" section). If the real net rate is still below even the demo's very low `enterNetYieldAprPercent` when you go to record, do **not** fake an entry — walk through the agent correctly declining to trade instead. This is still a live, on-chain-grounded recording, not a talk-only fallback:

1. Run `prepare_demo.py` as in step 2 above. If you already ran it earlier and want a fresh visible on-chain moment for the recording, revoke the wallet's existing USDC/WBTC allowances for the GMX router first (`approve(router, 0)` for both tokens) so `main.py`'s normal startup safety step (`ensure_approvals`) genuinely re-submits and confirms two fresh approval transactions live in Terminal 2 — this is the agent's real, unmodified startup logic, not a scripted extra step.
2. **Terminal 1** (`make agent`):
   - `what are my current holdings?`
   - `what's my current position?`
   - `what's the current market rate, and why haven't you entered a trade?` (uses the `get_market_rate` tool — pulls the live GMX rate fresh, not a canned number, and compares it to your configured threshold)
   - `show me the recent activity` (shows the real, fresh approval tx links from this run, confirmable on Arbiscan)
3. **Terminal 2** (`make main`): let it run live. You should see the two real approval transactions submit and confirm (if you revoked beforehand), then per-cycle logs showing the real negative/low `instantaneousApr` and `action=none` — the agent correctly refusing to risk capital on an unfavorable trade.
4. Back in **Terminal 1**, ask `what's the current market rate?` again — the number should match what Terminal 2 just logged, proving both surfaces are reading the same live truth, not two different scripts.

This tells an equally real story: an agent that is armed (real approvals on-chain, ready to trade instantly), continuously monitoring genuine live GMX data, and disciplined enough to sit out a bad trade rather than force one — and can explain exactly why, with real numbers, when asked.
