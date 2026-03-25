# cn-ecommerce-scraper

拼多多/1688 电商商品爬虫 - 从店铺 URL 爬取所有商品清单和详情，支持商品属性、包装信息和详情图片抓取。

## 功能特点

- 自动识别平台（拼多多/1688）
- 支持批量爬取多个店铺
- 自动翻页获取所有商品
- 提取商品详情（价格、销量、库存、图片等）
- **新增**: 商品属性抓取 (品牌、型号、材质等)
- **新增**: 包装信息抓取 (包装规格、装箱数量等)
- **新增**: 详情页图片抓取
- **新增**: 每个商品保存到独立文件夹
- 支持断点续传
- 结果导出为 CSV/Excel

## 安装依赖

```bash
pip install requests beautifulsoup4 playwright
playwright install chromium
```

## 快速开始

### 1. 爬取店铺商品列表

```bash
# 拼多多
python scripts/crawl_pinduoduo.py "https://you.kuajingpinduoduo.com/shop-detail/shopDetail?shopId=xxx" --output products.csv

# 1688
python scripts/crawl_1688_browser.py "https://xxx.1688.com/page/creditlist.htm" --output products.csv
```

### 2. 获取商品详情

```bash
python scripts/fetch_details.py products.csv --output products_detailed.csv
```

### 3. 获取详情并保存到文件夹（推荐）

```bash
python scripts/fetch_details.py products.csv --output products_detailed.csv --folders --base-dir ./product_details
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
| attrs | 商品属性（JSON） |
| packaging | 包装信息 |
| detail_images | 详情页图片URL |

## 商品文件夹结构

使用 `--folders` 参数时，每个商品保存到独立文件夹：

```
product_details/
├── 商品A名称/
│   ├── product_info.json      # 商品完整信息
│   ├── images/               # 主图目录
│   ├── detail_images/        # 详情页图片
│   ├── description.txt       # 商品描述
│   ├── attributes.json       # 商品属性
│   └── packaging.txt         # 包装信息
└── 商品B名称/
    └── ...
```

## 注意事项

1. 请合理设置请求间隔，避免被封禁
2. 部分页面可能需要登录或验证码
3. 请遵守平台的 robots.txt 和使用条款

## License

MIT