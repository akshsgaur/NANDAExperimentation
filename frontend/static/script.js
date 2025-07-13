// Meeting Agents System Frontend JavaScript - Complete Version
// Compatible with Flask backend and handles all API response formats

class MeetingAgentsApp {
    constructor() {
        // Use current domain and port instead of hardcoded URLs
        this.apiBase = `${window.location.origin}/api`;
        this.pollingInterval = null;
        this.transcriptions = new Map();
        this.meetings = new Map();
        this.isPolling = false;
        
        this.init();
    }
    
    init() {
        console.log('🚀 Initializing Meeting Agents App...');
        this.setupEventListeners();
        this.checkSystemHealth();
        this.startPolling();
        
        // Initial data load
        this.refreshTranscriptions();
        this.refreshMeetings();
        
        console.log('✅ Meeting Agents App initialized');
    }
    
    setupEventListeners() {
        // System controls
        this.bindEvent('startServers', 'click', () => this.startServers());
        this.bindEvent('stopServers', 'click', () => this.stopServers());
        this.bindEvent('testMcp', 'click', () => this.testMcpCommunication());
        this.bindEvent('refreshStatus', 'click', () => this.checkSystemHealth());
        
        // NANDA controls
        this.bindEvent('registerNanda', 'click', () => this.registerWithNanda());
        this.bindEvent('discoverAgents', 'click', () => this.discoverAgents());
        this.bindEvent('refreshAgents', 'click', () => this.discoverAgents());
        this.bindEvent('categoryFilter', 'change', () => this.discoverAgents());
        
        // File upload setup
        this.setupFileUpload();
        
        // Meeting actions
        this.bindEvent('scheduleAllMeetings', 'click', () => this.scheduleAllMeetings());
        this.bindEvent('refreshMeetings', 'click', () => this.refreshMeetings());
        this.bindEvent('refreshTranscriptions', 'click', () => this.refreshTranscriptions());
        
        console.log('✅ Event listeners set up');
    }
    
    bindEvent(elementId, event, handler) {
        const element = document.getElementById(elementId);
        if (element) {
            element.addEventListener(event, handler);
        }
    }
    
    setupFileUpload() {
        const uploadArea = document.getElementById('uploadArea');
        const audioFile = document.getElementById('audioFile');
        const uploadForm = document.getElementById('uploadForm');
        
        if (uploadArea && audioFile) {
            uploadArea.addEventListener('click', () => audioFile.click());
            uploadArea.addEventListener('dragover', this.handleDragOver.bind(this));
            uploadArea.addEventListener('drop', this.handleDrop.bind(this));
            audioFile.addEventListener('change', this.handleFileSelect.bind(this));
        }
        
        if (uploadForm) {
            uploadForm.addEventListener('submit', this.handleFormSubmit.bind(this));
        }
    }
    
    async checkSystemHealth() {
        try {
            const response = await fetch(`${this.apiBase}/health`);
            const data = await response.json();
            
            const isHealthy = response.ok && (data.status === 'healthy');
            
            this.updateSystemStatus(isHealthy, data);
            
            if (data.servers) {
                this.updateServerStatus(data.servers);
            }
            
            // Update MCP communication status if available
            if (data.mcp_communication) {
                this.updateMCPStatus(data.mcp_communication);
            }
            
        } catch (error) {
            console.error('Health check failed:', error);
            this.updateSystemStatus(false, { error: error.message });
            this.updateServerStatus({
                transcriber: { running: false, status: 'stopped' },
                scheduler: { running: false, status: 'stopped' }
            });
        }
    }
    
    updateSystemStatus(isHealthy, data = {}) {
        // Update status indicator
        const indicator = document.getElementById('statusIndicator');
        const text = document.getElementById('statusText');
        
        if (indicator && text) {
            if (isHealthy) {
                indicator.className = 'status-indicator online';
                text.textContent = 'System Online';
            } else {
                indicator.className = 'status-indicator offline';
                text.textContent = data.error ? `System Error` : 'System Offline';
            }
        }
        
        // Update health status card
        const healthStatus = document.getElementById('healthStatus');
        if (healthStatus) {
            const statusClass = isHealthy ? 'bg-green-100 text-green-800 border-green-200' : 'bg-red-100 text-red-800 border-red-200';
            const statusText = isHealthy ? '✅ System Healthy' : '❌ System Degraded';
            
            healthStatus.innerHTML = `
                <div class="p-4 rounded-lg border ${statusClass}">
                    <h3 class="font-bold text-lg">${statusText}</h3>
                    <p class="text-sm mt-1">Last checked: ${new Date().toLocaleTimeString()}</p>
                    ${data.version ? `<p class="text-sm">Version: ${data.version}</p>` : ''}
                    ${data.error ? `<p class="text-sm text-red-600">Error: ${data.error}</p>` : ''}
                </div>
            `;
        }
        
        // Update environment info
        const envInfo = document.getElementById('environmentInfo');
        if (envInfo && data.environment) {
            envInfo.innerHTML = `
                <div class="text-sm space-y-1">
                    <p>OpenAI API: ${data.environment.openai_configured ? '✅ Configured' : '❌ Missing'}</p>
                    <p>Google Calendar: ${data.environment.google_credentials ? '✅ Available' : '❌ Missing'}</p>
                    <p>NANDA Token: ${data.environment.nanda_token ? '✅ Set' : '❌ Not Set'}</p>
                </div>
            `;
        }
    }
    
    updateServerStatus(servers) {
        // Update server indicators
        const transcriberStatus = document.getElementById('transcriberStatus');
        const schedulerStatus = document.getElementById('schedulerStatus');
        
        if (transcriberStatus) {
            transcriberStatus.className = `server-indicator ${servers.transcriber?.running ? 'running' : 'stopped'}`;
            transcriberStatus.title = `Transcriber: ${servers.transcriber?.running ? 'Running' : 'Stopped'}`;
        }
        
        if (schedulerStatus) {
            schedulerStatus.className = `server-indicator ${servers.scheduler?.running ? 'running' : 'stopped'}`;
            schedulerStatus.title = `Scheduler: ${servers.scheduler?.running ? 'Running' : 'Stopped'}`;
        }
        
        // Update detailed server info
        const serverDetails = document.getElementById('serverDetails');
        if (serverDetails) {
            serverDetails.innerHTML = `
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div class="p-4 border rounded-lg">
                        <h4 class="font-bold text-lg mb-2">🎤 Transcriber Server</h4>
                        <div class="space-y-2 text-sm">
                            <p><strong>Status:</strong> ${servers.transcriber?.running ? '🟢 Running' : '🔴 Stopped'}</p>
                            ${servers.transcriber?.pid ? `<p><strong>PID:</strong> ${servers.transcriber.pid}</p>` : ''}
                            ${servers.transcriber?.uptime_seconds ? `<p><strong>Uptime:</strong> ${this.formatUptime(servers.transcriber.uptime_seconds)}</p>` : ''}
                            ${servers.transcriber?.started_at ? `<p><strong>Started:</strong> ${new Date(servers.transcriber.started_at).toLocaleString()}</p>` : ''}
                        </div>
                    </div>
                    <div class="p-4 border rounded-lg">
                        <h4 class="font-bold text-lg mb-2">📅 Scheduler Server</h4>
                        <div class="space-y-2 text-sm">
                            <p><strong>Status:</strong> ${servers.scheduler?.running ? '🟢 Running' : '🔴 Stopped'}</p>
                            ${servers.scheduler?.pid ? `<p><strong>PID:</strong> ${servers.scheduler.pid}</p>` : ''}
                            ${servers.scheduler?.uptime_seconds ? `<p><strong>Uptime:</strong> ${this.formatUptime(servers.scheduler.uptime_seconds)}</p>` : ''}
                            ${servers.scheduler?.started_at ? `<p><strong>Started:</strong> ${new Date(servers.scheduler.started_at).toLocaleString()}</p>` : ''}
                        </div>
                    </div>
                </div>
            `;
        }
    }
    
    updateMCPStatus(mcpCommunication) {
        const mcpStatus = document.getElementById('mcpStatus');
        if (mcpStatus) {
            mcpStatus.innerHTML = `
                <div class="p-4 border rounded-lg">
                    <h4 class="font-bold text-lg mb-2">🔗 MCP Communication</h4>
                    <div class="space-y-2 text-sm">
                        <p>Transcriber: ${mcpCommunication.transcriber ? '✅ Working' : '❌ Failed'}</p>
                        <p>Scheduler: ${mcpCommunication.scheduler ? '✅ Working' : '❌ Failed'}</p>
                    </div>
                </div>
            `;
        }
    }
    
    formatUptime(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        
        if (hours > 0) {
            return `${hours}h ${minutes}m ${secs}s`;
        } else if (minutes > 0) {
            return `${minutes}m ${secs}s`;
        } else {
            return `${secs}s`;
        }
    }
    
    async testMcpCommunication() {
        this.showToast('Testing MCP communication...', 'info');
        
        try {
            const response = await fetch(`${this.apiBase}/test-mcp`);
            const data = await response.json();
            
            if (data.overall_success) {
                this.showToast('✅ MCP communication test passed!', 'success');
            } else {
                const errors = [];
                if (data.mcp_communication_test?.transcriber && !data.mcp_communication_test.transcriber.success) {
                    errors.push(`Transcriber: ${data.mcp_communication_test.transcriber.error || 'Failed'}`);
                }
                if (data.mcp_communication_test?.scheduler && !data.mcp_communication_test.scheduler.success) {
                    errors.push(`Scheduler: ${data.mcp_communication_test.scheduler.error || 'Failed'}`);
                }
                this.showToast(`❌ MCP test failed:\n${errors.join('\n')}`, 'error');
            }
        } catch (error) {
            console.error('MCP test failed:', error);
            this.showToast(`❌ MCP test error: ${error.message}`, 'error');
        }
    }
    
    async startServers() {
        this.showToast('Starting MCP servers...', 'info');
        
        try {
            const response = await fetch(`${this.apiBase}/servers/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await response.json();
            
            if (data.success) {
                this.showToast('✅ Servers started successfully!', 'success');
                
                // Show detailed results if available
                if (data.communication_test) {
                    const testResults = [];
                    if (data.communication_test.transcriber) testResults.push('✅ Transcriber MCP working');
                    if (data.communication_test.scheduler) testResults.push('✅ Scheduler MCP working');
                    if (testResults.length > 0) {
                        this.showToast(testResults.join('\n'), 'success');
                    }
                }
                
                this.updateServerStatus(data.status || {});
            } else {
                const errorMsg = typeof data.results === 'object' ? 
                    Object.entries(data.results).map(([key, val]) => `${key}: ${val ? 'OK' : 'Failed'}`).join(', ') :
                    JSON.stringify(data.results);
                this.showToast(`❌ Failed to start servers: ${errorMsg}`, 'error');
            }
            
            // Refresh status after a delay
            setTimeout(() => this.checkSystemHealth(), 3000);
            
        } catch (error) {
            console.error('Failed to start servers:', error);
            this.showToast(`❌ Error starting servers: ${error.message}`, 'error');
        }
    }
    
    async stopServers() {
        this.showToast('Stopping MCP servers...', 'info');
        
        try {
            const response = await fetch(`${this.apiBase}/servers/stop`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await response.json();
            
            if (data.success) {
                this.showToast('✅ Servers stopped successfully!', 'success');
                this.updateServerStatus({
                    transcriber: { running: false },
                    scheduler: { running: false }
                });
            } else {
                const errorMsg = typeof data.results === 'object' ? 
                    Object.entries(data.results).map(([key, val]) => `${key}: ${val ? 'OK' : 'Failed'}`).join(', ') :
                    JSON.stringify(data.results);
                this.showToast(`❌ Failed to stop servers: ${errorMsg}`, 'error');
            }
            
            // Refresh status
            setTimeout(() => this.checkSystemHealth(), 1000);
            
        } catch (error) {
            console.error('Failed to stop servers:', error);
            this.showToast(`❌ Error stopping servers: ${error.message}`, 'error');
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
                this.showToast(`✅ Successfully registered ${data.registered_count} agents!`, 'success');
            } else {
                this.showToast(`❌ Failed to register agents: ${data.message || 'Unknown error'}`, 'error');
            }
        } catch (error) {
            console.error('NANDA registration failed:', error);
            this.showToast(`❌ Error registering with NANDA: ${error.message}`, 'error');
        }
    }
    
    async discoverAgents() {
        const categoryFilter = document.getElementById('categoryFilter');
        const category = categoryFilter ? categoryFilter.value : '';
        
        this.showToast('Discovering agents...', 'info');
        
        try {
            const url = category ? 
                `${this.apiBase}/nanda/discover?category=${category}` : 
                `${this.apiBase}/nanda/discover`;
                
            const response = await fetch(url);
            const data = await response.json();
            
            if (data.success) {
                this.displayAgents(data.agents || []);
                this.showToast(`✅ Found ${data.count} agents`, 'success');
            } else {
                this.showToast(`❌ Failed to discover agents: ${data.error}`, 'error');
                this.displayAgents([]);
            }
        } catch (error) {
            console.error('Agent discovery failed:', error);
            this.showToast(`❌ Error discovering agents: ${error.message}`, 'error');
            this.displayAgents([]);
        }
    }
    
    handleDragOver(e) {
        e.preventDefault();
        e.stopPropagation();
        e.currentTarget.classList.add('dragover');
    }
    
    handleDrop(e) {
        e.preventDefault();
        e.stopPropagation();
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
    
    handleFormSubmit(e) {
        e.preventDefault();
        const audioFile = document.getElementById('audioFile');
        const file = audioFile.files[0];
        if (file) {
            this.uploadFile(file);
        } else {
            this.showToast('❌ Please select an audio file', 'error');
        }
    }
    
    async uploadFile(file) {
        if (!this.isAudioFile(file)) {
            this.showToast('❌ Please select a valid audio file (mp3, m4a, wav, mp4, etc.)', 'error');
            return;
        }
        
        // Check file size (100MB limit)
        const maxSize = 100 * 1024 * 1024;
        if (file.size > maxSize) {
            this.showToast('❌ File too large. Maximum size is 100MB.', 'error');
            return;
        }
        
        const formData = new FormData();
        formData.append('audio', file);
        
        // Add optional parameters if form fields exist
        const languageSelect = document.getElementById('languageSelect');
        const promptInput = document.getElementById('transcriptionPrompt');
        
        if (languageSelect && languageSelect.value) {
            formData.append('language', languageSelect.value);
        }
        if (promptInput && promptInput.value) {
            formData.append('prompt', promptInput.value);
        }
        
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
                this.showToast(`✅ File uploaded successfully!\nTranscription ID: ${data.transcription_id}`, 'success');
                
                // Start monitoring transcription
                this.monitorTranscription(data.transcription_id);
                
                setTimeout(() => this.showUploadProgress(false), 2000);
                
                // Clear file input
                const audioFile = document.getElementById('audioFile');
                if (audioFile) audioFile.value = '';
                
            } else {
                throw new Error(data.error || 'Upload failed');
            }
        } catch (error) {
            console.error('Upload failed:', error);
            this.showToast(`❌ Upload failed: ${error.message}`, 'error');
            this.showUploadProgress(false);
        }
    }
    
    isAudioFile(file) {
        const audioTypes = [
            'audio/mp3', 'audio/mpeg', 'audio/m4a', 'audio/wav', 
            'audio/aiff', 'audio/mp4', 'audio/webm', 'audio/mpga'
        ];
        const audioExtensions = /\.(mp3|m4a|wav|aiff|mp4|mpeg|mpga|webm)$/i;
        
        return audioTypes.includes(file.type) || audioExtensions.test(file.name);
    }
    
    showUploadProgress(show) {
        const progressDiv = document.getElementById('uploadProgress');
        if (progressDiv) {
            progressDiv.style.display = show ? 'block' : 'none';
        }
    }
    
    updateProgress(percent, text) {
        const progressFill = document.getElementById('progressFill');
        const progressText = document.getElementById('progressText');
        
        if (progressFill) progressFill.style.width = `${percent}%`;
        if (progressText) progressText.textContent = text;
    }
    
    async monitorTranscription(transcriptionId) {
        const maxAttempts = 30;
        let attempts = 0;
        
        this.showToast(`📝 Monitoring transcription ${transcriptionId}...`, 'info');
        
        const checkStatus = async () => {
            try {
                const response = await fetch(`${this.apiBase}/transcription/${transcriptionId}`);
                const data = await response.json();
                
                this.transcriptions.set(transcriptionId, data);
                this.displayTranscriptions();
                
                if (data.status === 'completed') {
                    this.showToast('✅ Transcription completed!', 'success');
                    
                    // Auto-refresh meetings since they might have been analyzed
                    setTimeout(() => this.refreshMeetings(), 2000);
                    return;
                } else if (data.status === 'failed') {
                    this.showToast(`❌ Transcription failed: ${data.error || 'Unknown error'}`, 'error');
                    return;
                } else if (attempts < maxAttempts) {
                    attempts++;
                    this.updateProgress((attempts / maxAttempts) * 90, `Processing... (${attempts}/${maxAttempts})`);
                    setTimeout(checkStatus, 2000);
                } else {
                    this.showToast('⏰ Transcription taking longer than expected', 'warning');
                }
            } catch (error) {
                console.error('Error checking transcription status:', error);
                if (attempts < maxAttempts) {
                    attempts++;
                    setTimeout(checkStatus, 2000);
                }
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
                this.showToast('✅ Meeting analysis started!', 'success');
                // Refresh meetings after a delay
                setTimeout(() => this.refreshMeetings(), 3000);
            } else {
                this.showToast(`❌ Failed to analyze meetings: ${data.error}`, 'error');
            }
        } catch (error) {
            console.error('Meeting analysis failed:', error);
            this.showToast(`❌ Error analyzing meetings: ${error.message}`, 'error');
        }
    }
    
    async scheduleAllMeetings() {
        this.showToast('Scheduling all pending meetings...', 'info');
        
        try {
            const response = await fetch(`${this.apiBase}/schedule-meetings`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showToast(`✅ Successfully scheduled ${data.scheduled_count} meeting(s)!`, 'success');
                this.refreshMeetings();
            } else {
                this.showToast(`❌ Failed to schedule meetings: ${data.error || 'Unknown error'}`, 'error');
            }
        } catch (error) {
            console.error('Scheduling failed:', error);
            this.showToast(`❌ Error scheduling meetings: ${error.message}`, 'error');
        }
    }
    
    async scheduleSingleMeeting(meetingId) {
        this.showToast(`Scheduling meeting ${meetingId}...`, 'info');
        
        try {
            const response = await fetch(`${this.apiBase}/schedule-meetings`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ meeting_ids: [meetingId] })
            });

            const data = await response.json();

            if (data.success && data.scheduled_count > 0) {
                this.showToast('✅ Meeting scheduled successfully!', 'success');
                this.refreshMeetings();
            } else {
                const errorMsg = data.results?.join(', ') || data.error || 'Unknown error';
                this.showToast(`❌ Failed to schedule meeting: ${errorMsg}`, 'error');
            }
        } catch (error) {
            this.showToast(`❌ Error scheduling meeting: ${error.message}`, 'error');
        }
    }
    
    async refreshTranscriptions() {
        try {
            const response = await fetch(`${this.apiBase}/transcriptions`);
            const data = await response.json();
            
            // Handle both formats: direct array or object with transcriptions property
            const transcriptions = Array.isArray(data) ? data : (data.transcriptions || []);
            
            this.transcriptions.clear();
            transcriptions.forEach(t => this.transcriptions.set(t.id, t));
            
            this.displayTranscriptions();
        } catch (error) {
            console.error('Failed to refresh transcriptions:', error);
        }
    }
    
    displayTranscriptions() {
        const container = document.getElementById('transcriptionsList');
        if (!container) return;
        
        const transcriptions = Array.from(this.transcriptions.values());
        
        if (transcriptions.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-microphone-slash fa-3x mb-4 text-gray-400"></i>
                    <p class="text-gray-600">No transcriptions yet</p>
                    <p class="text-sm text-gray-500">Upload an audio file to get started</p>
                </div>
            `;
            return;
        }
        
        container.innerHTML = transcriptions.map(t => this.createTranscriptionItem(t)).join('');
    }
    
    createTranscriptionItem(transcription) {
        const statusClass = this.getStatusClass(transcription.status);
        const statusIcon = this.getStatusIcon(transcription.status);
        
        // Extract transcript text from MCP response if available
        const transcriptText = transcription.mcp_response ? 
            this.extractTranscriptFromResponse(transcription.mcp_response) : 
            transcription.text;
        
        return `
            <div class="transcription-item">
                <div class="item-header">
                    <div class="flex items-center gap-2">
                        <i class="fas fa-file-audio text-blue-500"></i>
                        <span class="item-title">${transcription.filename}</span>
                    </div>
                    <span class="item-status ${statusClass}">
                        <i class="fas fa-${statusIcon}"></i>
                        ${transcription.status.charAt(0).toUpperCase() + transcription.status.slice(1)}
                    </span>
                </div>
                
                ${transcriptText ? `
                    <div class="item-content">
                        <div class="item-text">${transcriptText}</div>
                    </div>
                ` : ''}
                
                <div class="item-meta">
                    <span><i class="fas fa-clock"></i> Uploaded: ${new Date(transcription.uploaded_at).toLocaleString()}</span>
                    ${transcription.completed_at ? `<span><i class="fas fa-check"></i> Completed: ${new Date(transcription.completed_at).toLocaleString()}</span>` : ''}
                    ${transcription.meetings_analyzed ? `<span><i class="fas fa-calendar"></i> Found ${transcription.meetings?.length || 0} meetings</span>` : ''}
                </div>
                
                ${transcription.status === 'completed' && !transcription.meetings_analyzed ? `
                    <div class="item-actions">
                        <button class="btn btn-primary" onclick="window.app.analyzeMeetings('${transcription.id}')">
                            <i class="fas fa-search"></i> Analyze for Meetings
                        </button>
                    </div>
                ` : ''}
            </div>
        `;
    }
    
    extractTranscriptFromResponse(mcpResponse) {
        // Extract transcript from MCP response format
        const match = mcpResponse.match(/\*\*Transcript:\*\*\n(.*?)(?:\n\n💡|$)/s);
        if (match) {
            return match[1].trim();
        }
        
        // Fallback: look for other patterns
        const lines = mcpResponse.split('\n');
        const transcriptIndex = lines.findIndex(line => line.includes('Transcript'));
        if (transcriptIndex >= 0 && transcriptIndex < lines.length - 1) {
            return lines.slice(transcriptIndex + 1).join('\n').trim();
        }
        
        return mcpResponse;
    }
    
    async refreshMeetings() {
        try {
            const response = await fetch(`${this.apiBase}/meetings`);
            const data = await response.json();
            
            // Handle both formats: direct array or object with meetings property
            const meetings = Array.isArray(data) ? data : (data.meetings || []);
            
            this.meetings.clear();
            meetings.forEach(meeting => this.meetings.set(meeting.id, meeting));
            
            this.displayMeetings();
        } catch (error) {
            console.error('Failed to refresh meetings:', error);
            
            // Show user-friendly error in the meetings list
            const container = document.getElementById('meetingsList');
            if (container) {
                container.innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-exclamation-triangle fa-3x mb-4 text-yellow-500"></i>
                        <p class="text-gray-600">Failed to load meetings</p>
                        <p class="text-sm text-gray-500">Please check if the servers are running</p>
                        <button class="btn btn-primary mt-2" onclick="window.app.checkSystemHealth()">
                            <i class="fas fa-refresh"></i> Retry
                        </button>
                    </div>
                `;
            }
        }
    }
    
    displayMeetings() {
        const container = document.getElementById('meetingsList');
        const scheduleButton = document.getElementById('scheduleAllMeetings');
        
        if (!container) return;
        
        const meetings = Array.from(this.meetings.values());
        
        if (meetings.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-calendar-times fa-3x mb-4 text-gray-400"></i>
                    <p class="text-gray-600">No meetings detected yet</p>
                    <p class="text-sm text-gray-500">Upload and analyze a transcription to find meetings</p>
                </div>
            `;
            if (scheduleButton) scheduleButton.style.display = 'none';
            return;
        }
        
        const unscheduledCount = meetings.filter(m => !m.scheduled).length;
        if (scheduleButton) {
            scheduleButton.style.display = unscheduledCount > 0 ? 'block' : 'none';
            scheduleButton.innerHTML = `
                <i class="fas fa-calendar-plus"></i> 
                Schedule All Meetings (${unscheduledCount})
            `;
        }
        
        container.innerHTML = meetings.map(m => this.createMeetingItem(m)).join('');
    }
    
    createMeetingItem(meeting) {
        const confidenceClass = this.getConfidenceClass(meeting.confidence);
        const scheduledStatus = meeting.scheduled ? 
            '<span class="item-status status-completed"><i class="fas fa-calendar-check"></i> Scheduled</span>' :
            '<span class="item-status status-pending"><i class="fas fa-calendar-plus"></i> Pending</span>';
        
        return `
            <div class="meeting-item ${meeting.scheduled ? 'scheduled' : 'pending'}">
                <div class="item-header">
                    <div class="flex items-center gap-2">
                        <i class="fas fa-calendar text-purple-500"></i>
                        <span class="item-title">${meeting.original_text}</span>
                    </div>
                    ${scheduledStatus}
                </div>
                
                <div class="item-content">
                    <div class="meeting-details grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <p><i class="fas fa-clock text-blue-500"></i> <strong>Date/Time:</strong></p>
                            <p class="ml-6">${new Date(meeting.datetime).toLocaleString()}</p>
                            
                            ${meeting.topic ? `
                                <p class="mt-2"><i class="fas fa-tag text-green-500"></i> <strong>Topic:</strong></p>
                                <p class="ml-6">${meeting.topic}</p>
                            ` : ''}
                        </div>
                        
                        <div>
                            <p><i class="fas fa-bullseye text-orange-500"></i> <strong>Confidence:</strong></p>
                            <div class="ml-6 meeting-confidence ${confidenceClass}">
                                ${meeting.confidence}%
                            </div>
                            
                            ${meeting.participants && meeting.participants.length > 0 ? `
                                <p class="mt-2"><i class="fas fa-users text-indigo-500"></i> <strong>Participants:</strong></p>
                                <p class="ml-6">${meeting.participants.join(', ')}</p>
                            ` : ''}
                        </div>
                    </div>
                    
                    ${meeting.context ? `
                        <div class="mt-3">
                            <p><i class="fas fa-info-circle text-gray-500"></i> <strong>Context:</strong></p>
                            <p class="ml-6 text-gray-600">${meeting.context}</p>
                        </div>
                    ` : ''}
                </div>
                
                ${meeting.scheduled && meeting.calendar_event ? `
                    <div class="item-meta bg-green-50 border border-green-200 rounded p-3">
                        <div class="flex items-center justify-between">
                            <div>
                                <p class="font-semibold text-green-800">✅ Successfully Scheduled</p>
                                <p class="text-sm text-green-600">Event ID: ${meeting.calendar_event.event_id}</p>
                                <p class="text-sm text-green-600">Scheduled at: ${new Date(meeting.scheduled_at).toLocaleString()}</p>
                            </div>
                            ${meeting.calendar_event.event_link ? `
                                <a href="${meeting.calendar_event.event_link}" target="_blank" class="btn btn-success">
                                    <i class="fas fa-external-link-alt"></i> View in Calendar
                                </a>
                            ` : ''}
                        </div>
                    </div>
                ` : `
                    <div class="item-actions">
                        <button class="btn btn-primary" onclick="window.app.scheduleSingleMeeting('${meeting.id}')">
                            <i class="fas fa-calendar-plus"></i> Schedule This Meeting
                        </button>
                    </div>
                `}
                
                <div class="item-meta-footer">
                    <span class="text-xs text-gray-500">
                        <i class="fas fa-file-alt"></i> Source: ${meeting.source_id || 'Unknown'}
                    </span>
                    ${meeting.detected_at ? `
                        <span class="text-xs text-gray-500">
                            <i class="fas fa-clock"></i> Detected: ${new Date(meeting.detected_at).toLocaleString()}
                        </span>
                    ` : ''}
                </div>
            </div>
        `;
    }
    
    displayAgents(agents) {
        const container = document.getElementById('agentsList');
        if (!container) return;
        
        if (agents.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-robot fa-3x mb-4 text-gray-400"></i>
                    <p class="text-gray-600">No agents found</p>
                    <p class="text-sm text-gray-500">Try adjusting the category filter or check your NANDA token</p>
                    <button class="btn btn-primary mt-2" onclick="window.app.discoverAgents()">
                        <i class="fas fa-refresh"></i> Retry Discovery
                    </button>
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
                    <div class="flex items-center gap-2">
                        <i class="fas fa-robot text-blue-500"></i>
                        <span class="item-title">${agent.name}</span>
                        ${agent.verified ? '<i class="fas fa-check-circle text-green-500" title="Verified"></i>' : ''}
                    </div>
                    <span class="item-status status-${agent.status || 'active'}">
                        <i class="fas fa-circle"></i> 
                        ${agent.status || 'Active'}
                    </span>
                </div>
                
                <div class="item-content">
                    ${agent.description ? `<p class="text-gray-700 mb-3">${agent.description}</p>` : ''}
                    
                    <div class="agent-details grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            ${agent.provider ? `<p><strong>Provider:</strong> ${agent.provider}</p>` : ''}
                            ${agent.types && agent.types.length > 0 ? `<p><strong>Types:</strong> ${agent.types.join(', ')}</p>` : ''}
                            ${agent.rating_display ? `<p><strong>Rating:</strong> ${agent.rating_display}</p>` : ''}
                        </div>
                        <div>
                            ${agent.uptime_display ? `<p><strong>Uptime:</strong> ${agent.uptime_display}</p>` : ''}
                            ${agent.created_date ? `<p><strong>Created:</strong> ${agent.created_date}</p>` : ''}
                        </div>
                    </div>
                    
                    ${agent.type_badges && agent.type_badges.length > 0 ? `
                        <div class="agent-capabilities mt-3">
                            <p class="text-sm font-semibold mb-2">Capabilities:</p>
                            <div class="flex flex-wrap gap-1">
                                ${agent.type_badges.map(badge => `<span class="capability-tag">${badge}</span>`).join('')}
                            </div>
                        </div>
                    ` : ''}
                    
                    ${agent.tag_badges && agent.tag_badges.length > 0 ? `
                        <div class="agent-tags mt-3">
                            <p class="text-sm font-semibold mb-2">Tags:</p>
                            <div class="flex flex-wrap gap-1">
                                ${agent.tag_badges.map(tag => `<span class="tag-badge">${tag}</span>`).join('')}
                            </div>
                        </div>
                    ` : ''}
                </div>
                
                <div class="item-meta">
                    ${agent.url ? `<a href="${agent.url}" target="_blank" class="btn btn-sm btn-outline"><i class="fas fa-globe"></i> View Details</a>` : ''}
                    ${agent.documentation_url ? `<a href="${agent.documentation_url}" target="_blank" class="btn btn-sm btn-outline"><i class="fas fa-book"></i> Documentation</a>` : ''}
                </div>
            </div>
        `;
    }
    
    getStatusClass(status) {
        switch (status) {
            case 'completed': return 'status-completed';
            case 'processing': return 'status-processing';
            case 'failed': return 'status-failed';
            default: return 'status-unknown';
        }
    }
    
    getStatusIcon(status) {
        switch (status) {
            case 'completed': return 'check-circle';
            case 'processing': return 'clock';
            case 'failed': return 'times-circle';
            default: return 'question-circle';
        }
    }
    
    getConfidenceClass(confidence) {
        if (confidence >= 80) return 'confidence-high';
        if (confidence >= 60) return 'confidence-medium';
        return 'confidence-low';
    }
    
    startPolling() {
        if (this.isPolling) return;
        
        this.isPolling = true;
        // Poll for updates every 15 seconds (reasonable frequency)
        this.pollingInterval = setInterval(() => {
            this.checkSystemHealth();
            
            // Only refresh data if we have items to update
            if (this.transcriptions.size > 0) {
                this.refreshTranscriptions();
            }
            if (this.meetings.size > 0) {
                this.refreshMeetings();
            }
        }, 15000);
        
        console.log('✅ Started polling for updates');
    }
    
    stopPolling() {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
            this.isPolling = false;
            console.log('⏹️ Stopped polling');
        }
    }
    
    showToast(message, type = 'info') {
        // Create toast container if it doesn't exist
        let container = document.getElementById('toastContainer');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toastContainer';
            container.className = 'toast-container';
            document.body.appendChild(container);
        }
        
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        const icon = this.getToastIcon(type);
        
        toast.innerHTML = `
            <div class="toast-content">
                <i class="fas fa-${icon} toast-icon"></i>
                <span class="toast-message">${message}</span>
                <button class="toast-close" onclick="this.parentElement.parentElement.remove()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;
        
        container.appendChild(toast);
        
        // Auto remove after timeout
        const timeout = type === 'error' ? 10000 : 5000;
        setTimeout(() => {
            if (toast.parentNode) {
                toast.classList.add('toast-fade-out');
                setTimeout(() => {
                    if (toast.parentNode) {
                        toast.parentNode.removeChild(toast);
                    }
                }, 300);
            }
        }, timeout);
        
        // Click to dismiss
        toast.addEventListener('click', () => {
            if (toast.parentNode) {
                toast.classList.add('toast-fade-out');
                setTimeout(() => {
                    if (toast.parentNode) {
                        toast.parentNode.removeChild(toast);
                    }
                }, 300);
            }
        });
        
        // Keep only last 3 messages
        while (container.children.length > 3) {
            container.removeChild(container.firstChild);
        }
        
        // Also log to console for debugging
        const logLevel = type === 'error' ? 'error' : type === 'warning' ? 'warn' : 'log';
        console[logLevel](`[${type.toUpperCase()}] ${message}`);
    }
    
    getToastIcon(type) {
        switch (type) {
            case 'success': return 'check-circle';
            case 'error': return 'times-circle';
            case 'warning': return 'exclamation-triangle';
            case 'info': return 'info-circle';
            default: return 'bell';
        }
    }
    
    // Utility methods
    async handleApiCall(url, options = {}) {
        try {
            const response = await fetch(url, options);
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || `HTTP ${response.status}: ${response.statusText}`);
            }
            
            return { success: true, data };
            
        } catch (error) {
            console.error('API call failed:', error);
            return { success: false, error: error.message };
        }
    }
    
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    // Cleanup method
    cleanup() {
        this.stopPolling();
        console.log('🧹 App cleanup completed');
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Create global app instance
    window.app = new MeetingAgentsApp();
    
    // Add comprehensive CSS if not already present
    if (!document.getElementById('meeting-agents-styles')) {
        const style = document.createElement('style');
        style.id = 'meeting-agents-styles';
        style.textContent = `
            /* Toast Container */
            .toast-container {
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 9999;
                max-width: 400px;
            }
            
            /* Toast Styles */
            .toast {
                margin-bottom: 10px;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                overflow: hidden;
                transform: translateX(100%);
                animation: slideIn 0.3s ease forwards;
            }
            
            .toast-fade-out {
                animation: slideOut 0.3s ease forwards;
            }
            
            @keyframes slideIn {
                to { transform: translateX(0); }
            }
            
            @keyframes slideOut {
                to { transform: translateX(100%); opacity: 0; }
            }
            
            .toast-content {
                display: flex;
                align-items: center;
                padding: 12px 16px;
                gap: 10px;
                cursor: pointer;
            }
            
            .toast-success { background: #d4f6d4; color: #2d7d32; border-left: 4px solid #4caf50; }
            .toast-error { background: #fdeaea; color: #c62828; border-left: 4px solid #f44336; }
            .toast-warning { background: #fff8e1; color: #f57f17; border-left: 4px solid #ff9800; }
            .toast-info { background: #e3f2fd; color: #1565c0; border-left: 4px solid #2196f3; }
            
            .toast-icon { flex-shrink: 0; }
            .toast-message { flex: 1; white-space: pre-line; font-size: 14px; }
            .toast-close { 
                background: none; border: none; cursor: pointer; opacity: 0.7;
                padding: 4px; border-radius: 50%; transition: opacity 0.2s;
            }
            .toast-close:hover { opacity: 1; background: rgba(0,0,0,0.1); }
            
            /* Status Indicators */
            .status-indicator {
                width: 12px; height: 12px; border-radius: 50%; display: inline-block; margin-right: 8px;
            }
            .status-indicator.online { background: #4caf50; box-shadow: 0 0 8px rgba(76, 175, 80, 0.6); }
            .status-indicator.offline { background: #f44336; box-shadow: 0 0 8px rgba(244, 67, 54, 0.6); }
            
            .server-indicator {
                width: 10px; height: 10px; border-radius: 50%; display: inline-block; margin-right: 6px;
            }
            .server-indicator.running { background: #4caf50; }
            .server-indicator.stopped { background: #f44336; }
            
            /* Empty States */
            .empty-state {
                text-align: center; padding: 60px 20px; color: #757575;
            }
            
            /* Item Cards */
            .transcription-item, .meeting-item, .agent-item {
                background: white; border: 1px solid #e0e0e0; border-radius: 12px;
                padding: 20px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                transition: box-shadow 0.2s ease;
            }
            .transcription-item:hover, .meeting-item:hover, .agent-item:hover {
                box-shadow: 0 4px 16px rgba(0,0,0,0.12);
            }
            
            /* Meeting States */
            .meeting-item.scheduled { border-color: #4caf50; background: #f8fff8; }
            .meeting-item.pending { border-color: #ff9800; background: #fffbf5; }
            
            /* Item Headers */
            .item-header {
                display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;
            }
            .item-title { font-weight: 600; font-size: 16px; color: #333; }
            
            /* Status Badges */
            .item-status {
                padding: 6px 12px; border-radius: 20px; font-size: 12px; font-weight: 600;
                display: flex; align-items: center; gap: 4px;
            }
            .status-completed { background: #e8f5e8; color: #2e7d32; }
            .status-processing { background: #e3f2fd; color: #1565c0; }
            .status-pending { background: #fff3e0; color: #f57c00; }
            .status-failed { background: #ffebee; color: #c62828; }
            .status-unknown { background: #f5f5f5; color: #757575; }
            
            /* Content Areas */
            .item-content { margin-bottom: 16px; }
            .item-text {
                background: #f8f9fa; padding: 16px; border-radius: 8px; font-size: 14px;
                line-height: 1.6; max-height: 120px; overflow-y: auto; border: 1px solid #e9ecef;
            }
            
            /* Meta Information */
            .item-meta { 
                font-size: 12px; color: #757575; display: flex; gap: 16px; flex-wrap: wrap;
                padding-top: 12px; border-top: 1px solid #f0f0f0;
            }
            .item-meta-footer {
                font-size: 11px; color: #9e9e9e; display: flex; gap: 16px; flex-wrap: wrap;
                margin-top: 12px; padding-top: 8px; border-top: 1px solid #f5f5f5;
            }
            
            /* Action Buttons */
            .item-actions { margin-top: 16px; }
            .btn {
                padding: 10px 16px; border: none; border-radius: 6px; cursor: pointer; font-size: 14px;
                text-decoration: none; display: inline-flex; align-items: center; gap: 6px;
                transition: all 0.2s ease; font-weight: 500;
            }
            .btn:hover { transform: translateY(-1px); box-shadow: 0 2px 8px rgba(0,0,0,0.15); }
            
            .btn-primary { background: #2196f3; color: white; }
            .btn-primary:hover { background: #1976d2; }
            .btn-success { background: #4caf50; color: white; }
            .btn-success:hover { background: #388e3c; }
            .btn-outline { background: white; color: #2196f3; border: 1px solid #2196f3; }
            .btn-outline:hover { background: #2196f3; color: white; }
            .btn-sm { padding: 6px 12px; font-size: 12px; }
            
            /* Confidence Indicators */
            .meeting-confidence { font-weight: 600; padding: 4px 8px; border-radius: 4px; display: inline-block; }
            .confidence-high { background: #e8f5e8; color: #2e7d32; }
            .confidence-medium { background: #fff3e0; color: #f57c00; }
            .confidence-low { background: #ffebee; color: #c62828; }
            
            /* Tags and Badges */
            .capability-tag, .tag-badge {
                background: #f5f5f5; color: #616161; padding: 4px 8px; border-radius: 12px;
                font-size: 11px; font-weight: 500; display: inline-block; margin: 2px;
            }
            .tag-badge { background: #e3f2fd; color: #1565c0; }
            
            /* Drag and Drop */
            .dragover {
                border-color: #2196f3 !important; background-color: #f3f8ff !important;
                box-shadow: 0 0 0 2px rgba(33, 150, 243, 0.2);
            }
            
            /* Progress Bar */
            #uploadProgress {
                margin-top: 16px; padding: 16px; background: #f8f9fa; border-radius: 8px; border: 1px solid #e9ecef;
            }
            #progressFill {
                height: 8px; background: #2196f3; border-radius: 4px; transition: width 0.3s ease;
            }
            #progressText {
                margin-top: 8px; font-size: 14px; color: #616161; text-align: center;
            }
            
            /* Responsive Design */
            @media (max-width: 768px) {
                .toast-container { right: 10px; left: 10px; max-width: none; }
                .item-header { flex-direction: column; align-items: flex-start; gap: 8px; }
                .item-meta { flex-direction: column; gap: 8px; }
                .transcription-item, .meeting-item, .agent-item { padding: 16px; }
            }
        `;
        document.head.appendChild(style);
    }
    
    // Add FontAwesome if not present
    if (!document.querySelector('link[href*="font-awesome"]') && !document.querySelector('script[src*="font-awesome"]')) {
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css';
        document.head.appendChild(link);
    }
    
    console.log('✅ Meeting Agents frontend loaded successfully');
});

// Handle page unload
window.addEventListener('beforeunload', () => {
    if (window.app) {
        window.app.cleanup();
    }
});

// Global functions for inline event handlers
window.scheduleSingleMeeting = (meetingId) => {
    if (window.app) {
        window.app.scheduleSingleMeeting(meetingId);
    }
};

// Export for potential module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = MeetingAgentsApp;
}