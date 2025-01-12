import pandas as pd
from wsb_scanner import WSBScanner
from stocktwits_scanner import StocktwitsScanner

class SocialScanner:
    def __init__(self):
        self.wsb_scanner = WSBScanner()
        self.stocktwits_scanner = StocktwitsScanner()
    
    def get_trending_stocks(self, limit=20):
        """
        Get trending stocks from all social sources and combine them
        Returns DataFrame with columns: ticker, mentions, sentiment, sources
        """
        print("Starting social scanner...")
        
        # Get data from all sources
        print("\nFetching Reddit/WSB data...")
        wsb_df = self.wsb_scanner.get_ape_wisdom(limit)  # Using only ApeWisdom for now
        print(f"WSB DataFrame shape: {wsb_df.shape}")
        
        print("\nFetching Stocktwits data...")
        stocktwits_df = self.stocktwits_scanner.get_trending_stocks(limit)
        print(f"Stocktwits DataFrame shape: {stocktwits_df.shape}")
        
        # Combine dataframes
        print("\nCombining data sources...")
        combined_df = pd.concat([wsb_df, stocktwits_df], ignore_index=True)
        print(f"Combined DataFrame shape: {combined_df.shape}")
        
        if combined_df.empty:
            return combined_df
        
        # Group by ticker and aggregate
        grouped = combined_df.groupby('ticker').agg({
            'mentions': 'sum',
            'sentiment': 'mean',
            'source': lambda x: ','.join(sorted(set(x))),
            'timestamp': 'first'
        }).reset_index()
        
        # Calculate a combined score (mentions + sentiment)
        grouped['score'] = (
            grouped['mentions'].rank(pct=True) * 0.7 +  # 70% weight on mentions
            grouped['sentiment'].rank(pct=True) * 0.3    # 30% weight on sentiment
        )
        
        # Sort by combined score and get top N
        final_df = grouped.sort_values('score', ascending=False).head(limit)
        
        print(f"\nFound {len(final_df)} total trending stocks after combining sources")
        return final_df

def main():
    scanner = SocialScanner()
    df = scanner.get_trending_stocks()
    
    if not df.empty:
        print("\nTop Social Trending Stocks:")
        for _, row in df.iterrows():
            print(f"\n{row['ticker']}:")
            print(f"Total Mentions: {row['mentions']}")
            print(f"Average Sentiment: {row['sentiment']:.3f}")
            print(f"Combined Score: {row['score']:.3f}")
            print(f"Sources: {row['source']}")
    else:
        print("No trending stocks found")

if __name__ == "__main__":
    main()
