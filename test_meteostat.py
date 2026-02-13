from meteostat import hourly, Station
from datetime import datetime

start = datetime(2024, 1, 1)
end = datetime(2024, 1, 5)
s = Station('42182')

try:
    print("Calling hourly(s, start, end)...")
    data = hourly(s, start, end)
    print("Result of hourly():", data)
    
    df = data.fetch()
    if df is not None and not df.empty:
        print("Success! Data shape:", df.shape)
        print(df.head())
    else:
        print("Still no data. fetch() returned:", df)
except Exception as e:
    print(f"Error occurred: {e}")
