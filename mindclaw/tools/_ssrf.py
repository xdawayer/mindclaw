# input: socket, ipaddress, urllib.parse
# output: 导出 is_safe_url
# pos: 共享 SSRF 防护模块，供 web.py 和 api_call.py 使用
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Shared SSRF protection for all HTTP-making tools."""

import ipaddress
import socket
from urllib.parse import urlparse

# CGNAT / shared address space (RFC 6598) — not covered by ipaddress.is_private
_CGNAT_NETWORK = ipaddress.ip_network("100.64.0.0/10")


def is_safe_url(url: str) -> bool:
    """Reject URLs targeting private/loopback/link-local/metadata/CGNAT addresses.

    Note: DNS rebinding can bypass this check if the attacker controls DNS.
    Callers should not follow redirects or should re-validate at each hop.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        for _, _, _, _, sockaddr in socket.getaddrinfo(hostname, None):
            ip = ipaddress.ip_address(sockaddr[0])
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or (ip.version == 4 and ip in _CGNAT_NETWORK)
            ):
                return False
        return True
    except (socket.gaierror, ValueError, OSError):
        return False
