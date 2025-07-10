#!/usr/bin/env python3
"""
Flask Backend API
Provides web interface and orchestrates MCP servers
"""

import asyncio
import json
import os
import base64
import tempfile
from datetime import datetime
from typing import Dict, List, Any, Optional

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
import subprocess
import threading
import signal
import sys
import time

# NANDA imports commented out temporarily - add back when files are ready
# from nanda_integration.nanda_client import NANDAClient, register_with_nanda
# from nanda_integration.agent_configs import create_agent_config

# Flask app setup - Fixed paths for your folder structure
app = Flask(__name__, template_folder='frontend/templates', static_folder='frontend/static')
CORS(app)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')

# Global state
mcp_processes = {}
transcriptions = {}
meetings = {}
agent_registrations = {}

class MCPServerManager:
    """Manages MCP server processes"""
    
    def __init__(self):
        self.servers = {}
        self.base_url = "http://localhost:5000"
    
    def start_server(self, server_name: str, script_path: str) -> bool:
        """Start an MCP server"""
        try:
            if server_name in self.servers:
                print(f"⚠️  Server {server_name} already running")
                return True
            
            # Start server process
            env = os.environ.copy()
            process = subprocess.Popen(
                [sys.executable, script_path],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            self.servers[server_name] = {
                'process': process,
                'script_path': script_path,
                'started_at': datetime.now()
            }
            
            print(f"✅ Started {server_name} server (PID: {process.pid})")
            return True
            
        except Exception as e:
            print(f"❌ Failed to start {server_name}: {e}")
            return False
    
    def stop_server(self, server_name: str) -> bool:
        """Stop an MCP server"""
        if server_name not in self.servers:
            return False
        
        try:
            process = self.servers[server_name]['process']
            process.terminate()
            process.wait(timeout=5)
            del self.servers[server_name]
            print(f"✅ Stopped {server_name} server")
            return True
        except Exception as e:
            print(f"❌ Failed to stop {server_name}: {e}")
            return False
    
    def get_server_status(self, server_name: str) -> Dict[str, Any]:
        """Get server status"""
        if server_name not in self.servers:
            return {"status": "stopped", "running": False}
        
        process = self.servers[server_name]['process']
        return {
            "status": "running" if process.poll() is None else "stopped",
            "running": process.poll() is None,
            "pid": process.pid,
            "started_at": self.servers[server_name]['started_at'].isoformat()
        }
    
    def stop_all(self):
        """Stop all servers"""
        for server_name in list(self.servers.keys()):
            self.stop_server(server_name)

# Global server manager
server_manager = MCPServerManager()

# Routes
@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/api/health')
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "servers": {
            "transcriber": server_manager.get_server_status("transcriber"),
            "scheduler": server_manager.get_server_status("scheduler")
        }
    })

@app.route('/api/servers/start', methods=['POST'])
def start_servers():
    """Start MCP servers"""
    results = {}
    
    # Updated paths for your folder structure
    results['transcriber'] = server_manager.start_server(
        "transcriber", 
        "mcp_servers/transcriber_server.py"
    )
    
    results['scheduler'] = server_manager.start_server(
        "scheduler", 
        "mcp_servers/scheduler_server.py"
    )
    
    # Wait a moment for servers to initialize
    time.sleep(2)
    
    return jsonify({
        "success": all(results.values()),
        "results": results,
        "status": {
            "transcriber": server_manager.get_server_status("transcriber"),
            "scheduler": server_manager.get_server_status("scheduler")
        }
    })

@app.route('/api/servers/stop', methods=['POST'])
def stop_servers():
    """Stop MCP servers"""
    results = {
        'transcriber': server_manager.stop_server("transcriber"),
        'scheduler': server_manager.stop_server("scheduler")
    }
    
    return jsonify({
        "success": all(results.values()),
        "results": results
    })

@app.route('/api/servers/status')
def server_status():
    """Get server status"""
    return jsonify({
        "transcriber": server_manager.get_server_status("transcriber"),
        "scheduler": server_manager.get_server_status("scheduler")
    })

@app.route('/api/upload', methods=['POST'])
def upload_audio():
    """Upload and transcribe audio file"""
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file provided"}), 400
    
    audio_file = request.files['audio']
    if audio_file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    try:
        # Read audio data
        audio_data = audio_file.read()
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        
        # Create transcription record
        transcription_id = f"trans_{len(transcriptions) + 1}"
        transcription = {
            "id": transcription_id,
            "filename": audio_file.filename,
            "uploaded_at": datetime.now().isoformat(),
            "status": "processing",
            "text": None,
            "meetings": []
        }
        
        transcriptions[transcription_id] = transcription
        
        # Start background transcription
        def transcribe_background():
            try:
                # Simulate MCP call to transcriber
                # In real implementation, this would call the MCP server
                import time
                time.sleep(2)  # Simulate processing time
                
                # Mock transcription result
                mock_text = f"This is a transcription of {audio_file.filename}. Let's schedule a meeting for tomorrow at 2pm to discuss the project progress."
                
                transcription["text"] = mock_text
                transcription["status"] = "completed"
                transcription["completed_at"] = datetime.now().isoformat()
                
            except Exception as e:
                transcription["status"] = "failed"
                transcription["error"] = str(e)
        
        thread = threading.Thread(target=transcribe_background)
        thread.start()
        
        return jsonify({
            "success": True,
            "transcription_id": transcription_id,
            "status": "processing"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/transcription/<transcription_id>')
def get_transcription(transcription_id: str):
    """Get transcription status and result"""
    if transcription_id not in transcriptions:
        return jsonify({"error": "Transcription not found"}), 404
    
    return jsonify(transcriptions[transcription_id])

@app.route('/api/transcriptions')
def list_transcriptions():
    """List all transcriptions"""
    return jsonify(list(transcriptions.values()))

@app.route('/api/analyze-meetings', methods=['POST'])
def analyze_meetings():
    """Analyze transcription for meetings"""
    data = request.get_json()
    transcription_id = data.get('transcription_id')
    
    if not transcription_id or transcription_id not in transcriptions:
        return jsonify({"error": "Transcription not found"}), 404
    
    transcription = transcriptions[transcription_id]
    
    if transcription["status"] != "completed":
        return jsonify({"error": "Transcription not completed"}), 400
    
    try:
        # Simulate meeting analysis
        def analyze_background():
            time.sleep(1)  # Simulate processing
            
            # Mock meeting detection
            mock_meetings = [
                {
                    "id": f"{transcription_id}_meeting_1",
                    "original_text": "Let's schedule a meeting for tomorrow at 2pm",
                    "datetime": "2025-07-10T14:00:00",
                    "context": "project discussion",
                    "confidence": 95,
                    "scheduled": False
                }
            ]
            
            # Store meetings
            for meeting in mock_meetings:
                meetings[meeting["id"]] = meeting
            
            transcription["meetings"] = mock_meetings
            transcription["meetings_analyzed"] = True
        
        thread = threading.Thread(target=analyze_background)
        thread.start()
        
        return jsonify({
            "success": True,
            "status": "analyzing"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/meetings')
def list_meetings():
    """List all detected meetings"""
    return jsonify(list(meetings.values()))

@app.route('/api/schedule-meetings', methods=['POST'])
def schedule_meetings():
    """Schedule detected meetings"""
    data = request.get_json()
    meeting_ids = data.get('meeting_ids', [])
    
    if not meeting_ids:
        # Schedule all unscheduled meetings
        meeting_ids = [mid for mid, meeting in meetings.items() 
                      if not meeting.get('scheduled', False)]
    
    scheduled_count = 0
    results = []
    
    for meeting_id in meeting_ids:
        if meeting_id in meetings:
            meeting = meetings[meeting_id]
            
            # Mock calendar scheduling
            meeting["scheduled"] = True
            meeting["calendar_event"] = {
                "event_id": f"cal_{meeting_id}",
                "event_link": f"https://calendar.google.com/event?id=cal_{meeting_id}",
                "title": "Meeting from Transcription",
                "datetime": meeting["datetime"]
            }
            
            scheduled_count += 1
            results.append(f"✅ Scheduled: {meeting['original_text']}")
    
    return jsonify({
        "success": True,
        "scheduled_count": scheduled_count,
        "results": results
    })

@app.route('/api/nanda/register', methods=['POST'])
def register_nanda():
    """Register agents with NANDA"""
    # Temporarily return mock data since NANDA integration is commented out
    return jsonify({
        "success": True,
        "message": "NANDA integration temporarily disabled",
        "agent_ids": {"transcriber": "mock_001", "scheduler": "mock_002"},
        "registered_count": 2
    })

@app.route('/api/nanda/discover')
def discover_nanda():
    """Discover agents via NANDA"""
    # Temporarily return mock data
    return jsonify({
        "success": True,
        "message": "NANDA integration temporarily disabled",
        "agents": [
            {
                "id": "mock_001",
                "name": "Meeting Transcriber Agent",
                "category": "transcription",
                "status": "active"
            }
        ],
        "count": 1
    })

@app.route('/api/agent-configs')
def get_agent_configs():
    """Get agent configurations"""
    # Temporarily return mock data
    return jsonify({
        "transcriber": {
            "name": "Meeting Transcriber Agent",
            "category": "transcription",
            "status": "active"
        },
        "scheduler": {
            "name": "Meeting Scheduler Agent", 
            "category": "scheduling",
            "status": "active"
        }
    })

# Static files
@app.route('/static/<path:filename>')
def static_files(filename):
    """Serve static files"""
    return send_from_directory('frontend/static', filename)

# Cleanup on exit
def cleanup_handler(signum, frame):
    """Handle cleanup on exit"""
    print("\n🛑 Shutting down...")
    server_manager.stop_all()
    sys.exit(0)

signal.signal(signal.SIGINT, cleanup_handler)
signal.signal(signal.SIGTERM, cleanup_handler)

if __name__ == '__main__':
    print("🌟 Starting Meeting Agents Flask Backend...")
    print("📍 Access the web interface at: http://localhost:5000")
    
    # Check environment
    if not os.getenv('OPENAI_API_KEY'):
        print("⚠️  Warning: OPENAI_API_KEY not set")
    
    app.run(
        debug=os.getenv('DEBUG', 'false').lower() == 'true',
        host='0.0.0.0',
        port=5001,
        threaded=True
    )