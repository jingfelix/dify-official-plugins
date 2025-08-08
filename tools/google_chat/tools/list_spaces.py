from collections.abc import Generator
from typing import Any

import requests

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from dify_plugin.entities.invoke_message import InvokeMessage


class ListSpacesTool(Tool):
    """
    Tool to list Google Chat spaces accessible to the authenticated user
    """
    
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        """
        List Google Chat spaces
        """
        # Extract parameters
        page_size = tool_parameters.get("page_size", 20)
        filter_str = tool_parameters.get("filter", "")
        
        # Get credentials
        access_token = self.runtime.credentials.get("access_token")
        if not access_token:
            yield self.create_text_message("Access token not found. Please authenticate first.")
            return
        
        # Build API request
        url = "https://chat.googleapis.com/v1/spaces"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        params = {
            "pageSize": min(page_size, 100)  # Max 100 per page
        }
        
        if filter_str:
            params["filter"] = filter_str
        
        try:
            all_spaces = []
            next_page_token = None
            page_count = 0
            max_pages = 5  # Limit to prevent excessive API calls
            
            while page_count < max_pages:
                if next_page_token:
                    params["pageToken"] = next_page_token
                
                response = requests.get(url, headers=headers, params=params, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    spaces = data.get("spaces", [])
                    all_spaces.extend(spaces)
                    
                    next_page_token = data.get("nextPageToken")
                    page_count += 1
                    
                    # Stop if we have enough spaces or no more pages
                    if not next_page_token or len(all_spaces) >= page_size:
                        break
                        
                elif response.status_code == 403:
                    yield self.create_text_message("Permission denied. Check if the bot has the required OAuth scopes.")
                    return
                else:
                    yield self.create_text_message(f"Error listing spaces: {response.status_code} - {response.text}")
                    return
            
            # Process and format spaces
            space_list = []
            for space in all_spaces[:page_size]:
                space_info = {
                    "name": space.get("name"),
                    "displayName": space.get("displayName", ""),
                    "spaceType": space.get("spaceType"),
                    "singleUserBotDm": space.get("singleUserBotDm", False),
                    "threaded": space.get("threaded", False),
                    "spaceDetails": space.get("spaceDetails", {}),
                    "spaceHistoryState": space.get("spaceHistoryState"),
                    "createTime": space.get("createTime"),
                    "adminInstalled": space.get("adminInstalled", False)
                }
                
                # Add description if available
                if space_info["spaceDetails"].get("description"):
                    space_info["description"] = space_info["spaceDetails"]["description"]
                
                space_list.append(space_info)
            
            # Return results
            result = {
                "total": len(space_list),
                "spaces": space_list,
                "hasMore": next_page_token is not None
            }
            
            yield self.create_json_message(result)
            
            # Create human-readable summary
            summary_lines = [f"Found {len(space_list)} spaces:"]
            
            # Group spaces by type
            rooms = []
            dms = []
            group_dms = []
            
            for space in space_list:
                space_id = space["name"].split("/")[-1] if space.get("name") else "unknown"
                display_name = space.get("displayName", "Unnamed Space")
                space_type = space.get("spaceType", "UNKNOWN")
                
                info = f"• {display_name} ({space_id})"
                if space.get("description"):
                    info += f" - {space['description'][:50]}..."
                
                if space_type == "ROOM":
                    rooms.append(info)
                elif space.get("singleUserBotDm"):
                    dms.append(info)
                elif space_type == "DIRECT_MESSAGE":
                    group_dms.append(info)
                else:
                    rooms.append(info)
            
            if rooms:
                summary_lines.append("\n🏠 Rooms:")
                summary_lines.extend(rooms[:5])
                if len(rooms) > 5:
                    summary_lines.append(f"  ... and {len(rooms) - 5} more rooms")
            
            if dms:
                summary_lines.append("\n💬 Direct Messages:")
                summary_lines.extend(dms[:5])
                if len(dms) > 5:
                    summary_lines.append(f"  ... and {len(dms) - 5} more DMs")
            
            if group_dms:
                summary_lines.append("\n👥 Group DMs:")
                summary_lines.extend(group_dms[:5])
                if len(group_dms) > 5:
                    summary_lines.append(f"  ... and {len(group_dms) - 5} more group DMs")
            
            yield self.create_text_message("\n".join(summary_lines))
            
        except requests.RequestException as e:
            yield self.create_log_message(
                label="Network Error",
                data={"error": str(e)},
                status=InvokeMessage.LogMessage.LogStatus.ERROR
            )
            yield self.create_text_message(f"Network error: {str(e)}")