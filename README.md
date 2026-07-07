# 招标公告采集 POC

这是一个可丢弃、可验证的采集 POC，用来回答一个问题：

> 全国公共资源交易平台的公开公告，是否能稳定转换为统一公告 JSON，并完成最小入库、去重和导出闭环。

当前范围只包含公开页面采集，不处理登录、验证码、自动投标、报价、CRM、商机评分或销售跟进。

## 环境准备

```powershell
cd D:\Pweb\mix采集poc
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m pip install -e .
```

## 运行

采集全国公共资源交易平台首页交易公告：

```powershell
.\.venv\Scripts\python -m tender_poc run ggzy --limit 20
```

当前支持的平台爬虫：

```powershell
.\.venv\Scripts\python -m tender_poc run ggzy --limit 20
.\.venv\Scripts\python -m tender_poc run sdic --limit 20
.\.venv\Scripts\python -m tender_poc run cec --limit 20
```

其中：

- `ggzy`：全国公共资源交易平台
- `sdic`：国投集团电子采购平台
- `cec`：CEC电子采购平台

查看入库统计：

```powershell
.\.venv\Scripts\python -m tender_poc stats
```

导出 JSONL：

```powershell
.\.venv\Scripts\python -m tender_poc export --format jsonl
```

默认数据位置：

- SQLite：`data\tenders.sqlite`
- 原始 HTML 快照：`data\raw\`
- 导出文件：`data\exports\tenders.jsonl`

部署到 Docker/Crawlab 时可以用环境变量固定数据目录：

```powershell
$env:TENDER_POC_DATA_DIR = "D:\Pweb\mix采集poc\data"
```

Linux 容器内推荐：

```bash
export TENDER_POC_DATA_DIR=/data/tender-poc
```

## 标准公告模型

核心模型是 `TenderNoticeV1`，字段包括：

- `id`
- `source_platform`
- `source_channel`
- `notice_type`
- `title`
- `buyer`
- `agency`
- `publish_time`
- `deadline`
- `bid_open_time`
- `region`
- `industry`
- `platform_url`
- `original_url`
- `attachments`
- `content_text`
- `raw_fields`
- `content_hash`
- `fetched_at`

## 后续接 Crawlab

Crawlab 只需要调度同一个命令：

```powershell
python -m tender_poc run ggzy --limit 20
```

因此当前 POC 不依赖 Crawlab，但入口形态已经按可调度任务设计。

本机 Docker Desktop 部署说明见：

```text
CRAWLAB_LOCAL.md
```
