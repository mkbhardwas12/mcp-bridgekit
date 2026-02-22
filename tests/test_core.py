import pytest
from mcp_bridgekit.core import BridgeKit

def test_bridgekit_init():
    bridge = BridgeKit()
    assert bridge.redis is not None
