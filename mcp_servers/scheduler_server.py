"""
Meeting Scheduler MCP Server
Analyzes text for meetings and schedules them on Google Calendar
"""

import asyncio
import json
import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import dateutil.parser
import openai
import pickle

from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
from mcp.types import Resource, Tool, TextContent

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Configuration
SCOPES = ['https://www.googleapis.com/auth/calendar']

# Global state
openai_client = None
calendar_service = None
detected_meetings = {}

def init_openai():
    """Initialize OpenAI client"""
    global openai_client
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    openai_client = openai.OpenAI(api_key=api_key)

def authenticate_google_calendar():
    """Authenticate with Google Calendar"""
    global calendar_service
    creds = None
    
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                raise Exception("credentials.json not found")
            
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    calendar_service = build('calendar', 'v3', credentials=creds)

async def analyze_meetings_with_llm(text: str) -> List[Dict[str, Any]]:
    """Use LLM to detect meetings in text"""
    try:
        system_prompt = """You are a meeting detection AI. Analyze the text and extract meeting mentions.

For each meeting, provide:
1. The exact text mentioning the meeting
2. Date/time mentioned
3. Context and confidence score (0-100)

Return JSON array format:
[
  {
    "meeting_text": "let's schedule a meeting for tomorrow at 2pm",
    "date_time": "tomorrow at 2pm",
    "context": "project discussion",
    "confidence": 95
  }
]

Only include mentions with confidence >= 70."""

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Analyze: {text}"}
            ],
            temperature=0.1,
            max_tokens=1000
        )

        llm_response = response.choices[0].message.content.strip()
        
        # Parse JSON
        start_idx = llm_response.find('[')
        end_idx = llm_response.rfind(']') + 1
        if start_idx >= 0 and end_idx > start_idx:
            json_str = llm_response[start_idx:end_idx]
            meetings_data = json.loads(json_str)
        else:
            meetings_data = json.loads(llm_response)

        # Process meetings
        processed_meetings = []
        for meeting_data in meetings_data:
            try:
                meeting_datetime = parse_datetime_from_text(meeting_data.get('date_time', ''))
                
                if meeting_datetime:
                    processed_meeting = {
                        "original_text": meeting_data.get('meeting_text', ''),
                        "datetime": meeting_datetime,
                        "context": meeting_data.get('context', ''),
                        "confidence": meeting_data.get('confidence', 0),
                        "llm_detected": True
                    }
                    processed_meetings.append(processed_meeting)
                    
            except Exception as e:
                continue

        return processed_meetings

    except Exception as e:
        print(f"LLM analysis failed: {e}")
        return []

def parse_datetime_from_text(date_time_str: str) -> Optional[datetime]:
    """Parse date/time from text"""
    if not date_time_str:
        return None
        
    date_time_str = date_time_str.lower().strip()
    now = datetime.now()
    
    # Handle common patterns
    if 'tomorrow' in date_time_str:
        base_date = now + timedelta(days=1)
        time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)', date_time_str)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2)) if time_match.group(2) else 0
            period = time_match.group(3)
            
            if period == 'pm' and hour != 12:
                hour += 12
            elif period == 'am' and hour == 12:
                hour = 0
                
            return base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        else:
            return base_date.replace(hour=10, minute=0, second=0, microsecond=0)
    
    # Try dateutil parser as fallback
    try:
        return dateutil.parser.parse(date_time_str, default=now, fuzzy=True)
    except:
        return (now + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)

async def create_calendar_event(meeting: Dict[str, Any], title: str = "Meeting from Transcription") -> Dict[str, Any]:
    """Create Google Calendar event"""
    try:
        event = {
            'summary': title,
            'description': f"Auto-scheduled from transcription.\n\nOriginal: {meeting['original_text']}\nContext: {meeting['context']}",
            'start': {
                'dateTime': meeting['datetime'].isoformat(),
                'timeZone': 'America/New_York',
            },
            'end': {
                'dateTime': (meeting['datetime'] + timedelta(hours=1)).isoformat(),
                'timeZone': 'America/New_York',
            },
        }
        
        created_event = calendar_service.events().insert(calendarId='primary', body=event).execute()
        
        return {
            "event_id": created_event['id'],
            "event_link": created_event.get('htmlLink'),
            "title": title,
            "datetime": meeting['datetime']
        }
        
    except Exception as e:
        raise Exception(f"Calendar event creation failed: {str(e)}")

# Create MCP server
server = Server("meeting-scheduler")

@server.list_resources()
async def list_resources() -> List[Resource]:
    """List detected meetings"""
    resources = []
    for meeting_id, meeting_data in detected_meetings.items():
        resources.append(Resource(
            uri=f"meeting://{meeting_id}",
            name=f"Meeting: {meeting_data['datetime'].strftime('%Y-%m-%d %H:%M')}",
            description=f"Detected meeting: {meeting_data['original_text']}",
            mimeType="application/json"
        ))
    return resources

@server.read_resource()
async def read_resource(uri: str) -> str:
    """Read meeting resource"""
    if not uri.startswith("meeting://"):
        raise ValueError(f"Unknown resource URI: {uri}")
    
    meeting_id = uri.replace("meeting://", "")
    if meeting_id not in detected_meetings:
        raise ValueError(f"Meeting not found: {meeting_id}")
    
    meeting = detected_meetings[meeting_id]
    return json.dumps(meeting, default=str, indent=2)

@server.list_tools()
async def list_tools() -> List[Tool]:
    """List available tools"""
    return [
        Tool(
            name="analyze_transcription_for_meetings",
            description="Analyze text for meeting mentions using LLM",
            inputSchema={
                "type": "object",
                "properties": {
                    "transcription_text": {"type": "string"},
                    "transcription_id": {"type": "string"}
                },
                "required": ["transcription_text"]
            }
        ),
        Tool(
            name="schedule_detected_meetings",
            description="Schedule all detected meetings on calendar",
            inputSchema={
                "type": "object",
                "properties": {
                    "meeting_title_prefix": {"type": "string"}
                }
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls"""
    try:
        if name == "analyze_transcription_for_meetings":
            text = arguments.get("transcription_text")
            transcription_id = arguments.get("transcription_id", "unknown")
            
            if not text:
                return [TextContent(type="text", text="Error: Missing transcription_text")]
            
            meetings = await analyze_meetings_with_llm(text)
            
            # Store meetings
            for i, meeting in enumerate(meetings):
                meeting_id = f"{transcription_id}_meeting_{i+1}"
                meeting["id"] = meeting_id
                meeting["scheduled"] = False
                detected_meetings[meeting_id] = meeting
            
            if not meetings:
                return [TextContent(type="text", text="No meetings detected")]
            
            result = f"🤖 Detected {len(meetings)} meeting(s):\n\n"
            for meeting in meetings:
                confidence_emoji = "🎯" if meeting.get("confidence", 0) >= 90 else "✅"
                result += f"{confidence_emoji} {meeting['original_text']}\n"
                result += f"   📅 {meeting['datetime'].strftime('%Y-%m-%d %H:%M')}\n"
                result += f"   🎯 Confidence: {meeting.get('confidence', 0)}%\n\n"
            
            return [TextContent(type="text", text=result)]
            
        elif name == "schedule_detected_meetings":
            title_prefix = arguments.get("meeting_title_prefix", "Meeting from Transcription")
            
            if not detected_meetings:
                return [TextContent(type="text", text="No meetings to schedule")]
            
            scheduled_count = 0
            results = []
            
            for meeting_id, meeting in detected_meetings.items():
                if not meeting.get("scheduled", False):
                    try:
                        event_result = await create_calendar_event(meeting, title_prefix)
                        meeting["scheduled"] = True
                        meeting["calendar_event"] = event_result
                        scheduled_count += 1
                        results.append(f"✅ Scheduled: {event_result['title']}")
                    except Exception as e:
                        results.append(f"❌ Failed: {meeting['original_text']} - {str(e)}")
            
            result_text = f"Scheduled {scheduled_count} meeting(s):\n\n" + "\n".join(results)
            return [TextContent(type="text", text=result_text)]
        
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
            
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]

async def main():
    """Main server function"""
    try:
        init_openai()
        print("✅ OpenAI client initialized")
    except Exception as e:
        print(f"❌ OpenAI initialization failed: {e}")
        return
    
    try:
        authenticate_google_calendar()
        print("✅ Google Calendar authenticated")
    except Exception as e:
        print(f"❌ Google Calendar authentication failed: {e}")
        return
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="meeting-scheduler",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                )
            )
        )

if __name__ == "__main__":
    print("📅 Starting Meeting Scheduler MCP Server...")
    asyncio.run(main())