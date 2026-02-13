import requests
import pandas as pd
from datetime import datetime, timedelta
import logging
from bs4 import BeautifulSoup

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class IEXScraper:
    """
    Scraper for IEX (Indian Energy Exchange) Market Data.
    Focuses on Day-Ahead Market (DAM) MCP and MCV.
    """
    
    def __init__(self):
        self.provisional_url = "https://iexrtmprice.com/view-dam-provisional-mcv-and-mcp-data/"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def fetch_provisional_dam(self):
        """
        Fetches provisional DAM data (MCP and MCV) from the iexrtmprice portal.
        Returns a tuple: (DataFrame, MarketDate)
        """
        try:
            logger.info(f"Fetching provisional DAM data from {self.provisional_url}")
            response = requests.get(self.provisional_url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract Market Date from h1 (e.g., "Unconstrained DAM Data for 14-02-2026")
            market_date = "N/A"
            h1 = soup.find('h1')
            if h1:
                h1_text = h1.get_text(strip=True)
                if 'for' in h1_text:
                    market_date = h1_text.split('for')[-1].strip()
            
            # Look for the table in the content
            table = soup.find('table')
            if not table:
                logger.warning("No table found on the provisional data page.")
                return None, market_date
            
            # Parse table rows
            rows = []
            for tr in table.find_all('tr'):
                cells = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
                if cells:
                    rows.append(cells)
            
            if not rows:
                return None, market_date
                
            # Convert to DataFrame
            df = pd.DataFrame(rows[1:], columns=rows[0])
            
            # Robust Column Cleaning
            def clean_header(h):
                h = h.upper()
                if 'MCP' in h: return 'MCP'
                if 'MCV' in h: return 'MCV'
                if any(x in h for x in ['BLOCK', 'TIME', 'INTERVAL', 'PERIOD']): return 'BLOCK'
                return h
            
            df.columns = [clean_header(c) for c in df.columns]
            
            # Ensure BLOCK column exists
            if 'BLOCK' not in df.columns:
                # Fallback: find any col with ' - ' in first few rows
                for col in df.columns:
                    if df[col].astype(str).str.contains(' - ').any():
                        df = df.rename(columns={col: 'BLOCK'})
                        break

            # Drop rows where MCP or MCV are non-numeric
            if 'MCP' in df.columns: df['MCP'] = pd.to_numeric(df['MCP'], errors='coerce')
            if 'MCV' in df.columns: df['MCV'] = pd.to_numeric(df['MCV'], errors='coerce')
            
            # Filter out known statistical rows
            exclude = ['MIN', 'MAX', 'AVERAGE', 'SUM', 'TOTAL', 'UNCONSTRAINED']
            df = df[~df['BLOCK'].astype(str).str.upper().isin(exclude)]
            # Keep only rows that look like time ranges (HH:MM - HH:MM)
            df = df[df['BLOCK'].astype(str).str.contains(r'\d{2}:\d{2}', na=False)]
                
            return df, market_date

        except Exception as e:
            logger.error(f"Error fetching provisional DAM data: {e}")
            return None, "Error"

    def get_latest_market_data(self):
        """
        High-level method to get MCP, MCV and Block timing.
        Returns a tuple: (Price/MCP, Volume/MCV, BlockTime, MarketDate)
        """
        df, market_date = self.fetch_provisional_dam()
        if df is not None and not df.empty:
            # Filter out summary rows (Min, Max, Avg, Sum)
            # Valid blocks have ' - ' and HH:MM pattern
            valid_blocks = df[df['BLOCK'].str.contains(':', na=False)]
            # Also exclude rows that are explicitly statistical
            exclude = ['MIN', 'MAX', 'AVERAGE', 'SUM', 'TOTAL']
            valid_blocks = valid_blocks[~valid_blocks['BLOCK'].str.upper().isin(exclude)]
            
            if not valid_blocks.empty:
                latest = valid_blocks.iloc[-1]
                mcp = latest['MCP']
                mcv = latest['MCV']
                block = latest['BLOCK']
                return mcp, mcv, block, market_date
        
        return None, None, "N/A", market_date

    def get_latest_mcp(self):
        """Legacy alias for backward compatibility."""
        mcp, _, _, date = self.get_latest_market_data()
        return mcp, date

if __name__ == "__main__":
    scraper = IEXScraper()
    df, m_date = scraper.fetch_provisional_dam()
    if df is not None:
        print(f"Latest IEX Provisional Data Scan for {m_date}:")
        print(df.head())
        print(f"\nMarket Summary: {scraper.get_latest_market_data()}")
    else:
        print("Failed to fetch data.")
