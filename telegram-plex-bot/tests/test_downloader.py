import pytest
import asyncio
import json
from unittest.mock import patch, MagicMock
from downloader import search_tpb, add_torrent, monitor_download

# Test for search_tpb: simulate a HTTP error.
def test_search_tpb_http_error(caplog):
    with patch("downloader.requests.get") as mock_get:
        # Simulate a request exception
        mock_get.side_effect = Exception("HTTP Error")
        result = search_tpb("Inception")
        assert result is None
        assert "An unexpected error occurred" in caplog.text

# Test for add_torrent: simulate an API error from qb.torrents_add.
def test_add_torrent_api_error(caplog):
    fake_torrent = {"name": "Test Movie", "magnet": "magnet:example", "info_hash": "12345"}
    with patch("downloader.qb.torrents_add") as mock_add:
        mock_add.side_effect = Exception("API Error")
        result = add_torrent(fake_torrent)
        assert result is None
        assert "Error adding torrent" in caplog.text

# Async test for monitor_download: simulate a successful download.
@pytest.mark.asyncio
async def test_monitor_download_success():
    fake_torrent = MagicMock()
    fake_torrent.progress = 1.0
    fake_torrent.state = "uploading"

    with patch("downloader.qb.torrents_info", return_value=[fake_torrent]), \
         patch("downloader.qb.torrents_delete") as mock_delete:
        result = await monitor_download("12345", timeout=5, poll_interval=1)
        assert result is True
        mock_delete.assert_called_once()

# Async test for monitor_download: simulate a timeout.
@pytest.mark.asyncio
async def test_monitor_download_timeout():
    fake_torrent = MagicMock()
    fake_torrent.progress = 0.5  # Never reaches 0.99
    fake_torrent.state = "downloading"
    
    with patch("downloader.qb.torrents_info", return_value=[fake_torrent]):
        result = await monitor_download("12345", timeout=3, poll_interval=1)
        assert result is False
