#!/usr/bin/env python3
"""
商品详情爬虫
根据商品ID或URL批量获取商品详情
"""
import sys
import json
import re
import csv
import time
import argparse
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("请先安装依赖: pip install requests beautifulsoup4")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent))
from utils import (
    Product, clean_text, extract_number, generate_product_id,
    get_timestamp, format_price, format_sales, format_stock,
    write_csv, read_csv, RateLimiter
)


class ProductDetailCrawler:
    """商品详情爬虫"""

    def __init__(self, rate_limiter: Optional[RateLimiter] = None, cookies: str = None):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })
        if cookies:
            for cookie in cookies.split(';'):
                if '=' in cookie:
                    name, value = cookie.strip().split('=', 1)
                    self.session.cookies.set(name, value)
        self.rate_limiter = rate_limiter or RateLimiter(delay=1.0)

    def detect_platform(self, url: str) -> str:
        """检测平台"""
        url_lower = url.lower()
        if 'pinduoduo' in url_lower or 'yangkeduo' in url_lower:
            return 'pinduoduo'
        if '1688.com' in url_lower:
            return '1688'
        if 'taobao' in url_lower:
            return 'taobao'
        if 'tmall' in url_lower:
            return 'tmall'
        if 'jd.com' in url_lower:
            return 'jd'
        return 'unknown'

    def fetch_pinduoduo_detail(self, url: str, product_id: str = '') -> Dict:
        """获取拼多多商品详情"""
        detail = {
            'description': '',
            'category': '',
            'stock': '',
            'images': '',
            'attrs': {}
        }

        if not url:
            return detail

        try:
            self.rate_limiter.wait()
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"请求失败: {e}")
            return detail

        soup = BeautifulSoup(response.text, 'html.parser')

        desc_elem = soup.find('div', class_=re.compile(r'desc|description|detail'))
        if desc_elem:
            detail['description'] = clean_text(desc_elem.get_text())[:2000]

        images = []
        for img in soup.find_all('img', src=True):
            src = img.get('src', '')
            if src and ('detail' in src or 'goods' in src or 'product' in src):
                if not src.startswith('http'):
                    src = 'https:' + src if src.startswith('//') else 'https://' + src
                images.append(src)
        detail['images'] = ','.join(images[:10])

        cat_bread = soup.find(['div', 'ul'], class_=re.compile(r'breadcrumb|crumb|category'))
        if cat_bread:
            cats = cat_bread.find_all(['a', 'span'])
            detail['category'] = ' > '.join([clean_text(c.get_text()) for c in cats])

        stock_elem = soup.find(['span', 'div'], class_=re.compile(r'stock|inventory|stockNum'))
        if stock_elem:
            detail['stock'] = extract_number(stock_elem.get_text())

        return detail

    def fetch_1688_detail(self, url: str, product_id: str = '') -> Dict:
        """获取1688商品详情"""
        detail = {
            'description': '',
            'category': '',
            'stock': '',
            'images': '',
            'attrs': {}
        }

        if not url:
            return detail

        try:
            self.rate_limiter.wait()
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"请求失败: {e}")
            return detail

        soup = BeautifulSoup(response.text, 'html.parser')

        desc_link = soup.find('a', {'data-inter-link': 'description'})
        if desc_link:
            desc_url = desc_link.get('href', '')
            if desc_url:
                if not desc_url.startswith('http'):
                    desc_url = 'https:' + desc_url if desc_url.startswith('//') else 'https://' + desc_url
                try:
                    desc_response = self.session.get(desc_url, timeout=30)
                    if desc_response.status_code == 200:
                        detail['description'] = clean_text(desc_response.text)[:2000]
                except:
                    pass

        if not detail['description']:
            desc_elem = soup.find('div', class_=re.compile(r'description|detail-desc|mod-detail-description'))
            if desc_elem:
                detail['description'] = clean_text(desc_elem.get_text())[:2000]

        images = []
        for img in soup.find_all('img', src=re.compile(r'cloudvideo|img\.1688|shopline')):
            src = img.get('src', '')
            if src and not src.startswith('data:'):
                if not src.startswith('http'):
                    src = 'https:' + src if src.startswith('//') else 'https://' + src
                images.append(src)
        detail['images'] = ','.join(images[:10])

        cat_bread = soup.find('div', class_=re.compile(r'bread-crumb|nav-breadcrumb|category'))
        if cat_bread:
            cats = cat_bread.find_all(['a', 'span'])
            detail['category'] = ' > '.join([clean_text(c.get_text()) for c in cats])

        mod_quantity = soup.find('div', class_=re.compile(r'mod-quantity|quantity'))
        if mod_quantity:
            stock_elem = mod_quantity.find(['span', 'input'])
            if stock_elem:
                detail['stock'] = stock_elem.get('value', '') or extract_number(stock_elem.get_text())

        price_elem = soup.find('span', class_=re.compile(r'price|Amount'))
        if price_elem:
            price_text = price_elem.get_text()
            detail['price'] = format_price(extract_number(price_text))

        return detail

    def fetch_detail(self, product: Product) -> Product:
        """获取单个商品详情"""
        platform = product.platform or self.detect_platform(product.product_url)

        if platform == 'pinduoduo':
            detail = self.fetch_pinduoduo_detail(product.product_url, product.product_id)
        elif platform == '1688':
            detail = self.fetch_1688_detail(product.product_url, product.product_id)
        else:
            detail = {
                'description': '',
                'category': '',
                'stock': '',
                'images': product.images or '',
            }

        product.description = detail.get('description', '')
        product.category = detail.get('category', '')
        product.stock = detail.get('stock', '')
        if detail.get('images'):
            product.images = detail.get('images')

        return product

    def fetch_batch(self, input_csv: str, output_csv: str = None, platform: str = None) -> List[Product]:
        """
        批量获取商品详情

        Args:
            input_csv: 包含商品ID/URL的CSV文件
            output_csv: 输出CSV文件路径
            platform: 平台类型（pinduoduo/1688）

        Returns:
            含详情的商品列表
        """
        products_data = read_csv(input_csv)
        print(f"从 {input_csv} 读取了 {len(products_data)} 个商品")

        products = []
        for i, row in enumerate(products_data):
            product = Product(
                shop_name=row.get('shop_name', ''),
                shop_url=row.get('shop_url', ''),
                platform=row.get('platform', platform or ''),
                product_id=row.get('product_id', ''),
                product_name=row.get('product_name', ''),
                product_url=row.get('product_url', ''),
                price=row.get('price', ''),
                sales=row.get('sales', ''),
                stock=row.get('stock', ''),
                images=row.get('images', ''),
                description=row.get('description', ''),
                category=row.get('category', ''),
                shop_id=row.get('shop_id', ''),
                crawl_time=get_timestamp()
            )

            if product.product_url or product.product_id:
                print(f"[{i+1}/{len(products_data)}] 正在获取: {product.product_name or product.product_id}")
                product = self.fetch_detail(product)
            else:
                print(f"[{i+1}/{len(products_data)}] 跳过无效商品")

            products.append(product)

        if output_csv:
            write_csv(products, output_csv)
            print(f"\n已保存到: {output_csv}")

        return products


def main():
    parser = argparse.ArgumentParser(description='商品详情爬虫')
    parser.add_argument('input_csv', help='输入CSV文件（包含product_id或product_url）')
    parser.add_argument('--output', '-o', default=None, help='输出CSV文件路径')
    parser.add_argument('--platform', '-p', default=None, choices=['pinduoduo', '1688', 'taobao', 'jd'], help='平台类型')
    parser.add_argument('--delay', '-d', type=float, default=1.0, help='请求间隔(秒)')
    parser.add_argument('--cookies', '-c', default=None, help='1688登录Cookie（可选）')

    args = parser.parse_args()

    output_file = args.output
    if not output_file:
        input_path = Path(args.input_csv)
        output_file = str(input_path.stem) + '_detailed.csv'

    crawler = ProductDetailCrawler(
        rate_limiter=RateLimiter(delay=args.delay),
        cookies=args.cookies
    )
    products = crawler.fetch_batch(args.input_csv, output_file, args.platform)

    print(f"\n完成! 共处理 {len(products)} 个商品")


if __name__ == "__main__":
    main()
