from typing import Any


SYSTEM_PROMPT = """You are a research assistant.
Use tools when factual or up-to-date information is needed.
Prefer:
1) call web_search first to find candidate links
2) then call web_crawler only for links you need to read in detail
For image tasks, prefer:
1) call image_search first
2) then image_crawl for candidate pages if needed
3) then image_fetch_save to download selected images
Never call tools in parallel.
When enough evidence is collected, provide a concise answer with sources."""


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search web results with optional search type, pagination, locale and time range filters",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "searchType": {
                        "type": "string",
                        "enum": [
                            "search",
                            "images",
                            "videos",
                            "news",
                            "shopping",
                            "places",
                            "scholar",
                            "patents",
                        ],
                    },
                    "type": {
                        "type": "string",
                        "enum": [
                            "search",
                            "images",
                            "videos",
                            "news",
                            "shopping",
                            "places",
                            "scholar",
                            "patents",
                        ],
                    },
                    "gl": {"type": "string"},
                    "hl": {"type": "string"},
                    "num": {"type": "integer"},
                    "page": {"type": "integer"},
                    "location": {"type": "string"},
                    "safe": {"type": "boolean"},
                    "autocorrect": {"type": "boolean"},
                    "tbs": {"type": "string"},
                    "dataRange": {
                        "type": "string",
                        "enum": ["past_hour", "past_day", "past_week", "past_month", "past_year"],
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_crawler",
            "description": "Fetch main content from a single webpage URL",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "includeMarkdown": {"type": "boolean"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "image_search",
            "description": "Search image results for a query and return normalized candidates",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "timeRange": {
                        "type": "string",
                        "enum": ["past_hour", "past_day", "past_week", "past_month", "past_year"],
                    },
                    "limit": {"type": "integer"},
                    "gl": {"type": "string"},
                    "hl": {"type": "string"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "image_crawl",
            "description": "Crawl a webpage and extract candidate images with context",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "image_fetch_save",
            "description": "Download and save one image to local pic folder",
            "parameters": {
                "type": "object",
                "properties": {
                    "imageUrl": {"type": "string"},
                    "nameHint": {"type": "string"},
                    "sourcePage": {"type": "string"},
                    "requestId": {"type": "string"},
                },
                "required": ["imageUrl"],
            },
        },
    },
]
