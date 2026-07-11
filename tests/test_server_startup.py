"""Startup should fail loud when the catalog can't load.

Previously main() swallowed a startup catalog-sync failure and continued to
mcp.run() with an unusable (or unbound) catalog. Now the failure propagates so
the operator sees it and the server does not start in a broken state.
"""

from unittest.mock import patch

import pytest

import poetry_mcp.server as server_module


def test_main_fails_loud_when_catalog_sync_fails():
    with patch.object(
        server_module, "get_catalog", side_effect=RuntimeError("vault unreadable")
    ), patch.object(server_module.mcp, "run") as mock_run:
        with pytest.raises(RuntimeError, match="vault unreadable"):
            server_module.main()

    # The server must not have started.
    mock_run.assert_not_called()
