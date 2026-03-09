"""Tests for src/api/client.py — YouBikeClient with mocked httpx."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.api.client import YouBikeClient


@pytest.fixture
def client():
    return YouBikeClient(timeout=5)


class TestFetchStationList:
    @pytest.mark.asyncio
    async def test_success(self, client):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "station_no": "500101001",
                "name_tw": "科技大樓",
                "parking_spaces": 30,
                "lat": 25.0,
                "lng": 121.5,
                "address_tw": "addr",
                "district_tw": "大安",
                "district_en": "Daan",
                "updated_at": "2026-01-01",
                "act": "1",
            }
        ]
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.api.client.httpx.AsyncClient", return_value=mock_client):
            stations = await client.fetch_station_list()
        assert len(stations) == 1
        assert stations[0].sno == "500101001"

    @pytest.mark.asyncio
    async def test_skips_items_without_station_no(self, client):
        mock_response = MagicMock()
        mock_response.json.return_value = [{"name_tw": "no-id"}]
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.api.client.httpx.AsyncClient", return_value=mock_client):
            stations = await client.fetch_station_list()
        assert len(stations) == 0

    @pytest.mark.asyncio
    async def test_exception_returns_empty(self, client):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Network error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.api.client.httpx.AsyncClient", return_value=mock_client):
            stations = await client.fetch_station_list()
        assert stations == []

    @pytest.mark.asyncio
    async def test_fallback_total_spaces(self, client):
        mock_response = MagicMock()
        mock_response.json.return_value = [{
            "station_no": "001",
            "name_tw": "X",
            "total_spaces": 50,
        }]
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.api.client.httpx.AsyncClient", return_value=mock_client):
            stations = await client.fetch_station_list()
        assert stations[0].tot == 50


class TestFetchParkingInfo:
    @pytest.mark.asyncio
    async def test_empty_ids_returns_empty(self, client):
        result = await client.fetch_parking_info([])
        assert result == {}

    @pytest.mark.asyncio
    async def test_success_with_data_key(self, client):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "retCode": 1,
            "retVal": {
                "data": [{
                    "station_no": "001",
                    "parking_spaces": 30,
                    "empty_spaces": 20,
                    "available_spaces_detail": {"yb2": 6, "eyb": 4},
                    "updated_at": "2026-01-01",
                }]
            }
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.api.client.httpx.AsyncClient", return_value=mock_client):
            result = await client.fetch_parking_info(["001"])
        assert "001" in result
        assert result["001"]["sbi"] == 10  # 6+4

    @pytest.mark.asyncio
    async def test_retval_as_list_directly(self, client):
        """When retVal is already a list (not wrapped in {data: ...})."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "retCode": 1,
            "retVal": [{
                "station_no": "002",
                "parking_spaces": 20,
                "empty_spaces": 10,
                "available_spaces_detail": {"yb2": 3, "eyb": 2},
                "updated_at": "2026-01-01",
            }]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.api.client.httpx.AsyncClient", return_value=mock_client):
            result = await client.fetch_parking_info(["002"])
        assert "002" in result

    @pytest.mark.asyncio
    async def test_retval_single_object(self, client):
        """When retVal.data is a single object instead of list."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "retCode": 1,
            "retVal": {
                "data": {
                    "station_no": "003",
                    "parking_spaces": 10,
                    "empty_spaces": 5,
                    "available_spaces_detail": {"yb2": 1, "eyb": 0},
                    "updated_at": "2026-01-01",
                }
            }
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.api.client.httpx.AsyncClient", return_value=mock_client):
            result = await client.fetch_parking_info(["003"])
        assert "003" in result

    @pytest.mark.asyncio
    async def test_retcode_not_1_returns_empty(self, client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"retCode": 0, "retVal": None}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.api.client.httpx.AsyncClient", return_value=mock_client):
            result = await client.fetch_parking_info(["001"])
        assert result == {}

    @pytest.mark.asyncio
    async def test_exception_returns_empty(self, client):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("fail"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.api.client.httpx.AsyncClient", return_value=mock_client):
            result = await client.fetch_parking_info(["001"])
        assert result == {}

    @pytest.mark.asyncio
    async def test_missing_station_no_skipped(self, client):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "retCode": 1,
            "retVal": [{"parking_spaces": 10, "empty_spaces": 5}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.api.client.httpx.AsyncClient", return_value=mock_client):
            result = await client.fetch_parking_info(["001"])
        assert result == {}

    @pytest.mark.asyncio
    async def test_missing_detail_defaults_zero(self, client):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "retCode": 1,
            "retVal": [{
                "station_no": "004",
                "parking_spaces": 10,
                "empty_spaces": 5,
            }]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.api.client.httpx.AsyncClient", return_value=mock_client):
            result = await client.fetch_parking_info(["004"])
        assert result["004"]["sbi_20"] == 0
        assert result["004"]["sbi_20e"] == 0
