"""管理员全局 IP 黑名单：支持单个 IP（IPv4/IPv6）和 CIDR 网段，一行一条，# 开头为注释。"""
import ipaddress
from functools import lru_cache

from src.db import setting

BLACKLIST_SETTING_KEY = "ip_blacklist"


def parse_ip_rules(text):
    """解析规则文本，返回 (networks, normalized_lines, invalid_lines)。"""
    networks, normalized, invalid = [], [], []
    for raw in (text or "").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        try:
            network = ipaddress.ip_network(line, strict=False)
        except ValueError:
            invalid.append(line)
            continue
        networks.append(network)
        normalized.append(str(network) if "/" in line else str(network.network_address))
    return networks, normalized, invalid


@lru_cache(maxsize=8)
def _compiled(text):
    return tuple(parse_ip_rules(text)[0])


def ip_matches(ip, networks):
    try:
        address = ipaddress.ip_address((ip or "").strip())
    except ValueError:
        return False
    return any(address.version == net.version and address in net for net in networks)


def is_ip_blacklisted(ip):
    text = setting(BLACKLIST_SETTING_KEY, "") or ""
    if not text.strip():
        return False
    return ip_matches(ip, _compiled(text))
