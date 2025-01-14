import os
import requests
import pandas as pd
import numpy as np
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
                
                # Filter to only stocks
                df = df[df['instrument_class'] == 'Stock']
                
                # Get sentiment from messages
                def get_message_sentiment(ticker):
                    try:
                        messages_url = f'https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json'
                        response = requests.get(messages_url, headers=self.headers)
                        if response.status_code == 200:
                            data = response.json()
                            messages = data.get('messages', [])
                            if messages:
                                # Count sentiment in last 100 messages
                                bullish = 0
                                bearish = 0
                                total = 0
                                
                                for message in messages[:100]:
                                    if 'entities' in message:
                                        sentiment = message['entities'].get('sentiment', {})
                                        if sentiment and 'basic' in sentiment:
                                            total += 1
                                            if sentiment['basic'] == 'Bullish':
                                                bullish += 1
                                            elif sentiment['basic'] == 'Bearish':
                                                bearish += 1
                                
                                if total > 0:
                                    bullish_ratio = bullish / total
                                    print(f"{ticker}: {bullish} bullish, {bearish} bearish, {total-bullish-bearish} neutral ({bullish_ratio:.2%} bullish)")
                                    return bullish_ratio
                        return 0.5  # Neutral if no data
                    except Exception as e:
                        print(f"Error getting sentiment for {ticker}: {str(e)}")
                        return 0.5
                
                print("\nGetting message sentiment...")
                df['bullish_ratio'] = df['ticker'].apply(get_message_sentiment)
                
                # Filter for minimum watchers to avoid penny stocks
                min_watchers = 1000
                df = df[df['mentions'] >= min_watchers]
                print(f"\nFound {len(df)} stocks with >{min_watchers:,} watchers")
                
                # Filter for >60% bullish
                df = df[df['bullish_ratio'] > 0.6]
                if df.empty:
                    print("No stocks found with >60% bullish sentiment")
                    return df
                
                # Calculate score as log10(watchers) * bullish_ratio
                df['log_mentions'] = np.log10(df['mentions'])
                df['score'] = df['log_mentions'] * df['bullish_ratio']
                
                # Sort by score
                df = df.sort_values('score', ascending=False)
                df['rank'] = range(1, len(df) + 1)
                
                print(f"\nFound {len(df)} stocks with >60% bullish sentiment")
                
                # Show analysis
                print("\nStock Analysis:")
                for _, row in df.iterrows():
                    print(f"{row['ticker']}: {row['mentions']:,} watchers (log10={row['log_mentions']:.2f}), {row['bullish_ratio']:.2%} bullish, score={row['score']:.2f}")
                
                # Add source and timestamp
                df['source'] = 'stocktwits'
                df['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Get top N stocks
                df = df.head(limit)
                
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
            print(f"\n{row['ticker']} (Rank {row['rank']}):")
            print(f"Watchlist Count: {row['mentions']:,} (log10={row['log_mentions']:.2f})")
            print(f"Bullish Ratio: {row['bullish_ratio']:.1%}")
            print(f"Score: {row['score']:.2f}")
    else:
        print("No trending stocks found")

if __name__ == "__main__":
    main()
