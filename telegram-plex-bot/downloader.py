import requests
import qbittorrentapi
from config import QBITTORRENT_HOST, QBITTORRENT_USERNAME, QBITTORRENT_PASSWORD
import json
import asyncio
import time

qb = qbittorrentapi.Client(host=QBITTORRENT_HOST, username=QBITTORRENT_USERNAME, password=QBITTORRENT_PASSWORD)
try:
    qb.auth_log_in()
except Exception as e:
    print("qBittorrent login failed:", e)  # Keep this print statement

def search_tpb(query: str):
    url = f"https://apibay.org/q.php?q={query}&cat=200"  # Or your mirror
    try:
        response = requests.get(url)
        response.raise_for_status()

        print("Raw API Response:", response.text)  # VERY IMPORTANT: Print raw text
        try:
            torrents = response.json()
            print("Parsed JSON:", json.dumps(torrents, indent=4))  # Print parsed JSON

            if isinstance(torrents, list):  # Check if it's a list
                print(f"Number of torrents found: {len(torrents)}")
                for torrent in torrents:
                    if isinstance(torrent, dict) and "info_hash" in torrent:
                        info_hash = torrent["info_hash"]
                        torrent["magnet"] = f"magnet:?xt=urn:btih:{info_hash}&dn={torrent.get('name', '')}&tr=udp://tracker.openbittorrent.com:80/announce" #Example trackers
                        print("Generated Magnet Link:", torrent["magnet"]) #Print magnet link
                    else:
                        print(f"Torrent data is not in the expected format: {torrent}")
                        torrents.remove(torrent)
            else:
                print("API response is not a list. Check the API or mirror.")
                print(f"Response: {torrents}")
                return None

            return torrents

        except json.JSONDecodeError as e:
            print(f"Invalid JSON: {e}. Response text: {response.text}")  # Print response text
            return None

    except requests.exceptions.RequestException as e:
        print(f"HTTP Error: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None


def add_torrent(torrent: dict) -> str: #Changed return to string to give back info_hash
    magnet_link = torrent.get("magnet")
    if not magnet_link:
        print("No magnet link available. This should not happen now.")
        return None

    try:
        qb.torrents_add(urls=magnet_link)
        info_hash = torrent.get("info_hash")
        return info_hash # Return the info_hash for monitoring

    except qbittorrentapi.APIError as e:
        print(f"qBittorrent API Error: {e}")
        return None
    except Exception as e:
        print(f"Error adding torrent: {e}")
        return None

async def monitor_download(info_hash: str, timeout: int = 1800, poll_interval: int = 10) -> bool:
    """
    Monitors the download of a torrent by its info_hash.
    Polls every `poll_interval` seconds until the torrent's progress is at least 99%
    or until the timeout (in seconds) is reached.
    Deletes the torrent from qBittorrent (without deleting the downloaded file).
    Returns True if the download completes, or False if it times out.
    """
    import time
    start_time = time.time()
    iteration = 0
    while time.time() - start_time < timeout:
        iteration += 1
        # Use torrents_info instead of torrents
        torrents_list = qb.torrents_info(torrent_hashes=info_hash)
        if torrents_list:
            torrent = torrents_list[0]
            print(f"[DEBUG] Iteration {iteration}: Torrent Status: {torrent.state}")
            print(f"[DEBUG] Iteration {iteration}: Download progress: {torrent.progress * 100:.1f}%")
            if torrent.progress >= 0.99:
                try:
                    qb.torrents_delete(torrent_hashes=info_hash, deleteFiles=False)
                    print(f"[DEBUG] Torrent {info_hash} removed from qBittorrent (files preserved).")
                    return True
                except Exception as e:
                    print(f"[DEBUG] Error removing torrent: {e}")
                    return False
        else:
            print(f"[DEBUG] Torrent with info_hash {info_hash} not found. Retrying...")
        await asyncio.sleep(poll_interval)
    print("[DEBUG] Download monitoring timed out.")
    return False

