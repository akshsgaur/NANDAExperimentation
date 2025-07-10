#!/usr/bin/env python3
"""
Agent Configuration Schemas
Defines the structure and validation for agent configurations
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import json

class AgentConfig:
    """Base agent configuration class"""
    
    def __init__(self, name: str, category: str, version: str = "1.0.0"):
        self.name = name
        self.category = category
        self.version = version
        self.type = "agent"
        self.protocols = ["MCP", "NANDA"]
        self.status = "active"
        self.registered_at = datetime.utcnow().isoformat()
        self.capabilities = []
        self.endpoints = {}
        self.input_types = []
        self.output_types = []
        self.tools = []
        self.dependencies = []
    
    def add_capability(self, capability: str) -> 'AgentConfig':
        """Add a capability to the agent"""
        if capability not in self.capabilities:
            self.capabilities.append(capability)
        return self
    
    def add_endpoint(self, name: str, url: str) -> 'AgentConfig':
        """Add an endpoint to the agent"""
        self.endpoints[name] = url
        return self
    
    def add_input_type(self, mime_type: str) -> 'AgentConfig':
        """Add supported input type"""
        if mime_type not in self.input_types:
            self.input_types.append(mime_type)
        return self
    
    def add_output_type(self, mime_type: str) -> 'AgentConfig':
        """Add supported output type"""
        if mime_type not in self.output_types:
            self.output_types.append(mime_type)
        return self
    
    def add_tool(self, name: str, description: str) -> 'AgentConfig':
        """Add a tool to the agent"""
        self.tools.append({
            "name": name,
            "description": description
        })
        return self
    
    def add_dependency(self, dep_type: str, category: str, description: str) -> 'AgentConfig':
        """Add a dependency"""
        self.dependencies.append({
            "type": dep_type,
            "category": category,
            "description": description
        })
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "type": self.type,
            "category": self.category,
            "version": self.version,
            "description": getattr(self, 'description', ''),
            "protocols": self.protocols,
            "capabilities": self.capabilities,
            "endpoints": self.endpoints,
            "input_types": self.input_types,
            "output_types": self.output_types,
            "tools": self.tools,
            "dependencies": self.dependencies,
            "status": self.status,
            "registered_at": self.registered_at
        }
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)

class TranscriberAgentConfig(AgentConfig):
    """Configuration for transcriber agent"""
    
    def __init__(self, base_url: str):
        super().__init__("Meeting Transcriber Agent", "transcription")
        self.description = "Transcribes audio files using OpenAI Whisper API"
        
        # Add capabilities
        self.add_capability("audio_transcription")
        self.add_capability("whisper_api")
        self.add_capability("multi_format")
        
        # Add endpoints
        self.add_endpoint("base_url", base_url)
        self.add_endpoint("health", f"{base_url}/health")
        self.add_endpoint("mcp", f"{base_url}/mcp")
        
        # Add supported types
        self.add_input_type("audio/m4a")
        self.add_input_type("audio/mp3")
        self.add_input_type("audio/wav")
        self.add_input_type("audio/aiff")
        
        self.add_output_type("text/plain")
        self.add_output_type("application/json")
        
        # Add tools
        self.add_tool("transcribe_audio_file", "Transcribe audio using Whisper API")
        self.add_tool("get_transcription", "Retrieve transcription by ID")

class SchedulerAgentConfig(AgentConfig):
    """Configuration for scheduler agent"""
    
    def __init__(self, base_url: str):
        super().__init__("Meeting Scheduler Agent", "scheduling")
        self.description = "Detects meetings and schedules them on Google Calendar"
        
        # Add capabilities
        self.add_capability("meeting_detection")
        self.add_capability("llm_analysis")
        self.add_capability("calendar_integration")
        self.add_capability("google_calendar")
        
        # Add endpoints
        self.add_endpoint("base_url", base_url)
        self.add_endpoint("health", f"{base_url}/health")
        self.add_endpoint("mcp", f"{base_url}/mcp")
        
        # Add supported types
        self.add_input_type("text/plain")
        self.add_input_type("application/json")
        
        self.add_output_type("application/json")
        
        # Add dependencies
        self.add_dependency("agent", "transcription", "Requires transcription input")
        
        # Add tools
        self.add_tool("analyze_transcription_for_meetings", "Detect meetings using LLM analysis")
        self.add_tool("schedule_detected_meetings", "Schedule meetings on Google Calendar")

# Configuration factory
def create_agent_config(agent_type: str, base_url: str) -> AgentConfig:
    """Factory function to create agent configurations"""
    if agent_type == "transcriber":
        return TranscriberAgentConfig(base_url)
    elif agent_type == "scheduler":
        return SchedulerAgentConfig(base_url)
    else:
        raise ValueError(f"Unknown agent type: {agent_type}")

# Validation functions
def validate_agent_config(config: Dict[str, Any]) -> List[str]:
    """Validate agent configuration"""
    errors = []
    
    required_fields = ["name", "type", "category", "version"]
    for field in required_fields:
        if field not in config:
            errors.append(f"Missing required field: {field}")
    
    if "endpoints" in config:
        if "base_url" not in config["endpoints"]:
            errors.append("Missing base_url endpoint")
    
    if "tools" in config:
        for tool in config["tools"]:
            if "name" not in tool or "description" not in tool:
                errors.append("Tool missing name or description")
    
    return errors

if __name__ == "__main__":
    # Test configuration creation
    base_url = "http://localhost:5000"
    
    # Create transcriber config
    transcriber = create_agent_config("transcriber", f"{base_url}/transcriber")
    print("Transcriber Config:")
    print(transcriber.to_json())
    print()
    
    # Create scheduler config
    scheduler = create_agent_config("scheduler", f"{base_url}/scheduler")
    print("Scheduler Config:")
    print(scheduler.to_json())
    print()
    
    # Validate configs
    errors = validate_agent_config(transcriber.to_dict())
    if errors:
        print("Transcriber validation errors:", errors)
    else:
        print("✅ Transcriber config valid")
    
    errors = validate_agent_config(scheduler.to_dict())
    if errors:
        print("Scheduler validation errors:", errors)
    else:
        print("✅ Scheduler config valid")