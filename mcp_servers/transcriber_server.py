"""
Meeting Transcriber MCP Server
Transcribes audio files using OpenAI Whisper API
"""

import asyncio
import json
import os
import base64
import tempfile
from pathlib import Path
from typing import Any, Dict, List
import openai

from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
from mcp.types import Resource, Tool, TextContent

# Global state
openai_client = None
transcriptions = {}

def init_openai():
    """Initialize OpenAI client"""
    global openai_client
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    openai_client = openai.OpenAI(api_key=api_key)

async def transcribe_audio(audio_data: bytes, filename: str) -> Dict[str, Any]:
    """Transcribe audio using OpenAI Whisper"""
    try:
        # Create temporary file
        with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as temp_file:
            temp_file.write(audio_data)
            temp_path = temp_file.name

        # Transcribe
        with open(temp_path, "rb") as audio_file:
            transcript = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json"
            )

        # Clean up
        os.unlink(temp_path)

        # Store result
        transcription_id = f"trans_{len(transcriptions) + 1}"
        result = {
            "id": transcription_id,
            "filename": filename,
            "text": transcript.text,
            "duration": getattr(transcript, 'duration', None),
            "language": getattr(transcript, 'language', None)
        }
        
        transcriptions[transcription_id] = result
        return result

    except Exception as e:
        raise Exception(f"Transcription failed: {str(e)}")

# Create MCP server
server = Server("meeting-transcriber")

@server.list_resources()
async def list_resources() -> List[Resource]:
    """List available transcription resources"""
    resources = []
    for trans_id, trans_data in transcriptions.items():
        resources.append(Resource(
            uri=f"transcription://{trans_id}",
            name=f"Transcription: {trans_data['filename']}",
            description=f"Audio transcription of {trans_data['filename']}",
            mimeType="text/plain"
        ))
    return resources

@server.read_resource()
async def read_resource(uri: str) -> str:
    """Read a transcription resource"""
    if not uri.startswith("transcription://"):
        raise ValueError(f"Unknown resource URI: {uri}")
    
    trans_id = uri.replace("transcription://", "")
    if trans_id not in transcriptions:
        raise ValueError(f"Transcription not found: {trans_id}")
    
    transcription = transcriptions[trans_id]
    return json.dumps(transcription, indent=2)

@server.list_tools()
async def list_tools() -> List[Tool]:
    """List available tools"""
    return [
        Tool(
            name="transcribe_audio_file",
            description="Transcribe an audio file using OpenAI Whisper",
            inputSchema={
                "type": "object",
                "properties": {
                    "audio_base64": {
                        "type": "string",
                        "description": "Base64 encoded audio file"
                    },
                    "filename": {
                        "type": "string",
                        "description": "Original filename"
                    }
                },
                "required": ["audio_base64", "filename"]
            }
        ),
        Tool(
            name="get_transcription",
            description="Get transcription by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "transcription_id": {"type": "string"}
                },
                "required": ["transcription_id"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls"""
    try:
        if name == "transcribe_audio_file":
            audio_base64 = arguments.get("audio_base64")
            filename = arguments.get("filename")
            
            if not audio_base64 or not filename:
                return [TextContent(type="text", text="Error: Missing audio_base64 or filename")]
            
            # Decode audio
            audio_data = base64.b64decode(audio_base64)
            
            # Transcribe
            result = await transcribe_audio(audio_data, filename)
            
            return [TextContent(
                type="text",
                text=f"Transcription completed!\n\nID: {result['id']}\nText: {result['text']}"
            )]
            
        elif name == "get_transcription":
            trans_id = arguments.get("transcription_id")
            if trans_id not in transcriptions:
                return [TextContent(type="text", text="Transcription not found")]
            
            transcription = transcriptions[trans_id]
            return [TextContent(type="text", text=json.dumps(transcription, indent=2))]
        
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
        print(f"❌ Failed to initialize OpenAI: {e}")
        return
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="meeting-transcriber",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                )
            )
        )

if __name__ == "__main__":
    print("🎤 Starting Meeting Transcriber MCP Server...")
    asyncio.run(main())
