// Meeting Agents System Frontend JavaScript

class MeetingAgentsApp {
    constructor() {
        this.apiBase = '/api';
        this.pollingInterval = null;
        this.transcriptions = new Map();
        this.meetings = new Map();
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.checkSystemHealth();
        this.startPolling();
    }
    
    setupEventListeners() {
        // System controls
        document.getElementById('startServers').addEventListener('click', () => this.startServers());
        document.getElementById('stopServers').addEventListener('click', () => this.stopServers());
        document.getElementById('registerNanda').addEventListener('click', () => this.registerWithNanda());
        document.getElementById('discoverAgents').addEventListener('click', () => this.discoverAgents());
        
        // File upload
        const uploadArea = document.getElementById('uploadArea');
        const audioFile = document.getElementById('audioFile');
        
        uploadArea.addEventListener('click', () => audioFile.click());
        uploadArea.addEventListener('dragover', this.handleDragOver.bind(this));
        uploadArea.addEventListener('drop', this.handleDrop.bind(this));
        audioFile.addEventListener('change', this.handleFileSelect.bind(this));
        
        // Meeting actions
        document.getElementById('scheduleAllMeetings').addEventListener('click', () => this.scheduleAllMeetings());
        
        // NANDA controls
        document.getElementById('refreshAgents').addEventListener('click', () => this.discoverAgents());
        document.getElementById('categoryFilter').addEventListener('change', () => this.discoverAgents());
    }
    
    async checkSystemHealth() {
        try {
            const response = await fetch(`${this.apiBase}/health`);
            const data = await response.json();
            
            this.updateSystemStatus(data.status === 'healthy');
            this.updateServerStatus(data.servers);
            
        } catch (error) {
            console.error('Health check failed:', error);
            this.updateSystemStatus(false);
        }
    }
    
    updateSystemStatus(isHealthy) {
        const indicator = document.getElementById('statusIndicator');
        const text = document.getElementById('statusText');
        
        if (isHealthy) {
            indicator.className = 'status-indicator online';
            text.textContent = 'System Online';
        } else {
            indicator.className = 'status-indicator offline';
            text.textContent = 'System Offline';
        }
    }
    
    updateServerStatus(servers) {
        const transcriberStatus = document.getElementById('transcriberStatus');
        const schedulerStatus = document.getElementById('schedulerStatus');
        
        transcriberStatus.className = `server-indicator ${servers.transcriber?.running ? 'running' : 'stopped'}`;
        schedulerStatus.className = `server-indicator ${servers.scheduler?.running ? 'running' : 'stopped'}`;
    }
    
    async startServers() {
        this.showToast('Starting MCP servers...', 'info');
        
        try {
            const response = await fetch(`${this.apiBase}/servers/start`, {
                method: 'POST'
            });
            const data = await response.json();
            
            if (data.success) {
                this.showToast('Servers started successfully!', 'success');
                this.updateServerStatus(data.status);
            } else {
                this.showToast('Failed to start some servers', 'error');
            }
        } catch (error) {
            console.error('Failed to start servers:', error);
            this.showToast('Error starting servers', 'error');
        }
    }
    
    async stopServers() {
        this.showToast('Stopping MCP servers...', 'info');
        
        try {
            const response = await fetch(`${this.apiBase}/servers/stop`, {
                method: 'POST'
            });
            const data = await response.json();
            
            if (data.success) {
                this.showToast('Servers stopped successfully!', 'success');
                this.updateServerStatus({
                    transcriber: { running: false },
                    scheduler: { running: false }
                });
            } else {
                this.showToast('Failed to stop some servers', 'error');
            }
        } catch (error) {
            console.error('Failed to stop servers:', error);
            this.showToast('Error stopping servers', 'error');
        }
    }
    
    async registerWithNanda() {
        this.showToast('Registering agents with NANDA...', 'info');
        
        try {
            const response = await fetch(`${this.apiBase}/nanda/register`, {
                method: 'POST'
            });
            const data = await response.json();
            
            if (data.success) {
                this.showToast(`Successfully registered ${data.registered_count} agents!`, 'success');
            } else {
                this.showToast('Failed to register agents', 'error');
            }
        } catch (error) {
            console.error('NANDA registration failed:', error);
            this.showToast('Error registering with NANDA', 'error');
        }
    }
    
    async discoverAgents() {
        const category = document.getElementById('categoryFilter').value;
        this.showToast('Discovering agents...', 'info');
        
        try {
            const url = category ? 
                `${this.apiBase}/nanda/discover?category=${category}` : 
                `${this.apiBase}/nanda/discover`;
                
            const response = await fetch(url);
            const data = await response.json();
            
            if (data.success) {
                this.displayAgents(data.agents);
                this.showToast(`Found ${data.count} agents`, 'success');
            } else {
                this.showToast('Failed to discover agents', 'error');
            }
        } catch (error) {
            console.error('Agent discovery failed:', error);
            this.showToast('Error discovering agents', 'error');
        }
    }
    
    handleDragOver(e) {
        e.preventDefault();
        e.currentTarget.classList.add('dragover');
    }
    
    handleDrop(e) {
        e.preventDefault();
        e.currentTarget.classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            this.uploadFile(files[0]);
        }
    }
    
    handleFileSelect(e) {
        const file = e.target.files[0];
        if (file) {
            this.uploadFile(file);
        }
    }
    
    async uploadFile(file) {
        if (!this.isAudioFile(file)) {
            this.showToast('Please select a valid audio file', 'error');
            return;
        }
        
        const formData = new FormData();
        formData.append('audio', file);
        
        this.showUploadProgress(true);
        this.updateProgress(0, 'Uploading...');
        
        try {
            const response = await fetch(`${this.apiBase}/upload`, {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.updateProgress(100, 'Upload complete!');
                this.showToast('File uploaded successfully!', 'success');
                
                // Start monitoring transcription
                this.monitorTranscription(data.transcription_id);
                
                setTimeout(() => this.showUploadProgress(false), 2000);
            } else {
                throw new Error(data.error || 'Upload failed');
            }
        } catch (error) {
            console.error('Upload failed:', error);
            this.showToast('Upload failed: ' + error.message, 'error');
            this.showUploadProgress(false);
        }
    }
    
    isAudioFile(file) {
        const audioTypes = ['audio/mp3', 'audio/m4a', 'audio/wav', 'audio/aiff', 'audio/mpeg'];
        return audioTypes.includes(file.type) || 
               file.name.toLowerCase().match(/\.(mp3|m4a|wav|aiff)$/);
    }
    
    showUploadProgress(show) {
        const progressDiv = document.getElementById('uploadProgress');
        progressDiv.style.display = show ? 'block' : 'none';
    }
    
    updateProgress(percent, text) {
        document.getElementById('progressFill').style.width = `${percent}%`;
        document.getElementById('progressText').textContent = text;
    }
    
    async monitorTranscription(transcriptionId) {
        const maxAttempts = 30;
        let attempts = 0;
        
        const checkStatus = async () => {
            try {
                const response = await fetch(`${this.apiBase}/transcription/${transcriptionId}`);
                const data = await response.json();
                
                this.transcriptions.set(transcriptionId, data);
                this.displayTranscriptions();
                
                if (data.status === 'completed') {
                    this.showToast('Transcription completed!', 'success');
                    return;
                } else if (data.status === 'failed') {
                    this.showToast('Transcription failed', 'error');
                    return;
                } else if (attempts < maxAttempts) {
                    attempts++;
                    setTimeout(checkStatus, 2000);
                }
            } catch (error) {
                console.error('Error checking transcription status:', error);
            }
        };
        
        checkStatus();
    }
    
    async analyzeMeetings(transcriptionId) {
        this.showToast('Analyzing transcription for meetings...', 'info');
        
        try {
            const response = await fetch(`${this.apiBase}/analyze-meetings`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ transcription_id: transcriptionId })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showToast('Meeting analysis started!', 'success');
                // Refresh meetings after a delay
                setTimeout(() => this.refreshMeetings(), 3000);
            } else {
                this.showToast('Failed to analyze meetings', 'error');
            }
        } catch (error) {
            console.error('Meeting analysis failed:', error);
            this.showToast('Error analyzing meetings', 'error');
        }
    }
    
    async scheduleAllMeetings() {
        this.showToast('Scheduling meetings...', 'info');
        
        try {
            const response = await fetch(`${this.apiBase}/schedule-meetings`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showToast(`Scheduled ${data.scheduled_count} meetings!`, 'success');
                this.refreshMeetings();
            } else {
                this.showToast('Failed to schedule meetings', 'error');
            }
        } catch (error) {
            console.error('Scheduling failed:', error);
            this.showToast('Error scheduling meetings', 'error');
        }
    }
    
    displayTranscriptions() {
        const container = document.getElementById('transcriptionsList');
        const transcriptions = Array.from(this.transcriptions.values());
        
        if (transcriptions.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-inbox"></i>
                    <p>No transcriptions yet. Upload an audio file to get started.</p>
                </div>
            `;
            return;
        }
        
        container.innerHTML = transcriptions.map(t => this.createTranscriptionItem(t)).join('');
    }
    
    createTranscriptionItem(transcription) {
        const statusClass = `status-${transcription.status}`;
        const statusIcon = transcription.status === 'completed' ? 'check-circle' :
                          transcription.status === 'processing' ? 'clock' : 'times-circle';
        
        return `
            <div class="transcription-item">
                <div class="item-header">
                    <span class="item-title">${transcription.filename}</span>
                    <span class="item-status ${statusClass}">
                        <i class="fas fa-${statusIcon}"></i>
                        ${transcription.status.charAt(0).toUpperCase() + transcription.status.slice(1)}
                    </span>
                </div>
                ${transcription.text ? `
                    <div class="item-content">
                        <div class="item-text">${transcription.text}</div>
                    </div>
                ` : ''}
                <div class="item-meta">
                    <span><i class="fas fa-clock"></i> ${new Date(transcription.uploaded_at).toLocaleString()}</span>
                    ${transcription.completed_at ? `<span><i class="fas fa-check"></i> Completed ${new Date(transcription.completed_at).toLocaleString()}</span>` : ''}
                </div>
                ${transcription.status === 'completed' ? `
                    <div class="item-actions">
                        <button class="btn btn-primary" onclick="app.analyzeMeetings('${transcription.id}')">
                            <i class="fas fa-search"></i> Analyze for Meetings
                        </button>
                    </div>
                ` : ''}
            </div>
        `;
    }
    
    async refreshMeetings() {
        try {
            const response = await fetch(`${this.apiBase}/meetings`);
            const meetings = await response.json();
            
            this.meetings.clear();
            meetings.forEach(meeting => this.meetings.set(meeting.id, meeting));
            
            this.displayMeetings();
        } catch (error) {
            console.error('Failed to refresh meetings:', error);
        }
    }
    
    displayMeetings() {
        const container = document.getElementById('meetingsList');
        const scheduleButton = document.getElementById('scheduleAllMeetings');
        const meetings = Array.from(this.meetings.values());
        
        if (meetings.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-calendar-times"></i>
                    <p>No meetings detected yet. Analyze a transcription to find meetings.</p>
                </div>
            `;
            scheduleButton.style.display = 'none';
            return;
        }
        
        const unscheduledCount = meetings.filter(m => !m.scheduled).length;
        scheduleButton.style.display = unscheduledCount > 0 ? 'block' : 'none';
        
        container.innerHTML = meetings.map(m => this.createMeetingItem(m)).join('');
    }
    
    createMeetingItem(meeting) {
        const confidenceClass = meeting.confidence >= 80 ? 'confidence-high' :
                               meeting.confidence >= 60 ? 'confidence-medium' : 'confidence-low';
        
        const scheduledStatus = meeting.scheduled ? 
            '<span class="item-status status-completed"><i class="fas fa-calendar-check"></i> Scheduled</span>' :
            '<span class="item-status status-processing"><i class="fas fa-calendar-plus"></i> Not Scheduled</span>';
        
        return `
            <div class="meeting-item">
                <div class="item-header">
                    <span class="item-title">${meeting.original_text}</span>
                    ${scheduledStatus}
                </div>
                <div class="item-content">
                    <div class="meeting-datetime">
                        <i class="fas fa-calendar"></i> 
                        ${new Date(meeting.datetime).toLocaleString()}
                    </div>
                    ${meeting.context ? `<p><strong>Context:</strong> ${meeting.context}</p>` : ''}
                    <div class="meeting-confidence ${confidenceClass}">
                        <i class="fas fa-bullseye"></i>
                        Confidence: ${meeting.confidence}%
                    </div>
                </div>
                ${meeting.calendar_event ? `
                    <div class="item-meta">
                        <a href="${meeting.calendar_event.event_link}" target="_blank" class="btn btn-info">
                            <i class="fas fa-external-link-alt"></i> View in Calendar
                        </a>
                    </div>
                ` : ''}
            </div>
        `;
    }
    
    displayAgents(agents) {
        const container = document.getElementById('agentsList');
        
        if (agents.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-robot"></i>
                    <p>No agents found. Try adjusting the category filter.</p>
                </div>
            `;
            return;
        }
        
        container.innerHTML = agents.map(agent => this.createAgentItem(agent)).join('');
    }
    
    createAgentItem(agent) {
        return `
            <div class="agent-item">
                <div class="item-header">
                    <span class="item-title">${agent.name}</span>
                    <span class="item-status status-completed">
                        <i class="fas fa-check-circle"></i> ${agent.status || 'Active'}
                    </span>
                </div>
                <div class="item-content">
                    <p><strong>Category:</strong> ${agent.category}</p>
                    <p><strong>Version:</strong> ${agent.version}</p>
                    ${agent.description ? `<p><strong>Description:</strong> ${agent.description}</p>` : ''}
                    ${agent.capabilities ? `
                        <div class="agent-capabilities">
                            ${agent.capabilities.map(cap => `<span class="capability-tag">${cap}</span>`).join('')}
                        </div>
                    ` : ''}
                </div>
                <div class="item-meta">
                    <span><i class="fas fa-globe"></i> ${agent.protocols ? agent.protocols.join(', ') : 'Unknown'}</span>
                    ${agent.registered_at ? `<span><i class="fas fa-clock"></i> ${new Date(agent.registered_at).toLocaleString()}</span>` : ''}
                </div>
            </div>
        `;
    }
    
    startPolling() {
        // Poll for updates every 5 seconds
        this.pollingInterval = setInterval(() => {
            this.checkSystemHealth();
            this.refreshMeetings();
        }, 5000);
    }
    
    stopPolling() {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
        }
    }
    
    showToast(message, type = 'info') {
        const container = document.getElementById('toastContainer');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        const icon = type === 'success' ? 'check-circle' :
                    type === 'error' ? 'times-circle' :
                    type === 'warning' ? 'exclamation-triangle' : 'info-circle';
        
        toast.innerHTML = `
            <i class="fas fa-${icon}"></i>
            <span>${message}</span>
        `;
        
        container.appendChild(toast);
        
        // Auto remove after 5 seconds
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 5000);
        
        // Click to dismiss
        toast.addEventListener('click', () => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        });
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new MeetingAgentsApp();
});

// Handle page unload
window.addEventListener('beforeunload', () => {
    if (window.app) {
        window.app.stopPolling();
    }
});