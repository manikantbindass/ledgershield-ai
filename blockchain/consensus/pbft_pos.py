"""Legacy path for the simulator. Unauthenticated legacy vote counting was removed.

Use Network.verify_certificate for signed prepare/commit certificates.
Validator membership is fixed; stake/trust do not weaken quorum requirements.
"""
from ledgershield.network import Network, NetworkConfig

__all__ = ["Network", "NetworkConfig"]
