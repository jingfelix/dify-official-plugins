from collections.abc import Generator
from typing import Any

import requests

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from dify_plugin.entities.invoke_message import InvokeMessage


class GetSpaceTool(Tool):
    """
    Tool to get information about a Google Chat space
    """
    
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        """
        Get space information from Google Chat API
        """
        # Extract parameters
        space_name = tool_parameters.get("space_name")
        if not space_name:
            yield self.create_text_message("Space name is required")
            return
        
        # Ensure space_name has correct format
        if not space_name.startswith("spaces/"):
            space_name = f"spaces/{space_name}"
        
        # Get credentials
        access_token = self.runtime.credentials.get("access_token")
        if not access_token:
            yield self.create_text_message("Access token not found. Please authenticate first.")
            return
        
        # Make API request
        url = f"https://chat.googleapis.com/v1/{space_name}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                space_data = response.json()
                
                # Format the response
                result = {
                    "name": space_data.get("name"),
                    "displayName": space_data.get("displayName"),
                    "spaceType": space_data.get("spaceType"),
                    "singleUserBotDm": space_data.get("singleUserBotDm", False),
                    "threaded": space_data.get("threaded", False),
                    "spaceDetails": space_data.get("spaceDetails", {}),
                    "spaceHistoryState": space_data.get("spaceHistoryState"),
                    "importMode": space_data.get("importMode", False),
                    "createTime": space_data.get("createTime"),
                    "adminInstalled": space_data.get("adminInstalled", False)
                }
                
                yield self.create_json_message(result)
                
                # Create a human-readable summary
                summary = f"""
Space Information:
- Name: {result['name']}
- Display Name: {result['displayName']}
- Type: {result['spaceType']}
- Threaded: {result['threaded']}
- History State: {result['spaceHistoryState']}
- Created: {result['createTime']}
"""
                yield self.create_text_message(summary.strip())
                
            elif response.status_code == 404:
                yield self.create_text_message(f"Space not found: {space_name}")
            elif response.status_code == 403:
                yield self.create_text_message("Permission denied. Check if the bot has access to this space.")
            else:
                yield self.create_text_message(f"Error getting space: {response.status_code} - {response.text}")
                
        except requests.RequestException as e:
            yield self.create_log_message(
                label="Network Error",
                data={"error": str(e)},
                status=InvokeMessage.LogMessage.LogStatus.ERROR
            )
            yield self.create_text_message(f"Network error: {str(e)}")