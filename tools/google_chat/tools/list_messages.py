from collections.abc import Generator
from typing import Any

import requests

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from dify_plugin.entities.invoke_message import InvokeMessage


class ListMessagesTool(Tool):
    """
    Tool to list messages in a Google Chat space
    """
    
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        """
        List messages in a Google Chat space
        """
        # Extract parameters
        space_name = tool_parameters.get("space_name")
        page_size = tool_parameters.get("page_size", 25)
        filter_str = tool_parameters.get("filter", "")
        order_by = tool_parameters.get("order_by", "createTime DESC")
        show_deleted = tool_parameters.get("show_deleted", False)
        
        if not space_name:
            yield self.create_text_message("Space name is required")
            return
        
        # Ensure correct format
        if not space_name.startswith("spaces/"):
            space_name = f"spaces/{space_name}"
        
        # Get credentials
        access_token = self.runtime.credentials.get("access_token")
        if not access_token:
            yield self.create_text_message("Access token not found. Please authenticate first.")
            return
        
        # Build API request
        url = f"https://chat.googleapis.com/v1/{space_name}/messages"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        params = {
            "pageSize": min(page_size, 100),  # Max 100 per page
            "orderBy": order_by,
            "showDeleted": str(show_deleted).lower()
        }
        
        if filter_str:
            params["filter"] = filter_str
        
        try:
            all_messages = []
            next_page_token = None
            page_count = 0
            max_pages = 3  # Limit pages to prevent excessive API calls
            
            while page_count < max_pages:
                if next_page_token:
                    params["pageToken"] = next_page_token
                
                response = requests.get(url, headers=headers, params=params, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    messages = data.get("messages", [])
                    all_messages.extend(messages)
                    
                    next_page_token = data.get("nextPageToken")
                    page_count += 1
                    
                    # Stop if we have enough messages or no more pages
                    if not next_page_token or len(all_messages) >= page_size:
                        break
                        
                elif response.status_code == 403:
                    yield self.create_text_message("Permission denied. Check if the bot has access to read messages.")
                    return
                elif response.status_code == 404:
                    yield self.create_text_message(f"Space not found: {space_name}")
                    return
                else:
                    yield self.create_text_message(f"Error listing messages: {response.status_code} - {response.text}")
                    return
            
            # Process and format messages
            message_list = []
            for message in all_messages[:page_size]:
                message_info = {
                    "name": message.get("name"),
                    "text": message.get("text", ""),
                    "createTime": message.get("createTime"),
                    "updateTime": message.get("updateTime"),
                    "sender": {
                        "name": message.get("sender", {}).get("name"),
                        "displayName": message.get("sender", {}).get("displayName", "Unknown"),
                        "type": message.get("sender", {}).get("type", "UNKNOWN")
                    },
                    "thread": message.get("thread", {}),
                    "deleted": message.get("deleteTime") is not None,
                    "hasAttachments": len(message.get("attachment", [])) > 0,
                    "reactionCount": sum(r.get("reactionCount", 0) for r in message.get("emojiReactionSummaries", []))
                }
                message_list.append(message_info)
            
            # Return results
            result = {
                "total": len(message_list),
                "messages": message_list,
                "hasMore": next_page_token is not None
            }
            
            yield self.create_json_message(result)
            
            # Create human-readable summary
            summary_lines = [f"Found {len(message_list)} messages in the space:"]
            for msg in message_list[:10]:  # Show first 10 messages
                sender = msg["sender"]["displayName"]
                text = msg["text"][:50] + "..." if len(msg["text"]) > 50 else msg["text"]
                time = msg["createTime"].split("T")[0] if msg.get("createTime") else "Unknown"
                
                extra_info = []
                if msg["hasAttachments"]:
                    extra_info.append("📎")
                if msg["reactionCount"] > 0:
                    extra_info.append(f"👍{msg['reactionCount']}")
                if msg["deleted"]:
                    extra_info.append("🗑️")
                
                extras = " ".join(extra_info) if extra_info else ""
                summary_lines.append(f"• [{time}] {sender}: {text} {extras}")
            
            if len(message_list) > 10:
                summary_lines.append(f"... and {len(message_list) - 10} more messages")
            
            yield self.create_text_message("\n".join(summary_lines))
            
        except requests.RequestException as e:
            yield self.create_log_message(
                label="Network Error",
                data={"error": str(e)},
                status=InvokeMessage.LogMessage.LogStatus.ERROR
            )
            yield self.create_text_message(f"Network error: {str(e)}")