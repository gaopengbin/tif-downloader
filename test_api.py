import asyncio
import aiohttp

async def test_datav():
    """Test DataV API access"""
    url = "https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json"
    
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as response:
                print(f"Status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    features = data.get("features", [])
                    print(f"Features count: {len(features)}")
                    if features:
                        print(f"First feature: {features[0].get('properties', {})}")
                else:
                    text = await response.text()
                    print(f"Error response: {text[:200]}")
        except Exception as e:
            print(f"Error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_datav())
