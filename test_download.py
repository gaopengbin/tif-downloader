import asyncio
import aiohttp
from app.core.tile import TileCoord

async def test_single_tile():
    """Test downloading a single Google satellite tile"""
    
    # Test coordinates (Beijing area, zoom 10)
    tile = TileCoord(x=850, y=390, z=10)
    
    # OSM URL
    url = f"https://a.tile.openstreetmap.org/{tile.z}/{tile.x}/{tile.y}.png"
    
    print(f"Testing URL: {url}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        proxy = "http://127.0.0.1:10808"  # V2Ray proxy
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            print(f"Starting download with proxy: {proxy}...")
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10), proxy=proxy) as response:
                print(f"Status: {response.status}")
                print(f"Headers: {dict(response.headers)}")
                
                if response.status == 200:
                    data = await response.read()
                    print(f"Downloaded {len(data)} bytes")
                    
                    # Save to file
                    with open("test_tile.jpg", "wb") as f:
                        f.write(data)
                    print("Saved to test_tile.jpg")
                else:
                    text = await response.text()
                    print(f"Error response: {text[:500]}")
                    
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_single_tile())
