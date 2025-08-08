from collections.abc import Generator
from typing import Any

import requests

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from dify_plugin.entities.invoke_message import InvokeMessage


class GetMessageTool(Tool):
    """
    Tool to get a specific message from a Google Chat space
    """
    
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        """
        Get a specific message from Google Chat
        """
        # Extract parameters
        message_name = tool_parameters.get("message_name")
        
        if not message_name:
            yield self.create_text_message("Message name is required")
            return
        
        # Ensure correct format
        if not message_name.startswith("spaces/"):
            # If only message ID is provided, we need the space name
            space_name = tool_parameters.get("space_name")
            if space_name:
                if not space_name.startswith("spaces/"):
                    space_name = f"spaces/{space_name}"
                message_name = f"{space_name}/messages/{message_name}"
            else:
                yield self.create_text_message("Full message name or space name is required")
                return
        
        # Get credentials
        access_token = self.runtime.credentials.get("access_token")
        if not access_token:
            yield self.create_text_message("Access token not found. Please authenticate first.")
            return
        
        # Make API request
        url = f"https://chat.googleapis.com/v1/{message_name}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                message_data = response.json()
                
                # Format the response
                result = {
                    "name": message_data.get("name"),
                    "text": message_data.get("text"),
                    "formattedText": message_data.get("formattedText"),
                    "createTime": message_data.get("createTime"),
                    "updateTime": message_data.get("updateTime"),
                    "deleteTime": message_data.get("deleteTime"),
                    "sender": message_data.get("sender", {}),
                    "thread": message_data.get("thread", {}),
                    "space": message_data.get("space", {}),
                    "attachments": message_data.get("attachment", []),
                    "emojiReactionSummaries": message_data.get("emojiReactionSummaries", []),
                    "annotations": message_data.get("annotations", [])
                }
                
                yield self.create_json_message(result)
                
                # Create human-readable summary
                sender_name = result.get("sender", {}).get("displayName", "Unknown")
                text = result.get("text", "")
                create_time = result.get("createTime", "Unknown")
                thread_name = result.get("thread", {}).get("name", "")
                
                summary = f"""
Message Details:
- Sender: {sender_name}
- Text: {text[:200]}{'...' if len(text) > 200 else ''}
- Created: {create_time}
"""
                if thread_name:
                    summary += f"- Thread: {thread_name.split('/')[-1]}\n"
                
                if result.get("emojiReactionSummaries"):
                    reactions = []
                    for reaction in result["emojiReactionSummaries"]:
                        emoji = reaction.get("emoji", {}).get("unicode", "")
                        count = reaction.get("reactionCount", 0)
                        reactions.append(f"{emoji} ({count})")
                    summary += f"- Reactions: {', '.join(reactions)}\n"
                
                yield self.create_text_message(summary.strip())
                
            elif response.status_code == 404:
                yield self.create_text_message(f"Message not found: {message_name}")
            elif response.status_code == 403:
                yield self.create_text_message("Permission denied. Check if the bot has access to this message.")
            else:
                yield self.create_text_message(f"Error getting message: {response.status_code} - {response.text}")
                
        except requests.RequestException as e:
            yield self.create_log_message(
                label="Network Error",
                data={"error": str(e)},
                status=InvokeMessage.LogMessage.LogStatus.ERROR
            )
            yield self.create_text_message(f"Network error: {str(e)}")