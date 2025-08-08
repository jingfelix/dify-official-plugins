from collections.abc import Generator
from typing import Any

import requests

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from dify_plugin.entities.invoke_message import InvokeMessage


class GetMemberTool(Tool):
    """
    Tool to get information about a member in a Google Chat space
    """
    
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        """
        Get member information from Google Chat API
        """
        # Extract parameters
        space_name = tool_parameters.get("space_name")
        member_name = tool_parameters.get("member_name")
        
        if not space_name:
            yield self.create_text_message("Space name is required")
            return
        
        if not member_name:
            yield self.create_text_message("Member name is required")
            return
        
        # Ensure correct format
        if not space_name.startswith("spaces/"):
            space_name = f"spaces/{space_name}"
        
        # Handle member name format
        if not member_name.startswith("users/"):
            member_name = f"users/{member_name}"
        
        # Get credentials
        access_token = self.runtime.credentials.get("access_token")
        if not access_token:
            yield self.create_text_message("Access token not found. Please authenticate first.")
            return
        
        # Make API request
        url = f"https://chat.googleapis.com/v1/{space_name}/members/{member_name}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                member_data = response.json()
                
                # Format the response
                result = {
                    "name": member_data.get("name"),
                    "state": member_data.get("state"),
                    "role": member_data.get("role"),
                    "createTime": member_data.get("createTime"),
                    "deleteTime": member_data.get("deleteTime"),
                    "member": member_data.get("member", {})
                }
                
                # Extract user information if available
                if "member" in member_data:
                    member_info = member_data["member"]
                    if member_info.get("type") == "HUMAN":
                        result["memberType"] = "HUMAN"
                        result["displayName"] = member_info.get("displayName")
                        result["domainId"] = member_info.get("domainId")
                    elif member_info.get("type") == "BOT":
                        result["memberType"] = "BOT"
                        result["displayName"] = member_info.get("displayName")
                
                yield self.create_json_message(result)
                
                # Create a human-readable summary
                member_type = result.get("memberType", "UNKNOWN")
                display_name = result.get("displayName", "Unknown")
                summary = f"""
Member Information:
- Display Name: {display_name}
- Type: {member_type}
- State: {result.get('state', 'UNKNOWN')}
- Role: {result.get('role', 'MEMBER')}
- Joined: {result.get('createTime', 'Unknown')}
"""
                yield self.create_text_message(summary.strip())
                
            elif response.status_code == 404:
                yield self.create_text_message(f"Member not found in space")
            elif response.status_code == 403:
                yield self.create_text_message("Permission denied. Check if the bot has access to member information.")
            else:
                yield self.create_text_message(f"Error getting member: {response.status_code} - {response.text}")
                
        except requests.RequestException as e:
            yield self.create_log_message(
                label="Network Error",
                data={"error": str(e)},
                status=InvokeMessage.LogMessage.LogStatus.ERROR
            )
            yield self.create_text_message(f"Network error: {str(e)}")