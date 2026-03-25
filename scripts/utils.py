"""
电商爬虫通用工具模块
"""
import re
import csv
import time
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from urllib.parse import urlparse, parse_qs


@dataclass
class Product:
    """商品数据结构"""
    shop_name: str = ""
    shop_url: str = ""
    platform: str = ""
    product_id: str = ""
    product_name: str = ""
    product_url: str = ""
    price: str = ""
    sales: str = ""
    stock: str = ""
    images: str = ""
    description: str = ""
    category: str = ""
    shop_id: str = ""
    crawl_time: str = ""
    # 新增字段
    attrs: str = ""          # 商品属性 (JSON字符串)
    packaging: str = ""      # 包装信息
    detail_html: str = ""     # 详情页HTML
    detail_images: str = ""    # 详情页图片

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)

    def to_csv_row(self) -> List[str]:
        return [
            self.shop_name, self.shop_url, self.platform, self.product_id,
            self.product_name, self.product_url, self.price, self.sales,
            self.stock, self.images, self.description, self.category,
            self.shop_id, self.crawl_time, self.attrs, self.packaging,
            self.detail_html, self.detail_images
        ]

    def to_json(self) -> Dict:
        """转换为JSON兼容的字典"""
        return {
            "shop_name": self.shop_name,
            "shop_url": self.shop_url,
            "platform": self.platform,
            "product_id": self.product_id,
            "product_name": self.product_name,
            "product_url": self.product_url,
            "price": self.price,
            "sales": self.sales,
            "stock": self.stock,
            "images": self.images,
            "description": self.description,
            "category": self.category,
            "shop_id": self.shop_id,
            "crawl_time": self.crawl_time,
            "attrs": self.attrs,
            "packaging": self.packaging,
            "detail_images": self.detail_images,
        }


CSV_HEADERS = [
    "shop_name", "shop_url", "platform", "product_id", "product_name",
    "product_url", "price", "sales", "stock", "images", "description",
    "category", "shop_id", "crawl_time", "attrs", "packaging",
    "detail_html", "detail_images"
]


def get_timestamp() -> str:
    """获取当前时间戳"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def sanitize_filename(name: str) -> str:
    """清理文件名，去除非法字符"""
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    name = re.sub(r'\s+', '_', name)
    return name[:100]


def clean_text(text: str) -> str:
    """清理文本，去除多余空白和HTML标签"""
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def extract_number(text: str) -> str:
    """从文本中提取数字"""
    if not text:
        return ""
    match = re.search(r'[\d,.]+', text.replace(',', ''))
    return match.group() if match else ""


def generate_product_id(platform: str, url: str) -> str:
    """从URL生成商品ID"""
    if not url:
        return hashlib.md5(str(time.time()).encode()).hexdigest()[:12]

    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    if platform == "pinduoduo":
        goods_id = query.get('goods_id', [''])[0]
        if goods_id:
            return goods_id

    elif platform == "1688":
        offer_id = query.get('offerId', [''])[0]
        if not offer_id:
            offer_id = query.get('id', [''])[0]
        if offer_id:
            return offer_id

    path_match = re.search(r'/(\d+)\.html', url)
    if path_match:
        return path_match.group(1)

    return hashlib.md5(url.encode()).hexdigest()[:12]


def extract_shop_id(url: str, platform: str) -> str:
    """从URL提取店铺ID"""
    parsed = urlparse(url)

    if platform == "pinduoduo":
        if 'shopId' in url:
            match = re.search(r'shopId=(\d+)', url)
            if match:
                return match.group(1)
        if 'shop_id' in url:
            match = re.search(r'shop_id=(\d+)', url)
            if match:
                return match.group(1)

    elif platform == "1688":
        host = parsed.netloc
        if 'winport' in host:
            return "winport_" + host.split('.')[0]
        match = re.search(r'(\w+)\.1688\.com', host)
        if match:
            return match.group(1)

    return hashlib.md5(url.encode()).hexdigest()[:12]


def write_csv(products: List[Product], output_path: str) -> None:
    """写入CSV文件"""
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADERS)
        for product in products:
            writer.writerow(product.to_csv_row())


def read_csv(input_path: str) -> List[Dict[str, str]]:
    """读取CSV文件"""
    products = []
    with open(input_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            products.append(row)
    return products


def save_progress(processed_ids: set, progress_file: str) -> None:
    """保存进度"""
    with open(progress_file, 'w', encoding='utf-8') as f:
        json.dump(list(processed_ids), f)


def load_progress(progress_file: str) -> set:
    """加载进度"""
    if Path(progress_file).exists():
        with open(progress_file, 'r', encoding='utf-8') as f:
            return set(json.load(f))
    return set()


def format_price(price_str: str) -> str:
    """格式化价格"""
    if not price_str:
        return ""
    price_str = price_str.replace('¥', '').replace('$', '').strip()
    try:
        return f"{float(price_str):.2f}"
    except ValueError:
        return price_str


def format_sales(sales_str: str) -> str:
    """格式化销量"""
    if not sales_str:
        return "0"
    sales_str = sales_str.replace('销量', '').replace('已售', '').replace('拼单', '').strip()

    if '万' in sales_str:
        try:
            num = float(sales_str.replace('万', ''))
            return str(int(num * 10000))
        except ValueError:
            pass

    match = re.search(r'[\d,]+', sales_str)
    return match.group().replace(',', '') if match else "0"


def format_stock(stock_str: str) -> str:
    """格式化库存"""
    if not stock_str:
        return "0"
    stock_str = stock_str.replace('库存', '').replace('件', '').strip()

    if '万' in stock_str:
        try:
            num = float(stock_str.replace('万', ''))
            return str(int(num * 10000))
        except ValueError:
            pass

    match = re.search(r'[\d,]+', stock_str)
    return match.group().replace(',', '') if match else "0"


class RateLimiter:
    """请求频率限制器"""

    def __init__(self, delay: float = 2.0):
        self.delay = delay
        self.last_request = 0

    def wait(self) -> None:
        """等待足够的时间"""
        elapsed = time.time() - self.last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self.last_request = time.time()


def detect_product_url_type(url: str) -> str:
    """检测商品链接类型"""
    if 'pin.d/uoduo' in url or 'duomai' in url:
        return "pinduoduo"
    if '1688.com' in url:
        return "1688"
    if 'taobao' in url or 'tmall' in url:
        return "taobao"
    if 'jd.com' in url:
        return "jd"
    return "unknown"


def download_image(url: str, session: requests.Session = None, timeout: int = 30) -> Optional[bytes]:
    """下载图片并返回二进制内容"""
    if not url:
        return None
    try:
        if session:
            response = session.get(url, timeout=timeout)
        else:
            import requests as req
            response = req.get(url, timeout=timeout)
        response.raise_for_status()
        return response.content
    except Exception:
        return None


def download_images_to_folder(urls: List[str], folder_path: str, session: requests.Session = None, prefix: str = "") -> List[str]:
    """
    下载多个图片到指定文件夹

    Args:
        urls: 图片URL列表
        folder_path: 保存文件夹路径
        session: requests Session
        prefix: 文件名前缀

    Returns:
        保存的文件路径列表
    """
    saved_paths = []
    Path(folder_path).mkdir(parents=True, exist_ok=True)

    for i, url in enumerate(urls):
        if not url:
            continue
        content = download_image(url, session)
        if content:
            # 提取文件扩展名
            ext = '.jpg'
            if '.png' in url.lower():
                ext = '.png'
            elif '.gif' in url.lower():
                ext = '.gif'
            elif '.webp' in url.lower():
                ext = '.webp'

            filename = f"{prefix}{i+1:03d}{ext}" if prefix else f"image_{i+1:03d}{ext}"
            filepath = Path(folder_path) / filename
            try:
                with open(filepath, 'wb') as f:
                    f.write(content)
                saved_paths.append(str(filepath))
            except Exception:
                pass

    return saved_paths


def save_product_folder(product: Product, base_dir: str, session: requests.Session = None) -> str:
    """
    保存商品详情到独立文件夹

    Args:
        product: 商品数据
        base_dir: 基础目录
        session: requests Session

    Returns:
        保存的文件夹路径
    """
    # 创建以商品名命名的文件夹
    folder_name = sanitize_filename(product.product_name) or f"product_{product.product_id}"
    folder_path = Path(base_dir) / folder_name
    folder_path.mkdir(parents=True, exist_ok=True)

    # 1. 保存商品信息JSON
    info_file = folder_path / "product_info.json"
    with open(info_file, 'w', encoding='utf-8') as f:
        json.dump(product.to_json(), f, ensure_ascii=False, indent=2)

    # 2. 保存商品主图
    if product.images:
        main_urls = [url.strip() for url in product.images.split(',') if url.strip()]
        if main_urls:
            download_images_to_folder(main_urls, str(folder_path / "images"), session, "main_")

    # 3. 保存详情页图片
    if product.detail_images:
        detail_urls = [url.strip() for url in product.detail_images.split(',') if url.strip()]
        if detail_urls:
            download_images_to_folder(detail_urls, str(folder_path / "detail_images"), session, "detail_")

    # 4. 保存详情描述到文本文件
    if product.description:
        desc_file = folder_path / "description.txt"
        with open(desc_file, 'w', encoding='utf-8') as f:
            f.write(product.description)

    # 5. 保存属性信息
    if product.attrs:
        attrs_file = folder_path / "attributes.json"
        try:
            # 如果是JSON字符串则保存为JSON，否则保存为文本
            attrs_data = json.loads(product.attrs)
            with open(attrs_file, 'w', encoding='utf-8') as f:
                json.dump(attrs_data, f, ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            attrs_file = folder_path / "attributes.txt"
            with open(attrs_file, 'w', encoding='utf-8') as f:
                f.write(product.attrs)

    # 6. 保存包装信息
    if product.packaging:
        pkg_file = folder_path / "packaging.txt"
        with open(pkg_file, 'w', encoding='utf-8') as f:
            f.write(product.packaging)

    # 7. 保存详情页HTML（可选，用于调试）
    if product.detail_html:
        html_file = folder_path / "detail.html"
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(product.detail_html)

    return str(folder_path)
