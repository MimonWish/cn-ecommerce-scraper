#!/usr/bin/env python3
"""
1688工厂页面爬虫（浏览器版本）
使用Playwright处理JavaScript动态加载的页面
"""
import sys
import csv
import time
import argparse
from pathlib import Path
from typing import List, Optional

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("请先安装: pip install playwright && playwright install chromium")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent))
from utils import (
    Product, clean_text, extract_number, generate_product_id,
    get_timestamp, format_price, format_sales,
    write_csv, sanitize_filename
)


class Alibaba1688BrowserCrawler:
    """1688工厂页面爬虫（浏览器版）"""

    def __init__(self):
        self.products: List[Product] = []

    def extract_shop_id_from_url(self, url: str) -> Optional[str]:
        """从URL提取店铺ID"""
        import re
        member_match = re.search(r'memberId=b2b-(\w+)', url)
        if member_match:
            return member_match.group(1)
        return None

    def crawl(self, shop_url: str, max_pages: int = 50, output_file: str = None) -> List[Product]:
        """
        使用浏览器爬取店铺商品

        Args:
            shop_url: 店铺URL
            max_pages: 最大爬取页数
            output_file: 输出文件路径

        Returns:
            商品列表
        """
        print(f"开始爬取1688工厂页面: {shop_url}")

        shop_id = self.extract_shop_id_from_url(shop_url)
        print(f"店铺ID: {shop_id}")

        all_products = []
        shop_name = "未知店铺"

        with sync_playwright() as p:
            # 启动浏览器
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
            )
            page = context.new_page()

            # 启用请求拦截
            offers_data = []
            page.on("response", lambda response: self._handle_response(response, offers_data))

            print("正在加载页面...")
            try:
                page.goto(shop_url, wait_until="networkidle", timeout=60000)
            except Exception as e:
                print(f"页面加载超时: {e}")
                page.wait_for_timeout(5000)

            # 等待商品加载
            print("等待商品数据加载...")
            page.wait_for_timeout(3000)

            # 获取店铺名称
            try:
                title_elem = page.query_selector('.company-name, .shop-name, .factory-name, [class*="name"]')
                if title_elem:
                    shop_name = clean_text(title_elem.inner_text())
            except:
                pass

            print(f"店铺名称: {shop_name}")

            # 解析已拦截的数据
            for offer in offers_data:
                product = Product(
                    shop_name=shop_name,
                    shop_url=shop_url,
                    platform='1688',
                    product_id=offer.get('id', ''),
                    product_name=offer.get('title', '') or offer.get('name', ''),
                    product_url=f"https://detail.1688.com/offer/{offer.get('id', '')}.html",
                    price=format_price(str(offer.get('price', '0'))),
                    sales=format_sales(str(offer.get('saleCount', offer.get('sales', '0')))),
                    images=offer.get('imageUrl', '') or offer.get('img', ''),
                    shop_id=shop_id or '',
                    crawl_time=get_timestamp()
                )
                all_products.append(product)

            # 如果没有拦截到数据，尝试从页面DOM提取
            if not all_products:
                print("从页面DOM提取商品...")
                all_products = self._extract_from_dom(page, shop_name, shop_url, shop_id)

            # 翻页处理
            page_num = 1
            while page_num < max_pages:
                try:
                    # 查找下一页按钮
                    next_btn = page.query_selector('.page-next, .next-page, [class*="next"], [class*="pagination"] button:last-child')
                    if next_btn and not next_btn.is_disabled():
                        next_btn.click()
                        page.wait_for_timeout(2000)
                        page_num += 1
                        print(f"正在处理第 {page_num} 页...")
                    else:
                        break
                except Exception as e:
                    print(f"翻页失败: {e}")
                    break

            browser.close()

        print(f"\n爬取完成! 共获取 {len(all_products)} 个商品")

        if output_file and all_products:
            write_csv(all_products, output_file)
            print(f"已保存到: {output_file}")

        self.products = all_products
        return all_products

    def _handle_response(self, response, offers_data: list):
        """处理响应，拦截商品数据"""
        try:
            url = response.url
            if 'offer' in url.lower() or 'getOfferList' in url or 'factoryOffer' in url:
                if response.status == 200:
                    try:
                        data = response.json()
                        if 'offers' in data:
                            offers_data.extend(data['offers'])
                        elif 'data' in data and isinstance(data['data'], list):
                            offers_data.extend(data['data'])
                        elif isinstance(data, list):
                            offers_data.extend(data)
                    except:
                        pass
        except:
            pass

    def _extract_from_dom(self, page, shop_name: str, shop_url: str, shop_id: str) -> List[Product]:
        """从页面DOM提取商品"""
        products = []

        # 尝试多种选择器
        selectors = [
            '.offer-item',
            '.product-item',
            '.goods-item',
            '[class*="offer"]',
            '[class*="product"]',
            '[class*="goods"]',
            '.list-item',
        ]

        items = []
        for selector in selectors:
            try:
                items = page.query_selector_all(selector)
                if items:
                    print(f"使用选择器 {selector} 找到 {len(items)} 个商品")
                    break
            except:
                pass

        for item in items:
            try:
                # 提取商品ID
                product_id = ''
                link = item.query_selector('a[href*="offer"]')
                if link:
                    href = link.get_attribute('href')
                    import re
                    match = re.search(r'/offer/(\d+)', href or '')
                    if match:
                        product_id = match.group(1)

                # 提取商品名称
                title = ''
                title_elem = item.query_selector('[class*="title"], [class*="name"], [class*="subject"]')
                if title_elem:
                    title = clean_text(title_elem.inner_text())

                # 提取价格
                price = ''
                price_elem = item.query_selector('[class*="price"], .price')
                if price_elem:
                    price = format_price(extract_number(price_elem.inner_text()))

                # 提取销量
                sales = '0'
                sales_elem = item.query_selector('[class*="sale"], [class*="sold"], [class*="num"]')
                if sales_elem:
                    sales = format_sales(sales_elem.inner_text())

                # 提取图片
                img = ''
                img_elem = item.query_selector('img')
                if img_elem:
                    img = img_elem.get_attribute('src') or ''

                if product_id or title:
                    product = Product(
                        shop_name=shop_name,
                        shop_url=shop_url,
                        platform='1688',
                        product_id=product_id,
                        product_name=title,
                        product_url=f"https://detail.1688.com/offer/{product_id}.html" if product_id else '',
                        price=price,
                        sales=sales,
                        images=img,
                        shop_id=shop_id or '',
                        crawl_time=get_timestamp()
                    )
                    products.append(product)
            except Exception as e:
                continue

        return products


def main():
    parser = argparse.ArgumentParser(description='1688工厂页面爬虫（浏览器版）')
    parser.add_argument('url', help='店铺URL')
    parser.add_argument('--output', '-o', default='products.csv', help='输出CSV文件路径')
    parser.add_argument('--max-pages', '-m', type=int, default=50, help='最大爬取页数')

    args = parser.parse_args()

    output_file = args.output
    if not output_file.endswith('.csv'):
        output_file += '.csv'

    crawler = Alibaba1688BrowserCrawler()
    products = crawler.crawl(args.url, max_pages=args.max_pages, output_file=output_file)

    if not products:
        print("\n警告: 未能获取任何商品")
        sys.exit(1)


if __name__ == "__main__":
    main()
