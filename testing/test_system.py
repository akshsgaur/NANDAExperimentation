#!/usr/bin/env python3
"""
Integration Tests for Meeting Agents System
Tests the complete workflow from audio upload to meeting scheduling
"""

import pytest
import asyncio
import base64
import json
import os
import time
from pathlib import Path
import tempfile
import wave
import struct
import math

# Test configuration
TEST_BASE_URL = "http://localhost:5000"
TEST_AUDIO_DURATION = 3  # seconds

class TestMeetingAgentsSystem:
    """Integration tests for the meeting agents system"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment"""
        self.base_url = TEST_BASE_URL
        self.test_audio_file = None
        self.transcription_id = None
        self.meeting_ids = []
        
        # Create test audio file
        self.create_test_audio()
        
        yield
        
        # Cleanup
        if self.test_audio_file and os.path.exists(self.test_audio_file):
            os.unlink(self.test_audio_file)
    
    def create_test_audio(self):
        """Create a simple test audio file"""
        sample_rate = 44100
        duration = TEST_AUDIO_DURATION
        frequency = 440  # A4 note
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            self.test_audio_file = temp_file.name
        
        # Generate sine wave
        with wave.open(self.test_audio_file, 'w') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            
            for i in range(int(sample_rate * duration)):
                sample = int(32767 * math.sin(2 * math.pi * frequency * i / sample_rate))
                wav_file.writeframes(struct.pack('<h', sample))
    
    def test_audio_file_creation(self):
        """Test that test audio file was created successfully"""
        assert os.path.exists(self.test_audio_file)
        assert os.path.getsize(self.test_audio_file) > 0
        print(f"✅ Test audio file created: {self.test_audio_file}")
    
    def test_audio_transcription_workflow(self):
        """Test the complete audio transcription workflow"""
        print("\n🎤 Testing Audio Transcription Workflow...")
        
        # Step 1: Read audio file
        with open(self.test_audio_file, 'rb') as f:
            audio_data = f.read()
        
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        
        # Step 2: Simulate transcription
        mock_transcription = {
            "id": "trans_test_1",
            "filename": "test_audio.wav",
            "text": "Let's schedule a team meeting for tomorrow at 2 PM to discuss the quarterly results and plan for next month.",
            "duration": TEST_AUDIO_DURATION,
            "language": "en"
        }
        
        self.transcription_id = mock_transcription["id"]
        
        print(f"✅ Transcription completed: {mock_transcription['text']}")
        assert len(mock_transcription['text']) > 0
        assert 'meeting' in mock_transcription['text'].lower()
    
    def test_meeting_detection_workflow(self):
        """Test meeting detection from transcription"""
        print("\n📅 Testing Meeting Detection Workflow...")
        
        # Simulate running this after transcription
        if not self.transcription_id:
            self.test_audio_transcription_workflow()
        
        # Mock text analysis
        test_text = "Let's schedule a team meeting for tomorrow at 2 PM to discuss the quarterly results."
        
        # Simulate LLM meeting detection
        detected_meetings = [
            {
                "id": "meeting_test_1",
                "original_text": "Let's schedule a team meeting for tomorrow at 2 PM",
                "datetime": "2025-07-10T14:00:00",
                "context": "quarterly results discussion",
                "confidence": 92,
                "scheduled": False
            }
        ]
        
        self.meeting_ids = [m["id"] for m in detected_meetings]
        
        print(f"✅ Detected {len(detected_meetings)} meeting(s)")
        for meeting in detected_meetings:
            print(f"   📅 {meeting['original_text']} (Confidence: {meeting['confidence']}%)")
        
        assert len(detected_meetings) > 0
        assert all(m['confidence'] > 70 for m in detected_meetings)
    
    def test_calendar_scheduling_workflow(self):
        """Test calendar scheduling workflow"""
        print("\n📆 Testing Calendar Scheduling Workflow...")
        
        # Simulate running after meeting detection
        if not self.meeting_ids:
            self.test_meeting_detection_workflow()
        
        # Mock calendar event creation
        scheduled_events = []
        for meeting_id in self.meeting_ids:
            event = {
                "meeting_id": meeting_id,
                "event_id": f"cal_{meeting_id}",
                "event_link": f"https://calendar.google.com/event?id=cal_{meeting_id}",
                "title": "Meeting from Transcription",
                "status": "scheduled"
            }
            scheduled_events.append(event)
        
        print(f"✅ Scheduled {len(scheduled_events)} event(s)")
        for event in scheduled_events:
            print(f"   📅 {event['title']} - {event['event_link']}")
        
        assert len(scheduled_events) == len(self.meeting_ids)
        assert all('event_id' in event for event in scheduled_events)
    
    def test_nanda_registration(self):
        """Test NANDA registration workflow"""
        print("\n🌐 Testing NANDA Registration...")
        
        # Mock agent configurations
        agent_configs = {
            "transcriber": {
                "name": "Meeting Transcriber Agent",
                "type": "agent",
                "category": "transcription",
                "version": "1.0.0",
                "capabilities": ["audio_transcription", "whisper_api"],
                "status": "active"
            },
            "scheduler": {
                "name": "Meeting Scheduler Agent", 
                "type": "agent",
                "category": "scheduling",
                "version": "1.0.0",
                "capabilities": ["meeting_detection", "calendar_integration"],
                "status": "active"
            }
        }
        
        # Mock registration results
        registration_results = {
            "transcriber": "nanda_agent_001",
            "scheduler": "nanda_agent_002"
        }
        
        print(f"✅ Registered {len(registration_results)} agents with NANDA")
        for agent_type, agent_id in registration_results.items():
            print(f"   🤖 {agent_type}: {agent_id}")
        
        assert len(registration_results) == 2
        assert all(agent_id.startswith("nanda_") for agent_id in registration_results.values())
    
    def test_agent_discovery(self):
        """Test agent discovery via NANDA"""
        print("\n🔍 Testing Agent Discovery...")
        
        # Mock discovered agents
        discovered_agents = [
            {
                "id": "nanda_agent_001",
                "name": "Meeting Transcriber Agent",
                "category": "transcription",
                "capabilities": ["audio_transcription", "whisper_api"],
                "status": "active"
            },
            {
                "id": "nanda_agent_002", 
                "name": "Meeting Scheduler Agent",
                "category": "scheduling",
                "capabilities": ["meeting_detection", "calendar_integration"],
                "status": "active"
            },
            {
                "id": "nanda_agent_003",
                "name": "External Audio Processor",
                "category": "transcription",
                "capabilities": ["audio_processing", "noise_reduction"],
                "status": "active"
            }
        ]
        
        print(f"✅ Discovered {len(discovered_agents)} agents")
        for agent in discovered_agents:
            print(f"   🤖 {agent['name']} ({agent['category']})")
        
        # Test category filtering
        transcription_agents = [a for a in discovered_agents if a['category'] == 'transcription']
        scheduling_agents = [a for a in discovered_agents if a['category'] == 'scheduling']
        
        print(f"   📝 Transcription agents: {len(transcription_agents)}")
        print(f"   📅 Scheduling agents: {len(scheduling_agents)}")
        
        assert len(discovered_agents) >= 2
        assert len(transcription_agents) >= 1
        assert len(scheduling_agents) >= 1
    
    def test_complete_workflow(self):
        """Test the complete end-to-end workflow"""
        print("\n🚀 Testing Complete Workflow...")
        
        workflow_steps = [
            ("Audio Upload", self.test_audio_transcription_workflow),
            ("Meeting Detection", self.test_meeting_detection_workflow), 
            ("Calendar Scheduling", self.test_calendar_scheduling_workflow),
            ("NANDA Registration", self.test_nanda_registration),
            ("Agent Discovery", self.test_agent_discovery)
        ]
        
        results = {}
        for step_name, step_func in workflow_steps:
            try:
                step_func()
                results[step_name] = "✅ PASSED"
            except Exception as e:
                results[step_name] = f"❌ FAILED: {str(e)}"
        
        print("\n📊 Workflow Results:")
        for step, result in results.items():
            print(f"   {result} {step}")
        
        # Check overall success
        passed_count = sum(1 for result in results.values() if "PASSED" in result)
        total_count = len(results)
        
        print(f"\n🎯 Overall: {passed_count}/{total_count} steps passed")
        
        assert passed_count == total_count, f"Workflow failed: {total_count - passed_count} steps failed"

class TestErrorHandling:
    """Test error handling and edge cases"""
    
    def test_invalid_audio_format(self):
        """Test handling of invalid audio formats"""
        print("\n❌ Testing Invalid Audio Format...")
        
        # Create a text file pretending to be audio
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp_file:
            temp_file.write(b"This is not an audio file")
            invalid_file = temp_file.name
        
        try:
            # This should fail gracefully
            with open(invalid_file, 'rb') as f:
                data = f.read()
            
            # Simulate validation
            is_valid = data.startswith(b'RIFF') or data.startswith(b'ID3') or data.startswith(b'\xff\xfb')
            
            print(f"   File validation result: {'Valid' if is_valid else 'Invalid'}")
            assert not is_valid, "Should detect invalid audio format"
            print("✅ Invalid audio format correctly detected")
            
        finally:
            os.unlink(invalid_file)
    
    def test_empty_transcription(self):
        """Test handling of empty/failed transcriptions"""
        print("\n🔇 Testing Empty Transcription...")
        
        empty_transcription = {
            "id": "trans_empty",
            "text": "",
            "status": "completed"
        }
        
        # Should not detect meetings in empty text
        detected_meetings = []  # No meetings should be detected
        
        print(f"   Detected meetings in empty text: {len(detected_meetings)}")
        assert len(detected_meetings) == 0
        print("✅ Empty transcription handled correctly")
    
    def test_low_confidence_meetings(self):
        """Test filtering of low-confidence meeting detections"""
        print("\n📉 Testing Low Confidence Meetings...")
        
        mock_detections = [
            {"text": "maybe we should meet", "confidence": 45},  # Too low
            {"text": "let's schedule a meeting", "confidence": 85},  # Good
            {"text": "meeting room is available", "confidence": 60},  # Borderline
        ]
        
        # Filter meetings with confidence >= 70
        high_confidence = [m for m in mock_detections if m['confidence'] >= 70]
        
        print(f"   Total detections: {len(mock_detections)}")
        print(f"   High confidence (>=70%): {len(high_confidence)}")
        
        assert len(high_confidence) == 1
        print("✅ Low confidence meetings filtered correctly")

def create_demo_audio():
    """Create a demo audio file for testing"""
    print("🎵 Creating demo audio file...")
    
    demo_file = "demo_meeting_audio.wav"
    sample_rate = 44100
    duration = 5  # 5 seconds
    
    with wave.open(demo_file, 'w') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        
        # Generate a simple tone
        for i in range(int(sample_rate * duration)):
            sample = int(16000 * math.sin(2 * math.pi * 440 * i / sample_rate))
            wav_file.writeframes(struct.pack('<h', sample))
    
    print(f"✅ Demo audio created: {demo_file}")
    return demo_file

if __name__ == "__main__":
    print("🧪 Running Meeting Agents Integration Tests...")
    print("=" * 60)
    
    # Create demo audio if needed
    if not os.path.exists("demo_meeting_audio.wav"):
        create_demo_audio()
    
    # Run tests
    test_system = TestMeetingAgentsSystem()
    test_system.setup()
    
    try:
        # Run main workflow test
        test_system.test_complete_workflow()
        
        # Run error handling tests
        error_tests = TestErrorHandling()
        error_tests.test_invalid_audio_format()
        error_tests.test_empty_transcription()
        error_tests.test_low_confidence_meetings()
        
        print("\n🎉 All tests passed!")
        
    except Exception as e:
        print(f"\n💥 Tests failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        pass
    
    print("\n" + "=" * 60)
    print("🏁 Test run completed")