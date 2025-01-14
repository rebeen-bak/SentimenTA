import pandas as pd
from wsb_scanner import WSBScanner
from stocktwits_scanner import StocktwitsScanner
from technical_analysis import TechnicalAnalyzer

class SocialScanner:
    def __init__(self):
        self.wsb_scanner = WSBScanner()
        self.stocktwits_scanner = StocktwitsScanner()
        self.technical_analyzer = TechnicalAnalyzer()
    
    def get_trending_stocks(self, limit=20):
        """
        Get trending stocks from Reddit and Stocktwits, then rank by TA
        Returns DataFrame with columns: ticker, sentiment_rank, ta_rank, final_rank
        """
        print("Starting social scanner...")
        
        # Get top 20 from each source
        print("\nFetching Reddit data...")
        wsb_df = self.wsb_scanner.get_trending_stocks(limit)
        wsb_df = wsb_df.head(limit)
        wsb_df['ape_rank'] = range(1, len(wsb_df) + 1)
        
        print("\nFetching Stocktwits data...")
        st_df = self.stocktwits_scanner.get_trending_stocks(limit)
        st_df = st_df.head(limit)
        st_df['st_rank'] = range(1, len(st_df) + 1)
        
        # Combine dataframes
        if not wsb_df.empty and not st_df.empty:
            # Merge on ticker, keeping all stocks from both sources
            df = pd.merge(wsb_df[['ticker', 'ape_rank']], 
                         st_df[['ticker', 'st_rank']], 
                         on='ticker', 
                         how='outer')
            
            # Fill missing ranks with high value (worse than being rank 20)
            df['ape_rank'] = df['ape_rank'].fillna(limit + 1)
            df['st_rank'] = df['st_rank'].fillna(limit + 1)
            
            # Calculate sentiment rank:
            # - If in both lists: average of ranks
            # - If in one list: use that rank
            df['in_both'] = (~df['ape_rank'].isna()) & (~df['st_rank'].isna())
            df['sentiment_rank'] = df.apply(
                lambda row: (row['ape_rank'] + row['st_rank']) / 2 if row['in_both']
                else min(row['ape_rank'], row['st_rank']),
                axis=1
            )
            
            print(f"\nFound {len(df)} unique stocks from both sources")
            
            # Run technical analysis
            print("\nRunning technical analysis...")
            ta_results = []
            for _, row in df.iterrows():
                ticker = row['ticker']
                print(f"\nAnalyzing {ticker}...")
                ta_data = self.technical_analyzer.analyze_stock(ticker)
                if ta_data:
                    ta_results.append({
                        'ticker': ticker,
                        'technical_score': ta_data['score']
                    })
            
            # Add technical ranks
            ta_df = pd.DataFrame(ta_results)
            if not ta_df.empty:
                ta_df = ta_df.sort_values('technical_score', ascending=False)
                ta_df['ta_rank'] = range(1, len(ta_df) + 1)
                
                # Merge technical ranks
                df = pd.merge(df, ta_df[['ticker', 'ta_rank']], on='ticker', how='left')
                
                # Calculate final rank (sentiment + technical)
                df['final_rank'] = df['sentiment_rank'] + df['ta_rank']
                
                # Sort by final rank (lower is better)
                df = df.sort_values('final_rank')
                
                print("\nFinal Rankings:")
                for _, row in df.iterrows():
                    print(f"{row['ticker']}: sentiment={row['sentiment_rank']:.0f}, "
                          f"ta={row['ta_rank']:.0f}, final={row['final_rank']:.0f}")
                
                return df
            
        print("No stocks found or no technical data available")
        return pd.DataFrame()

def main():
    scanner = SocialScanner()
    df = scanner.get_trending_stocks()
    
    if not df.empty:
        print("\nTop Ranked Stocks (lower is better):")
        print("- Sentiment rank: Best rank between ApeWisdom (1-20) and Stocktwits (1-20)")
        print("- TA rank: Technical analysis rank (1-N)")
        print("- Final rank: sentiment_rank + ta_rank")
        print("\nTop 10 Stocks:")
        
        for _, row in df.head(10).iterrows():
            print(f"\n{row['ticker']}:")
            in_both = row['in_both']
            if in_both:
                print(f"ApeWisdom Rank: {row['ape_rank']:.0f}")
                print(f"Stocktwits Rank: {row['st_rank']:.0f}")
                print(f"Average Sentiment Rank: {row['sentiment_rank']:.1f}")
            else:
                if row['ape_rank'] <= 20:
                    print(f"ApeWisdom Rank: {row['ape_rank']:.0f}")
                if row['st_rank'] <= 20:
                    print(f"Stocktwits Rank: {row['st_rank']:.0f}")
                print(f"Sentiment Rank: {row['sentiment_rank']:.0f}")
            print(f"Technical Rank: {row['ta_rank']:.0f}")
            print(f"Final Rank: {row['final_rank']:.0f}")
    else:
        print("No stocks found")

if __name__ == "__main__":
    main()
