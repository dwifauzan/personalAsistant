import pytest
from unittest.mock import patch, MagicMock
from llm import chat

@patch("llm.ollama.chat")
def test_chat_no_tool_calls(mock_chat):
    mock_response = {
        "message": {
            "role": "assistant",
            "content": "Hello!",
        }
    }
    mock_chat.return_value = mock_response

    result = chat([{"role": "user", "content": "Hi"}])
    assert result["message"]["content"] == "Hello!"
    assert mock_chat.call_count == 1

@patch("llm.execute_tools_parallel")
@patch("llm.ollama.chat")
def test_chat_with_tool_calls(mock_chat, mock_execute):
    tool_call_response = {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "function": {
                        "name": "web_search",
                        "arguments": {"query": "test"},
                    }
                }
            ],
        }
    }

    final_response = {
        "message": {
            "role": "assistant",
            "content": "Here are the results...",
        }
    }

    mock_chat.side_effect = [tool_call_response, final_response]
    mock_execute.return_value = ["Search results..."]

    result = chat([{"role": "user", "content": "Search for test"}])
    assert result["message"]["content"] == "Here are the results..."
    assert mock_chat.call_count == 2

@patch("llm.execute_tools_parallel")
@patch("llm.ollama.chat")
def test_chat_max_rounds_forces_final_response(mock_chat, mock_execute):
    tool_call_response = {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "function": {
                        "name": "web_search",
                        "arguments": {"query": "test"},
                    }
                }
            ],
        }
    }

    final_response = {
        "message": {
            "role": "assistant",
            "content": "Final answer",
        }
    }

    mock_chat.side_effect = [tool_call_response, tool_call_response, tool_call_response, final_response]
    mock_execute.return_value = ["Search results..."]

    result = chat([{"role": "user", "content": "Search"}])
    assert result["message"]["content"] == "Final answer"
