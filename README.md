# 🚀 KRX AutoTrader v2.0 (Wall Street Grade)

A professional, high-frequency-capable automated trading system for the Korean (KRX) stock market. 

## 🌟 Key Features

- **Multi-Factor AI Engine**: Integrates Machine Learning (XGBoost, LightGBM) and Deep Learning (LSTM with Attention) for predictive alpha generation.
- **Dynamic Regime Detection**: Adapts strategy parameters in real-time based on HMM-driven market regime analysis (Bull/Bear/Sideways).
- **Execution Efficiency**: Smart Order Routing (SOR) with VWAP, TWAP, and Iceberg algorithms to minimize market impact.
- **Deep Recovery Strategy**: Specialized isolated module for managing high-cost basis positions (e.g., POSCO Holdings, LG Chem) using advanced technical/AI averaging-down triggers.
- **Premium Dashboard**: Glassmorphism-inspired dark UI with real-time terminal metrics, risk monitoring, and AI factor score visualization.

## 🏗️ Architecture

- **Backend**: Python (FastAPI), AsyncIO, ML/AI (Scikit-Learn, XGBoost, PyTorch/TensorFlow placeholder), NumPy, Pandas.
- **Frontend**: React, Vite, Recharts, Lightweight-Charts.
- **Broker Integration**: Kiwoom OpenAPI (REST).

## 🚀 Getting Started

### Backend
1. Create a virtual environment: `python -m venv .venv`
2. Install dependencies: `pip install -r backend/requirements.txt`
3. Set your API keys in `.env` or via the Dashboard Settings.
4. Run: `python -m backend.main`

### Frontend
1. Navigate to: `cd frontend`
2. Install node modules: `npm install`
3. Run dev server: `npm run dev`

## 🛡️ Risk Management
- Daily Loss Limits
- Max Pullback / MDD Shield
- Smart Kill-Switch (Event-Risk Driven)
- Position Sizing (Kelly Criterion / Risk Parity)

---
*Disclaimer: Trading stocks involves significant risk. This system is for educational and specialized trading purposes.*
