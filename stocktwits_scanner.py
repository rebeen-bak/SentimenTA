import os
import requests
import pandas as pd
from datetime import datetime
import json

class StocktwitsScanner:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def get_trending_stocks(self, limit=20):
        """
        Get trending stocks from Stocktwits
        Returns DataFrame with columns: ticker, watchlist_count, sentiment, source, timestamp
        """
        try:
            print("Fetching Stocktwits trending data...")
            url = 'https://api.stocktwits.com/api/2/trending/symbols.json'
            response = requests.get(url, headers=self.headers)
            
            if response.status_code != 200:
                print(f"Error: Stocktwits API returned status code {response.status_code}")
                return pd.DataFrame()
            
            try:
                data = response.json()
                symbols = data.get('symbols', [])
                
                # Convert to DataFrame
                df = pd.DataFrame(symbols)
                if df.empty:
                    return df
                
                # Rename columns to match our schema
                df = df.rename(columns={
                    'symbol': 'ticker',
                    'watchlist_count': 'mentions'
                })
                
                # Calculate sentiment based on watchlist ranking
                df['rank'] = df['mentions'].rank(ascending=False)
                df['sentiment'] = (df['rank'].max() - df['rank']) / df['rank'].max() * 2 - 1
                
                # Add source and timestamp
                df['source'] = 'stocktwits'
                df['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Sort by mentions and get top N
                df = df.sort_values('mentions', ascending=False).head(limit)
                
                print(f"Found {len(df)} trending stocks from Stocktwits")
                return df
                
            except json.JSONDecodeError:
                print("Error: Invalid JSON response from Stocktwits")
                return pd.DataFrame()
                
        except Exception as e:
            print(f"Error fetching Stocktwits data: {str(e)}")
            return pd.DataFrame()

def main():
    scanner = StocktwitsScanner()
    df = scanner.get_trending_stocks()
    
    if not df.empty:
        print("\nTop Trending Stocks on Stocktwits:")
        for _, row in df.iterrows():
            print(f"\n{row['ticker']}:")
            print(f"Watchlist Count: {row['mentions']}")
            print(f"Sentiment Score: {row['sentiment']:.3f}")
    else:
        print("No trending stocks found")

if __name__ == "__main__":
    main()
