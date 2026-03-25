# cn-ecommerce-scraper

拼多多/1688 电商商品爬虫 - 从店铺 URL 爬取所有商品清单和详情，输出为 CSV/Excel 文件。

## 功能特点

- 自动识别平台（拼多多/1688）
- 支持批量爬取多个店铺
- 自动翻页获取所有商品
- 提取商品详情（价格、销量、库存、图片等）
- 支持断点续传
- 结果导出为 CSV/Excel

## 安装依赖

```bash
pip install requests beautifulsoup4 playwright
playwright install chromium
```

## 使用方法

### 1. 检测平台

```bash
python scripts/detect_platform.py "<店铺URL>"
```

### 2. 爬取商品列表

**拼多多店铺：**
```bash
python scripts/crawl_pinduoduo.py "<店铺URL>" --output products.csv
```

**1688店铺：**
```bash
python scripts/crawl_1688_browser.py "<店铺URL>" --output products.csv
```

### 3. 获取商品详情（如需）

```bash
python scripts/fetch_details.py products.csv --output products_with_details.csv
```

## 输出字段

| 字段 | 说明 |
|------|------|
| shop_name | 店铺名称 |
| shop_url | 店铺URL |
| platform | 平台（pinduoduo/1688） |
| product_id | 商品ID |
| product_name | 商品名称 |
| product_url | 商品详情页URL |
| price | 价格 |
| sales | 销量 |
| stock | 库存 |
| images | 商品图片URL |
| description | 商品描述 |
| category | 商品类目 |
| shop_id | 店铺ID |
| crawl_time | 爬取时间 |

## 注意事项

1. 请合理设置请求间隔，避免被封禁
2. 部分页面可能需要登录或验证码
3. 请遵守平台的 robots.txt 和使用条款

## License

MIT