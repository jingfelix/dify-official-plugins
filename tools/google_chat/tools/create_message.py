from collections.abc import Generator
from typing import Any
import json

import requests

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from dify_plugin.entities.invoke_message import InvokeMessage


class CreateMessageTool(Tool):
    """
    Tool to create and send a message in a Google Chat space
    """
    
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        """
        Create a message in a Google Chat space
        """
        # Extract parameters
        space_name = tool_parameters.get("space_name")
        text = tool_parameters.get("text")
        thread_name = tool_parameters.get("thread_name")
        reply_to = tool_parameters.get("reply_to")
        request_id = tool_parameters.get("request_id")
        
        if not space_name:
            yield self.create_text_message("Space name is required")
            return
        
        if not text:
            yield self.create_text_message("Message text is required")
            return
        
        # Ensure correct format
        if not space_name.startswith("spaces/"):
            space_name = f"spaces/{space_name}"
        
        # Get credentials
        access_token = self.runtime.credentials.get("access_token")
        if not access_token:
            yield self.create_text_message("Access token not found. Please authenticate first.")
            return
        
        # Build message payload
        message_data = {
            "text": text
        }
        
        # Add thread information if provided
        if thread_name:
            if not thread_name.startswith("spaces/"):
                thread_name = f"{space_name}/threads/{thread_name}"
            message_data["thread"] = {"name": thread_name}
        
        # Add reply information if provided
        if reply_to:
            if not reply_to.startswith("spaces/"):
                reply_to = f"{space_name}/messages/{reply_to}"
            if "thread" not in message_data:
                message_data["thread"] = {}
            message_data["thread"]["threadReply"] = {"messageId": reply_to}
        
        # Build API request
        url = f"https://chat.googleapis.com/v1/{space_name}/messages"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        params = {}
        if request_id:
            params["requestId"] = request_id
        
        try:
            response = requests.post(
                url, 
                headers=headers, 
                params=params,
                data=json.dumps(message_data),
                timeout=10
            )
            
            if response.status_code == 200:
                message_result = response.json()
                
                # Format the response
                result = {
                    "name": message_result.get("name"),
                    "text": message_result.get("text"),
                    "createTime": message_result.get("createTime"),
                    "sender": message_result.get("sender", {}),
                    "thread": message_result.get("thread", {}),
                    "formattedText": message_result.get("formattedText")
                }
                
                yield self.create_json_message(result)
                
                # Create success message
                message_id = result["name"].split("/")[-1] if result.get("name") else "unknown"
                thread_info = ""
                if result.get("thread", {}).get("name"):
                    thread_id = result["thread"]["name"].split("/")[-1]
                    thread_info = f" in thread {thread_id}"
                
                success_msg = f"Message sent successfully! Message ID: {message_id}{thread_info}"
                yield self.create_text_message(success_msg)
                
            elif response.status_code == 403:
                yield self.create_text_message("Permission denied. Check if the bot has permission to send messages in this space.")
            elif response.status_code == 404:
                yield self.create_text_message(f"Space not found: {space_name}")
            else:
                yield self.create_text_message(f"Error sending message: {response.status_code} - {response.text}")
                
        except requests.RequestException as e:
            yield self.create_log_message(
                label="Network Error",
                data={"error": str(e)},
                status=InvokeMessage.LogMessage.LogStatus.ERROR
            )
            yield self.create_text_message(f"Network error: {str(e)}")