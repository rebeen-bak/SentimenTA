import os
import requests
import pandas as pd
from datetime import datetime
import json

class WSBScanner:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def get_swaggy_stocks(self, limit=20):
        """
        Get trending stocks from SwaggyStocks
        Returns DataFrame with columns: ticker, mentions, sentiment, source, timestamp
        """
        try:
            print("Fetching SwaggyStocks data...")
            url = 'https://api.swaggystocks.com/stocks/sentiment'
            response = requests.get(url, headers=self.headers)
            
            if response.status_code != 200:
                print(f"Error: SwaggyStocks API returned status code {response.status_code}")
                return pd.DataFrame()
            
            try:
                data = response.json()
                # Convert to DataFrame
                df = pd.DataFrame(data.get('data', []))
            except json.JSONDecodeError:
                print("Error: Invalid JSON response from SwaggyStocks")
                return pd.DataFrame()
            if df.empty:
                return df
                
            # Rename columns to match our schema
            df = df.rename(columns={
                'ticker': 'ticker',
                'mentions': 'mentions',
                'sentiment': 'sentiment'
            })
            
            # Add source and timestamp
            df['source'] = 'swaggy'
            df['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Sort by mentions and get top N
            df = df.sort_values('mentions', ascending=False).head(limit)
            
            print(f"Found {len(df)} trending stocks from SwaggyStocks")
            return df
            
        except Exception as e:
            print(f"Error fetching SwaggyStocks data: {str(e)}")
            return pd.DataFrame()
    
    def get_ape_wisdom(self, limit=20):
        """
        Get trending stocks from ApeWisdom
        Returns DataFrame with columns: ticker, mentions, sentiment, source, timestamp
        """
        try:
            print("Fetching ApeWisdom data...")
            url = 'https://apewisdom.io/api/v1.0/filter/all-stocks/page/1'
            response = requests.get(url, headers=self.headers)
            
            if response.status_code != 200:
                print(f"Error: ApeWisdom API returned status code {response.status_code}")
                return pd.DataFrame()
            
            data = response.json()
            results = data.get('results', [])
            
            # Convert to DataFrame
            df = pd.DataFrame(results)
            if df.empty:
                return df
                
            # Rename columns to match our schema
            df = df.rename(columns={
                'ticker': 'ticker',
                'mentions': 'mentions'
            })
            
            # Calculate sentiment (rank normalized to -1 to 1 range)
            df['sentiment'] = (df['rank'].max() - df['rank']) / df['rank'].max() * 2 - 1
            
            # Add source and timestamp
            df['source'] = 'apewisdom'
            df['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Sort by mentions and get top N
            df = df.sort_values('mentions', ascending=False).head(limit)
            
            print(f"Found {len(df)} trending stocks from ApeWisdom")
            return df
            
        except Exception as e:
            print(f"Error fetching ApeWisdom data: {str(e)}")
            return pd.DataFrame()
    
    def get_trending_stocks(self, limit=20):
        """
        Get trending stocks from all sources and combine them
        Returns DataFrame with columns: ticker, mentions, sentiment, source, timestamp
        """
        # Get data from both sources
        swaggy_df = self.get_swaggy_stocks(limit)
        ape_df = self.get_ape_wisdom(limit)
        
        # Combine dataframes
        combined_df = pd.concat([swaggy_df, ape_df], ignore_index=True)
        
        if combined_df.empty:
            return combined_df
            
        # Group by ticker and aggregate
        grouped = combined_df.groupby('ticker').agg({
            'mentions': 'sum',
            'sentiment': 'mean',
            'source': lambda x: ','.join(sorted(set(x))),
            'timestamp': 'first'
        }).reset_index()
        
        # Sort by total mentions and get top N
        final_df = grouped.sort_values('mentions', ascending=False).head(limit)
        
        print(f"\nFound {len(final_df)} total trending stocks after combining sources")
        return final_df

def main():
    scanner = WSBScanner()
    df = scanner.get_trending_stocks()
    
    if not df.empty:
        print("\nTop Trending Stocks:")
        for _, row in df.iterrows():
            print(f"\n{row['ticker']}:")
            print(f"Total Mentions: {row['mentions']}")
            print(f"Average Sentiment: {row['sentiment']:.3f}")
            print(f"Sources: {row['source']}")
    else:
        print("No trending stocks found")

if __name__ == "__main__":
    main()
