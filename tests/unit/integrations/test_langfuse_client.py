"""
Unit tests for LangfuseClient with defensive programming.
"""

import sys
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch

# Add project root to path
_project_root = Path(__file__).parent.parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


class TestLangfuseClient:
    """Test LangfuseClient defensive behavior."""

    def test_client_disabled_when_langfuse_not_enabled(self):
        """Test that client is None when Langfuse is disabled."""
        with patch("integrations.langfuse.client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(langfuse_enabled=False)

            # Import fresh to trigger __init__
            from integrations.langfuse.client import LangfuseClient

            # Reset singleton for test
            LangfuseClient._instance = None
            client = LangfuseClient()

            assert client.client is None
            assert client.is_enabled() is False

    def test_client_validates_required_methods_on_init(self):
        """Test that client validates methods on initialization."""
        with patch("integrations.langfuse.client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                langfuse_enabled=True,
                langfuse_public_key="test_key",
                langfuse_secret_key="test_secret",
                langfuse_host="http://localhost:3000",
            )

            # Mock Langfuse class with missing methods
            mock_langfuse_class = MagicMock()
            mock_langfuse_instance = MagicMock()
            # Remove 'trace' method to simulate API mismatch
            delattr(mock_langfuse_instance, "trace")
            mock_langfuse_class.return_value = mock_langfuse_instance

            with patch("integrations.langfuse.client.Langfuse", mock_langfuse_class):
                from integrations.langfuse.client import LangfuseClient

                # Reset singleton
                LangfuseClient._instance = None
                client = LangfuseClient()

                # Should detect missing method and disable client
                assert client.client is None

    def test_create_trace_handles_missing_method_gracefully(self):
        """Test that create_trace handles missing trace method gracefully."""
        with patch("integrations.langfuse.client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                langfuse_enabled=True,
                langfuse_public_key="test_key",
                langfuse_secret_key="test_secret",
                langfuse_host="http://localhost:3000",
            )

            # Create client with mock that lacks trace method
            from integrations.langfuse.client import LangfuseClient

            LangfuseClient._instance = None
            client = LangfuseClient()

            # Manually set client to mock without trace method
            mock_client = MagicMock()
            delattr(mock_client, "trace")
            client.client = mock_client

            # Should return None without raising
            result = client.create_trace("test", user_id="123")
            assert result is None

    def test_create_trace_returns_none_when_disabled(self):
        """Test that create_trace returns None when client is disabled."""
        with patch("integrations.langfuse.client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(langfuse_enabled=False)

            from integrations.langfuse.client import LangfuseClient

            LangfuseClient._instance = None
            client = LangfuseClient()

            result = client.create_trace("test", user_id="123")
            assert result is None

    def test_flush_handles_missing_method_gracefully(self):
        """Test that flush handles missing flush method gracefully."""
        with patch("integrations.langfuse.client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                langfuse_enabled=True,
                langfuse_public_key="test_key",
                langfuse_secret_key="test_secret",
                langfuse_host="http://localhost:3000",
            )

            from integrations.langfuse.client import LangfuseClient

            LangfuseClient._instance = None
            client = LangfuseClient()

            # Manually set client to mock without flush method
            mock_client = MagicMock()
            delattr(mock_client, "flush")
            client.client = mock_client

            # Should not raise
            client.flush()

    def test_flush_does_nothing_when_disabled(self):
        """Test that flush does nothing when client is disabled."""
        with patch("integrations.langfuse.client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(langfuse_enabled=False)

            from integrations.langfuse.client import LangfuseClient

            LangfuseClient._instance = None
            client = LangfuseClient()

            # Should not raise
            client.flush()

    @pytest.mark.asyncio
    async def test_trace_scope_yields_none_when_disabled(self):
        """Test that trace_scope yields None when Langfuse is disabled."""
        with patch("integrations.langfuse.client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(langfuse_enabled=False)

            from integrations.langfuse.client import trace_scope

            async with trace_scope("test", user_id="123") as trace:
                assert trace is None

    @pytest.mark.asyncio
    async def test_trace_scope_handles_exceptions_gracefully(self):
        """Test that trace_scope handles exceptions gracefully."""
        with patch("integrations.langfuse.client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(langfuse_enabled=False)

            from integrations.langfuse.client import trace_scope

            # Should not raise even if body raises
            with pytest.raises(ValueError, match="test error"):
                async with trace_scope("test", user_id="123") as trace:
                    raise ValueError("test error")


class TestLangfuseClientSingleton:
    """Test LangfuseClient singleton behavior."""

    def test_singleton_pattern(self):
        """Test that LangfuseClient follows singleton pattern."""
        with patch("integrations.langfuse.client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(langfuse_enabled=False)

            from integrations.langfuse.client import LangfuseClient

            # Reset singleton
            LangfuseClient._instance = None

            client1 = LangfuseClient()
            client2 = LangfuseClient()

            assert client1 is client2
