import httpx
import json

async def check_api():
    url = "https://apis.youbike.com.tw/json/station-min-yb2.json"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        data = response.json()
        if data and len(data) > 0:
            print(f"Number of stations: {len(data)}")
            print(f"Keys in first item: {list(data[0].keys())}")
            print(f"Sample data: {data[0]}")
        else:
            print("No data found")

if __name__ == "__main__":
    import asyncio
    asyncio.run(check_api())
