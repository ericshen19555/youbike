"""Tests for src/notifiers/ — BaseNotifier and TelegramNotifier."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.notifiers.base import BaseNotifier
from src.notifiers.telegram import TelegramNotifier


class TestBaseNotifier:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            BaseNotifier()


class TestTelegramNotifier:
    def test_init(self):
        tn = TelegramNotifier("token123", "chat1")
        assert tn.token == "token123"
        assert tn.default_chat_id == "chat1"
        assert "token123" in tn.api_url

    @pytest.mark.asyncio
    async def test_send_with_chat_id(self):
        tn = TelegramNotifier("tok", "default_chat")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.notifiers.telegram.httpx.AsyncClient", return_value=mock_client):
            result = await tn.send_notification("hello", chat_id="override")
        assert result is True
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        assert call_kwargs[1]["json"]["chat_id"] == "override"

    @pytest.mark.asyncio
    async def test_send_with_default_chat_id(self):
        tn = TelegramNotifier("tok", "default_chat")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.notifiers.telegram.httpx.AsyncClient", return_value=mock_client):
            result = await tn.send_notification("hello")
        assert result is True
        call_kwargs = mock_client.post.call_args
        assert call_kwargs[1]["json"]["chat_id"] == "default_chat"

    @pytest.mark.asyncio
    async def test_send_no_chat_id_returns_false(self):
        tn = TelegramNotifier("tok", None)
        result = await tn.send_notification("hello")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_exception_returns_false(self):
        tn = TelegramNotifier("tok", "chat")

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("fail"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.notifiers.telegram.httpx.AsyncClient", return_value=mock_client):
            result = await tn.send_notification("hello")
        assert result is False
