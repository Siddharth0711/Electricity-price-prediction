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
        Fetches provisional DAM data (Price and Volume) from the portal.
        """
        try:
            logger.info(f"Fetching provisional DAM data from {self.provisional_url}")
            # Use verify=False for mirror site compatibility (handles legacy SSL certs)
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            response = requests.get(self.provisional_url, headers=self.headers, timeout=12, verify=False)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract Market Date (Default to tomorrow for DAM if missing)
            market_date = (datetime.now() + timedelta(days=1)).strftime("%d-%m-%Y")
            h1 = soup.find('h1')
            if h1:
                h1_text = h1.get_text(strip=True)
                if 'for' in h1_text:
                    market_date = h1_text.split('for')[-1].strip()
            
            table = soup.find('table')
            if not table: return None, market_date
            
            rows = []
            for tr in table.find_all('tr'):
                cells = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
                if cells: rows.append(cells)
            
            if not rows: return None, market_date
            
            df = pd.DataFrame(rows[1:], columns=rows[0])
            
            # Clean Headers
            def clean_h(h):
                h = str(h).upper()
                if 'MCP' in h: return 'MCP'
                if 'MCV' in h: return 'MCV'
                if any(x in h for x in ['BLOCK', 'TIME', 'INTERVAL']): return 'BLOCK'
                return h
            df.columns = [clean_h(c) for c in df.columns]
            
            # Clean Data
            if 'MCP' in df.columns: df['MCP'] = pd.to_numeric(df['MCP'], errors='coerce')
            if 'MCV' in df.columns: df['MCV'] = pd.to_numeric(df['MCV'], errors='coerce')
            
            # Filter rows (exclude summary statistcs and keep only HH:MM patterns)
            exclude = ['MIN', 'MAX', 'AVERAGE', 'SUM', 'TOTAL', 'UNCONSTRAINED', 'CONSTRAINED']
            df = df[~df['BLOCK'].astype(str).str.upper().isin(exclude)]
            df = df[df['BLOCK'].astype(str).str.contains(r'\d{1,2}:\d{2}', na=False)]
                
            return df.dropna(subset=['MCP']), market_date

        except Exception as e:
            logger.error(f"Scraper Error: {e}")
            return None, "Error"

    def get_latest_market_data(self):
        """
        Returns (MCP, MCV, Block, Date) for the block matching CURRENT IST time.
        """
        df, market_date = self.fetch_provisional_dam()
        if df is not None and not df.empty:
            # Match current clock time to the correct 15-min block
            now = datetime.now()
            # If server is in UTC (likely on Cloud), shift to IST
            # Indian Market is active 24/7 in 15-min blocks, but sync is usually in IST
            # Detect if 'now' is likely UTC (approx 5.5 hours behind IST)
            # A simpler way is to just assume most cloud hosts are UTC
            if -1 <= (datetime.utcnow().hour - now.hour) <= 1: 
                now = now + timedelta(hours=5, minutes=30)
            
            target_start = f"{now.hour:02d}:{(now.minute // 15) * 15:02d}"
            
            match = df[df['BLOCK'].astype(str).str.startswith(target_start)]
            row = match.iloc[0] if not match.empty else df.iloc[-1]
            
            try:
                mcp = float(row['MCP'])
                mcv = float(row['MCV'])
                return mcp, mcv, str(row['BLOCK']), market_date
            except Exception: pass
            
        return None, None, "Syncing...", market_date

    def get_latest_mcp(self):
        res = self.get_latest_market_data()
        return res[0], res[3]

if __name__ == "__main__":
    s = IEXScraper()
    print(f"Sync Test: {s.get_latest_market_data()}")
