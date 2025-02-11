import requests
import qbittorrentapi
from config import QBITTORRENT_HOST, QBITTORRENT_USERNAME, QBITTORRENT_PASSWORD
import json
import asyncio
import time
import logging
from functools import wraps

# Set up logging for this module
logger = logging.getLogger(__name__)

# --- Synchronous Error Handler Decorator ---
def error_handler(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.exception(f"Error in {func.__name__}: {e}")
            return None
    return wrapper

# Initialize qBittorrent client
qb = qbittorrentapi.Client(
    host=QBITTORRENT_HOST, username=QBITTORRENT_USERNAME, password=QBITTORRENT_PASSWORD
)
try:
    qb.auth_log_in()
except Exception as e:
    print("qBittorrent login failed:", e)  # Keep this print statement as per your instruction

@error_handler
def search_tpb(query: str):
    url = f"https://apibay.org/q.php?q={query}&cat=200"  # Or your mirror
    try:
        response = requests.get(url)
        response.raise_for_status()

        logger.info("Raw API Response: %s", response.text)  # Log raw API response
        try:
            torrents = response.json()
            logger.info("Parsed JSON: %s", json.dumps(torrents, indent=4))

            if isinstance(torrents, list):  # Ensure response is a list
                logger.info("Number of torrents found: %d", len(torrents))
                # Use a copy of the list when removing items
                for torrent in torrents.copy():
                    if isinstance(torrent, dict) and "info_hash" in torrent:
                        info_hash = torrent["info_hash"]
                        torrent["magnet"] = (
                            f"magnet:?xt=urn:btih:{info_hash}"
                            f"&dn={torrent.get('name', '')}"
                            "&tr=udp://tracker.openbittorrent.com:80/announce"
                        )
                        logger.info("Generated Magnet Link: %s", torrent["magnet"])
                    else:
                        logger.warning("Torrent data is not in the expected format: %s", torrent)
                        torrents.remove(torrent)
            else:
                logger.error("API response is not a list. Check the API or mirror. Response: %s", torrents)
                return None

            return torrents

        except json.JSONDecodeError as e:
            logger.error("Invalid JSON: %s. Response text: %s", e, response.text)
            return None

    except requests.exceptions.RequestException as e:
        logger.error("HTTP Error: %s", e)
        return None
    except Exception as e:
        logger.exception("An unexpected error occurred in search_tpb: %s", e)
        return None

@error_handler
def add_torrent(torrent: dict) -> str:
    """
    Adds a torrent to qBittorrent using the magnet link stored in the torrent dict.
    Returns the info_hash for monitoring, or None on failure.
    """
    magnet_link = torrent.get("magnet")
    if not magnet_link:
        logger.error("No magnet link available. This should not happen now.")
        return None

    try:
        qb.torrents_add(urls=magnet_link)
        info_hash = torrent.get("info_hash")
        return info_hash

    except qbittorrentapi.APIError as e:
        logger.error("qBittorrent API Error: %s", e)
        return None
    except Exception as e:
        logger.exception("Error adding torrent: %s", e)
        return None

async def monitor_download(info_hash: str, timeout: int = 1800, poll_interval: int = 10) -> bool:
    """
    Monitors the download of a torrent by its info_hash.
    Polls every `poll_interval` seconds until the torrent's progress is at least 99%
    or until the timeout is reached.
    Deletes the torrent from qBittorrent (without deleting the downloaded file).
    Returns True if the download completes, or False if it times out.
    """
    start_time = time.time()
    iteration = 0
    while time.time() - start_time < timeout:
        iteration += 1
        torrents_list = qb.torrents_info(torrent_hashes=info_hash)
        if torrents_list:
            torrent = torrents_list[0]
            logger.debug("[DEBUG] Iteration %d: Torrent Status: %s", iteration, torrent.state)
            logger.debug("[DEBUG] Iteration %d: Download progress: %.1f%%", iteration, torrent.progress * 100)
            if torrent.progress >= 0.99:
                try:
                    qb.torrents_delete(torrent_hashes=info_hash, deleteFiles=False)
                    logger.debug("[DEBUG] Torrent %s removed from qBittorrent (files preserved).", info_hash)
                    return True
                except Exception as e:
                    logger.exception("[DEBUG] Error removing torrent: %s", e)
                    return False
        else:
            logger.debug("[DEBUG] Torrent with info_hash %s not found. Retrying...", info_hash)
        await asyncio.sleep(poll_interval)
    logger.debug("[DEBUG] Download monitoring timed out.")
    return False
