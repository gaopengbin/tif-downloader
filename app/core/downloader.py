"""Async tile downloader with concurrency control."""

import asyncio
import random
from io import BytesIO
from typing import Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass, field

import aiohttp
from PIL import Image

from ..config import TILE_SOURCES, DOWNLOAD_SETTINGS, USER_AGENTS, TILE_SIZE, HTTP_PROXY
from .tile import TileCoord


@dataclass
class DownloadResult:
    """Result of a tile download."""
    tile: TileCoord
    success: bool
    image: Optional[Image.Image] = None
    error: Optional[str] = None


@dataclass
class DownloadProgress:
    """Download progress tracker."""
    total: int = 0
    completed: int = 0
    failed: int = 0
    status: str = "pending"
    
    def to_dict(self) -> Dict:
        return {
            "total": self.total,
            "completed": self.completed,
            "failed": self.failed,
            "status": self.status,
            "percent": round(self.completed / self.total * 100, 1) if self.total > 0 else 0
        }


class TileDownloader:
    """Async tile downloader with rate limiting and retry logic."""
    
    def __init__(
        self,
        source: str = "google_satellite",
        max_concurrent: int = None,
        retry_times: int = None,
        timeout: int = None,
        delay: float = None,
        proxy: str = None
    ):
        """
        Initialize the downloader.
        
        Args:
            source: Tile source key from TILE_SOURCES
            max_concurrent: Maximum concurrent downloads
            retry_times: Number of retries on failure
            timeout: Request timeout in seconds
            delay: Delay between requests in seconds
            proxy: HTTP proxy URL (optional, uses config default if not provided)
        """
        if source not in TILE_SOURCES:
            raise ValueError(f"Unknown tile source: {source}. Available: {list(TILE_SOURCES.keys())}")
        
        self.source = source
        self.source_config = TILE_SOURCES[source]
        self.max_concurrent = max_concurrent or DOWNLOAD_SETTINGS["max_concurrent"]
        self.retry_times = retry_times or DOWNLOAD_SETTINGS["retry_times"]
        self.timeout = timeout or DOWNLOAD_SETTINGS["timeout"]
        self.delay = delay or DOWNLOAD_SETTINGS["delay"]
        self.proxy = proxy  # Use provided proxy or None
        
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._session: Optional[aiohttp.ClientSession] = None
    
    def _get_tile_url(self, tile: TileCoord) -> str:
        """Generate tile URL with subdomain rotation."""
        url_template = self.source_config["url"]
        subdomains = self.source_config.get("subdomains", [])
        
        # Choose random subdomain if available
        if subdomains:
            subdomain = random.choice(subdomains)
            url = url_template.replace("{s}", subdomain)
        else:
            url = url_template
        
        # Replace coordinate placeholders
        url = url.replace("{x}", str(tile.x))
        url = url.replace("{y}", str(tile.y))
        url = url.replace("{z}", str(tile.z))
        
        return url
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with random User-Agent."""
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
        }
        
        # Set specific Referer for Tianditu
        if "tianditu" in self.source:
            headers["Referer"] = "https://map.tianditu.gov.cn/"
        else:
            headers["Referer"] = "https://www.google.com/maps"
            
        return headers
    
    async def _download_tile(self, tile: TileCoord) -> DownloadResult:
        """Download a single tile with retry logic."""
        url = self._get_tile_url(tile)
        last_error = None
        
        # Bypass proxy for domestic sites (Tianditu)
        proxy = self.proxy
        if "tianditu.gov.cn" in url:
            proxy = None
        
        for attempt in range(self.retry_times + 1):
            try:
                async with self._semaphore:
                    # Add delay between requests
                    if self.delay > 0:
                        await asyncio.sleep(self.delay * random.uniform(0.5, 1.5))
                    
                    async with self._session.get(
                        url,
                        headers=self._get_headers(),
                        timeout=aiohttp.ClientTimeout(total=self.timeout),
                        proxy=proxy
                    ) as response:
                        if response.status == 200:
                            data = await response.read()
                            image = Image.open(BytesIO(data))
                            # Convert to RGB if necessary
                            if image.mode != "RGB":
                                image = image.convert("RGB")
                            return DownloadResult(tile=tile, success=True, image=image)
                        else:
                            last_error = f"HTTP {response.status}"
            
            except asyncio.TimeoutError:
                last_error = "Timeout"
            except aiohttp.ClientError as e:
                last_error = str(e)
            except Exception as e:
                last_error = str(e)
            
            # Wait before retry
            if attempt < self.retry_times:
                await asyncio.sleep(1 * (attempt + 1))
        
        return DownloadResult(tile=tile, success=False, error=last_error)
    
    async def download_tiles(
        self,
        tiles: List[TileCoord],
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None
    ) -> Tuple[Dict[Tuple[int, int], Image.Image], DownloadProgress]:
        """
        Download multiple tiles concurrently.
        
        Args:
            tiles: List of tile coordinates to download
            progress_callback: Optional callback for progress updates
        
        Returns:
            Tuple of (tile_images dict, final progress)
        """
        progress = DownloadProgress(total=len(tiles), status="downloading")
        tile_images: Dict[Tuple[int, int], Image.Image] = {}
        
        self._semaphore = asyncio.Semaphore(self.max_concurrent)
        
        connector = aiohttp.TCPConnector(limit=self.max_concurrent, ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            self._session = session
            
            # Create tasks for all tiles
            tasks = [self._download_tile(tile) for tile in tiles]
            
            # Process results as they complete
            for coro in asyncio.as_completed(tasks):
                result = await coro
                
                if result.success and result.image:
                    tile_images[(result.tile.x, result.tile.y)] = result.image
                    progress.completed += 1
                else:
                    progress.failed += 1
                    print(f"Failed to download tile {result.tile}: {result.error}")
                
                if progress_callback:
                    progress_callback(progress)
        
        progress.status = "completed" if progress.failed == 0 else "completed_with_errors"
        return tile_images, progress
    
    def download_tiles_sync(
        self,
        tiles: List[TileCoord],
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None
    ) -> Tuple[Dict[Tuple[int, int], Image.Image], DownloadProgress]:
        """
        Synchronous wrapper for download_tiles.
        """
        return asyncio.run(self.download_tiles(tiles, progress_callback))


def create_blank_tile() -> Image.Image:
    """Create a blank (white) tile for missing tiles."""
    return Image.new("RGB", (TILE_SIZE, TILE_SIZE), (255, 255, 255))
