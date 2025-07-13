#!/usr/bin/env python3
"""
Fixed MCP Server Manager for Meeting Agents
Resolves communication issues between Flask app and MCP servers
"""

import asyncio
import json
import os
import subprocess
import threading
import signal
import sys
import time
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from queue import Queue, Empty
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler('logs/mcp_manager.log') if os.path.exists('logs') else logging.NullHandler()
    ]
)
logger = logging.getLogger(__name__)

class FixedMCPClient:
    """Fixed MCP Client with proper JSON-RPC communication"""
    
    def __init__(self, server_process):
        self.process = server_process
        self.request_id = 0
        self.response_queue = Queue()
        self.running = True
        self.lock = threading.Lock()
        
        # Start reader thread with better error handling
        self.reader_thread = threading.Thread(target=self._read_responses, daemon=True)
        self.reader_thread.start()
        
        # Initialize the server with proper MCP handshake
        self._initialize_server()
    
    def _initialize_server(self):
        """Initialize MCP server with proper handshake"""
        try:
            # Send initialization request
            init_request = {
                "jsonrpc": "2.0",
                "id": 0,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "roots": {
                            "listChanged": True
                        },
                        "sampling": {}
                    },
                    "clientInfo": {
                        "name": "meeting-agents-client",
                        "version": "1.0.0"
                    }
                }
            }
            
            self._send_request(init_request)
            time.sleep(2)  # Give server time to initialize
            
            # Send initialized notification
            initialized_notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            }
            
            self._send_request(initialized_notification)
            logger.info("MCP server initialization completed")
            
        except Exception as e:
            logger.error(f"Failed to initialize MCP server: {e}")
    
    def _read_responses(self):
        """Read responses from MCP server with better error handling"""
        buffer = ""
        
        while self.running and self.process.poll() is None:
            try:
                # Read character by character to handle line buffering issues
                char = self.process.stdout.read(1)
                if not char:
                    time.sleep(0.01)
                    continue
                
                buffer += char
                
                # Look for complete JSON-RPC messages
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    line = line.strip()
                    
                    if line:
                        try:
                            response = json.loads(line)
                            self.response_queue.put(response)
                            logger.debug(f"Received MCP response: {response.get('id', 'notification')}")
                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse MCP response: {line[:100]}...")
                            continue
                            
            except Exception as e:
                if self.running:
                    logger.error(f"Error reading from MCP server: {e}")
                break
        
        logger.info("MCP client reader thread stopped")
    
    def _send_request(self, request):
        """Send request to MCP server"""
        try:
            request_json = json.dumps(request) + "\n"
            self.process.stdin.write(request_json)
            self.process.stdin.flush()
            logger.debug(f"Sent MCP request: {request.get('method', 'unknown')} (ID: {request.get('id', 'N/A')})")
        except BrokenPipeError:
            logger.error("Broken pipe when sending to MCP server")
            raise
    
    def call_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None, timeout: int = 30) -> dict:
        """Call a tool on the MCP server with improved error handling"""
        with self.lock:
            self.request_id += 1
            
            if arguments is None:
                arguments = {}
            
            request = {
                "jsonrpc": "2.0",
                "id": self.request_id,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }
            
            try:
                self._send_request(request)
                
                # Wait for response with timeout
                start_time = time.time()
                while time.time() - start_time < timeout:
                    try:
                        response = self.response_queue.get(timeout=1)
                        
                        # Check if this is our response
                        if response.get("id") == self.request_id:
                            if "error" in response:
                                error_code = response["error"].get("code", -32603)
                                error_message = response["error"].get("message", "Unknown error")
                                logger.error(f"MCP Error {error_code}: {error_message}")
                                return {"error": f"MCP Error {error_code}: {error_message}"}
                            
                            logger.info(f"Successfully received response for {tool_name}")
                            return response
                        else:
                            # Put back non-matching response
                            self.response_queue.put(response)
                            
                    except Empty:
                        continue
                
                logger.warning(f"Timeout waiting for response to {tool_name}")
                return {"error": f"Timeout waiting for response after {timeout}s"}
                
            except Exception as e:
                logger.error(f"Error calling tool {tool_name}: {e}")
                return {"error": f"Communication error: {str(e)}"}
    
    def close(self):
        """Close the MCP client"""
        logger.info("Closing MCP client...")
        self.running = False
        
        try:
            if self.process.poll() is None:
                self.process.stdin.close()
                self.process.terminate()
                self.process.wait(timeout=5)
        except:
            try:
                self.process.kill()
                self.process.wait(timeout=2)
            except:
                pass
        
        logger.info("MCP client closed")

class FixedMCPServerManager:
    """Fixed MCP Server Manager with proper process management"""
    
    def __init__(self):
        self.servers = {}
        self.clients = {}
        self.base_path = os.path.dirname(os.path.abspath(__file__))
    
    def start_server(self, server_name: str, script_path: str) -> bool:
        """Start MCP server with proper process configuration"""
        try:
            if server_name in self.servers:
                logger.warning(f"Server {server_name} already running")
                return True
            
            # Resolve script path
            if not os.path.isabs(script_path):
                script_path = os.path.join(self.base_path, script_path)
            
            if not os.path.exists(script_path):
                logger.error(f"Script not found: {script_path}")
                return False
            
            # Setup environment
            env = os.environ.copy()
            env['PYTHONPATH'] = self.base_path
            env['PYTHONUNBUFFERED'] = '1'  # Ensure unbuffered output
            
            # Start server process with proper configuration
            logger.info(f"Starting {server_name} server from {script_path}")
            
            process = subprocess.Popen(
                [sys.executable, script_path],
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=0,  # Unbuffered
                universal_newlines=True
            )
            
            # Wait for server to start
            time.sleep(3)
            
            if process.poll() is not None:
                # Process terminated, check for errors
                stdout, stderr = process.communicate()
                logger.error(f"Failed to start {server_name}")
                logger.error(f"STDOUT: {stdout}")
                logger.error(f"STDERR: {stderr}")
                return False
            
            # Store server info
            self.servers[server_name] = {
                'process': process,
                'script_path': script_path,
                'started_at': datetime.now(),
                'status': 'running'
            }
            
            # Create MCP client
            try:
                self.clients[server_name] = FixedMCPClient(process)
                logger.info(f"✅ Started {server_name} server (PID: {process.pid})")
                
                # Test the connection with a simple call
                test_response = self._test_server_connection(server_name)
                if "error" not in test_response:
                    logger.info(f"✅ {server_name} MCP communication test passed")
                else:
                    logger.warning(f"⚠️ {server_name} MCP communication test failed: {test_response.get('error')}")
                
                return True
                
            except Exception as e:
                logger.error(f"Failed to create MCP client for {server_name}: {e}")
                self._cleanup_server(server_name)
                return False
            
        except Exception as e:
            logger.error(f"Failed to start {server_name}: {e}")
            return False
    
    def _test_server_connection(self, server_name: str) -> dict:
        """Test MCP server connection"""
        if server_name not in self.clients:
            return {"error": "Client not available"}
        
        client = self.clients[server_name]
        
        # Test with appropriate method based on server type
        if server_name == "transcriber":
            return client.call_tool("list_transcriptions", {"status_filter": "all"}, timeout=10)
        elif server_name == "scheduler":
            return client.call_tool("get_upcoming_meetings", {"days_ahead": 7, "max_results": 10}, timeout=10)
        else:
            return {"error": "Unknown server type"}
    
    def stop_server(self, server_name: str) -> bool:
        """Stop MCP server"""
        if server_name not in self.servers:
            logger.warning(f"Server {server_name} not found")
            return False
        
        try:
            logger.info(f"Stopping {server_name} server...")
            
            # Close client first
            if server_name in self.clients:
                self.clients[server_name].close()
                del self.clients[server_name]
            
            # Stop server process
            self._cleanup_server(server_name)
            
            logger.info(f"✅ Stopped {server_name} server")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop {server_name}: {e}")
            return False
    
    def _cleanup_server(self, server_name: str):
        """Clean up server process"""
        if server_name in self.servers:
            server_info = self.servers[server_name]
            process = server_info['process']
            
            try:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
            except Exception as e:
                logger.error(f"Error cleaning up {server_name}: {e}")
            
            del self.servers[server_name]
    
    def get_server_status(self, server_name: str) -> Dict[str, Any]:
        """Get server status"""
        if server_name not in self.servers:
            return {"status": "stopped", "running": False}
        
        server_info = self.servers[server_name]
        process = server_info['process']
        is_running = process.poll() is None
        
        if not is_running:
            # Clean up dead server
            self._cleanup_server(server_name)
            return {"status": "stopped", "running": False}
        
        return {
            "status": "running",
            "running": True,
            "pid": process.pid,
            "started_at": server_info['started_at'].isoformat(),
            "uptime_seconds": (datetime.now() - server_info['started_at']).total_seconds()
        }
    
    def call_server_tool(self, server_name: str, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> dict:
        """Call tool on MCP server"""
        if server_name not in self.clients:
            return {"error": f"Server {server_name} not running or no client available"}
        
        if arguments is None:
            arguments = {}
        
        client = self.clients[server_name]
        
        # Use longer timeout for transcription operations
        timeout = 300 if tool_name == "transcribe_audio_file" else 60
        
        try:
            return client.call_tool(tool_name, arguments, timeout=timeout)
        except Exception as e:
            logger.error(f"Error calling {tool_name} on {server_name}: {e}")
            return {"error": f"Tool call error: {str(e)}"}
    
    def stop_all(self):
        """Stop all servers"""
        logger.info("Stopping all MCP servers...")
        for server_name in list(self.servers.keys()):
            self.stop_server(server_name)
        logger.info("All MCP servers stopped")

# Test function
def test_mcp_manager():
    """Test the fixed MCP manager"""
    manager = FixedMCPServerManager()
    
    try:
        # Test transcriber
        print("Testing transcriber server...")
        if manager.start_server("transcriber", "mcp_servers/transcriber_server.py"):
            status = manager.get_server_status("transcriber")
            print(f"Transcriber status: {status}")
            
            # Test a simple call
            result = manager.call_server_tool("transcriber", "list_transcriptions", {"status_filter": "all"})
            print(f"Test call result: {result}")
        
        # Test scheduler
        print("\nTesting scheduler server...")
        if manager.start_server("scheduler", "mcp_servers/scheduler_server.py"):
            status = manager.get_server_status("scheduler")
            print(f"Scheduler status: {status}")
            
            # Test a simple call
            result = manager.call_server_tool("scheduler", "get_upcoming_meetings", {"days_ahead": 7})
            print(f"Test call result: {result}")
        
        # Keep alive for testing
        print("\nServers running. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping servers...")
    
    finally:
        manager.stop_all()

if __name__ == "__main__":
    # Ensure logs directory exists
    os.makedirs("logs", exist_ok=True)
    
    # Run test
    test_mcp_manager()