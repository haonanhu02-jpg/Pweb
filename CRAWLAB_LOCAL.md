# 本机 Docker Desktop 部署 Crawlab

本文档用于在本机 Docker Desktop 上运行单节点 Crawlab + MongoDB，并调度当前 POC 的 3 个爬虫。

## 1. 启动

```powershell
cd D:\Pweb\mix采集poc
docker compose -f docker-compose.crawlab.yml up -d --build
```

查看容器状态：

```powershell
docker compose -f docker-compose.crawlab.yml ps
```

查看 Crawlab 日志：

```powershell
docker compose -f docker-compose.crawlab.yml logs -f crawlab
```

## 2. 打开 Crawlab

浏览器打开：

```text
http://localhost:8080
```

默认账号：

```text
admin / admin
```

首次登录后立即修改密码。

## 3. 验证 POC 运行环境

容器内查看已入库统计：

```powershell
docker compose -f docker-compose.crawlab.yml exec crawlab sh -lc "cd /opt/tender-poc && python -m tender_poc stats"
```

容器内运行一条采集验证：

```powershell
docker compose -f docker-compose.crawlab.yml exec crawlab sh -lc "cd /opt/tender-poc && python -m tender_poc run ggzy --limit 1"
```

数据目录通过环境变量固定到：

```text
TENDER_POC_DATA_DIR=/data/tender-poc
```

宿主机对应目录：

```text
D:\Pweb\mix采集poc\data
```

## 4. 在 Crawlab UI 创建 Spider

创建 3 个 Spider，命令分别为：

```bash
cd /opt/tender-poc && python -m tender_poc run ggzy --limit 20
```

```bash
cd /opt/tender-poc && python -m tender_poc run sdic --limit 20
```

```bash
cd /opt/tender-poc && python -m tender_poc run cec --limit 20
```

```bash
cd /opt/tender-poc && python -m tender_poc run crrc --limit 20
```

建议命名：

- `tender-ggzy`
- `tender-sdic`
- `tender-cec`
- `tender-crrc`

## 5. 定时建议

当前阶段继续使用 SQLite，3 个任务不要同一分钟并发运行。

建议错峰：

```text
ggzy: 0 */2 * * *
sdic: 20 */2 * * *
cec: 40 */2 * * *
crrc: 10 */2 * * *
```

## 6. 常用命令

停止：

```powershell
docker compose -f docker-compose.crawlab.yml down
```

重启：

```powershell
docker compose -f docker-compose.crawlab.yml up -d
```

导出 JSONL：

```powershell
docker compose -f docker-compose.crawlab.yml exec crawlab sh -lc "cd /opt/tender-poc && python -m tender_poc export --format jsonl"
```

导出文件在宿主机：

```text
D:\Pweb\mix采集poc\data\exports\tenders.jsonl
```

## 7. 注意

- 不上传 `.venv` 到 Crawlab。
- `data/` 和 `docker-data/` 是本机持久化目录，不提交代码仓库。
- 如果 `8080` 端口被占用，把 `docker-compose.crawlab.yml` 中 `8080:8080` 改成 `18080:8080`，然后访问 `http://localhost:18080`。
- 中招平台暂不纳入本次 Crawlab 验证，因为当前直接请求会被安全策略拦截。
