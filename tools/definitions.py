TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for general information. Use when you need current data, facts, or information beyond your training cutoff.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (default 3, max 5)",
                        "default": 3
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "news_search",
            "description": "Search for latest news articles and breaking stories. Use when the user asks about recent events, news, or current happenings.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The news search query"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of articles (default 3, max 5)",
                        "default": 3
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "finance_lookup",
            "description": "Look up stock market indices and financial data. Use for questions about IHSG, Nasdaq, Dow Jones, S&P 500, or specific stock symbols.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol_or_name": {
                        "type": "string",
                        "description": "The index name (IHSG, Nasdaq) or stock symbol"
                    }
                },
                "required": ["symbol_or_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browse_url",
            "description": "Fetch and read the content of a specific webpage. Use when you have a URL and need to extract information from it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to browse"
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": "Maximum characters to extract (default 5000)",
                        "default": 5000
                    }
                },
                "required": ["url"]
            }
        }
    }
]
