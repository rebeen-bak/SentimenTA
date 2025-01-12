import os
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import talib
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.enums import OrderSide
from dotenv import load_dotenv

class TechnicalAnalyzer:
    def __init__(self):
        load_dotenv()
        api_key = os.getenv('ALPACA_API_KEY')
        api_secret = os.getenv('ALPACA_SECRET_KEY')
        self.client = StockHistoricalDataClient(api_key, api_secret)
        
    def get_historical_data(self, symbol, lookback_days=100):
        """Get historical data from Alpaca"""
        end = datetime.now()
        start = end - timedelta(days=lookback_days)
        
        request = StockBarsRequest(
            symbol_or_symbols=[symbol],
            timeframe=TimeFrame.Day,
            start=start,
            end=end
        )
        
        bars = self.client.get_stock_bars(request)
        df = bars.df
        
        if df.empty:
            return None
            
        return df
    
    def calculate_indicators(self, df):
        """Calculate technical indicators"""
        # Convert multi-index to single index
        df = df.reset_index(level=1, drop=True)
        
        # Basic indicators
        df['SMA_20'] = talib.SMA(df['close'], timeperiod=20)
        df['SMA_50'] = talib.SMA(df['close'], timeperiod=50)
        df['RSI'] = talib.RSI(df['close'], timeperiod=14)
        
        # MACD
        macd, macd_signal, _ = talib.MACD(df['close'])
        df['MACD'] = macd
        df['MACD_Signal'] = macd_signal
        
        # Bollinger Bands
        upper, middle, lower = talib.BBANDS(df['close'])
        df['BB_Upper'] = upper
        df['BB_Middle'] = middle
        df['BB_Lower'] = lower
        
        return df
    
    def analyze_stock(self, symbol, side=None):
        """
        Analyze a stock and return trading signals
        Args:
            symbol: Stock symbol
            side: OrderSide.BUY for long analysis, OrderSide.SELL for short analysis, None for both
        """
        print(f"Getting historical data for {symbol}...")
        df = self.get_historical_data(symbol)
        if df is None:
            print(f"No historical data available for {symbol}")
            return None
        print(f"Got {len(df)} days of data")
            
        print("Calculating technical indicators...")
        df = self.calculate_indicators(df)
        print("Indicators calculated successfully")
        
        # Get latest values and previous values for momentum
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        week_ago = df.iloc[-5] if len(df) >= 5 else df.iloc[0]
        
        print("\nLatest values:")
        print(f"Price: ${latest['close']:.2f}")
        print(f"RSI: {latest['RSI']:.2f}")
        print(f"MACD: {latest['MACD']:.3f} vs Signal: {latest['MACD_Signal']:.3f}")
        print(f"20 SMA: {latest['SMA_20']:.2f} vs 50 SMA: {latest['SMA_50']:.2f}")
        
        signals = {
            'symbol': symbol,
            'price': latest['close'],
            'signals': [],
            'raw_score': 0,  # Raw technical score (-100 to 100)
            'score': 0,      # Normalized score (0 to 1)
            'momentum': 0    # Price momentum (percent change)
        }
        
        # Calculate momentum
        signals['momentum'] = ((latest['close'] / week_ago['close']) - 1) * 100
        
        # Trend Analysis
        if latest['SMA_20'] > latest['SMA_50']:
            if side != OrderSide.SELL:  # Bullish or neutral analysis
                signals['signals'].append("Bullish trend: 20 SMA above 50 SMA")
                signals['score'] += 20
            else:  # Short analysis - bearish signal
                signals['signals'].append("Warning: 20 SMA above 50 SMA (uptrend)")
                signals['score'] -= 20
        else:
            if side != OrderSide.BUY:  # Bearish or neutral analysis
                signals['signals'].append("Bearish trend: 20 SMA below 50 SMA")
                signals['score'] -= 20
            else:  # Long analysis - bearish signal
                signals['signals'].append("Warning: 20 SMA below 50 SMA (downtrend)")
                signals['score'] += 20
        
        # RSI Analysis
        if 30 <= latest['RSI'] <= 70:
            signals['signals'].append(f"RSI neutral at {latest['RSI']:.2f}")
        elif latest['RSI'] < 30:
            if side != OrderSide.SELL:  # Bullish or neutral analysis
                signals['signals'].append(f"Oversold: RSI at {latest['RSI']:.2f}")
                signals['score'] += 30
            else:  # Short analysis - potential reversal warning
                signals['signals'].append(f"Warning: RSI oversold at {latest['RSI']:.2f}")
                signals['score'] -= 15
        else:  # RSI > 70
            if side != OrderSide.BUY:  # Bearish or neutral analysis
                signals['signals'].append(f"Overbought: RSI at {latest['RSI']:.2f}")
                signals['score'] -= 30
            else:  # Long analysis - potential reversal warning
                signals['signals'].append(f"Warning: RSI overbought at {latest['RSI']:.2f}")
                signals['score'] += 15
        
        # MACD Analysis
        if latest['MACD'] > latest['MACD_Signal'] and prev['MACD'] <= prev['MACD_Signal']:
            if side != OrderSide.SELL:  # Bullish or neutral analysis
                signals['signals'].append("Bullish MACD crossover")
                signals['score'] += 25
            else:  # Short analysis - reversal warning
                signals['signals'].append("Warning: Bullish MACD crossover")
                signals['score'] -= 25
        elif latest['MACD'] < latest['MACD_Signal'] and prev['MACD'] >= prev['MACD_Signal']:
            if side != OrderSide.BUY:  # Bearish or neutral analysis
                signals['signals'].append("Bearish MACD crossover")
                signals['score'] -= 25
            else:  # Long analysis - reversal warning
                signals['signals'].append("Warning: Bearish MACD crossover")
                signals['score'] += 25
        
        # Bollinger Bands Analysis
        if latest['close'] < latest['BB_Lower']:
            if side != OrderSide.SELL:  # Bullish or neutral analysis
                signals['signals'].append("Price below lower Bollinger Band - potential oversold")
                signals['score'] += 25
            else:  # Short analysis - potential reversal warning
                signals['signals'].append("Warning: Price below lower Bollinger Band")
                signals['score'] -= 15
        elif latest['close'] > latest['BB_Upper']:
            if side != OrderSide.BUY:  # Bearish or neutral analysis
                signals['signals'].append("Price above upper Bollinger Band - potential overbought")
                signals['score'] -= 25
            else:  # Long analysis - potential reversal warning
                signals['signals'].append("Warning: Price above upper Bollinger Band")
                signals['score'] += 15
        
        # Add momentum to score
        if side == OrderSide.BUY:
            signals['score'] += (signals['momentum'] > 0) * 20  # Bonus for positive momentum
        elif side == OrderSide.SELL:
            signals['score'] += (signals['momentum'] < 0) * 20  # Bonus for negative momentum
            
        # Normalize score from -100,100 to 0,1 range
        signals['raw_score'] = signals['score']
        signals['score'] = (signals['score'] + 100) / 200
        return signals

def analyze_hype_stocks(hype_stocks):
    """Analyze technical indicators for hype stocks"""
    analyzer = TechnicalAnalyzer()
    results = []
    
    for stock in hype_stocks:
        ticker = stock['ticker']
        print(f"Analyzing technical indicators for {ticker}...")
        
        technical_data = analyzer.analyze_stock(ticker)
        if technical_data:
            # Combine sentiment and technical analysis
            combined_score = (stock['average_sentiment'] * 50) + (technical_data['score'] * 0.5)
            results.append({
                'ticker': ticker,
                'sentiment_score': stock['average_sentiment'],
                'technical_score': technical_data['score'],
                'combined_score': combined_score,
                'price': technical_data['price'],
                'technical_signals': technical_data['signals'],
                'recent_news': stock['recent_news']
            })
    
    # Sort by combined score
    results.sort(key=lambda x: x['combined_score'], reverse=True)
    return results

if __name__ == "__main__":
    # Test with a single stock
    analyzer = TechnicalAnalyzer()
    result = analyzer.analyze_stock('AAPL')
    print(f"\nAnalysis for AAPL:")
    print(f"Price: ${result['price']:.2f}")
    print(f"Technical Score: {result['score']}")
    print("\nSignals:")
    for signal in result['signals']:
        print(f"- {signal}")
