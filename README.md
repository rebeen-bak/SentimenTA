# Hype Trading Bot

An automated trading bot that combines social sentiment analysis with technical indicators and momentum to identify and trade potential breakout stocks.

## Features

- Multi-source stock screening:
  - Reddit WSB sentiment via SwaggyStocks
  - ApeWisdom for broader Reddit stock mentions
  - Stocktwits trending stocks
- Combines technical screening with social sentiment analysis
- Technical Analysis:
  - Simple Moving Averages (20 and 50 day)
  - Relative Strength Index (RSI)
  - Moving Average Convergence Divergence (MACD)
  - Bollinger Bands
  - Price Momentum
- Position Management:
  - Side-specific technical analysis for longs/shorts
  - Momentum-based entry and exit criteria
  - Dynamic exposure management
  - Automatic position closure based on:
    * Technical signals
    * Price momentum
    * Stop losses
    * Position age
    * Total exposure limits
- Risk Management:
  - Maximum 8% exposure per position
  - Gradual position building (2% steps)
  - Maximum 160% total exposure (80% long + 80% short)
  - Momentum confirmation required for new positions
  - Stricter thresholds when near max exposure
- Executes trades automatically through Alpaca's paper trading API
- Handles market hours gracefully with pending order tracking

## Setup


1. Install TA-Lib: (C library must be installed before python "ta-lib" wrapper)
- On Ubuntu/Debian:
```bash
sudo apt-install ta-lib
```
- On macOS:
```bash
brew install ta-lib
```

2. Install required packages:
```bash
pip install -r requirements.txt
```



3. Create an Alpaca paper trading account at https://app.alpaca.markets/signup
   - Get your API key and secret from the dashboard

4. Copy the environment variables template:
```bash
cp .env.example .env
```

5. Edit `.env` and add your Alpaca API credentials:
```
ALPACA_API_KEY=your_api_key_here
ALPACA_SECRET_KEY=your_secret_key_here
```

## Usage

Run the main trading script:
```bash
source .env
python trader.py
```

The bot follows a two-step process:

1. Manage Existing Positions:
   - Analyze each position with side-specific technical analysis
   - Check momentum direction against position side
   - Close positions that meet exit criteria:
     * Negative momentum for longs (< -2%)
     * Positive momentum for shorts (> +2%)
     * Technical signals move against position
     * Stop loss hit (-5%)
     * Position age > 5 days with minimal P&L
     * Over exposure with weak technicals

2. Find New Opportunities:
   - Screen for trending stocks from social sources
   - Calculate technical indicators and momentum
   - Rank stocks by combined social and technical scores
   - Filter candidates based on:
     * Long: Above 70th percentile + positive momentum
     * Short: Below 30th percentile + negative momentum
     * Stricter thresholds when exposure > 70%
   - Place orders that will execute when market opens

## Components

- `social_scanner.py`: Multi-source social sentiment analysis
  - Reddit WSB sentiment
  - ApeWisdom stock mentions
  - Stocktwits trending stocks
- `technical_analysis.py`: Technical indicators and momentum analysis
- `position_manager.py`: Position and risk management
- `trader.py`: Main script orchestrating the trading process

## Risk Warning

This is a paper trading bot for educational purposes. Always thoroughly test trading strategies with paper trading before considering real money trading. While the bot implements various risk management features like position sizing, momentum confirmation, and exposure limits, you should adjust these parameters based on your risk tolerance and strategy.
