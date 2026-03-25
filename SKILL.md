---
name: ecommerce-scraper
description: >
  拼多多/1688电商商品爬虫 - 从店铺URL爬取所有商品清单和详情，输出为CSV/Excel文件。
  当用户需要爬取拼多多或1688店铺的商品列表、获取商品详情、导出商品数据为表格时使用。
  支持批量处理多个店铺URL，自动识别平台，自动翻页爬取所有商品。
license: MIT
metadata:
  author: claude
  version: "1.0.0"
---

# 拼多多/1688 商品爬虫

从拼多多或1688店铺URL爬取商品列表和详情，输出为CSV/Excel格式。

## 何时使用

- 用户提供一个拼多多/1688店铺URL，要求爬取所有商品
- 用户需要导出店铺商品列表为Excel表格
- 用户需要批量获取商品详情（价格、销量、库存等）
- 用户需要分析竞争对手店铺的商品结构

## 输入要求

**必填：** 店铺页面URL（拼多多或1688）

**示例URL格式：**
- 拼多多：`https://you.kuajingpinduoduo.com/shop-detail/shopDetail?shopId=xxx`
- 1688：`https://xxx.1688.com/page/creditlist.htm` 或 `https://winport.winportdetail.1688.com/`

## 输出

CSV/Excel文件，包含以下字段：

| 字段 | 说明 |
|------|------|
| `shop_name` | 店铺名称 |
| `shop_url` | 店铺URL |
| `platform` | 平台（pinduoduo/1688） |
| `product_id` | 商品ID |
| `product_name` | 商品名称 |
| `product_url` | 商品详情页URL |
| `price` | 价格 |
| `sales` | 销量 |
| `stock` | 库存 |
| `images` | 商品图片URL（逗号分隔） |
| `description` | 商品描述 |
| `category` | 商品类目 |
| `shop_id` | 店铺ID |
| `crawl_time` | 爬取时间 |

## 使用流程

### 步骤1：分析URL并识别平台

收到店铺URL后，使用脚本检测平台类型：

```bash
python scripts/detect_platform.py "<店铺URL>"
```

### 步骤2：爬取商品列表

根据平台选择对应脚本：

**拼多多店铺：**
```bash
python scripts/crawl_pinduoduo.py "<店铺URL>" --output products.csv
```

**1688店铺：**
```bash
python scripts/crawl_1688.py "<店铺URL>" --output products.csv
```

### 步骤3：获取商品详情（如需详情信息）

```bash
python scripts/fetch_details.py products.csv --output products_with_details.csv
```

### 步骤4：导出最终CSV

最终输出已包含所有字段，可直接使用。

## 脚本说明

### detect_platform.py
自动识别URL所属平台（pinduoduo/1688）

| 参数 | 说明 |
|------|------|
| `url` | 店铺URL |

### crawl_pinduoduo.py
爬取拼多多店铺商品列表

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `url` | 店铺URL | 必填 |
| `--output` | 输出CSV路径 | output.csv |
| `--max-pages` | 最大爬取页数 | 50 |
| `--delay` | 请求间隔(秒) | 2 |

### crawl_1688.py
爬取1688店铺商品列表（使用Playwright自动处理JavaScript动态加载）

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `url` | 店铺URL | 必填 |
| `--output` | 输出CSV路径 | output.csv |
| `--max-pages` | 最大爬取页数 | 50 |
| `--delay` | 请求间隔(秒) | 2 |

**依赖：** 需要安装 Playwright
```bash
pip install playwright
playwright install chromium
```

### fetch_details.py
批量获取商品详情

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `input_csv` | 包含商品ID的CSV | 必填 |
| `--output` | 输出CSV路径 | output_detailed.csv |
| `--platform` | 平台类型 | auto |
| `--delay` | 请求间隔(秒) | 1 |

## 输出文件

所有输出文件保存到当前目录，文件名格式：
- `{shop_name}_{platform}_products.csv` - 商品列表
- `{shop_name}_{platform}_details.csv` - 含详情的商品列表

## 注意事项

1. **频率限制**：设置合理的请求间隔，避免被封禁
2. **反爬处理**：部分页面可能需要验证码或登录状态
3. **增量更新**：支持断点续传，已爬取商品不会重复爬取
4. **数据清洗**：自动去除HTML标签、空格等

## 错误处理

- URL无效或不可访问：输出错误信息并跳过
- 网络超时：自动重试3次
- 反爬拦截：降低请求频率或更换IP
- 部分失败：记录失败商品ID，支持单独重爬
