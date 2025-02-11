import qbittorrentapi
from config import QBITTORRENT_HOST, QBITTORRENT_USERNAME, QBITTORRENT_PASSWORD

try:
    qb = qbittorrentapi.Client(host=QBITTORRENT_HOST, username=QBITTORRENT_USERNAME, password=QBITTORRENT_PASSWORD)
    qb.auth_log_in()
    print(type(qb.torrents))  # Print the type

    info_hash = "dd168a1f093d17674623907bed846a480f10530f"  # Replace with a real info_hash
    torrents = qb.torrents(torrent_hashes=info_hash)
    print(torrents)  # Print the result

except Exception as e:
    print(f"Error: {e}")