#!/usr/bin/env python3
"""
拼多多店铺商品爬虫
爬取指定店铺的所有商品列表
"""
import sys
import json
import re
import csv
import time
import argparse
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("请先安装依赖: pip install requests beautifulsoup4")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent))
from utils import (
    Product, clean_text, extract_number, generate_product_id,
    extract_shop_id, get_timestamp, format_price, format_sales,
    write_csv, save_progress, load_progress, RateLimiter, sanitize_filename
)


class PinduoduoCrawler:
    """拼多多店铺爬虫"""

    def __init__(self, rate_limiter: Optional[RateLimiter] = None):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })
        self.rate_limiter = rate_limiter or RateLimiter(delay=2.0)
        self.products: List[Product] = []

    def extract_shop_id_from_url(self, url: str) -> Optional[str]:
        """从URL提取店铺ID"""
        shop_id_match = re.search(r'shop[Ii]d=(\d+)', url)
        if shop_id_match:
            return shop_id_match.group(1)

        shop_id_match = re.search(r'shop_id=(\d+)', url)
        if shop_id_match:
            return shop_id_match.group(1)

        return None

    def extract_shop_name(self, soup: BeautifulSoup) -> str:
        """提取店铺名称"""
        name_selectors = [
            '.shop-name', '.shopTitle', '.shop-info-name',
            '[class*="shop-name"]', '[class*="shopTitle"]',
            '.store-name', '.name'
        ]

        for selector in name_selectors:
            elem = soup.select_one(selector)
            if elem:
                return clean_text(elem.get_text())

        title = soup.find('title')
        if title:
            title_text = clean_text(title.get_text())
            match = re.search(r'【(.*?)】', title_text)
            if match:
                return match.group(1)

        return "未知店铺"

    def parse_product_list_page(self, html: str, shop_name: str, shop_url: str) -> List[Dict]:
        """解析商品列表页面"""
        products = []
        soup = BeautifulSoup(html, 'html.parser')

        product_patterns = [
            {'class': 'goods-item', 'tag': 'div'},
            {'class': 'product-item', 'tag': 'div'},
            {'class': 'goods-list-item', 'tag': 'div'},
            {'class': 'search-result-item', 'tag': 'div'},
            {'id': re.compile(r'^goods_?\d+'), 'tag': 'div'},
        ]

        items = []
        for pattern in product_patterns:
            if 'class' in pattern:
                items = soup.find_all(pattern['tag'], class_=pattern['class'])
            elif 'id' in pattern:
                items = soup.find_all(pattern['tag'], id=pattern['id'])
            if items:
                break

        if not items:
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'goodsList' in script.string:
                    try:
                        match = re.search(r'goodsList\s*[=:]\s*(\[.*?\]);', script.string, re.DOTALL)
                        if match:
                            data = json.loads(match.group(1))
                            return data
                    except:
                        pass

        for item in items:
            product = {}

            link_elem = item.find('a', href=True) or item.find('a')
            if link_elem:
                href = link_elem.get('href', '')
                if not href.startswith('http'):
                    href = 'https://you.kuajingpinduoduo.com' + href
                product['url'] = href
                product['id'] = generate_product_id('pinduoduo', href)
            else:
                product['url'] = ''
                product['id'] = ''

            name_elem = item.find(['a', 'span', 'div'], class_=re.compile(r'name|title|goodsName'))
            if name_elem:
                product['name'] = clean_text(name_elem.get_text())
            else:
                img = item.find('img')
                if img:
                    alt = img.get('alt', '')
                    if alt:
                        product['name'] = clean_text(alt)
                    else:
                        product['name'] = '未知商品'
                else:
                    product['name'] = '未知商品'

            price_elem = item.find(['span', 'div'], class_=re.compile(r'price|Price'))
            if price_elem:
                price_text = price_elem.get_text()
                product['price'] = format_price(extract_number(price_text))
            else:
                product['price'] = ''

            sales_elem = item.find(['span', 'div'], class_=re.compile(r'sales|Sales|sold'))
            if sales_elem:
                product['sales'] = format_sales(sales_elem.get_text())
            else:
                product['sales'] = '0'

            img_elem = item.find('img')
            if img_elem:
                src = img_elem.get('src') or img_elem.get('data-src', '')
                if src and not src.startswith('http'):
                    src = 'https:' + src
                product['image'] = src
            else:
                product['image'] = ''

            products.append(product)

        return products

    def crawl(self, shop_url: str, max_pages: int = 50, output_file: str = None) -> List[Product]:
        """
        爬取店铺商品

        Args:
            shop_url: 店铺URL
            max_pages: 最大爬取页数
            output_file: 输出文件路径

        Returns:
            商品列表
        """
        print(f"开始爬取拼多多店铺: {shop_url}")

        shop_id = self.extract_shop_id_from_url(shop_url)
        if not shop_id:
            print("警告: 无法从URL提取店铺ID，尝试从页面获取")

        self.rate_limiter.wait()
        try:
            response = self.session.get(shop_url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"请求失败: {e}")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        shop_name = self.extract_shop_name(soup)

        if not shop_id:
            meta = soup.find('meta', {'name': 'shopId'})
            if meta:
                shop_id = meta.get('content', '')

        print(f"店铺名称: {shop_name}")
        print(f"店铺ID: {shop_id}")

        all_products = []
        page = 1

        api_urls = []
        if shop_id:
            api_urls.append(
                f"https://you.kuajingpinduoduo.com/shop-detail/shopDetail/goodsList?shopId={shop_id}&page=1&pageSize=50"
            )

        crawled_urls = set()

        while page <= max_pages:
            print(f"\n正在爬取第 {page}/{max_pages} 页...")

            products = []
            api_url = None

            if page == 1 and api_urls:
                api_url = api_urls[0]
            elif shop_id:
                api_url = f"https://you.kuajingpinduoduo.com/shop-detail/shopDetail/goodsList?shopId={shop_id}&page={page}&pageSize=50"

            if api_url and api_url not in crawled_urls:
                self.rate_limiter.wait()
                try:
                    headers = {
                        'Referer': shop_url,
                        'X-Requested-With': 'XMLHttpRequest',
                    }
                    api_response = self.session.get(api_url, headers=headers, timeout=30)
                    if api_response.status_code == 200:
                        try:
                            data = api_response.json()
                            if 'goods_list' in data:
                                raw_products = data['goods_list']
                                for p in raw_products:
                                    product = Product(
                                        shop_name=shop_name,
                                        shop_url=shop_url,
                                        platform='pinduoduo',
                                        product_id=str(p.get('goods_id', '')),
                                        product_name=clean_text(p.get('goods_name', '')),
                                        product_url=p.get('goods_url', ''),
                                        price=format_price(str(p.get('price', ''))),
                                        sales=format_sales(str(p.get('sales', '0'))),
                                        images=p.get('image_url', ''),
                                        shop_id=shop_id or '',
                                        crawl_time=get_timestamp()
                                    )
                                    products.append(product)
                            elif 'data' in data:
                                raw_products = data['data']
                                if isinstance(raw_products, list):
                                    for p in raw_products:
                                        product = Product(
                                            shop_name=shop_name,
                                            shop_url=shop_url,
                                            platform='pinduoduo',
                                            product_id=str(p.get('goods_id', p.get('id', ''))),
                                            product_name=clean_text(p.get('goods_name', p.get('name', ''))),
                                            product_url=p.get('goods_url', p.get('url', '')),
                                            price=format_price(str(p.get('price', '0'))),
                                            sales=format_sales(str(p.get('sales', '0'))),
                                            images=p.get('image_url', p.get('img', '')),
                                            shop_id=shop_id or '',
                                            crawl_time=get_timestamp()
                                        )
                                        products.append(product)
                        except json.JSONDecodeError:
                            pass
                        crawled_urls.add(api_url)
                except requests.RequestException as e:
                    print(f"API请求失败: {e}")

            if not products:
                print("尝试从HTML解析商品列表...")
                products_data = self.parse_product_list_page(response.text, shop_name, shop_url)
                for p in products_data:
                    product = Product(
                        shop_name=shop_name,
                        shop_url=shop_url,
                        platform='pinduoduo',
                        product_id=p.get('id', ''),
                        product_name=p.get('name', ''),
                        product_url=p.get('url', ''),
                        price=p.get('price', ''),
                        sales=p.get('sales', '0'),
                        images=p.get('image', ''),
                        shop_id=shop_id or '',
                        crawl_time=get_timestamp()
                    )
                    products.append(product)

            if not products:
                print("未找到更多商品，停止爬取")
                break

            print(f"本页找到 {len(products)} 个商品")
            all_products.extend(products)
            page += 1

        print(f"\n爬取完成! 共获取 {len(all_products)} 个商品")

        if output_file and all_products:
            write_csv(all_products, output_file)
            print(f"已保存到: {output_file}")

        self.products = all_products
        return all_products


def main():
    parser = argparse.ArgumentParser(description='拼多多店铺商品爬虫')
    parser.add_argument('url', help='店铺URL')
    parser.add_argument('--output', '-o', default='products.csv', help='输出CSV文件路径')
    parser.add_argument('--max-pages', '-m', type=int, default=50, help='最大爬取页数')
    parser.add_argument('--delay', '-d', type=float, default=2.0, help='请求间隔(秒)')

    args = parser.parse_args()

    output_file = args.output
    if not output_file.endswith('.csv'):
        output_file += '.csv'

    crawler = PinduoduoCrawler(rate_limiter=RateLimiter(delay=args.delay))
    products = crawler.crawl(args.url, max_pages=args.max_pages, output_file=output_file)

    if not products:
        print("\n警告: 未能获取任何商品")
        print("可能原因:")
        print("  1. 页面需要登录或验证码")
        print("  2. 店铺URL格式不正确")
        print("  3. 页面结构已变更")
        sys.exit(1)


if __name__ == "__main__":
    main()
