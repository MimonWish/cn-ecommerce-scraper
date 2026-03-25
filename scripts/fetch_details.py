#!/usr/bin/env python3
"""
商品详情爬虫
根据商品ID或URL批量获取商品详情
支持抓取商品属性、包装信息、详情图片
每个商品保存到独立文件夹
"""
import sys
import json
import re
import csv
import time
import argparse
from pathlib import Path
from typing import List, Dict, Optional, Any
from urllib.parse import urlparse
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
    get_timestamp, format_price, format_sales, format_stock,
    write_csv, read_csv, RateLimiter, sanitize_filename,
    download_images_to_folder, save_product_folder
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
            'attrs': {},
            'packaging': '',
            'detail_images': '',
            'detail_html': '',
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

        html_content = response.text
        soup = BeautifulSoup(html_content, 'html.parser')
        detail['detail_html'] = html_content

        # 1. 提取商品属性
        detail['attrs'] = self._extract_pinduoduo_attrs(soup)

        # 2. 提取包装信息
        detail['packaging'] = self._extract_pinduoduo_packaging(soup)

        # 3. 提取商品描述
        desc_elem = soup.find('div', class_=re.compile(r'desc|description|detail'))
        if desc_elem:
            detail['description'] = clean_text(desc_elem.get_text())[:5000]

        # 4. 提取主图
        images = []
        for img in soup.find_all('img', src=True):
            src = img.get('src', '')
            if src and ('goods' in src or 'product' in src or 'item' in src):
                if not src.startswith('http'):
                    src = 'https:' + src if src.startswith('//') else 'https://' + src
                images.append(src)
        detail['images'] = ','.join(images[:10])

        # 5. 提取详情页图片
        detail_images = []
        for img in soup.find_all('img', {'data-src': True}):
            src = img.get('data-src', '')
            if src and not src.startswith('data:'):
                if not src.startswith('http'):
                    src = 'https:' + src if src.startswith('//') else 'https://' + src
                detail_images.append(src)
        detail['detail_images'] = ','.join(detail_images[:30])

        # 6. 提取分类
        cat_bread = soup.find(['div', 'ul'], class_=re.compile(r'breadcrumb|crumb|category'))
        if cat_bread:
            cats = cat_bread.find_all(['a', 'span'])
            detail['category'] = ' > '.join([clean_text(c.get_text()) for c in cats])

        # 7. 提取库存
        stock_elem = soup.find(['span', 'div'], class_=re.compile(r'stock|inventory|stockNum'))
        if stock_elem:
            detail['stock'] = extract_number(stock_elem.get_text())

        return detail

    def _extract_pinduoduo_attrs(self, soup: BeautifulSoup) -> Dict:
        """提取拼多多商品属性"""
        attrs = {}

        # 尝试从页面脚本中提取属性数据
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                # 查找window.__INIT_PROPS__或其他初始化数据
                if 'goodsDetail' in script.string or 'goods_info' in script.string:
                    try:
                        # 尝试提取JSON数据
                        match = re.search(r'\{[^{}]*"attrs"[^{}]*\}', script.string)
                        if match:
                            json_str = match.group()
                            data = json.loads(json_str)
                            if 'attrs' in data:
                                attrs = data['attrs']
                    except:
                        pass

        # 尝试从DL/DT/DD列表中提取属性
        attr_tables = soup.find_all('table', class_=re.compile(r'attr|property|spec'))
        for table in attr_tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    key = clean_text(cells[0].get_text())
                    value = clean_text(cells[1].get_text())
                    if key and value:
                        attrs[key] = value

        # 尝试从DL列表中提取
        dl_list = soup.find_all('dl', class_=re.compile(r'attr|property|spec'))
        for dl in dl_list:
            dts = dl.find_all('dt')
            dds = dl.find_all('dd')
            for dt, dd in zip(dts, dds):
                key = clean_text(dt.get_text())
                value = clean_text(dd.get_text())
                if key and value:
                    attrs[key] = value

        return attrs

    def _extract_pinduoduo_packaging(self, soup: BeautifulSoup) -> str:
        """提取拼多多包装信息"""
        packaging_text = ""

        # 查找包装列表
        patterns = [
            re.compile(r'包装[：:]?\s*([^\n<]+)'),
            re.compile(r'包装规格[：:]?\s*([^\n<]+)'),
            re.compile(r'装箱[规格数量][：:]?\s*([^\n<]+)'),
        ]

        for pattern in patterns:
            match = pattern.search(str(soup))
            if match:
                packaging_text = match.group(1).strip()
                break

        # 尝试从特定元素提取
        if not packaging_text:
            pkg_elem = soup.find(['div', 'span'], class_=re.compile(r'packaging|package|包装'))
            if pkg_elem:
                packaging_text = clean_text(pkg_elem.get_text())

        return packaging_text

    def fetch_1688_detail(self, url: str, product_id: str = '') -> Dict:
        """获取1688商品详情"""
        detail = {
            'description': '',
            'category': '',
            'stock': '',
            'images': '',
            'attrs': {},
            'packaging': '',
            'detail_images': '',
            'detail_html': '',
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

        html_content = response.text
        soup = BeautifulSoup(html_content, 'html.parser')
        detail['detail_html'] = html_content

        # 1. 提取商品属性
        detail['attrs'] = self._extract_1688_attrs(soup, html_content)

        # 2. 提取包装信息
        detail['packaging'] = self._extract_1688_packaging(soup, html_content)

        # 3. 提取商品描述
        desc_link = soup.find('a', {'data-inter-link': 'description'})
        if desc_link:
            desc_url = desc_link.get('href', '')
            if desc_url:
                if not desc_url.startswith('http'):
                    desc_url = 'https:' + desc_url if desc_url.startswith('//') else 'https://' + desc_url
                try:
                    desc_response = self.session.get(desc_url, timeout=30)
                    if desc_response.status_code == 200:
                        detail['description'] = clean_text(desc_response.text)[:5000]
                except:
                    pass

        if not detail['description']:
            desc_elem = soup.find('div', class_=re.compile(r'description|detail-desc|mod-detail-description'))
            if desc_elem:
                detail['description'] = clean_text(desc_elem.get_text())[:5000]

        # 4. 提取主图
        images = []
        for img in soup.find_all('img', src=re.compile(r'1688|alibaba|alicdn')):
            src = img.get('src', '')
            if src and 'offer' in src.lower() or 'product' in src.lower():
                if not src.startswith('http'):
                    src = 'https:' + src if src.startswith('//') else 'https://' + src
                images.append(src)
        # 也尝试从脚本中提取图片数据
        if not images:
            for script in soup.find_all('script'):
                if script.string and 'imageList' in script.string:
                    match = re.search(r'imageList\s*[=:]\s*\[([^\]]+)\]', script.string)
                    if match:
                        img_urls = re.findall(r'["\']([^"\']+)["\']', match.group(1))
                        for img_url in img_urls:
                            if img_url.startswith('http'):
                                images.append(img_url)
        detail['images'] = ','.join(images[:10])

        # 5. 提取详情页图片
        detail_images = []
        for img in soup.find_all('img', src=True):
            src = img.get('src', '')
            if src and ('detail' in src or 'desc' in src or 'content' in src):
                if not src.startswith('http'):
                    src = 'https:' + src if src.startswith('//') else 'https://' + src
                if not src.startswith('data:'):
                    detail_images.append(src)
        detail['detail_images'] = ','.join(detail_images[:50])

        # 6. 提取分类
        cat_bread = soup.find('div', class_=re.compile(r'bread-crumb|nav-breadcrumb|category'))
        if cat_bread:
            cats = cat_bread.find_all(['a', 'span'])
            detail['category'] = ' > '.join([clean_text(c.get_text()) for c in cats])

        # 7. 提取库存
        mod_quantity = soup.find('div', class_=re.compile(r'mod-quantity|quantity'))
        if mod_quantity:
            stock_elem = mod_quantity.find(['span', 'input'])
            if stock_elem:
                detail['stock'] = stock_elem.get('value', '') or extract_number(stock_elem.get_text())

        return detail

    def _extract_1688_attrs(self, soup: BeautifulSoup, html_content: str) -> Dict:
        """提取1688商品属性"""
        attrs = {}

        # 方法1: 从页面JSON数据中提取
        try:
            # 查找window.__INIT_DATA__或类似数据
            match = re.search(r'window\.__PINPOINT_STORE__\s*=\s*(\{.*?\});', html_content, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
                if 'item' in data and 'attributes' in data['item']:
                    attrs = data['item']['attributes']
        except:
            pass

        # 方法2: 从属性表格中提取
        attr_tables = soup.find_all('table', class_=re.compile(r'attr|property|spec|parameter'))
        for table in attr_tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    key = clean_text(cells[0].get_text())
                    value = clean_text(cells[1].get_text())
                    if key and value:
                        attrs[key] = value

        # 方法3: 从DL列表中提取
        dl_list = soup.find_all('dl', class_=re.compile(r'attr|property|spec|feature'))
        for dl in dl_list:
            dts = dl.find_all('dt')
            dds = dl.find_all('dd')
            for dt, dd in zip(dts, dds):
                key = clean_text(dt.get_text())
                value = clean_text(dd.get_text())
                if key and value:
                    attrs[key] = value

        # 方法4: 从数据模块中提取
        for script in soup.find_all('script'):
            if script.string:
                # 查找var data = {...} 或 similar patterns
                if 'specs' in script.string or 'attributes' in script.string:
                    matches = re.findall(r'["\'](\w+)["\']\s*:\s*["\']([^"\']+)["\']', script.string)
                    for key, value in matches:
                        if len(key) > 1 and len(value) > 0:
                            attrs[key] = value

        return attrs

    def _extract_1688_packaging(self, soup: BeautifulSoup, html_content: str) -> str:
        """提取1688包装信息"""
        packaging_text = ""

        # 1688通常有包装信息在属性里
        patterns = [
            re.compile(r'包装[规格方式][：:]?\s*([^<\n]+)'),
            re.compile(r'装箱[规格数量][：:]?\s*([^<\n]+)'),
            re.compile(r'包装清单[：:]?\s*([^<\n]+)'),
            re.compile(r'包装说明[：:]?\s*([^<\n]+)'),
        ]

        for pattern in patterns:
            match = pattern.search(html_content)
            if match:
                packaging_text = match.group(1).strip()
                break

        # 尝试从特定元素提取
        if not packaging_text:
            # 查找包装相关的模块
            pkg_module = soup.find(['div', 'table'], class_=re.compile(r'packaging|package|包装|装箱'))
            if pkg_module:
                packaging_text = clean_text(pkg_module.get_text())

        # 也尝试从dl/dt/dd结构中提取
        if not packaging_text:
            for dl in soup.find_all('dl'):
                dt_text = clean_text(dl.find('dt').get_text() if dl.find('dt') else '')
                if '包装' in dt_text:
                    dd_text = clean_text(dl.find('dd').get_text() if dl.find('dd') else '')
                    if dd_text:
                        packaging_text = dd_text
                        break

        return packaging_text

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
                'attrs': {},
                'packaging': '',
                'detail_images': '',
                'detail_html': '',
            }

        # 更新商品属性
        product.description = detail.get('description', '')
        product.category = detail.get('category', '')
        product.stock = detail.get('stock', '')
        product.attrs = json.dumps(detail.get('attrs', {}), ensure_ascii=False)
        product.packaging = detail.get('packaging', '')
        product.detail_images = detail.get('detail_images', '')
        product.detail_html = detail.get('detail_html', '')
        if detail.get('images'):
            product.images = detail.get('images')

        return product

    def fetch_batch(self, input_csv: str, output_csv: str = None, platform: str = None,
                    save_folders: bool = False, folders_base_dir: str = None) -> List[Product]:
        """
        批量获取商品详情

        Args:
            input_csv: 包含商品ID/URL的CSV文件
            output_csv: 输出CSV文件路径
            platform: 平台类型（pinduoduo/1688）
            save_folders: 是否为每个商品创建独立文件夹
            folders_base_dir: 商品文件夹保存的基础目录

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

            # 如果启用文件夹保存，每个商品处理完后立即保存
            if save_folders and folders_base_dir:
                folder_path = save_product_folder(product, folders_base_dir, self.session)
                print(f"  商品详情已保存到: {folder_path}")

        if output_csv:
            write_csv(products, output_csv)
            print(f"\nCSV已保存到: {output_csv}")

        return products


def main():
    parser = argparse.ArgumentParser(description='商品详情爬虫 - 支持属性、包装信息和文件夹保存')
    parser.add_argument('input_csv', help='输入CSV文件（包含product_id或product_url）')
    parser.add_argument('--output', '-o', default=None, help='输出CSV文件路径')
    parser.add_argument('--platform', '-p', default=None, choices=['pinduoduo', '1688', 'taobao', 'jd'], help='平台类型')
    parser.add_argument('--delay', '-d', type=float, default=1.0, help='请求间隔(秒)')
    parser.add_argument('--cookies', '-c', default=None, help='1688登录Cookie（可选）')
    parser.add_argument('--folders', '-f', action='store_true', help='为每个商品创建独立文件夹')
    parser.add_argument('--base-dir', '-b', default='./product_details', help='商品文件夹保存基础目录')

    args = parser.parse_args()

    output_file = args.output
    if not output_file:
        input_path = Path(args.input_csv)
        output_file = str(input_path.stem) + '_detailed.csv'

    # 创建基础目录
    if args.folders:
        Path(args.base_dir).mkdir(parents=True, exist_ok=True)
        print(f"商品文件夹将保存到: {args.base_dir}")

    crawler = ProductDetailCrawler(
        rate_limiter=RateLimiter(delay=args.delay),
        cookies=args.cookies
    )
    products = crawler.fetch_batch(
        args.input_csv,
        output_file,
        args.platform,
        save_folders=args.folders,
        folders_base_dir=args.base_dir
    )

    print(f"\n完成! 共处理 {len(products)} 个商品")
    if args.folders:
        print(f"商品详情文件夹已保存到: {args.base_dir}")


if __name__ == "__main__":
    main()