"""
NANDA Registry Client
Handles registration and discovery of agents
"""

import asyncio
import aiohttp
import json
from datetime import datetime
from typing import Dict, List, Optional, Any

class NANDAClient:
    """Client for NANDA Registry operations"""
    
    def __init__(self, registry_url: str = "https://nanda-registry.com"):
        self.registry_url = registry_url
        self.api_url = f"{registry_url}/api/v1"
        
    async def register_agent(self, agent_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Register an agent with NANDA registry"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/agents",
                    json=agent_config,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status in [200, 201]:
                        result = await response.json()
                        print(f"✅ Agent registered: {result.get('id', 'unknown')}")
                        return result
                    else:
                        error_text = await response.text()
                        print(f"❌ Registration failed: {response.status} - {error_text}")
                        return None
        except Exception as e:
            print(f"❌ Registration error: {e}")
            return None
    
    async def discover_agents(self, criteria: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
        """Discover agents in the registry"""
        try:
            async with aiohttp.ClientSession() as session:
                params = criteria or {}
                async with session.get(
                    f"{self.api_url}/agents",
                    params=params
                ) as response:
                    if response.status == 200:
                        agents = await response.json()
                        return agents if isinstance(agents, list) else []
                    else:
                        print(f"❌ Discovery failed: {response.status}")
                        return []
        except Exception as e:
            print(f"❌ Discovery error: {e}")
            return []
    
    async def get_agent_details(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about an agent"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.api_url}/agents/{agent_id}") as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        print(f"❌ Failed to get agent details: {response.status}")
                        return None
        except Exception as e:
            print(f"❌ Error getting agent details: {e}")
            return None

# Agent configuration templates
def create_transcriber_config(base_url: str) -> Dict[str, Any]:
    """Create configuration for transcriber agent"""
    return {
        "name": "Meeting Transcriber Agent",
        "type": "agent",
        "category": "transcription",
        "version": "1.0.0",
        "description": "Transcribes audio files using OpenAI Whisper API",
        "protocols": ["MCP", "NANDA"],
        "capabilities": ["audio_transcription", "whisper_api", "multi_format"],
        "endpoints": {
            "base_url": base_url,
            "health": f"{base_url}/health",
            "mcp": f"{base_url}/mcp"
        },
        "input_types": ["audio/m4a", "audio/mp3", "audio/wav"],
        "output_types": ["text/plain", "application/json"],
        "tools": [
            {
                "name": "transcribe_audio_file",
                "description": "Transcribe audio using Whisper API"
            }
        ],
        "status": "active",
        "registered_at": datetime.utcnow().isoformat()
    }

def create_scheduler_config(base_url: str) -> Dict[str, Any]:
    """Create configuration for scheduler agent"""
    return {
        "name": "Meeting Scheduler Agent",
        "type": "agent",
        "category": "scheduling",
        "version": "1.0.0",
        "description": "Detects meetings and schedules them on Google Calendar",
        "protocols": ["MCP", "NANDA"],
        "capabilities": ["meeting_detection", "llm_analysis", "calendar_integration"],
        "endpoints": {
            "base_url": base_url,
            "health": f"{base_url}/health",
            "mcp": f"{base_url}/mcp"
        },
        "input_types": ["text/plain"],
        "output_types": ["application/json"],
        "dependencies": [
            {
                "type": "agent",
                "category": "transcription",
                "description": "Requires transcription input"
            }
        ],
        "tools": [
            {
                "name": "analyze_transcription_for_meetings",
                "description": "Detect meetings using LLM analysis"
            }
        ],
        "status": "active",
        "registered_at": datetime.utcnow().isoformat()
    }

async def register_with_nanda(base_url: str = "http://localhost:5000") -> Dict[str, str]:
    """Register both agents with NANDA"""
    client = NANDAClient()
    
    print("🌐 Registering agents with NANDA...")
    
    # Register transcriber
    transcriber_config = create_transcriber_config(f"{base_url}/transcriber")
    transcriber_result = await client.register_agent(transcriber_config)
    
    # Register scheduler
    scheduler_config = create_scheduler_config(f"{base_url}/scheduler")
    scheduler_result = await client.register_agent(scheduler_config)
    
    agent_ids = {}
    if transcriber_result:
        agent_ids['transcriber'] = transcriber_result.get('id', 'unknown')
    if scheduler_result:
        agent_ids['scheduler'] = scheduler_result.get('id', 'unknown')
    
    print(f"✅ Registered {len(agent_ids)} agents with NANDA")
    return agent_ids

async def discover_agents(category: str = None) -> List[Dict[str, Any]]:
    """Discover agents by category"""
    client = NANDAClient()
    criteria = {"category": category} if category else {}
    agents = await client.discover_agents(criteria)
    
    print(f"🔍 Found {len(agents)} agents")
    for agent in agents[:3]:  # Show first 3
        print(f"  • {agent.get('name', 'Unknown')} ({agent.get('category', 'N/A')})")
    
    return agents

if __name__ == "__main__":
    # Test NANDA integration
    asyncio.run(discover_agents("transcription"))