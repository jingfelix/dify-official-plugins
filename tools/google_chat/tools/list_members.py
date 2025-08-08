from collections.abc import Generator
from typing import Any

import requests

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from dify_plugin.entities.invoke_message import InvokeMessage


class ListMembersTool(Tool):
    """
    Tool to list members in a Google Chat space
    """
    
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        """
        List members in a Google Chat space
        """
        # Extract parameters
        space_name = tool_parameters.get("space_name")
        page_size = tool_parameters.get("page_size", 20)
        filter_str = tool_parameters.get("filter", "")
        show_groups = tool_parameters.get("show_groups", False)
        show_invited = tool_parameters.get("show_invited", False)
        
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
        url = f"https://chat.googleapis.com/v1/{space_name}/members"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        params = {
            "pageSize": min(page_size, 100),  # Max 100 per page
            "showGroups": str(show_groups).lower(),
            "showInvited": str(show_invited).lower()
        }
        
        if filter_str:
            params["filter"] = filter_str
        
        try:
            all_members = []
            next_page_token = None
            page_count = 0
            max_pages = 5  # Limit to prevent excessive API calls
            
            while page_count < max_pages:
                if next_page_token:
                    params["pageToken"] = next_page_token
                
                response = requests.get(url, headers=headers, params=params, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    members = data.get("memberships", [])
                    all_members.extend(members)
                    
                    next_page_token = data.get("nextPageToken")
                    page_count += 1
                    
                    if not next_page_token:
                        break
                        
                elif response.status_code == 403:
                    yield self.create_text_message("Permission denied. Check if the bot has access to list members.")
                    return
                else:
                    yield self.create_text_message(f"Error listing members: {response.status_code} - {response.text}")
                    return
            
            # Process and format members
            member_list = []
            for membership in all_members:
                member_info = {
                    "name": membership.get("name"),
                    "state": membership.get("state"),
                    "role": membership.get("role"),
                    "createTime": membership.get("createTime")
                }
                
                # Extract member details
                member = membership.get("member", {})
                if member.get("type") == "HUMAN":
                    member_info["type"] = "HUMAN"
                    member_info["displayName"] = member.get("displayName", "Unknown")
                    member_info["email"] = member.get("email")
                elif member.get("type") == "BOT":
                    member_info["type"] = "BOT"
                    member_info["displayName"] = member.get("displayName", "Bot")
                else:
                    member_info["type"] = member.get("type", "UNKNOWN")
                    member_info["displayName"] = "Unknown"
                
                member_list.append(member_info)
            
            # Return results
            result = {
                "total": len(member_list),
                "members": member_list,
                "hasMore": next_page_token is not None
            }
            
            yield self.create_json_message(result)
            
            # Create human-readable summary
            summary_lines = [f"Found {len(member_list)} members in the space:"]
            for member in member_list[:10]:  # Show first 10 members
                display_name = member.get("displayName", "Unknown")
                member_type = member.get("type", "UNKNOWN")
                role = member.get("role", "MEMBER")
                state = member.get("state", "UNKNOWN")
                summary_lines.append(f"• {display_name} ({member_type}) - Role: {role}, State: {state}")
            
            if len(member_list) > 10:
                summary_lines.append(f"... and {len(member_list) - 10} more members")
            
            yield self.create_text_message("\n".join(summary_lines))
            
        except requests.RequestException as e:
            yield self.create_log_message(
                label="Network Error",
                data={"error": str(e)},
                status=InvokeMessage.LogMessage.LogStatus.ERROR
            )
            yield self.create_text_message(f"Network error: {str(e)}")