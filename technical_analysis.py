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
        try:
            # Get today's date in ET
            et_tz = datetime.now().astimezone().tzinfo
            today = datetime.now(et_tz).date()
            
            # Set end to today's market close (4 PM ET)
            end = datetime.combine(today, datetime.strptime('16:00', '%H:%M').time())
            end = end.replace(tzinfo=et_tz)
            
            # Set start to lookback days before
            start = end - timedelta(days=lookback_days)
            
            print(f"Requesting data from {start} to {end} ET")
            
            request = StockBarsRequest(
                symbol_or_symbols=[symbol],
                timeframe=TimeFrame.Day,
                start=start,
                end=end,
                adjustment='all'  # Get adjusted prices
            )
            
            bars = self.client.get_stock_bars(request)
            df = bars.df
            
            if df.empty:
                print(f"No data returned for {symbol}")
                return None
            
            # Print actual date range we got
            print(f"Got data from {df.index[0]} to {df.index[-1]} ET")
            
            # Print last few prices to verify freshness
            print("\nLast 5 closing prices:")
            for date, price in df['close'][-5:].items():
                print(f"{date}: ${price:.2f}")
            
            return df
            
        except Exception as e:
            print(f"Error getting data: {str(e)}")
            return None
    
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
        
        # Get latest values
        latest = df.iloc[-1]  # Today's close
        prev = df.iloc[-2]    # Yesterday's close
        
        # Calculate 24h changes to match ApeWisdom timeframe
        price_24h_change = ((latest['close'] / prev['close']) - 1) * 100
        mentions_24h_change = None  # We'll get this from ApeWisdom
        
        print("\nPrice Data (24h Changes):")
        print(f"Latest close: ${latest['close']:.2f}")
        print(f"Previous close: ${prev['close']:.2f}")
        print(f"24h Change: {price_24h_change:+.2f}%")
        print(f"Date range: {df.index[0]} to {df.index[-1]}")
        
        print("\nIndicators:")
        print(f"RSI: {latest['RSI']:.2f}")
        print(f"MACD: {latest['MACD']:.3f} vs Signal: {latest['MACD_Signal']:.3f}")
        print(f"20 SMA: {latest['SMA_20']:.2f} vs 50 SMA: {latest['SMA_50']:.2f}")
        
        signals = {
            'symbol': symbol,
            'price': latest['close'],
            'signals': [],
            'raw_score': 0,  # Raw technical score (-100 to 100)
            'score': 0,      # Normalized score (0 to 1)
            'momentum': price_24h_change  # 24h price change
        }
        
        # Price must be above both moving averages for bullish
        price = latest['close']
        sma20 = latest['SMA_20']
        sma50 = latest['SMA_50']
        
        if price > sma20 and price > sma50:
            if sma20 > sma50:  # Perfect uptrend
                signals['signals'].append("Strong bullish trend: Price > 20 SMA > 50 SMA")
                signals['score'] += 30
            else:  # Price above but mixed MAs
                signals['signals'].append("Mixed trend: Price above MAs but 20 SMA < 50 SMA")
                signals['score'] += 10
        else:  # Price below either MA
            if price < sma20 and price < sma50:
                signals['signals'].append("Bearish trend: Price below both MAs")
                signals['score'] -= 30
            else:
                signals['signals'].append("Mixed trend: Price between MAs")
                signals['score'] -= 10
        
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
        
        # MACD Analysis - require strong signals
        macd = latest['MACD']
        signal = latest['MACD_Signal']
        macd_diff = macd - signal  # Difference between MACD and signal
        
        if abs(macd_diff) < 0.1:  # Very close - no clear signal
            signals['signals'].append("Weak MACD signal")
            signals['score'] -= 10
        elif macd > signal:
            if macd_diff > 0.5:  # Strong bullish
                signals['signals'].append("Strong bullish MACD")
                signals['score'] += 30
            else:  # Weak bullish
                signals['signals'].append("Weak bullish MACD")
                signals['score'] += 10
        else:  # MACD below signal
            if macd_diff < -0.5:  # Strong bearish
                signals['signals'].append("Strong bearish MACD")
                signals['score'] -= 30
            else:  # Weak bearish
                signals['signals'].append("Weak bearish MACD")
                signals['score'] -= 10
        
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
        
        # 24h momentum analysis
        if signals['momentum'] > 2:  # >2% gain
            signals['signals'].append(f"Strong 24h gain: {signals['momentum']:.1f}%")
            signals['score'] += 30
        elif signals['momentum'] > 0:  # Any gain
            signals['signals'].append(f"24h gain: {signals['momentum']:.1f}%")
            signals['score'] += 15
        elif signals['momentum'] > -2:  # Small loss
            signals['signals'].append(f"Small 24h loss: {signals['momentum']:.1f}%")
            signals['score'] -= 15
        else:  # >2% loss
            signals['signals'].append(f"Large 24h loss: {signals['momentum']:.1f}%")
            signals['score'] -= 30
            
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
