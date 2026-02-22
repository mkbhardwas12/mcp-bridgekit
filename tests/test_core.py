import pytest
from mcp_bridgekit.core import BridgeKit

def test_init():
    bridge = BridgeKit()
    assert bridge is not None
