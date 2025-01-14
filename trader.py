import os
import time
from datetime import datetime
from dotenv import load_dotenv
from alpaca.trading.enums import OrderSide
from social_scanner import SocialScanner
from technical_analysis import TechnicalAnalyzer
from position_manager import PositionManager
import pandas as pd

class Trader:
    def __init__(self):
        self.position_manager = PositionManager()
    
    def manage_existing_positions(self, analyzer):
        """First step: Analyze and manage existing positions"""
        print("\nStep 1: Managing Existing Positions...")
        
        # Get current positions
        current_positions = self.position_manager.update_positions()
        if not current_positions:
            print("No existing positions to manage.")
            return
            
        # Analyze each position
        for symbol in list(current_positions.keys()):
            print(f"\nAnalyzing {symbol}...")
            position = current_positions[symbol]
            side = OrderSide.BUY if float(position.qty) > 0 else OrderSide.SELL
            technical_data = analyzer.analyze_stock(symbol, side)
            
            if technical_data:
                # Check if position should be closed based on technical signals
                if self.position_manager.should_close_position(symbol, technical_data):
                    self.position_manager.close_position(symbol)
                else:
                    print(f"Maintaining position in {symbol}:")
                    print(f"Technical score: {technical_data['score']:.2f}")
                    print("Signals:")
                    for signal in technical_data['signals']:
                        print(f"  - {signal}")
                    print(f"Momentum: {technical_data['momentum']:.1f}%")
            else:
                print(f"Could not get technical data for {symbol} - maintaining position")
    
    def find_new_opportunities(self, analyzer):
        """Find and execute new trading opportunities"""
        print("\nFinding New Opportunities...")
        
        # Get ranked stocks from social scanner
        scanner = SocialScanner()
        print("\nFinding and ranking social stocks...")
        df = scanner.get_trending_stocks()
        
        if df.empty:
            print("No trending stocks found.")
            return
        
        # Get current positions and pending orders
        current_positions = set(self.position_manager.positions.keys())
        pending_orders = {order['symbol'] for order in self.position_manager.pending_orders}
        
        # Get top 10 stocks by final rank
        top_stocks = df.head(10)
        target_symbols = set(top_stocks['ticker'])
        
        # Check positions that fell out of top 10
        for symbol in current_positions:
            if symbol not in target_symbols:
                print(f"\n{symbol} fell out of top 10, checking technicals...")
                technical_data = analyzer.analyze_stock(symbol)
                if technical_data:
                    if technical_data['score'] < 0.4:  # Below 40% technical score
                        print(f"Closing {symbol} - weak technicals: {technical_data['score']:.2f}")
                        self.position_manager.close_position(symbol)
                    else:
                        print(f"Keeping {symbol} - good technicals: {technical_data['score']:.2f}")
        
        # Enter new positions for stocks in top 10
        print("\nChecking for new positions (8% each):")
        for _, stock in top_stocks.iterrows():
            ticker = stock['ticker']
            
            # Skip if we already have position
            if ticker in current_positions:
                print(f"\nSkipping {ticker} - already in portfolio")
                continue
                
            # Skip if we already have a pending order (prevent duplicate after-hours orders)
            if ticker in pending_orders:
                print(f"\nSkipping {ticker} - order already queued")
                print(f"Will execute when market opens")
                continue
                
            # Get latest price and verify technicals
            technical_data = analyzer.analyze_stock(ticker)
            if not technical_data:
                print(f"Could not get price data for {ticker}")
                continue
            
            price = technical_data['price']
            print(f"\n{ticker} (Final Rank: {stock['final_rank']:.1f}):")
            print(f"Sentiment Rank: {stock['sentiment_rank']:.1f}")
            print(f"Technical Rank: {stock['ta_rank']}")
            print(f"Current Price: ${price:.2f}")
            
            # Verify technicals still good
            if technical_data['score'] < 0.4:  # Below 40% technical score
                print(f"Skipping {ticker} - weak technicals: {technical_data['score']:.2f}")
                continue
            
            # Calculate 8% position
            shares, allow_trade = self.position_manager.calculate_target_position(
                ticker,
                price,
                OrderSide.BUY,
                target_pct=0.08  # 8% position size
            )
            
            if allow_trade and shares > 0:
                print(f"Placing order for {shares} shares (8% position)")
                order = self.position_manager.place_order(
                    ticker,
                    shares,
                    side=OrderSide.BUY
                )
                if order:
                    print(f"Order placed successfully: {order.id}")
            else:
                print("Skipping trade - position limits reached")
    
    def should_exit_position(self, symbol, technical_data):
        """Determine if we should exit a position based only on technicals"""
        # Exit if:
        # 1. Strong bearish trend (price below both MAs)
        # 2. Strong bearish MACD
        # 3. Large 24h loss (>5%)
        # Get values from technical data
        price = technical_data['price']
        signals = technical_data['signals']
        momentum = technical_data['momentum']
        
        # Parse moving averages from signals
        below_both_mas = any('below both MAs' in signal for signal in signals)
        
        # Parse MACD from signals
        strong_bearish_macd = any('Strong bearish MACD' in signal for signal in signals)
        
        exit_signals = []
        
        if below_both_mas:
            exit_signals.append("Price below both moving averages")
            
        if strong_bearish_macd:
            exit_signals.append("Strong bearish MACD signal")
            
        if momentum < -5:  # >5% loss in 24h
            exit_signals.append(f"Large price drop: {momentum:.1f}%")
            
        # Exit if any two signals are triggered
        if len(exit_signals) >= 2:
            print(f"\nExit signals for {symbol}:")
            for signal in exit_signals:
                print(f"- {signal}")
            return True
            
        return False
    
    def monitor_positions(self, interval_seconds=300):  # 5 minutes
        """Continuously monitor positions and exit based on technicals"""
        analyzer = TechnicalAnalyzer()
        
        while True:
            positions = self.position_manager.update_positions()
            if not positions:
                print("No positions to monitor")
                break
                
            print("\nMonitoring positions...")
            for symbol in list(positions.keys()):
                technical_data = analyzer.analyze_stock(symbol)
                if technical_data:
                    if self.should_exit_position(symbol, technical_data):
                        print(f"\nExiting {symbol} based on technical signals")
                        self.position_manager.close_position(symbol)
                        
            time.sleep(interval_seconds)
    
    def analyze_and_trade(self):
        """Main trading function - three-step process"""
        # Initialize analyzer
        analyzer = TechnicalAnalyzer()
        
        # Step 1: Manage existing positions
        self.manage_existing_positions(analyzer)
        
        # Step 2: Find new opportunities
        self.find_new_opportunities(analyzer)
        
        # Step 3: Start monitoring loop
        print("\nStarting position monitor...")
        self.monitor_positions()

def main():
    trader = Trader()
    trader.analyze_and_trade()

if __name__ == "__main__":
    main()
