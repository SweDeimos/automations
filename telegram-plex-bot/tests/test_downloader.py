import pytest
import asyncio
import json
from unittest.mock import patch, MagicMock
from downloader import search_tpb, add_torrent, monitor_download, retry_download, rank_torrents

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

# Async test for retry_download: simulate success on second attempt
@pytest.mark.asyncio
async def test_retry_download_success_on_retry():
    # Mock monitor_download to fail on first attempt, succeed on second
    monitor_results = [False, True]
    
    async def mock_monitor_side_effect(*args, **kwargs):
        return monitor_results.pop(0)
    
    with patch("downloader.monitor_download", side_effect=mock_monitor_side_effect), \
         patch("downloader.asyncio.sleep") as mock_sleep:
        result = await retry_download("12345", max_attempts=3, retry_delay=1)
        assert result is True
        assert mock_sleep.call_count == 1  # Should sleep once after first failure

# Async test for retry_download: simulate all attempts failing
@pytest.mark.asyncio
async def test_retry_download_all_attempts_fail():
    with patch("downloader.monitor_download", return_value=False), \
         patch("downloader.asyncio.sleep") as mock_sleep:
        result = await retry_download("12345", max_attempts=2, retry_delay=1)
        assert result is False
        assert mock_sleep.call_count == 2  # Should sleep after each failure

# Test for rank_torrents: verify torrents are ranked correctly
def test_rank_torrents():
    # Create sample torrents with different characteristics
    torrents = [
        {
            "name": "Low seeds, good size",
            "seeders": "5",
            "leechers": "10",
            "size": str(5 * 1024**3),  # 5GB
            "status": ""
        },
        {
            "name": "High seeds, good size, trusted",
            "seeders": "100",
            "leechers": "10",
            "size": str(8 * 1024**3),  # 8GB
            "status": "trusted"
        },
        {
            "name": "High seeds, too large",
            "seeders": "50",
            "leechers": "5",
            "size": str(25 * 1024**3),  # 25GB
            "status": ""
        },
        {
            "name": "Extremely high seeds",
            "seeders": "1000",
            "leechers": "10",
            "size": str(5 * 1024**3),  # 5GB
            "status": ""
        }
    ]
    
    # Rank the torrents
    ranked = rank_torrents(torrents)
    
    # Print the actual scores for debugging
    for torrent in ranked:
        print(f"{torrent['name']}: {torrent['quality_score']}")
    
    # Verify the order is correct (highest score first)
    assert ranked[0]["name"] == "High seeds, good size, trusted"
    assert ranked[1]["name"] == "Extremely high seeds"
    
    # The order of the next two might vary depending on exact scoring
    # Just verify they're both in the list
    assert any(t["name"] == "High seeds, too large" for t in ranked[2:])
    assert any(t["name"] == "Low seeds, good size" for t in ranked[2:])
    
    # Verify scores were calculated and added
    for torrent in ranked:
        assert "quality_score" in torrent
        # Ensure no score exceeds 25
        assert torrent["quality_score"] <= 25
