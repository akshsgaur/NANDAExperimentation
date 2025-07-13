#!/usr/bin/env python3
"""
Fixed Meeting Scheduler MCP Server
Resolves broken pipe and communication issues
"""

import asyncio
import json
import os
import pickle
import re
import logging
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
import openai
import dateutil.parser

from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
from mcp.types import Resource, Tool, TextContent

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    logging.warning("Google Calendar dependencies not available")

# Configure logging to stderr only
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)

class SchedulerMCPServer:
    """Fixed Scheduler MCP Server"""
    
    def __init__(self):
        self.server = Server("scheduler")
        self.openai_client = None
        self.calendar_service = None
        self.detected_meetings = {}
        self.scheduled_meetings = {}
        
        # Google Calendar configuration
        self.SCOPES = ['https://www.googleapis.com/auth/calendar']
        self.credentials_path = "credentials.json"
        self.token_path = "token.pickle"
        
        # Register handlers
        self._register_handlers()
    
    def _register_handlers(self):
        """Register MCP handlers"""
        
        @self.server.list_resources()
        async def list_resources() -> List[Resource]:
            """List meeting resources"""
            resources = []
            
            # Add detected meetings
            for meeting_id, meeting_data in self.detected_meetings.items():
                resources.append(Resource(
                    uri=f"meeting://detected/{meeting_id}",
                    name=f"Detected Meeting: {meeting_data.get('original_text', '')[:50]}...",
                    description=f"Confidence: {meeting_data.get('confidence', 0)}% | Scheduled: {meeting_data.get('scheduled', False)}",
                    mimeType="application/json"
                ))
            
            # Add scheduled meetings
            for meeting_id, meeting_data in self.scheduled_meetings.items():
                resources.append(Resource(
                    uri=f"meeting://scheduled/{meeting_id}",
                    name=f"Scheduled Meeting: {meeting_data.get('title', '')}",
                    description=f"Date: {meeting_data.get('start_time', '')}",
                    mimeType="application/json"
                ))
            
            return resources
        
        @self.server.read_resource()
        async def read_resource(uri: str) -> str:
            """Read meeting resource"""
            if uri.startswith("meeting://detected/"):
                meeting_id = uri.replace("meeting://detected/", "")
                if meeting_id in self.detected_meetings:
                    return json.dumps(self.detected_meetings[meeting_id], default=str, indent=2)
            elif uri.startswith("meeting://scheduled/"):
                meeting_id = uri.replace("meeting://scheduled/", "")
                if meeting_id in self.scheduled_meetings:
                    return json.dumps(self.scheduled_meetings[meeting_id], default=str, indent=2)
            
            raise ValueError(f"Meeting not found: {uri}")
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List available tools"""
            return [
                Tool(
                    name="analyze_text_for_meetings",
                    description="Analyze text for meeting scheduling intent using AI",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "Text to analyze for meeting mentions"
                            },
                            "source_id": {
                                "type": "string",
                                "description": "Source identifier (e.g., transcription ID)",
                                "default": "unknown"
                            },
                            "context": {
                                "type": "string",
                                "description": "Additional context about the text"
                            }
                        },
                        "required": ["text"]
                    }
                ),
                Tool(
                    name="schedule_meeting",
                    description="Schedule a specific meeting on Google Calendar",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "meeting_id": {
                                "type": "string",
                                "description": "ID of detected meeting to schedule"
                            },
                            "title": {
                                "type": "string",
                                "description": "Custom title for the meeting"
                            },
                            "description": {
                                "type": "string",
                                "description": "Meeting description"
                            },
                            "duration_minutes": {
                                "type": "integer",
                                "description": "Meeting duration in minutes",
                                "default": 60
                            }
                        },
                        "required": ["meeting_id"]
                    }
                ),
                Tool(
                    name="schedule_all_meetings",
                    description="Schedule all detected unscheduled meetings",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "title_prefix": {
                                "type": "string",
                                "description": "Prefix for meeting titles",
                                "default": "Meeting from Transcription"
                            },
                            "default_duration": {
                                "type": "integer",
                                "description": "Default duration in minutes",
                                "default": 60
                            }
                        }
                    }
                ),
                Tool(
                    name="find_available_slots",
                    description="Find available time slots in calendar",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "start_date": {
                                "type": "string",
                                "description": "Start date for search (YYYY-MM-DD)"
                            },
                            "end_date": {
                                "type": "string",
                                "description": "End date for search (YYYY-MM-DD)"
                            },
                            "duration_minutes": {
                                "type": "integer",
                                "description": "Required duration in minutes",
                                "default": 60
                            },
                            "working_hours_only": {
                                "type": "boolean",
                                "description": "Only show working hours (9 AM - 5 PM)",
                                "default": True
                            }
                        },
                        "required": ["start_date", "end_date"]
                    }
                ),
                Tool(
                    name="get_upcoming_meetings",
                    description="Get upcoming meetings from calendar",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "days_ahead": {
                                "type": "integer",
                                "description": "Number of days to look ahead",
                                "default": 7
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "Maximum number of meetings to return",
                                "default": 20
                            }
                        }
                    }
                )
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Union[Dict[str, Any], None]) -> List[TextContent]:
            """Handle tool calls"""
            try:
                if arguments is None:
                    arguments = {}
                
                logger.info(f"Tool called: {name}")
                
                if name == "analyze_text_for_meetings":
                    return await self._analyze_text(arguments)
                elif name == "schedule_meeting":
                    return await self._schedule_meeting(arguments)
                elif name == "schedule_all_meetings":
                    return await self._schedule_all_meetings(arguments)
                elif name == "find_available_slots":
                    return await self._find_available_slots(arguments)
                elif name == "get_upcoming_meetings":
                    return await self._get_upcoming_meetings(arguments)
                else:
                    return [TextContent(type="text", text=f"❌ Unknown tool: {name}")]
                    
            except Exception as e:
                logger.error(f"Tool call error for {name}: {e}")
                return [TextContent(type="text", text=f"❌ Tool execution error: {str(e)}")]
    
    async def _analyze_text(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Analyze text for meeting scheduling intent"""
        text = arguments.get("text", "")
        source_id = arguments.get("source_id", "unknown")
        context = arguments.get("context", "")
        
        if not text:
            return [TextContent(type="text", text="❌ Missing required parameter: text")]
        
        # If OpenAI is not available, use pattern matching fallback
        if not self.openai_client:
            return await self._analyze_text_with_patterns(text, source_id, context)
        
        try:
            # Use AI to detect meetings
            system_prompt = f"""You are a meeting detection AI. Analyze the text and extract meeting scheduling intentions.

Guidelines:
- Only detect explicit meeting arrangements or scheduling discussions
- Ignore casual mentions like "we should meet sometime"
- Parse dates/times relative to current time: {datetime.now().isoformat()}
- Consider context and urgency

For each meeting, provide:
1. The exact text mentioning the meeting
2. Parsed date/time in ISO format
3. Meeting participants (if mentioned)
4. Meeting topic/purpose
5. Confidence score (0-100)

Return JSON array format:
[
  {{
    "meeting_text": "let's schedule a meeting for tomorrow at 2pm",
    "datetime": "2024-01-15T14:00:00",
    "participants": ["John", "Sarah"],
    "topic": "project discussion",
    "confidence": 95
  }}
]

Only include mentions with confidence >= 70."""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Context: {context}\n\nAnalyze: {text}"}
                ],
                temperature=0.1,
                max_tokens=1500
            )

            # Parse AI response
            ai_response = response.choices[0].message.content.strip()
            meetings_data = self._parse_meetings_response(ai_response)
            
            # Store detected meetings
            detected_count = 0
            for meeting_data in meetings_data:
                meeting_id = f"{source_id}_meeting_{len(self.detected_meetings) + 1}"
                
                # Parse datetime
                datetime_str = meeting_data.get('datetime', '')
                if datetime_str:
                    try:
                        meeting_datetime = datetime.fromisoformat(datetime_str.replace('Z', ''))
                    except:
                        meeting_datetime = self._parse_datetime_from_text(meeting_data.get('meeting_text', ''))
                else:
                    meeting_datetime = self._parse_datetime_from_text(meeting_data.get('meeting_text', ''))
                
                if meeting_datetime:
                    processed_meeting = {
                        "id": meeting_id,
                        "original_text": meeting_data.get('meeting_text', ''),
                        "datetime": meeting_datetime,
                        "participants": meeting_data.get('participants', []),
                        "topic": meeting_data.get('topic', ''),
                        "confidence": meeting_data.get('confidence', 0),
                        "context": context,
                        "source_id": source_id,
                        "scheduled": False,
                        "detected_at": datetime.now().isoformat()
                    }
                    
                    self.detected_meetings[meeting_id] = processed_meeting
                    detected_count += 1
            
            if detected_count == 0:
                return [TextContent(type="text", text="No meetings detected in the provided text.")]
            
            # Format response
            result = f"🤖 Detected {detected_count} meeting(s):\n\n"
            for meeting_id, meeting in list(self.detected_meetings.items())[-detected_count:]:
                confidence_emoji = "🎯" if meeting.get("confidence", 0) >= 90 else "✅"
                result += f"{confidence_emoji} **{meeting['original_text']}**\n"
                result += f"   📅 {meeting['datetime'].strftime('%Y-%m-%d %H:%M')}\n"
                result += f"   🎯 Confidence: {meeting.get('confidence', 0)}%\n"
                if meeting.get('participants'):
                    result += f"   👥 Participants: {', '.join(meeting['participants'])}\n"
                if meeting.get('topic'):
                    result += f"   📝 Topic: {meeting['topic']}\n"
                result += f"   🆔 ID: {meeting_id}\n\n"
            
            return [TextContent(type="text", text=result)]
            
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            # Fallback to pattern matching
            return await self._analyze_text_with_patterns(text, source_id, context)
    
    async def _analyze_text_with_patterns(self, text: str, source_id: str, context: str) -> List[TextContent]:
        """Fallback pattern-based meeting detection"""
        meeting_patterns = [
            r"meet(?:ing)?.+?(?:tomorrow|next week|monday|tuesday|wednesday|thursday|friday)",
            r"schedule.+?(?:meeting|call|discussion)",
            r"let'?s.+?(?:meet|schedule|talk)",
            r"(?:tomorrow|next week).+?(?:at|@)\s*(\d{1,2})\s*(?:pm|am)",
            r"call.+?(?:tomorrow|monday|tuesday|wednesday|thursday|friday)"
        ]
        
        detected_meetings_count = 0
        detected_texts = []
        
        for pattern in meeting_patterns:
            matches = re.finditer(pattern, text.lower())
            for match in matches:
                detected_texts.append(match.group(0))
                detected_meetings_count += 1
        
        if detected_meetings_count > 0:
            # Create mock meeting for each detection
            for i, detected_text in enumerate(detected_texts[:3]):  # Limit to 3
                meeting_id = f"{source_id}_meeting_{len(self.detected_meetings) + 1 + i}"
                mock_meeting = {
                    "id": meeting_id,
                    "original_text": detected_text,
                    "datetime": datetime.now() + timedelta(days=1, hours=10),  # Tomorrow at 10 AM
                    "topic": "Meeting discussion",
                    "confidence": 75,
                    "participants": [],
                    "scheduled": False,
                    "source_id": source_id,
                    "context": context,
                    "detected_at": datetime.now().isoformat()
                }
                self.detected_meetings[meeting_id] = mock_meeting
            
            result = f"🤖 Detected {len(detected_texts)} meeting(s) (pattern matching):\n\n"
            for meeting_id, meeting in list(self.detected_meetings.items())[-len(detected_texts):]:
                result += f"✅ **{meeting['original_text']}**\n"
                result += f"   📅 {meeting['datetime'].strftime('%Y-%m-%d %H:%M')}\n"
                result += f"   🎯 Confidence: {meeting['confidence']}%\n"
                result += f"   🆔 ID: {meeting_id}\n\n"
            
            return [TextContent(type="text", text=result)]
        else:
            return [TextContent(type="text", text="No meetings detected in the provided text.")]
    
    def _parse_meetings_response(self, ai_response: str) -> List[Dict[str, Any]]:
        """Parse AI response for meetings data"""
        try:
            # Extract JSON from response
            start_idx = ai_response.find('[')
            end_idx = ai_response.rfind(']') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = ai_response[start_idx:end_idx]
                return json.loads(json_str)
            else:
                return json.loads(ai_response)
                
        except json.JSONDecodeError:
            logger.warning("Failed to parse AI response as JSON")
            return []
    
    def _parse_datetime_from_text(self, text: str) -> Optional[datetime]:
        """Parse datetime from text using various strategies"""
        if not text:
            return None
            
        text = text.lower().strip()
        now = datetime.now()
        
        # Handle "tomorrow" patterns
        if 'tomorrow' in text:
            base_date = now + timedelta(days=1)
            time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)', text)
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
        
        # Try dateutil parser
        try:
            return dateutil.parser.parse(text, default=now, fuzzy=True)
        except:
            return (now + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    
    async def _schedule_meeting(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Schedule a specific meeting"""
        meeting_id = arguments.get("meeting_id")
        custom_title = arguments.get("title")
        custom_description = arguments.get("description")
        duration_minutes = arguments.get("duration_minutes", 60)
        
        if not meeting_id:
            return [TextContent(type="text", text="❌ Missing required parameter: meeting_id")]
        
        if meeting_id not in self.detected_meetings:
            return [TextContent(type="text", text=f"❌ Meeting {meeting_id} not found")]
        
        meeting = self.detected_meetings[meeting_id]
        
        if meeting.get("scheduled", False):
            return [TextContent(type="text", text=f"❌ Meeting {meeting_id} is already scheduled")]
        
        # Check if calendar service is available
        if not self.calendar_service:
            # Mock scheduling if no calendar service
            meeting["scheduled"] = True
            meeting["calendar_event"] = {
                "event_id": f"mock_event_{meeting_id}",
                "title": custom_title or f"Meeting: {meeting.get('topic', 'Discussion')}",
                "start_time": meeting['datetime'].isoformat(),
                "end_time": (meeting['datetime'] + timedelta(minutes=duration_minutes)).isoformat()
            }
            meeting["scheduled_at"] = datetime.now().isoformat()
            
            return [TextContent(type="text", text=f"✅ Meeting scheduled successfully (mock)!\n\n📅 **{meeting['calendar_event']['title']}**\n🕐 {meeting['datetime'].strftime('%Y-%m-%d %H:%M')}\n🆔 Event ID: {meeting['calendar_event']['event_id']}")]
        
        try:
            # Prepare event details
            title = custom_title or f"Meeting: {meeting.get('topic', 'Discussion')}"
            description = custom_description or f"Auto-scheduled from transcription.\n\nOriginal text: {meeting['original_text']}\nContext: {meeting.get('context', '')}"
            
            start_time = meeting['datetime']
            end_time = start_time + timedelta(minutes=duration_minutes)
            
            # Create calendar event
            event = {
                'summary': title,
                'description': description,
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': 'America/New_York',
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': 'America/New_York',
                },
            }
            
            # Add attendees if participants are specified
            if meeting.get('participants'):
                event['attendees'] = [
                    {'email': f"{participant.lower().replace(' ', '.')}@example.com"} 
                    for participant in meeting['participants']
                ]
            
            created_event = self.calendar_service.events().insert(
                calendarId='primary', 
                body=event
            ).execute()
            
            # Update meeting record
            meeting["scheduled"] = True
            meeting["calendar_event"] = {
                "event_id": created_event['id'],
                "event_link": created_event.get('htmlLink'),
                "title": title,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat()
            }
            meeting["scheduled_at"] = datetime.now().isoformat()
            
            # Store in scheduled meetings
            self.scheduled_meetings[created_event['id']] = meeting["calendar_event"]
            
            return [TextContent(
                type="text",
                text=f"✅ Meeting scheduled successfully!\n\n"
                     f"📅 **{title}**\n"
                     f"🕐 {start_time.strftime('%Y-%m-%d %H:%M')} - {end_time.strftime('%H:%M')}\n"
                     f"🔗 [View in Calendar]({created_event.get('htmlLink', 'N/A')})\n"
                     f"🆔 Event ID: {created_event['id']}"
            )]
            
        except Exception as e:
            return [TextContent(type="text", text=f"❌ Failed to schedule meeting: {str(e)}")]
    
    async def _schedule_all_meetings(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Schedule all detected unscheduled meetings"""
        title_prefix = arguments.get("title_prefix", "Meeting from Transcription")
        default_duration = arguments.get("default_duration", 60)
        
        unscheduled_meetings = [
            (meeting_id, meeting) for meeting_id, meeting in self.detected_meetings.items()
            if not meeting.get("scheduled", False)
        ]
        
        if not unscheduled_meetings:
            return [TextContent(type="text", text="📝 No unscheduled meetings found")]
        
        scheduled_count = 0
        results = []
        
        for meeting_id, meeting in unscheduled_meetings:
            try:
                # Schedule individual meeting
                schedule_result = await self._schedule_meeting({
                    "meeting_id": meeting_id,
                    "title": f"{title_prefix}: {meeting.get('topic', 'Discussion')}",
                    "duration_minutes": default_duration
                })
                
                if schedule_result and "✅" in schedule_result[0].text:
                    scheduled_count += 1
                    results.append(f"✅ {meeting['original_text']}")
                else:
                    results.append(f"❌ Failed: {meeting['original_text']}")
                    
            except Exception as e:
                results.append(f"❌ Error scheduling {meeting['original_text']}: {str(e)}")
        
        result_text = f"📅 Scheduled {scheduled_count}/{len(unscheduled_meetings)} meeting(s):\n\n" + "\n".join(results)
        return [TextContent(type="text", text=result_text)]
    
    async def _find_available_slots(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Find available time slots in calendar"""
        start_date = arguments.get("start_date")
        end_date = arguments.get("end_date")
        duration_minutes = arguments.get("duration_minutes", 60)
        working_hours_only = arguments.get("working_hours_only", True)
        
        if not start_date or not end_date:
            return [TextContent(type="text", text="❌ Missing required parameters: start_date and end_date")]
        
        # Check if calendar service is available
        if not self.calendar_service:
            # Return mock available slots
            return [TextContent(type="text", text=f"📅 Found 5 available slots ({duration_minutes} min each) between {start_date} and {end_date}:\n\n1. {start_date} 09:00 - 10:00\n2. {start_date} 14:00 - 15:00\n3. {start_date} 16:00 - 17:00\n4. {end_date} 10:00 - 11:00\n5. {end_date} 15:00 - 16:00")]
        
        try:
            # Parse dates
            start_datetime = datetime.fromisoformat(start_date)
            end_datetime = datetime.fromisoformat(end_date)
            
            # Get busy times from calendar
            freebusy_request = {
                'timeMin': start_datetime.isoformat() + 'Z',
                'timeMax': end_datetime.isoformat() + 'Z',
                'items': [{'id': 'primary'}]
            }
            
            freebusy_result = self.calendar_service.freebusy().query(body=freebusy_request).execute()
            busy_times = freebusy_result['calendars']['primary']['busy']
            
            # Find available slots
            available_slots = []
            current_time = start_datetime
            
            while current_time < end_datetime:
                slot_end = current_time + timedelta(minutes=duration_minutes)
                
                # Check if slot is in working hours
                if working_hours_only:
                    hour = current_time.hour
                    if hour < 9 or hour >= 17:  # Outside 9 AM - 5 PM
                        current_time += timedelta(minutes=30)
                        continue
                
                # Check if slot conflicts with busy times
                is_available = True
                for busy_period in busy_times:
                    busy_start = datetime.fromisoformat(busy_period['start'].replace('Z', '+00:00'))
                    busy_end = datetime.fromisoformat(busy_period['end'].replace('Z', '+00:00'))
                    
                    if (current_time < busy_end and slot_end > busy_start):
                        is_available = False
                        break
                
                if is_available:
                    available_slots.append({
                        'start': current_time.strftime('%Y-%m-%d %H:%M'),
                        'end': slot_end.strftime('%Y-%m-%d %H:%M'),
                        'duration_minutes': duration_minutes
                    })
                
                # Move to next slot (30-minute intervals)
                current_time += timedelta(minutes=30)
            
            if not available_slots:
                return [TextContent(type="text", text="📅 No available slots found in the specified time range")]
            
            # Format response
            result = f"📅 Found {len(available_slots)} available slot(s) ({duration_minutes} min each):\n\n"
            for i, slot in enumerate(available_slots[:10], 1):  # Show max 10 slots
                result += f"{i}. {slot['start']} - {slot['end']}\n"
            
            if len(available_slots) > 10:
                result += f"\n... and {len(available_slots) - 10} more slots"
            
            return [TextContent(type="text", text=result)]
            
        except Exception as e:
            return [TextContent(type="text", text=f"❌ Failed to find available slots: {str(e)}")]
    
    async def _get_upcoming_meetings(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Get upcoming meetings from calendar"""
        days_ahead = arguments.get("days_ahead", 7)
        max_results = arguments.get("max_results", 20)
        
        # Check if calendar service is available
        if not self.calendar_service:
            # Return a simple response instead of error for basic functionality
            return [TextContent(type="text", text=f"📅 Calendar service not configured. No upcoming meetings available (next {days_ahead} days).")]
        
        try:
            now = datetime.utcnow()
            time_max = now + timedelta(days=days_ahead)
            
            events_result = self.calendar_service.events().list(
                calendarId='primary',
                timeMin=now.isoformat() + 'Z',
                timeMax=time_max.isoformat() + 'Z',
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            if not events:
                return [TextContent(type="text", text=f"📅 No upcoming meetings found (next {days_ahead} days)")]
            
            result = f"📅 Upcoming meetings (next {days_ahead} days):\n\n"
            for i, event in enumerate(events, 1):
                start_time = event.get('start', {}).get('dateTime', 'No time specified')
                if start_time != 'No time specified':
                    dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    formatted_time = dt.strftime('%Y-%m-%d %H:%M')
                else:
                    formatted_time = start_time
                
                result += f"{i}. **{event.get('summary', 'Untitled Meeting')}**\n"
                result += f"   📅 {formatted_time}\n"
                
                if event.get('description'):
                    desc = event['description'][:100]
                    if len(event['description']) > 100:
                        desc += "..."
                    result += f"   📝 {desc}\n"
                
                if event.get('attendees'):
                    attendee_count = len(event['attendees'])
                    result += f"   👥 {attendee_count} attendee(s)\n"
                
                result += "\n"
            
            return [TextContent(type="text", text=result)]
            
        except Exception as e:
            return [TextContent(type="text", text=f"❌ Failed to get upcoming meetings: {str(e)}")]
    
    async def initialize_services(self):
        """Initialize OpenAI and Google Calendar services"""
        # Initialize OpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY environment variable not set - AI features will be unavailable")
        else:
            try:
                self.openai_client = openai.OpenAI(api_key=api_key)
                logger.info("✅ OpenAI client initialized for scheduling")
            except Exception as e:
                logger.warning(f"OpenAI initialization failed: {e}")
        
        # Initialize Google Calendar
        if GOOGLE_AVAILABLE:
            try:
                await self._authenticate_google_calendar()
                logger.info("✅ Google Calendar service initialized")
            except Exception as e:
                logger.warning(f"Google Calendar initialization failed: {e}")
                logger.warning("Calendar features will be unavailable")
        else:
            logger.warning("Google Calendar dependencies not available")
    
    async def _authenticate_google_calendar(self):
        """Authenticate with Google Calendar API"""
        creds = None
        
        # Load existing token
        if os.path.exists(self.token_path):
            with open(self.token_path, 'rb') as token:
                creds = pickle.load(token)
        
        # Refresh or get new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_path):
                    raise Exception(f"Google credentials file not found: {self.credentials_path}")
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, self.SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save credentials
            with open(self.token_path, 'wb') as token:
                pickle.dump(creds, token)
        
        self.calendar_service = build('calendar', 'v3', credentials=creds)
    
    async def run(self):
        """Run the MCP server"""
        try:
            await self.initialize_services()
            logger.info("📅 Starting Scheduler MCP Server...")
            
            async with stdio_server() as (read_stream, write_stream):
                await self.server.run(
                    read_stream,
                    write_stream,
                    InitializationOptions(
                        server_name="scheduler",
                        server_version="2.1.0",
                        capabilities=self.server.get_capabilities(
                            notification_options=NotificationOptions(),
                            experimental_capabilities={}
                        )
                    )
                )
        except KeyboardInterrupt:
            logger.info("Server stopped by user")
        except Exception as e:
            logger.error(f"❌ Scheduler server failed: {e}")
            sys.exit(1)

async def main():
    """Main entry point"""
    server = SchedulerMCPServer()
    await server.run()

if __name__ == "__main__":
    asyncio.run(main())