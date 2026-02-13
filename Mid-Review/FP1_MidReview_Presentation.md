# Mid-Review Presentation: AI-Driven Electricity Price Forecasting

## 🏢 Project Objective
Developing a high-precision forecasting and strategic bidding terminal for the Indian Energy Exchange (IEX) using weather-driven machine learning models.

---

## 📅 Progress & Milestones (CRISP-ML Q)
- **Business Understanding**: Focused on 15-minute block volatility (96 blocks/day).
- **Data Engineering**: Integrated live feeds from IEX Prov. DAM and 10+ National Renewable Hubs.
- **Modeling**: XG Boost & Linear Ensembles for next-block price prediction.
- **Deployment**: Live dashboard with "Locked" IST sync and strategic signals.

---

## 💹 Strategic Bidding Research (New Addition)
Based on direct IEX Market Rule analysis, we have integrated the following strategic bidding types:

### 1. Single Bid (Portfolio Bid)
*   **Definition**: Price-quantity pair for a specific 15-minute time block.
*   **Key Property**: Allows **Partial Execution**.
*   **Logic**: If current MCP is between two bid points, linear interpolation is used to determine cleared quantity.
*   *Best for: Flexible generators (Solar/Hydro).*

### 2. Block Bid
*   **Definition**: A single price/quantity for a continuous set of blocks (e.g., 4 Peak Hours).
*   **Key Property**: **All-or-None** execution.
*   **Logic**: Bid is only cleared if the Average MCP across all blocks $\ge$ Bid Price.
*   *Best for: Baseload plants (Coal/Gas) with high ramp-up/down costs.*

---

## 🛠️ Dashboard Features
- **Live Sync**: Matches IEX provisional Clearing Price for the current 15-min interval.
- **National Intelligence**: Predictor considers aggregate supply from 10+ clusters (Rajasthan, AP, Gujarat).
- **Bidding Strategy Lab**: Interactive guide explaining market mechanics.

---

## ⏭️ Next Steps
- Integration of POSOCO national load data for demand-side refinement.
- Backtesting Bidding Strategies using the "Single Bid" linear interpolation logic.
- Final API deployment for external consumption.
