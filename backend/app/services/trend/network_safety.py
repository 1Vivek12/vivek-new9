"""Network safety and SSRF prevention module for source feed ingestion."""

import ipaddress
import socket
from typing import Optional, Tuple
from urllib.parse import urlparse

# Private / reserved IPv4 networks to block
BLOCKED_IPV4_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),          # Current network
    ipaddress.ip_network("10.0.0.0/8"),          # Private-Use (RFC 1918)
    ipaddress.ip_network("127.0.0.0/8"),         # Loopback
    ipaddress.ip_network("169.254.0.0/16"),      # Link-Local (e.g. AWS 169.254.169.254)
    ipaddress.ip_network("172.16.0.0/12"),       # Private-Use (RFC 1918)
    ipaddress.ip_network("192.0.0.0/24"),        # IETF Protocol Assignments
    ipaddress.ip_network("192.0.2.0/24"),        # TEST-NET-1
    ipaddress.ip_network("192.168.0.0/16"),      # Private-Use (RFC 1918)
    ipaddress.ip_network("198.18.0.0/15"),       # Benchmarking
    ipaddress.ip_network("198.51.100.0/24"),     # TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),      # TEST-NET-3
    ipaddress.ip_network("224.0.0.0/4"),         # Multicast
    ipaddress.ip_network("240.0.0.0/4"),         # Reserved for Future Use
    ipaddress.ip_network("255.255.255.255/32"),  # Broadcast
]

# Private / reserved IPv6 networks to block
BLOCKED_IPV6_NETWORKS = [
    ipaddress.ip_network("::1/128"),             # Loopback
    ipaddress.ip_network("::/128"),              # Unspecified
    ipaddress.ip_network("::ffff:0:0/96"),       # IPv4-mapped IPv6
    ipaddress.ip_network("fe80::/10"),           # Link-Local
    ipaddress.ip_network("fc00::/7"),            # Unique Local Unicast (ULA)
    ipaddress.ip_network("ff00::/8"),            # Multicast
]

# Explicitly blocked hostnames
BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "ip6-localhost",
    "ip6-loopback",
    "metadata.google.internal",
    "metadata.internal",
    "169.254.169.254",
    "instance-data",
}

# Ingestion safety limits
MAX_FEED_PAYLOAD_BYTES = 2 * 1024 * 1024  # 2MB maximum payload to prevent DoS
CONNECT_TIMEOUT_SECONDS = 5.0
READ_TIMEOUT_SECONDS = 10.0


class SSRFValidationError(ValueError):
    """Raised when a URL violates SSRF or network safety policies."""
    pass


def is_ip_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check whether an IP address belongs to any blocked/private/loopback ranges."""
    if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_multicast or ip.is_reserved:
        return True

    if isinstance(ip, ipaddress.IPv4Address):
        for net in BLOCKED_IPV4_NETWORKS:
            if ip in net:
                return True
    elif isinstance(ip, ipaddress.IPv6Address):
        for net in BLOCKED_IPV6_NETWORKS:
            if ip in net:
                return True
    return False


def validate_source_url(url: str, check_dns: bool = True) -> Tuple[bool, Optional[str]]:
    """
    Validate a feed or source URL against SSRF and network security constraints.
    Returns (True, None) if safe, or (False, error_reason) if unsafe.
    """
    if not url or not isinstance(url, str):
        return False, "URL cannot be empty."

    url = url.strip()

    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, f"Malformed URL: {e}"

    # 1. Scheme check: only http and https allowed
    if parsed.scheme.lower() not in ("http", "https"):
        return False, f"Forbidden URL scheme '{parsed.scheme}'. Only http and https are permitted."

    # 2. Host check
    hostname = parsed.hostname
    if not hostname:
        return False, "URL must contain a valid hostname."

    hostname_lower = hostname.lower().strip()

    if hostname_lower in BLOCKED_HOSTNAMES:
        return False, f"Access to hostname '{hostname}' is blocked."

    if hostname_lower.endswith(".local") or hostname_lower.endswith(".internal"):
        return False, f"Internal domains ({hostname}) are blocked."

    # 3. Direct IP address check
    try:
        ip_obj = ipaddress.ip_address(hostname_lower)
        if is_ip_blocked(ip_obj):
            return False, f"Direct connection to private/reserved IP {hostname} is blocked."
    except ValueError:
        # Not a raw IP literal; proceed to DNS resolution check if requested
        pass

    # 4. Port check: allow standard HTTP(S) and customary web ports, block internal ports
    if parsed.port is not None:
        if parsed.port in (22, 25, 3306, 5432, 6379, 8080, 9200, 27017, 11211, 2375):
            return False, f"Connection to port {parsed.port} is blocked."

    # 5. DNS Resolution check (prevent DNS rebinding / hostnames resolving to private IPs)
    if check_dns:
        try:
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            addr_info = socket.getaddrinfo(hostname, port)
            for _family, _, _, _, sockaddr in addr_info:
                ip_str = sockaddr[0]
                ip_obj = ipaddress.ip_address(ip_str)
                if is_ip_blocked(ip_obj):
                    return False, f"Hostname '{hostname}' resolves to blocked IP '{ip_str}'."
        except socket.gaierror as e:
            return False, f"DNS resolution failed for '{hostname}': {e}"
        except Exception as e:
            return False, f"Error validating hostname '{hostname}': {e}"

    return True, None


def sanitize_canonical_url(url: str) -> str:
    """Normalize and sanitize a canonical story/article URL, removing tracking parameters."""
    if not url:
        return ""
    try:
        parsed = urlparse(url.strip())
        # Clean query parameters commonly used for tracking
        if parsed.query:
            query_pairs = parsed.query.split("&")
            cleaned_pairs = [
                p for p in query_pairs
                if not any(p.lower().startswith(prefix) for prefix in (
                    "utm_", "fbclid=", "gclid=", "msclkid=", "ref=", "source="
                ))
            ]
            new_query = "&".join(cleaned_pairs)
        else:
            new_query = ""

        clean_path = parsed.path.rstrip("/")
        if not clean_path:
            clean_path = "/"

        reconstructed = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{clean_path}"
        if new_query:
            reconstructed += f"?{new_query}"
        return reconstructed
    except Exception:
        return url.strip()
