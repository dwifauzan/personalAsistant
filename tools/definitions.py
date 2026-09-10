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
    },
    {
        "type": "function",
        "function": {
            "name": "set_reminder",
            "description": "Set a reminder for the user at a specific time. Use when the user asks to be reminded about something at a certain time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "time": {
                        "type": "string",
                        "description": "Time for the reminder in HH:MM format (24-hour). Example: '20:00' for 8 PM."
                    },
                    "message": {
                        "type": "string",
                        "description": "The reminder message to speak to the user"
                    }
                },
                "required": ["time", "message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_reminders",
            "description": "Get all active reminders. Use when the user asks to see their reminders.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_reminder",
            "description": "Delete a reminder at a specific time. Use when the user wants to remove a reminder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "time": {
                        "type": "string",
                        "description": "Time of the reminder to delete in HH:MM format (24-hour)"
                    }
                },
                "required": ["time"]
            }
        }
    }
]
