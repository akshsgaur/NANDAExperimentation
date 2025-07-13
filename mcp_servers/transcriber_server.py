#!/usr/bin/env python3
"""
Fixed Meeting Transcriber MCP Server
Resolves broken pipe and communication issues
"""

import asyncio
import json
import os
import base64
import tempfile
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import openai

from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
from mcp.types import Resource, Tool, TextContent

# Configure logging to stderr only
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)

# Global state
openai_client = None
transcriptions = {}
upload_directory = "frontend/static/uploads"

class TranscriptionError(Exception):
    """Custom exception for transcription errors"""
    pass

def init_openai():
    """Initialize OpenAI client"""
    global openai_client
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEY environment variable not set")
        return False
    
    try:
        openai_client = openai.OpenAI(api_key=api_key)
        # Test the connection
        models = openai_client.models.list()
        logger.info("✅ OpenAI client initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}")
        return False

def ensure_upload_directory():
    """Ensure upload directory exists"""
    Path(upload_directory).mkdir(parents=True, exist_ok=True)

def validate_audio_file(filename: str, audio_data: bytes) -> Dict[str, Any]:
    """Validate audio file before transcription"""
    # Check file size (max 25MB for OpenAI Whisper)
    max_size = 25 * 1024 * 1024  # 25MB
    if len(audio_data) > max_size:
        raise TranscriptionError(f"Audio file too large: {len(audio_data)} bytes (max: {max_size})")
    
    # Check file extension
    supported_formats = {'.mp3', '.mp4', '.mpeg', '.mpga', '.m4a', '.wav', '.webm'}
    file_ext = Path(filename).suffix.lower()
    if file_ext not in supported_formats:
        raise TranscriptionError(f"Unsupported audio format: {file_ext}. Supported: {supported_formats}")
    
    logger.info(f"Audio file validation passed: {filename} ({len(audio_data)} bytes)")
    return {
        "filename": filename,
        "size_bytes": len(audio_data),
        "format": file_ext,
        "valid": True
    }

async def transcribe_audio(audio_data: bytes, filename: str, 
                          language: Optional[str] = None,
                          prompt: Optional[str] = None) -> Dict[str, Any]:
    """Transcribe audio using OpenAI Whisper"""
    if not openai_client:
        raise TranscriptionError("OpenAI client not initialized")
    
    try:
        # Validate input
        validation_result = validate_audio_file(filename, audio_data)
        
        # Create transcription record
        transcription_id = f"trans_{len(transcriptions) + 1}_{int(datetime.now().timestamp())}"
        
        transcription_record = {
            "id": transcription_id,
            "filename": filename,
            "status": "processing",
            "created_at": datetime.now().isoformat(),
            "validation": validation_result,
            "language": language,
            "prompt": prompt
        }
        
        transcriptions[transcription_id] = transcription_record
        logger.info(f"Started transcription {transcription_id} for {filename}")

        # Create temporary file with proper extension
        file_ext = Path(filename).suffix or '.m4a'
        with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as temp_file:
            temp_file.write(audio_data)
            temp_path = temp_file.name

        try:
            # Transcribe with OpenAI Whisper
            with open(temp_path, "rb") as audio_file:
                transcribe_params = {
                    "model": "whisper-1",
                    "file": audio_file,
                    "response_format": "verbose_json"
                }
                
                if language:
                    transcribe_params["language"] = language
                if prompt:
                    transcribe_params["prompt"] = prompt
                
                logger.info(f"Calling OpenAI Whisper API for {transcription_id}")
                transcript = openai_client.audio.transcriptions.create(**transcribe_params)

            # Update transcription record with results
            transcription_record.update({
                "status": "completed",
                "text": transcript.text,
                "duration": getattr(transcript, 'duration', None),
                "detected_language": getattr(transcript, 'language', None),
                "segments": getattr(transcript, 'segments', []),
                "completed_at": datetime.now().isoformat()
            })
            
            logger.info(f"✅ Transcription {transcription_id} completed successfully")
            
            # Optionally save transcript to file
            if os.path.exists(upload_directory):
                transcript_file = Path(upload_directory) / f"{transcription_id}.txt"
                with open(transcript_file, 'w', encoding='utf-8') as f:
                    f.write(transcript.text)
                transcription_record["transcript_file"] = str(transcript_file)
            
            return transcription_record

        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    except openai.OpenAIError as e:
        error_msg = f"OpenAI API error: {str(e)}"
        logger.error(f"❌ Transcription {transcription_id} failed: {error_msg}")
        
        transcription_record.update({
            "status": "failed",
            "error": error_msg,
            "failed_at": datetime.now().isoformat()
        })
        raise TranscriptionError(error_msg)
        
    except Exception as e:
        error_msg = f"Transcription error: {str(e)}"
        logger.error(f"❌ Transcription {transcription_id} failed: {error_msg}")
        
        transcription_record.update({
            "status": "failed", 
            "error": error_msg,
            "failed_at": datetime.now().isoformat()
        })
        raise TranscriptionError(error_msg)

async def analyze_transcription(transcription_id: str, analysis_type: str = "summary") -> Dict[str, Any]:
    """Analyze transcription for insights using OpenAI"""
    if not openai_client:
        raise TranscriptionError("OpenAI client not initialized")
        
    if transcription_id not in transcriptions:
        raise TranscriptionError(f"Transcription {transcription_id} not found")
    
    transcription = transcriptions[transcription_id]
    
    if transcription["status"] != "completed":
        raise TranscriptionError(f"Transcription {transcription_id} is not completed")
    
    text = transcription["text"]
    
    analysis_prompts = {
        "summary": "Provide a concise summary of this meeting or conversation, highlighting the main topics and key points discussed.",
        "action_items": "Extract all action items, tasks, and follow-ups mentioned. Format as a numbered list with responsible parties if mentioned.",
        "decisions": "Identify all decisions made during this conversation. Include what was decided and any context.",
        "participants": "Identify the participants in this conversation based on the transcription. Note their roles if apparent.",
        "sentiment": "Analyze the overall sentiment and tone of this conversation. Note any emotional indicators or concerns raised.",
        "topics": "Extract and categorize the main topics discussed in this conversation.",
        "questions": "List all questions asked during this conversation and whether they were answered."
    }
    
    prompt = analysis_prompts.get(analysis_type, analysis_prompts["summary"])
    
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": f"You are an expert meeting analyst. {prompt}"},
                {"role": "user", "content": f"Analyze this transcription:\n\n{text}"}
            ],
            temperature=0.1,
            max_tokens=1000
        )
        
        analysis_result = {
            "transcription_id": transcription_id,
            "analysis_type": analysis_type,
            "result": response.choices[0].message.content,
            "analyzed_at": datetime.now().isoformat()
        }
        
        # Store analysis in transcription record
        if "analysis" not in transcription:
            transcription["analysis"] = {}
        transcription["analysis"][analysis_type] = analysis_result
        
        logger.info(f"✅ Analysis '{analysis_type}' completed for {transcription_id}")
        return analysis_result
        
    except Exception as e:
        error_msg = f"Analysis failed: {str(e)}"
        logger.error(f"❌ Analysis failed for {transcription_id}: {error_msg}")
        raise TranscriptionError(error_msg)

# Create MCP server
server = Server("meeting-transcriber")

@server.list_resources()
async def list_resources() -> List[Resource]:
    """List available transcription resources"""
    resources = []
    for trans_id, trans_data in transcriptions.items():
        status = trans_data.get("status", "unknown")
        filename = trans_data.get("filename", "unknown")
        
        resources.append(Resource(
            uri=f"transcription://{trans_id}",
            name=f"Transcription: {filename}",
            description=f"Status: {status} | File: {filename}",
            mimeType="application/json"
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
    return json.dumps(transcription, indent=2, default=str)

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
                        "description": "Original filename with extension"
                    },
                    "language": {
                        "type": "string",
                        "description": "Language code (e.g., 'en', 'es', 'fr') - optional"
                    },
                    "prompt": {
                        "type": "string", 
                        "description": "Optional prompt to guide transcription"
                    }
                },
                "required": ["audio_base64", "filename"]
            }
        ),
        Tool(
            name="get_transcription",
            description="Get transcription details by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "transcription_id": {
                        "type": "string",
                        "description": "Transcription ID to retrieve"
                    }
                },
                "required": ["transcription_id"]
            }
        ),
        Tool(
            name="analyze_transcription",
            description="Analyze transcription for insights and content extraction",
            inputSchema={
                "type": "object",
                "properties": {
                    "transcription_id": {
                        "type": "string",
                        "description": "Transcription ID to analyze"
                    },
                    "analysis_type": {
                        "type": "string",
                        "enum": ["summary", "action_items", "decisions", "participants", "sentiment", "topics", "questions"],
                        "description": "Type of analysis to perform",
                        "default": "summary"
                    }
                },
                "required": ["transcription_id"]
            }
        ),
        Tool(
            name="list_transcriptions",
            description="List all transcriptions with their status",
            inputSchema={
                "type": "object",
                "properties": {
                    "status_filter": {
                        "type": "string",
                        "enum": ["all", "completed", "processing", "failed"],
                        "description": "Filter by transcription status",
                        "default": "all"
                    }
                }
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: Union[Dict[str, Any], None]) -> List[TextContent]:
    """Handle tool calls"""
    try:
        if arguments is None:
            arguments = {}
        
        logger.info(f"Tool called: {name}")
        
        if name == "transcribe_audio_file":
            audio_base64 = arguments.get("audio_base64")
            filename = arguments.get("filename")
            language = arguments.get("language")
            prompt = arguments.get("prompt")
            
            if not audio_base64 or not filename:
                return [TextContent(type="text", text="❌ Missing required parameters: audio_base64 and filename")]
            
            try:
                # Decode audio
                audio_data = base64.b64decode(audio_base64)
                
                # Transcribe
                result = await transcribe_audio(audio_data, filename, language, prompt)
                
                response_text = f"""✅ Transcription completed successfully!

📋 **Transcription Details:**
- ID: {result['id']}
- Filename: {result['filename']}
- Duration: {result.get('duration', 'Unknown')} seconds
- Language: {result.get('detected_language', 'Unknown')}
- Status: {result['status']}

📝 **Transcript:**
{result['text']}

💡 Use tool 'analyze_transcription' with ID '{result['id']}' to extract insights, action items, or generate summaries."""
                
                return [TextContent(type="text", text=response_text)]
                
            except TranscriptionError as e:
                return [TextContent(type="text", text=f"❌ Transcription failed: {str(e)}")]
            except Exception as e:
                logger.error(f"Unexpected error in transcription: {e}")
                return [TextContent(type="text", text=f"❌ Unexpected error: {str(e)}")]
            
        elif name == "get_transcription":
            trans_id = arguments.get("transcription_id")
            
            if not trans_id:
                return [TextContent(type="text", text="❌ Missing required parameter: transcription_id")]
            
            if trans_id not in transcriptions:
                return [TextContent(type="text", text=f"❌ Transcription '{trans_id}' not found")]
            
            transcription = transcriptions[trans_id]
            
            response_text = f"""📋 **Transcription Details: {trans_id}**

**Basic Info:**
- Filename: {transcription.get('filename', 'Unknown')}
- Status: {transcription.get('status', 'Unknown')}
- Created: {transcription.get('created_at', 'Unknown')}

**Content:**
- Language: {transcription.get('detected_language', 'Unknown')}
- Duration: {transcription.get('duration', 'Unknown')} seconds
- Text: {transcription.get('text', 'No text available')}

**Analysis Available:** {', '.join(transcription.get('analysis', {}).keys()) if transcription.get('analysis') else 'None'}"""

            return [TextContent(type="text", text=response_text)]
            
        elif name == "analyze_transcription":
            trans_id = arguments.get("transcription_id")
            analysis_type = arguments.get("analysis_type", "summary")
            
            if not trans_id:
                return [TextContent(type="text", text="❌ Missing required parameter: transcription_id")]
            
            try:
                result = await analyze_transcription(trans_id, analysis_type)
                
                response_text = f"""📊 **Analysis Complete: {analysis_type.title()}**

**Transcription ID:** {trans_id}
**Analysis Type:** {analysis_type}
**Analyzed At:** {result['analyzed_at']}

**Results:**
{result['result']}"""

                return [TextContent(type="text", text=response_text)]
                
            except TranscriptionError as e:
                return [TextContent(type="text", text=f"❌ Analysis failed: {str(e)}")]
            
        elif name == "list_transcriptions":
            status_filter = arguments.get("status_filter", "all")
            
            filtered_transcriptions = transcriptions
            if status_filter != "all":
                filtered_transcriptions = {
                    tid: tdata for tid, tdata in transcriptions.items()
                    if tdata.get("status") == status_filter
                }
            
            if not filtered_transcriptions:
                return [TextContent(type="text", text=f"📝 No transcriptions found with status: {status_filter}")]
            
            response_lines = [f"📝 **Transcriptions ({status_filter})**: {len(filtered_transcriptions)} found\n"]
            
            for trans_id, trans_data in filtered_transcriptions.items():
                status = trans_data.get("status", "unknown")
                filename = trans_data.get("filename", "unknown")
                created = trans_data.get("created_at", "unknown")
                
                status_emoji = {"completed": "✅", "processing": "⏳", "failed": "❌"}.get(status, "❓")
                
                response_lines.append(f"{status_emoji} **{trans_id}**")
                response_lines.append(f"   📁 File: {filename}")
                response_lines.append(f"   📅 Created: {created}")
                response_lines.append(f"   🔄 Status: {status}")
                response_lines.append("")
            
            return [TextContent(type="text", text="\n".join(response_lines))]
        
        else:
            return [TextContent(type="text", text=f"❌ Unknown tool: {name}")]
            
    except Exception as e:
        logger.error(f"Tool call error for {name}: {e}")
        return [TextContent(type="text", text=f"❌ Tool execution error: {str(e)}")]

async def main():
    """Main server function"""
    try:
        # Ensure directories exist
        ensure_upload_directory()
        
        # Initialize OpenAI (don't fail if not available)
        openai_initialized = init_openai()
        if not openai_initialized:
            logger.warning("OpenAI not initialized - transcription features will be limited")
        
        logger.info("🎤 Meeting Transcriber MCP Server starting...")
        
        # Run the server
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="meeting-transcriber",
                    server_version="2.1.0",
                    capabilities=server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={}
                    )
                )
            )
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"❌ Failed to start transcriber server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())