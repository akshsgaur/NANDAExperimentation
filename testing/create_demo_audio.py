#!/usr/bin/env python3
"""
Demo Audio Generator
Creates sample audio files with meeting-related content for testing
"""

import wave
import struct
import math
import random
import os
from datetime import datetime, timedelta
import tempfile

class AudioGenerator:
    """Generate audio files for testing purposes"""
    
    def __init__(self, sample_rate=44100):
        self.sample_rate = sample_rate
    
    def generate_tone(self, frequency, duration, amplitude=0.3):
        """Generate a sine wave tone"""
        samples = []
        for i in range(int(self.sample_rate * duration)):
            sample = amplitude * math.sin(2 * math.pi * frequency * i / self.sample_rate)
            samples.append(int(sample * 32767))
        return samples
    
    def generate_silence(self, duration):
        """Generate silence"""
        return [0] * int(self.sample_rate * duration)
    
    def generate_noise(self, duration, amplitude=0.1):
        """Generate background noise"""
        samples = []
        for i in range(int(self.sample_rate * duration)):
            sample = amplitude * (random.random() - 0.5) * 2
            samples.append(int(sample * 32767))
        return samples
    
    def create_meeting_demo_audio(self, filename="demo_meeting.wav"):
        """Create demo audio that would contain meeting-related speech"""
        print(f"🎵 Creating demo audio: {filename}")
        
        # Create a sequence representing different parts of a conversation
        audio_sequence = []
        
        # Opening (representing "Hello everyone")
        audio_sequence.extend(self.generate_tone(440, 0.5))  # A4
        audio_sequence.extend(self.generate_silence(0.2))
        audio_sequence.extend(self.generate_tone(494, 0.5))  # B4
        audio_sequence.extend(self.generate_silence(0.3))
        
        # Meeting content (representing "Let's schedule a meeting")
        audio_sequence.extend(self.generate_tone(523, 0.4))  # C5
        audio_sequence.extend(self.generate_silence(0.1))
        audio_sequence.extend(self.generate_tone(587, 0.4))  # D5
        audio_sequence.extend(self.generate_silence(0.1))
        audio_sequence.extend(self.generate_tone(659, 0.4))  # E5
        audio_sequence.extend(self.generate_silence(0.2))
        
        # Time reference (representing "tomorrow at 2 PM")
        audio_sequence.extend(self.generate_tone(698, 0.3))  # F5
        audio_sequence.extend(self.generate_silence(0.1))
        audio_sequence.extend(self.generate_tone(784, 0.3))  # G5
        audio_sequence.extend(self.generate_silence(0.2))
        
        # Add some background noise
        noise = self.generate_noise(len(audio_sequence) / self.sample_rate, 0.05)
        audio_sequence = [a + n for a, n in zip(audio_sequence, noise)]
        
        # Write to file
        with wave.open(filename, 'w') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(self.sample_rate)
            
            for sample in audio_sequence:
                wav_file.writeframes(struct.pack('<h', sample))
        
        print(f"✅ Created demo audio: {filename} ({len(audio_sequence)/self.sample_rate:.1f}s)")
        return filename

def create_demo_scenarios():
    """Create multiple demo scenarios"""
    generator = AudioGenerator()
    demo_files = []
    
    scenarios = [
        {
            "name": "team_meeting",
            "description": "Team meeting scheduling",
            "frequencies": [440, 494, 523, 587],  # A, B, C, D
            "pattern": [0.5, 0.2, 0.4, 0.3, 0.6, 0.2]
        },
        {
            "name": "client_call", 
            "description": "Client call arrangement",
            "frequencies": [523, 659, 784, 880],  # C, E, G, A
            "pattern": [0.4, 0.1, 0.5, 0.2, 0.3, 0.1, 0.4]
        },
        {
            "name": "project_discussion",
            "description": "Project planning discussion", 
            "frequencies": [330, 392, 466, 523],  # E, G, A#, C
            "pattern": [0.6, 0.3, 0.4, 0.2, 0.5, 0.1]
        }
    ]
    
    print("🎬 Creating demo scenarios...")
    
    for scenario in scenarios:
        filename = f"demo_{scenario['name']}.wav"
        
        # Generate audio based on pattern
        audio_sequence = []
        for i, duration in enumerate(scenario['pattern']):
            if i % 2 == 0:  # Tone
                freq_idx = i // 2 % len(scenario['frequencies'])
                freq = scenario['frequencies'][freq_idx]
                audio_sequence.extend(generator.generate_tone(freq, duration))
            else:  # Silence
                audio_sequence.extend(generator.generate_silence(duration))
        
        # Add background noise
        noise = generator.generate_noise(len(audio_sequence) / generator.sample_rate, 0.03)
        audio_sequence = [a + n for a, n in zip(audio_sequence, noise)]
        
        # Write file
        with wave.open(filename, 'w') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(generator.sample_rate)
            
            for sample in audio_sequence:
                wav_file.writeframes(struct.pack('<h', sample))
        
        demo_files.append({
            "filename": filename,
            "description": scenario['description'],
            "duration": len(audio_sequence) / generator.sample_rate
        })
        
        print(f"   ✅ {filename} - {scenario['description']} ({len(audio_sequence)/generator.sample_rate:.1f}s)")
    
    return demo_files

def create_test_audio_with_metadata():
    """Create test audio with associated metadata for comprehensive testing"""
    generator = AudioGenerator()
    
    test_cases = [
        {
            "filename": "test_simple_meeting.wav",
            "expected_text": "Let's schedule a meeting for tomorrow at 2 PM to discuss the project.",
            "expected_meetings": [
                {
                    "text": "schedule a meeting for tomorrow at 2 PM",
                    "datetime": "tomorrow 2PM",
                    "confidence": 90
                }
            ]
        },
        {
            "filename": "test_multiple_meetings.wav", 
            "expected_text": "We need to meet Monday at 10 AM and then again Wednesday at 3 PM for the review.",
            "expected_meetings": [
                {
                    "text": "meet Monday at 10 AM", 
                    "datetime": "Monday 10AM",
                    "confidence": 85
                },
                {
                    "text": "Wednesday at 3 PM for the review",
                    "datetime": "Wednesday 3PM", 
                    "confidence": 88
                }
            ]
        },
        {
            "filename": "test_no_meetings.wav",
            "expected_text": "The weather is nice today and I enjoyed my coffee this morning.",
            "expected_meetings": []
        }
    ]
    
    print("🧪 Creating test audio with metadata...")
    
    metadata = []
    for test_case in test_cases:
        # Create unique audio pattern for each test case
        audio_sequence = []
        
        # Different patterns for different test cases
        if "simple" in test_case["filename"]:
            audio_sequence.extend(generator.generate_tone(440, 1.0))
            audio_sequence.extend(generator.generate_silence(0.5))
            audio_sequence.extend(generator.generate_tone(523, 0.8))
        elif "multiple" in test_case["filename"]:
            for freq in [330, 392, 466, 523, 587]:
                audio_sequence.extend(generator.generate_tone(freq, 0.4))
                audio_sequence.extend(generator.generate_silence(0.2))
        else:  # no meetings
            audio_sequence.extend(generator.generate_tone(200, 2.0, 0.2))
        
        # Write audio file
        with wave.open(test_case["filename"], 'w') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(generator.sample_rate)
            
            for sample in audio_sequence:
                wav_file.writeframes(struct.pack('<h', sample))
        
        # Add metadata
        test_case["duration"] = len(audio_sequence) / generator.sample_rate
        test_case["created_at"] = datetime.now().isoformat()
        metadata.append(test_case)
        
        print(f"   ✅ {test_case['filename']} - {len(test_case['expected_meetings'])} expected meetings")
    
    # Save metadata
    import json
    with open("test_audio_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    
    print("✅ Test metadata saved to test_audio_metadata.json")
    return metadata

def create_performance_test_audio():
    """Create audio files for performance testing"""
    generator = AudioGenerator()
    
    print("⚡ Creating performance test audio files...")
    
    # Different file sizes for testing
    test_sizes = [
        ("small", 5),    # 5 seconds
        ("medium", 30),  # 30 seconds  
        ("large", 120),  # 2 minutes
        ("xlarge", 300)  # 5 minutes
    ]
    
    for size_name, duration in test_sizes:
        filename = f"perf_test_{size_name}.wav"
        
        # Create complex audio pattern
        audio_sequence = []
        current_time = 0
        
        while current_time < duration:
            # Add a tone
            tone_duration = min(0.5, duration - current_time)
            freq = 440 + (current_time * 50) % 440  # Varying frequency
            audio_sequence.extend(generator.generate_tone(freq, tone_duration, 0.3))
            current_time += tone_duration
            
            if current_time >= duration:
                break
                
            # Add silence
            silence_duration = min(0.2, duration - current_time)
            audio_sequence.extend(generator.generate_silence(silence_duration))
            current_time += silence_duration
        
        # Write file
        with wave.open(filename, 'w') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(generator.sample_rate)
            
            for sample in audio_sequence:
                wav_file.writeframes(struct.pack('<h', sample))
        
        file_size = os.path.getsize(filename) / (1024 * 1024)  # MB
        print(f"   ✅ {filename} - {duration}s ({file_size:.1f} MB)")

def main():
    """Main function to create all demo files"""
    print("🎵 Demo Audio Generator")
    print("=" * 40)
    
    # Create output directory
    os.makedirs("demo_audio", exist_ok=True)
    os.chdir("demo_audio")
    
    try:
        # Create basic demo
        generator = AudioGenerator()
        generator.create_meeting_demo_audio()
        
        # Create scenario demos
        demo_files = create_demo_scenarios()
        
        # Create test audio with metadata
        test_metadata = create_test_audio_with_metadata()
        
        # Create performance test files
        create_performance_test_audio()
        
        print("\n📁 Created files:")
        for file in os.listdir("."):
            if file.endswith(".wav"):
                size = os.path.getsize(file) / 1024  # KB
                print(f"   📄 {file} ({size:.1f} KB)")
        
        print(f"\n✅ All demo audio files created in ./demo_audio/")
        print(f"📊 Total files: {len([f for f in os.listdir('.') if f.endswith('.wav')])}")
        
    except Exception as e:
        print(f"❌ Error creating demo files: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()