#!/usr/bin/env python3
"""
检测URL所属电商平台
支持：拼多多、1688、淘宝、天猫、京东
"""
import sys
import re
from urllib.parse import urlparse


PLATFORMS = {
    "pinduoduo": ["pinduoduo", "duoduo", "you.kuajingpinduoduo", "mobile.yangkeduo", "pinduoduo.com"],
    "1688": ["1688.com", "alibaba.com", "alibaba1688"],
    "taobao": ["taobao.com"],
    "tmall": ["tmall.com", "tmall.hk"],
    "jd": ["jd.com", "jd.hk"],
}


def detect_platform(url: str) -> str:
    """
    检测URL所属平台

    Args:
        url: 电商平台URL

    Returns:
        平台名称 (pinduoduo/1688/taobao/tmall/jd/unknown)
    """
    if not url:
        return "unknown"

    url_lower = url.lower()

    for platform, keywords in PLATFORMS.items():
        for keyword in keywords:
            if keyword in url_lower:
                return platform

    return "unknown"


def is_valid_shop_url(url: str) -> bool:
    """
    检查是否为有效的店铺URL

    Args:
        url: 待检查的URL

    Returns:
        是否有效
    """
    if not url or len(url) < 10:
        return False

    parsed = urlparse(url)
    if not parsed.netloc:
        return False

    platform = detect_platform(url)
    return platform != "unknown"


def extract_shop_info(url: str) -> dict:
    """
    从URL中提取店铺信息

    Args:
        url: 店铺URL

    Returns:
        包含店铺信息的字典
    """
    parsed = urlparse(url)
    platform = detect_platform(url)

    info = {
        "url": url,
        "platform": platform,
        "domain": parsed.netloc,
        "path": parsed.path,
        "valid": is_valid_shop_url(url)
    }

    if platform == "pinduoduo":
        shop_id_match = re.search(r'shop[Ii]d=(\d+)', url)
        if shop_id_match:
            info["shop_id"] = shop_id_match.group(1)

        shop_id_match = re.search(r'shop_id=(\d+)', url)
        if shop_id_match:
            info["shop_id"] = shop_id_match.group(1)

    elif platform == "1688":
        # sale.1688.com/factory/xxx?memberId=b2b-xxx
        member_match = re.search(r'memberId=b2b-(\w+)', url)
        if member_match:
            info["shop_id"] = member_match.group(1)
        else:
            shop_id_match = re.search(r'(\w+)\.1688\.com', parsed.netloc)
            if shop_id_match:
                info["shop_id"] = shop_id_match.group(1)
            elif 'winport' in parsed.netloc:
                info["shop_id"] = parsed.netloc.split('.')[0]

    return info


def main():
    if len(sys.argv) < 2:
        print("用法: python detect_platform.py <URL>")
        print("\n示例:")
        print("  python detect_platform.py 'https://you.kuajingpinduoduo.com/shop-detail/shopDetail?shopId=123456'")
        print("  python detect_platform.py 'https://xxx.1688.com/page/creditlist.htm'")
        sys.exit(1)

    url = sys.argv[1]

    platform = detect_platform(url)
    info = extract_shop_info(url)

    print(f"URL: {url}")
    print(f"平台: {platform}")
    print(f"域名: {info['domain']}")
    print(f"路径: {info['path']}")
    print(f"有效店铺URL: {info['valid']}")

    if 'shop_id' in info:
        print(f"店铺ID: {info['shop_id']}")


if __name__ == "__main__":
    main()
