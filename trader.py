import os
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
        """Second step: Find and execute new trading opportunities"""
        print("\nStep 2: Finding New Opportunities...")
        
        # Get social sentiment data
        scanner = SocialScanner()
        print("\nFinding trending social stocks...")
        df = scanner.get_trending_stocks()
        
        if df.empty:
            print("No trending stocks found today.")
            return
        
        print("\nAnalyzing technical indicators...")
        analyzed_stocks = []
        
        for _, stock in df.iterrows():
            ticker = stock['ticker']
            # Skip crypto tickers
            if '.X' in ticker:
                continue
                
            print(f"\nAnalyzing {ticker}...")
            # Initial neutral analysis for screening
            technical_data = analyzer.analyze_stock(ticker, None)
            if technical_data:
                analyzed_stocks.append({
                    'ticker': ticker,
                    'price': technical_data['price'],
                    'social_score': stock['score'],
                    'sentiment': stock['sentiment'],
                    'mentions': stock['mentions'],
                    'technical_score': technical_data['score'],
                    'technical_signals': technical_data['signals'],
                    'momentum': technical_data['momentum'],
                    'sources': stock['source']
                })
        
        if not analyzed_stocks:
            print("No stocks passed technical analysis.")
            return
        
        # Convert scores to percentile ranks
        scores = [stock['social_score'] for stock in analyzed_stocks]
        social_ranks = pd.Series(scores).rank(pct=True)
        
        scores = [stock['technical_score'] for stock in analyzed_stocks]
        technical_ranks = pd.Series(scores).rank(pct=True)
        
        # Calculate combined score using percentile ranks
        for i, stock in enumerate(analyzed_stocks):
            stock['social_percentile'] = social_ranks[i]
            stock['technical_percentile'] = technical_ranks[i]
            stock['combined_score'] = (
                social_ranks[i] * 0.4 +      # 40% weight on social metrics
                technical_ranks[i] * 0.6      # 60% weight on technical analysis
            )
        
        # Sort stocks by combined score
        analyzed_stocks.sort(key=lambda x: x['combined_score'], reverse=True)
        
        # Check exposure before proceeding
        account = self.position_manager.get_account_info()
        available_equity = float(account['equity'])
        current_exposure = sum(p.get_exposure(available_equity) 
                             for p in self.position_manager.positions.values())
        
        # More conservative exposure limit for new positions
        if current_exposure >= self.position_manager.max_total_exposure * 0.9:  # 90% of max
            print(f"\nNear maximum exposure ({current_exposure:.1%}) - no new positions")
            print(f"Max allowed: {self.position_manager.max_total_exposure * 100:.0f}%")
            print("Focusing on managing existing positions")
            return
            
        remaining_exposure = self.position_manager.max_total_exposure - current_exposure
        print(f"\nCurrent exposure: {current_exposure:.1%}")
        print(f"Remaining exposure available: {remaining_exposure:.1%}")
        
        # Second pass: Process new opportunities
        print("\nProcessing trading opportunities...")
        
        # Use very strict thresholds when near capacity
        if current_exposure > self.position_manager.max_total_exposure * 0.7:  # Above 70% capacity
            long_threshold = 0.80  # Only exceptional longs
            short_threshold = 0.20  # Only exceptional shorts
            print("Using stricter thresholds due to high exposure")
        else:
            long_threshold = 0.70  # Normal thresholds
            short_threshold = 0.30
        
        # Get current position symbols
        current_positions = set(self.position_manager.positions.keys())
        
        # Filter candidates with strict thresholds
        long_candidates = [s for s in analyzed_stocks 
                         if s['combined_score'] > long_threshold 
                         and s['ticker'] not in current_positions][:10]
        
        short_candidates = [s for s in analyzed_stocks 
                          if s['combined_score'] < short_threshold 
                          and s['ticker'] not in current_positions][-10:]
        short_candidates.reverse()  # Show worst first
        
        # Ensure no overlap between long and short lists
        long_symbols = set(s['ticker'] for s in long_candidates)
        short_candidates = [s for s in short_candidates if s['ticker'] not in long_symbols]
        
        print("\nLong Opportunities (Top 10):")
        for stock in long_candidates:
            print(f"\n{stock['ticker']}:")
            print(f"Current Price: ${stock['price']:.2f}")
            print(f"Social Metrics:")
            print(f"  Raw Score: {stock['social_score']:.3f}")
            print(f"  Percentile: {stock['social_percentile']:.1%}")
            print(f"  Mentions: {stock['mentions']}")
            print(f"  Sentiment: {stock['sentiment']:.3f}")
            print(f"  Sources: {stock['sources']}")
            
            # Re-analyze with long bias
            technical_data = analyzer.analyze_stock(stock['ticker'], OrderSide.BUY)
            if technical_data:
                print(f"Technical Analysis (Long Bias):")
                print(f"  Score: {technical_data['score']:.3f}")
                print(f"  Momentum: {technical_data['momentum']:.1f}%")
                print("  Signals:")
                for signal in technical_data['signals']:
                    print(f"    - {signal}")
                
                print(f"Combined Score (Percentile): {stock['combined_score']:.1%}")
                
                if technical_data['momentum'] > 0:  # Only long if momentum is positive
                    shares, allow_trade = self.position_manager.calculate_target_position(
                        stock['ticker'], 
                        stock['price'],
                        OrderSide.BUY
                    )
                    
                    if allow_trade and shares > 0:
                        print(f"\nPlacing LONG order for {shares} shares of {stock['ticker']}")
                        order = self.position_manager.place_order(
                            stock['ticker'], 
                            shares, 
                            side=OrderSide.BUY
                        )
                        if order:
                            print(f"Long order placed successfully: {order.id}")
                    else:
                        print("\nSkipping long trade - position limits reached")
                else:
                    print("\nSkipping long trade - negative momentum")
        
        print("\nShort Opportunities (Bottom 10):")
        for stock in short_candidates:
            print(f"\n{stock['ticker']}:")
            print(f"Current Price: ${stock['price']:.2f}")
            print(f"Social Metrics:")
            print(f"  Raw Score: {stock['social_score']:.3f}")
            print(f"  Percentile: {stock['social_percentile']:.1%}")
            print(f"  Mentions: {stock['mentions']}")
            print(f"  Sentiment: {stock['sentiment']:.3f}")
            print(f"  Sources: {stock['sources']}")
            
            # Re-analyze with short bias
            technical_data = analyzer.analyze_stock(stock['ticker'], OrderSide.SELL)
            if technical_data:
                print(f"Technical Analysis (Short Bias):")
                print(f"  Score: {technical_data['score']:.3f}")
                print(f"  Momentum: {technical_data['momentum']:.1f}%")
                print("  Signals:")
                for signal in technical_data['signals']:
                    print(f"    - {signal}")
                
                print(f"Combined Score (Percentile): {stock['combined_score']:.1%}")
                
                if technical_data['momentum'] < 0:  # Only short if momentum is negative
                    shares, allow_trade = self.position_manager.calculate_target_position(
                        stock['ticker'],
                        stock['price'],
                        OrderSide.SELL
                    )
                    
                    if allow_trade and shares > 0:
                        print(f"\nPlacing SHORT order for {shares} shares of {stock['ticker']}")
                        order = self.position_manager.place_order(
                            stock['ticker'],
                            shares,
                            side=OrderSide.SELL
                        )
                        if order:
                            print(f"Short order placed successfully: {order.id}")
                    else:
                        print("\nSkipping short trade - position limits reached")
                else:
                    print("\nSkipping short trade - positive momentum")
        
        # Final position update
        current_positions = self.position_manager.update_positions()
        print("\nTrading session complete.")

    def analyze_and_trade(self):
        """Main trading function - two-step process"""
        # Initialize analyzer
        analyzer = TechnicalAnalyzer()
        
        # Step 1: Manage existing positions
        self.manage_existing_positions(analyzer)
        
        # Step 2: Find new opportunities
        self.find_new_opportunities(analyzer)
        
        # Final position update
        self.position_manager.update_positions()
        print("\nTrading session complete.")

def main():
    trader = Trader()
    trader.analyze_and_trade()

if __name__ == "__main__":
    main()
