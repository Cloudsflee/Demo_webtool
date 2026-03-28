# Serper Agent Demo

基于 Flask 的最小可运行 Demo，用于验证主 Agent 串行调用 Serper 工具链：

- `web_search`
- `web_crawler`
- `image_search`
- `image_crawl`
- `image_fetch_save`

## 功能范围

- `POST /agent/run`：执行主 Agent 循环（`parallel_tool_calls=false`）
- 工具错误会回注模型，避免 silent fail
- 图片下载按请求落盘到 `pic/<request_id>/`
- 提供测试前端页面：`GET /`

## 目录结构

```text
Demo/
  app.py
  agent.py
  schemas.py
  config.py
  tools/
    serper_search.py
    serper_crawler.py
    image_search.py
    image_crawl.py
    image_fetch_save.py
  pic/
    <request_id>/
      ...
  templates/
    index.html
  static/
    app.js
  requirements.txt
  .env.example
```

## 安装与运行

1. 创建虚拟环境并安装依赖

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

1. 配置环境变量

```bash
copy .env.example .env
```

然后编辑 `.env`，至少填写：

- `LLM_GATEWAY_HOST`
- `LLM_GATEWAY_TOKEN`
- `SERPER_API_KEY`

1. 启动服务

```bash
python app.py
```

默认地址：`http://127.0.0.1:5000`

## API 示例

`POST /agent/run`

请求体：

```json
{
  "user_input": "请搜索并总结今天AI行业重点动态，附来源链接",
  "max_turns": 6,
  "debug": true
}
```

响应体：

```json
{
  "answer": "final assistant text",
  "turns": 3,
  "request_id": "20260328123001_ab12cd34",
  "request_pic_dir": "D:/04_projects/advoo-myself/Demo/pic/20260328123001_ab12cd34",
  "downloaded_images": [
    {
      "request_id": "20260328123001_ab12cd34",
      "image_url": "https://...",
      "source_page": "https://...",
      "saved_path": "pic/20260328123001_ab12cd34/logo_xxx.png",
      "public_url": "/pic/20260328123001_ab12cd34/logo_xxx.png",
      "file_name": "logo_xxx.png",
      "mime": "image/png",
      "size": 12345,
      "sha256": "..."
    }
  ],
  "tool_calls": [
    {
      "name": "web_search",
      "args": { "query": "..." },
      "status": "ok",
      "http_status": 200
    }
  ],
  "debug_logs": []
}
```

## 验收检查

- 正常查询触发 `web_search`
- 深入阅读链接时触发 `web_crawler`
- 图片请求可触发 `image_search -> image_crawl -> image_fetch_save`
- 本次请求下载图片可在前端“本次请求下载图片”区域直接查看
- 缺失 `SERPER_API_KEY` 时报错清晰
- `max_turns` 生效
- `dataRange` 映射 `tbs` 正确
