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
        This is often faster and cleaner than the main IEX portal for real-time dashboards.
        """
        try:
            logger.info(f"Fetching provisional DAM data from {self.provisional_url}")
            response = requests.get(self.provisional_url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for the table in the content
            table = soup.find('table')
            if not table:
                logger.warning("No table found on the provisional data page.")
                return None
            
            # Parse table rows
            rows = []
            for tr in table.find_all('tr'):
                cells = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
                if cells:
                    rows.append(cells)
            
            if not rows:
                return None
                
            # Convert to DataFrame
            df = pd.DataFrame(rows[1:], columns=rows[0])
            
            # Robust Column Cleaning
            def clean_header(h):
                h = h.upper()
                if 'MCP' in h: return 'MCP'
                if 'MCV' in h: return 'MCV'
                if 'BLOCK' in h or 'TIME' in h or 'INTERVAL' in h: return 'BLOCK'
                return h
            
            df.columns = [clean_header(c) for c in df.columns]
            
            # Drop rows where MCP or MCV are non-numeric (like summary rows)
            if 'MCP' in df.columns:
                df['MCP'] = pd.to_numeric(df['MCP'], errors='coerce')
            if 'MCV' in df.columns:
                df['MCV'] = pd.to_numeric(df['MCV'], errors='coerce')
                
            df = df.dropna(subset=['MCP', 'MCV'] if 'MCP' in df.columns and 'MCV' in df.columns else [])
                
            return df

        except Exception as e:
            logger.error(f"Error fetching provisional DAM data: {e}")
            return None

    def get_latest_mcp(self):
        """
        High-level method to get the latest available MCP.
        """
        df = self.fetch_provisional_dam()
        if df is not None and not df.empty:
            # Assuming the last row is the most recent or the average
            # Typically, we want the average or the last block
            mcp_col = [c for c in df.columns if 'MCP' in c.upper()][0]
            latest_val = df[mcp_col].iloc[-1]
            return latest_val
        return None

if __name__ == "__main__":
    scraper = IEXScraper()
    data = scraper.fetch_provisional_dam()
    if data is not None:
        print("Latest IEX Provisional Data Scan:")
        print(data.head())
        print(f"\nLatest MCP: {scraper.get_latest_mcp()}")
    else:
        print("Failed to fetch data.")
