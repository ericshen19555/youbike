import asyncio
import sys
import os

# Ensure the root directory is in the python path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.api.client import YouBikeClient

async def test_api_v3():
    client = YouBikeClient()
    
    print("Step 1: Fetching Station List (GET)...")
    try:
        stations = await client.fetch_station_list()
        print(f"Total stations found: {len(stations)}")
        if stations:
            print(f"First station: {stations[0].sna} ({stations[0].sno}) at {stations[0].sarea}")
    except Exception as e:
        print(f"Error fetching station list: {e}")
        return

    # Let's pick a known station or just the first few
    target_ids = [s.sno for s in stations[:3]]
    # Add a known Taipei station if possible (e.g., 500101001 - MRT Technology Bldg)
    if "500101001" not in target_ids:
        target_ids.append("500101001")

    print(f"\nStep 2: Fetching Real-time Info (POST) for: {target_ids}...")
    try:
        realtime = await client.fetch_parking_info(target_ids)
        print(f"Real-time records received: {len(realtime)}")
        for sno, data in realtime.items():
            print(f"--- Station: {sno} ---")
            print(f"  Available Bikes: {data['sbi']} (2.0: {data['sbi_20']}, E-Bike: {data['sbi_20e']})")
            print(f"  Empty Spaces: {data['bemp']}")
            print(f"  Total Spaces: {data['tot']}")
            print(f"  Last Update: {data['updatetime']}")
    except Exception as e:
        print(f"Error fetching real-time info: {e}")

if __name__ == "__main__":
    asyncio.run(test_api_v3())
