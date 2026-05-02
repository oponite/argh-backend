
import asyncio
import httpx
import time
from app.core.deps.http_client import get_http_client
from app.services.basketball.integrations.nba_stats import fetch_rows

async def validate():
    print("--- NBA API Validation Script ---")
    client = get_http_client()
    
    # We'll try to fetch team stats which was failing before
    print("Attempting to fetch league team stats (Advanced)...")
    start_time = time.time()
    try:
        # fetch_rows uses the configured client and includes retries/timeouts
        rows = await fetch_rows(client, measure_type="Advanced", last_n_games=5)
        duration = time.time() - start_time
        print(f"✅ Success! Retrieved {len(rows)} teams in {duration:.2f} seconds.")
        if rows:
            print(f"Sample data (First Team): {rows[0].get('TEAM_NAME')}")
    except Exception as e:
        duration = time.time() - start_time
        print(f"❌ Failed after {duration:.2f} seconds.")
        print(f"Error: {e}")

    print("\nAttempting to fetch scoring data...")
    start_time = time.time()
    try:
        rows = await fetch_rows(client, measure_type="Scoring", last_n_games=0)
        duration = time.time() - start_time
        print(f"✅ Success! Retrieved {len(rows)} teams in {duration:.2f} seconds.")
    except Exception as e:
        duration = time.time() - start_time
        print(f"❌ Failed after {duration:.2f} seconds.")
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(validate())
