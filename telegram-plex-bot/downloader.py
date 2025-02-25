import requests
import qbittorrentapi
from config import QBITTORRENT_HOST, QBITTORRENT_USERNAME, QBITTORRENT_PASSWORD
import json
import asyncio
import time
import logging
from functools import wraps
from typing import Dict, List, Optional, Any, Union

# Set up logging for this module
logger = logging.getLogger(__name__)

# --- Synchronous Error Handler Decorator ---
def error_handler(func):
    """
    Decorator to handle exceptions in synchronous functions.
    Logs the exception and returns None on failure.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.exception(f"Error in {func.__name__}: {e}")
            return None
    return wrapper

# Initialize qBittorrent client
try:
    qb = qbittorrentapi.Client(
        host=QBITTORRENT_HOST, 
        username=QBITTORRENT_USERNAME, 
        password=QBITTORRENT_PASSWORD
    )
    qb.auth_log_in()
    logger.info(f"Successfully connected to qBittorrent {qb.app.version}")
except Exception as e:
    logger.error(f"qBittorrent login failed: {e}")
    qb = None

@error_handler
def search_tpb(query: str) -> Optional[List[Dict[str, Any]]]:
    """
    Search for torrents using The Pirate Bay API.
    Only returns movie torrents, filtering out TV series.
    
    Args:
        query: The search query string
        
    Returns:
        List of movie torrent dictionaries or None if search failed
    """
    if not query:
        logger.error("Empty search query provided")
        return None
        
    # URL encode the query
    encoded_query = requests.utils.quote(query)
    # Use category 201 (Movies) instead of 200 (Video) to filter out TV series
    url = f"https://apibay.org/q.php?q={encoded_query}&cat=201"
    
    try:
        logger.info(f"Searching for: {query}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        # Parse JSON response
        try:
            torrents = response.json()
            
            # Validate response format
            if not isinstance(torrents, list):
                logger.error(f"API response is not a list: {torrents}")
                return None
                
            logger.info(f"Found {len(torrents)} torrents for query: {query}")
            
            # Filter out invalid torrents, TV series, and add magnet links
            valid_torrents = []
            for torrent in torrents:
                if not isinstance(torrent, dict) or "info_hash" not in torrent:
                    logger.warning(f"Invalid torrent data: {torrent}")
                    continue
                
                # Skip torrents that look like TV series
                name = torrent.get("name", "").lower()
                if any(tv_pattern in name for tv_pattern in ["s01", "s02", "s03", "season", "episode", "e01", "e02", "complete series"]):
                    logger.debug(f"Skipping TV series: {name}")
                    continue
                
                # Add the search query to the torrent data for history tracking
                torrent["search_query"] = query
                
                # Generate magnet link
                info_hash = torrent["info_hash"]
                torrent["magnet"] = (
                    f"magnet:?xt=urn:btih:{info_hash}"
                    f"&dn={requests.utils.quote(torrent.get('name', ''))}"
                    "&tr=udp://tracker.openbittorrent.com:80/announce"
                    "&tr=udp://tracker.opentrackr.org:1337/announce"
                )
                
                valid_torrents.append(torrent)
                logger.debug(f"Found valid torrent: {torrent.get('name')} | Seeds: {torrent.get('seeders')} | Size: {int(torrent.get('size', 0)) / (1024**3):.2f} GB")
            
            logger.info(f"Found {len(valid_torrents)} movie torrents after filtering")    
            # Rank torrents by quality score before returning
            ranked_torrents = rank_torrents(valid_torrents)
            logger.info(f"Torrents ranked by quality score")
            
            # Log top 3 torrents
            for i, torrent in enumerate(ranked_torrents[:3], 1):
                logger.info(f"Top {i}: {torrent.get('name')} | Score: {torrent.get('quality_score', 0):.1f} | Seeds: {torrent.get('seeders')}")
                
            return ranked_torrents

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response: {e}")
            logger.debug(f"Response text: {response.text[:500]}")
            return None

    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP Error: {e}")
        return None

@error_handler
def add_torrent(torrent: Dict[str, Any]) -> Optional[str]:
    """
    Adds a torrent to qBittorrent using the magnet link.
    
    Args:
        torrent: Dictionary containing torrent information
        
    Returns:
        Info hash for monitoring or None on failure
    """
    if not qb:
        logger.error("qBittorrent client not initialized")
        return None
        
    magnet_link = torrent.get("magnet")
    if not magnet_link:
        logger.error("No magnet link available in torrent data")
        return None

    try:
        logger.info(f"Adding torrent: {torrent.get('name', 'Unknown')}")
        logger.info(f"   Seeds: {torrent.get('seeders', 'N/A')} | Size: {int(torrent.get('size', 0)) / (1024**3):.2f} GB | Score: {torrent.get('quality_score', 0):.1f}")
        qb.torrents_add(urls=magnet_link)
        info_hash = torrent.get("info_hash")
        logger.info(f"Torrent added successfully with hash: {info_hash}")
        return info_hash
    except qbittorrentapi.APIError as e:
        logger.error(f"qBittorrent API Error: {e}")
        return None

async def monitor_download(
    info_hash: str, 
    timeout: int = 1800, 
    poll_interval: int = 10
) -> bool:
    """
    Monitors the download progress of a torrent.
    
    Args:
        info_hash: The info hash of the torrent to monitor
        timeout: Maximum time to wait for download (seconds)
        poll_interval: How often to check progress (seconds)
        
    Returns:
        True if download completed successfully, False otherwise
    """
    if not qb:
        logger.error("qBittorrent client not initialized")
        return False
        
    if not info_hash:
        logger.error("No info hash provided for monitoring")
        return False
        
    start_time = time.time()
    logger.info(f"Starting download monitoring for torrent: {info_hash}")
    
    try:
        last_logged_progress = -1
        last_logged_state = None
        
        while time.time() - start_time < timeout:
            torrents_list = qb.torrents_info(torrent_hashes=info_hash)
            
            if not torrents_list:
                logger.warning(f"Torrent {info_hash} not found in qBittorrent")
                await asyncio.sleep(poll_interval)
                continue
                
            torrent = torrents_list[0]
            progress = torrent.progress * 100
            
            # Log progress every 10% or when state changes
            current_progress_tens = int(progress / 10)
            if current_progress_tens > last_logged_progress or torrent.state != last_logged_state:
                download_speed = torrent.dlspeed / (1024**2)  # Convert to MB/s
                eta_seconds = torrent.eta
                eta_str = f"{eta_seconds // 3600}h {(eta_seconds % 3600) // 60}m {eta_seconds % 60}s" if eta_seconds < 8640000 else "Unknown"
                
                logger.info(f"Download progress: {progress:.1f}% | Speed: {download_speed:.2f} MB/s | ETA: {eta_str} | State: {torrent.state}")
                last_logged_progress = current_progress_tens
                last_logged_state = torrent.state
            
            # Check if download is complete
            if progress >= 99.0:
                try:
                    # Remove torrent but keep files
                    qb.torrents_delete(torrent_hashes=info_hash, deleteFiles=False)
                    logger.info(f"Download complete! Torrent {info_hash} removed from qBittorrent.")
                    return True
                except Exception as e:
                    logger.error(f"Error removing torrent: {e}")
                    # Still return True as download completed
                    return True
                    
            await asyncio.sleep(poll_interval)
            
        # Timeout reached
        logger.warning(f"Download monitoring timed out after {timeout} seconds")
        return False
        
    except Exception as e:
        logger.error(f"Error monitoring download: {e}")
        return False

async def retry_download(info_hash, max_attempts=3, retry_delay=30):
    """Retry failed downloads with exponential backoff"""
    for attempt in range(max_attempts):
        logger.info(f"Download attempt {attempt+1}/{max_attempts} for {info_hash}")
        if await monitor_download(info_hash):
            logger.info(f"Download successful on attempt {attempt+1}")
            return True
        
        if attempt < max_attempts - 1:  # Don't sleep after the last attempt
            sleep_time = retry_delay * (2 ** attempt)
            logger.info(f"Download attempt {attempt+1}/{max_attempts} failed, retrying in {sleep_time} seconds")
            await asyncio.sleep(sleep_time)
    
    logger.warning(f"All {max_attempts} download attempts failed for {info_hash}")
    return False

def rank_torrents(torrents):
    """Rank torrents by a quality score (seeds, size, trusted status)"""
    for torrent in torrents:
        # Calculate quality score based on multiple factors
        seeders = int(torrent.get('seeders', 0))
        leechers = int(torrent.get('leechers', 0))
        size_gb = int(torrent.get('size', 0)) / (1024**3)
        
        # Favor torrents with good seed/leech ratio and reasonable size
        # Cap seed score at 10 to prevent exceeding the max total score
        seed_ratio = seeders / max(leechers, 1)
        seed_score = min(seed_ratio, 2) * 5  # Max 10 points (was previously uncapped)
        
        # Size score - max 10 points
        size_score = 10 if 1 < size_gb < 15 else max(0, 10 - abs(size_gb - 8))
        
        # Trusted uploader bonus - 5 points
        trusted_score = 5 if torrent.get('status') == 'trusted' else 0
        
        # Combine scores - max 25 points total
        raw_score = seed_score + size_score + trusted_score
        torrent['quality_score'] = min(raw_score, 25)  # Ensure score never exceeds 25
        
        # Log detailed scoring for debugging
        logger.debug(f"Scoring: {torrent.get('name', 'Unknown')}")
        logger.debug(f"  Seeds: {seeders}, Leechers: {leechers}, Ratio: {seed_ratio:.2f}, Seed Score: {seed_score:.1f}")
        logger.debug(f"  Size: {size_gb:.2f} GB, Size Score: {size_score:.1f}")
        logger.debug(f"  Trusted: {torrent.get('status') == 'trusted'}, Trusted Score: {trusted_score}")
        logger.debug(f"  Total Score: {torrent['quality_score']:.1f}/25")
    
    # Return sorted torrents
    return sorted(torrents, key=lambda t: t.get('quality_score', 0), reverse=True)

