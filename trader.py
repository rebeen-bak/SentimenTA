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
        """Manage existing positions"""
        current_positions = self.position_manager.update_positions()
        if not current_positions:
            return
            
        # Check each position
        for symbol in list(current_positions.keys()):
            position = current_positions[symbol]
            side = OrderSide.BUY if float(position.qty) > 0 else OrderSide.SELL
            technical_data = analyzer.analyze_stock(symbol, side)
            
            if technical_data and self.should_exit_position(symbol, technical_data):
                print(f"\nSELL {symbol}: {', '.join(technical_data['exit_signals'])}")
                self.position_manager.close_position(symbol)
    
    def find_new_opportunities(self, analyzer):
        """Find and execute new trades"""
        # Get ranked stocks
        scanner = SocialScanner()
        df = scanner.get_trending_stocks()
        if df.empty:
            return
        
        # Show top 10 rankings
        print("\nTop 10 Ranked Stocks:")
        for _, stock in df.head(10).iterrows():
            print(f"{stock['ticker']}: Rank {stock['final_rank']:.1f} (Sentiment: {stock['sentiment_rank']:.1f}, TA: {stock['ta_rank']:.0f})")
        
        # Get current positions and pending orders
        current_positions = set(self.position_manager.positions.keys())
        pending_orders = {order['symbol'] for order in self.position_manager.pending_orders}
        
        # Check positions that fell out of top 10
        top_stocks = df.head(10)
        target_symbols = set(top_stocks['ticker'])
        for symbol in current_positions:
            if symbol not in target_symbols:
                technical_data = analyzer.analyze_stock(symbol)
                if technical_data and technical_data['score'] < 0.4:
                    print(f"\nSELL {symbol}: Fell out of top 10, weak technicals")
                    self.position_manager.close_position(symbol)
        
        # Enter new positions
        for _, stock in top_stocks.iterrows():
            ticker = stock['ticker']
            if ticker in current_positions:
                print(f"\nSkipping {ticker} - already in portfolio")
                continue
            if ticker in pending_orders:
                print(f"\nSkipping {ticker} - order already pending")
                continue
            
            technical_data = analyzer.analyze_stock(ticker)
            if not technical_data or technical_data['score'] < 0.4:
                continue
            
            shares, allow_trade = self.position_manager.calculate_target_position(
                ticker,
                technical_data['price'],
                OrderSide.BUY,
                target_pct=0.08
            )
            
            if allow_trade and shares > 0:
                print(f"\nBUY {ticker}: Rank {stock['final_rank']:.1f} (Sentiment: {stock['sentiment_rank']:.1f}, TA: {stock['ta_rank']:.0f})")
                print(f"Order: {shares} shares @ ${technical_data['price']:.2f}")
                self.position_manager.place_order(ticker, shares, side=OrderSide.BUY)
    
    def should_exit_position(self, symbol, technical_data):
        """Check exit signals"""
        signals = technical_data['signals']
        momentum = technical_data['momentum']
        
        exit_signals = []
        
        if any('below both MAs' in signal for signal in signals):
            exit_signals.append("Below MAs")
        if any('Strong bearish MACD' in signal for signal in signals):
            exit_signals.append("Bearish MACD")
        if momentum < -5:
            exit_signals.append(f"{momentum:.1f}% Drop")
        
        technical_data['exit_signals'] = exit_signals
        return len(exit_signals) >= 2
    
    def monitor_positions(self, interval_seconds=300):
        """Monitor positions every 5 minutes"""
        analyzer = TechnicalAnalyzer()
        
        while True:
            positions = self.position_manager.update_positions()
            if not positions:
                break
                
            for symbol in list(positions.keys()):
                technical_data = analyzer.analyze_stock(symbol)
                if technical_data and self.should_exit_position(symbol, technical_data):
                    print(f"\nSELL {symbol}: {', '.join(technical_data['exit_signals'])}")
                    self.position_manager.close_position(symbol)
                    
            time.sleep(interval_seconds)
    
    def analyze_and_trade(self):
        """Main trading loop"""
        analyzer = TechnicalAnalyzer()
        self.manage_existing_positions(analyzer)
        self.find_new_opportunities(analyzer)
        self.monitor_positions()

def main():
    trader = Trader()
    trader.analyze_and_trade()

if __name__ == "__main__":
    main()
