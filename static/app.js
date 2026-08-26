// OPS-Agent 前端应用
class OPSAgentApp {
    constructor() {
        this.apiBaseUrl = 'http://localhost:9900/api';
        this.currentMode = 'quick';
        this.sessionId = this.generateSessionId();
        this.isStreaming = false;
        this.currentChatHistory = [];
        this.chatHistories = this.loadChatHistories();
        this.isCurrentChatFromHistory = false;
        this.initializeElements();
        this.bindEvents();
        this.updateUI();
        this.initMarkdown();
        this.checkAndSetCentered();
        this.renderChatHistory();
    }
    initMarkdown() {
        const checkMarked = () => {
            if (typeof marked !== 'undefined') {
                try {
                    marked.setOptions({ breaks: true, gfm: true, headerIds: false, mangle: false });
                    if (typeof hljs !== 'undefined') {
                        marked.setOptions({ highlight: function(code, lang) {
                            if (lang && hljs.getLanguage(lang)) { try { return hljs.highlight(code, { language: lang }).value; } catch (err) {} }
                            return code;
                        }});
                    }
                } catch (e) { console.error('Markdown 配置失败:', e); }
            } else { setTimeout(checkMarked, 100); }
        };
        checkMarked();
    }
    renderMarkdown(content) {
        if (!content) return '';
        if (typeof marked === 'undefined') return this.escapeHtml(content);
        try { return marked.parse(content); } catch (e) { return this.escapeHtml(content); }
    }
    highlightCodeBlocks(container) {
        if (typeof hljs !== 'undefined' && container) {
            try { container.querySelectorAll('pre code').forEach((block) => { if (!block.classList.contains('hljs')) hljs.highlightElement(block); }); } catch (e) {}
        }
    }
    initializeElements() {
        this.sidebar = document.querySelector('.sidebar');
        this.newChatBtn = document.getElementById('newChatBtn');
        this.aiOpsSidebarBtn = document.getElementById('aiOpsSidebarBtn');
        this.messageInput = document.getElementById('messageInput');
        this.sendButton = document.getElementById('sendButton');
        this.toolsBtn = document.getElementById('toolsBtn');
        this.toolsMenu = document.getElementById('toolsMenu');
        this.uploadFileItem = document.getElementById('uploadFileItem');
        this.modeSelectorBtn = document.getElementById('modeSelectorBtn');
        this.modeDropdown = document.getElementById('modeDropdown');
        this.currentModeText = document.getElementById('currentModeText');
        this.fileInput = document.getElementById('fileInput');
        this.chatMessages = document.getElementById('chatMessages');
        this.loadingOverlay = document.getElementById('loadingOverlay');
        this.chatContainer = document.querySelector('.chat-container');
        this.welcomeGreeting = document.getElementById('welcomeGreeting');
        this.chatHistoryList = document.getElementById('chatHistoryList');
        this.checkAndSetCentered();
    }
    bindEvents() {
        if (this.newChatBtn) this.newChatBtn.addEventListener('click', () => this.newChat());
        if (this.aiOpsSidebarBtn) this.aiOpsSidebarBtn.addEventListener('click', () => this.triggerAIOps());
        if (this.modeSelectorBtn) this.modeSelectorBtn.addEventListener('click', (e) => { e.stopPropagation(); this.toggleModeDropdown(); });
        document.querySelectorAll('.dropdown-item').forEach(item => {
            item.addEventListener('click', () => { this.selectMode(item.getAttribute('data-mode')); this.closeModeDropdown(); });
        });
        document.addEventListener('click', (e) => { if (!this.modeSelectorBtn.contains(e.target) && !this.modeDropdown.contains(e.target)) this.closeModeDropdown(); });
        if (this.sendButton) this.sendButton.addEventListener('click', () => this.sendMessage());
        if (this.messageInput) this.messageInput.addEventListener('keypress', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this.sendMessage(); } });
        if (this.toolsBtn) this.toolsBtn.addEventListener('click', (e) => { e.stopPropagation(); this.toggleToolsMenu(); });
        if (this.uploadFileItem) this.uploadFileItem.addEventListener('click', () => { if (this.fileInput) this.fileInput.click(); this.closeToolsMenu(); });
        document.addEventListener('click', (e) => { if (this.toolsBtn && this.toolsMenu && !this.toolsBtn.contains(e.target) && !this.toolsMenu.contains(e.target)) this.closeToolsMenu(); });
        if (this.fileInput) this.fileInput.addEventListener('change', (e) => this.handleFileSelect(e));
    }
    toggleToolsMenu() { if (this.toolsMenu && this.toolsBtn) { const wrapper = this.toolsBtn.closest('.tools-btn-wrapper'); if (wrapper) wrapper.classList.toggle('active'); } }
    closeToolsMenu() { if (this.toolsMenu && this.toolsBtn) { const wrapper = this.toolsBtn.closest('.tools-btn-wrapper'); if (wrapper) wrapper.classList.remove('active'); } }
    newChat() {
        if (this.isStreaming) { this.showNotification('请等待当前对话完成', 'warning'); return; }
        if (this.currentChatHistory.length > 0) { if (this.isCurrentChatFromHistory) this.updateCurrentChatHistory(); else this.saveCurrentChat(); }
        this.isStreaming = false; if (this.messageInput) this.messageInput.value = '';
        this.currentChatHistory = []; this.isCurrentChatFromHistory = false;
        if (this.chatMessages) this.chatMessages.innerHTML = '';
        this.sessionId = this.generateSessionId(); this.currentMode = 'quick'; this.updateUI();
        this.checkAndSetCentered(); this.renderChatHistory();
    }
    saveCurrentChat() {
        if (this.currentChatHistory.length === 0) return;
        const existingIndex = this.chatHistories.findIndex(h => h.id === this.sessionId);
        if (existingIndex !== -1) { this.updateCurrentChatHistory(); return; }
        const firstUserMessage = this.currentChatHistory.find(msg => msg.type === 'user');
        const title = firstUserMessage ? (firstUserMessage.content.substring(0, 30) + (firstUserMessage.content.length > 30 ? '...' : '')) : '新对话';
        this.chatHistories.unshift({ id: this.sessionId, title: title, messages: [...this.currentChatHistory], createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() });
        if (this.chatHistories.length > 50) this.chatHistories = this.chatHistories.slice(0, 50);
        this.saveChatHistories();
    }
    updateCurrentChatHistory() {
        if (this.currentChatHistory.length === 0) return;
        const existingIndex = this.chatHistories.findIndex(h => h.id === this.sessionId);
        if (existingIndex === -1) { this.saveCurrentChat(); return; }
        const history = this.chatHistories[existingIndex];
        history.messages = [...this.currentChatHistory]; history.updatedAt = new Date().toISOString();
        const firstUserMessage = this.currentChatHistory.find(msg => msg.type === 'user');
        if (firstUserMessage) { const newTitle = firstUserMessage.content.substring(0, 30) + (firstUserMessage.content.length > 30 ? '...' : ''); if (history.title !== newTitle) history.title = newTitle; }
        this.saveChatHistories();
    }
    loadChatHistories() { try { const stored = localStorage.getItem('chatHistories'); return stored ? JSON.parse(stored) : []; } catch (e) { return []; } }
    saveChatHistories() { try { localStorage.setItem('chatHistories', JSON.stringify(this.chatHistories)); } catch (e) {} }
    renderChatHistory() {
        if (!this.chatHistoryList) return; this.chatHistoryList.innerHTML = '';
        if (this.chatHistories.length === 0) return;
        this.chatHistories.forEach((history) => {
            const historyItem = document.createElement('div'); historyItem.className = 'history-item'; historyItem.dataset.historyId = history.id;
            historyItem.innerHTML = `<div class="history-item-content"><span class="history-item-title">${this.escapeHtml(history.title)}</span></div><button class="history-item-delete" data-history-id="${history.id}" title="删除"><svg viewBox="0 0 24 24" fill="none"><path d="M18 6L6 18M6 6L18 18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg></button>`;
            historyItem.addEventListener('click', (e) => { if (!e.target.closest('.history-item-delete')) this.loadChatHistory(history.id); });
            historyItem.querySelector('.history-item-delete').addEventListener('click', (e) => { e.stopPropagation(); this.deleteChatHistory(history.id); });
            this.chatHistoryList.appendChild(historyItem);
        });
    }
    async loadChatHistory(historyId) {
        const history = this.chatHistories.find(h => h.id === historyId); if (!history) return;
        if (this.currentChatHistory.length > 0 && this.sessionId !== historyId) { if (this.isCurrentChatFromHistory) this.updateCurrentChatHistory(); else this.saveCurrentChat(); }
        try {
            const response = await fetch(`/api/chat/session/${historyId}`);
            if (response.ok) { const data = await response.json(); const backendHistory = data.history || [];
                this.sessionId = history.id; this.isCurrentChatFromHistory = true;
                if (this.chatMessages) { this.chatMessages.innerHTML = '';
                    if (backendHistory.length > 0) { this.currentChatHistory = []; backendHistory.forEach(msg => { this.addMessage(msg.role === 'user' ? 'user' : 'assistant', msg.content, false, false); }); }
                    else { this.currentChatHistory = [...history.messages]; history.messages.forEach(msg => { this.addMessage(msg.type, msg.content, false, false); }); }
                }
            } else { this.sessionId = history.id; this.currentChatHistory = [...history.messages]; this.isCurrentChatFromHistory = true;
                if (this.chatMessages) { this.chatMessages.innerHTML = ''; history.messages.forEach(msg => { this.addMessage(msg.type, msg.content, false, false); }); }
            }
        } catch (error) { this.sessionId = history.id; this.currentChatHistory = [...history.messages]; this.isCurrentChatFromHistory = true;
            if (this.chatMessages) { this.chatMessages.innerHTML = ''; history.messages.forEach(msg => { this.addMessage(msg.type, msg.content, false, false); }); }
        }
        this.checkAndSetCentered(); this.renderChatHistory();
    }
    async deleteChatHistory(historyId) {
        try { const response = await fetch('/api/chat/clear', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ session_id: historyId }) });
            if (!response.ok) throw new Error('清空会话失败'); const result = await response.json();
            if (result.status === 'success') { this.chatHistories = this.chatHistories.filter(h => h.id !== historyId); this.saveChatHistories(); this.renderChatHistory();
                if (this.sessionId === historyId) { this.currentChatHistory = []; if (this.chatMessages) this.chatMessages.innerHTML = ''; this.sessionId = this.generateSessionId(); this.checkAndSetCentered(); }
                this.showNotification('会话已清空', 'success'); } else { throw new Error(result.message || '清空会话失败'); }
        } catch (error) { this.showNotification('删除失败: ' + error.message, 'error'); }
    }
    toggleModeDropdown() { if (this.modeSelectorBtn && this.modeDropdown) { const wrapper = this.modeSelectorBtn.closest('.mode-selector-wrapper'); if (wrapper) wrapper.classList.toggle('active'); } }
    closeModeDropdown() { if (this.modeSelectorBtn && this.modeDropdown) { const wrapper = this.modeSelectorBtn.closest('.mode-selector-wrapper'); if (wrapper) wrapper.classList.remove('active'); } }
    selectMode(mode) { if (this.isStreaming) { this.showNotification('请等待当前对话完成', 'warning'); return; } this.currentMode = mode; this.updateUI(); this.showNotification(`已切换到${mode === 'quick' ? '快速' : '流式'}模式`, 'info'); }
    updateUI() {
        if (this.currentModeText) this.currentModeText.textContent = this.currentMode === 'quick' ? '快速' : '流式';
        document.querySelectorAll('.dropdown-item').forEach(item => { item.classList.toggle('active', item.getAttribute('data-mode') === this.currentMode); });
        if (this.sendButton) this.sendButton.disabled = this.isStreaming;
        if (this.messageInput) { this.messageInput.disabled = this.isStreaming; this.messageInput.placeholder = '问问 OPS-Agent'; }
    }
    generateSessionId() { return 'session_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now(); }
    async sendMessage() {
        let message = ''; if (this.messageInput) message = this.messageInput.value.trim();
        if (!message) { this.showNotification('请输入消息内容', 'warning'); return; }
        if (this.isStreaming) { this.showNotification('请等待当前对话完成', 'warning'); return; }
        this.addMessage('user', message); if (this.messageInput) this.messageInput.value = '';
        this.isStreaming = true; this.updateUI();
        try { if (this.currentMode === 'quick') await this.sendQuickMessage(message); else await this.sendStreamMessage(message); }
        catch (error) { this.addMessage('assistant', '抱歉，发送消息时出现错误：' + error.message); }
        finally { this.isStreaming = false; this.updateUI();
            if (this.isCurrentChatFromHistory && this.currentChatHistory.length > 0) { this.updateCurrentChatHistory(); this.renderChatHistory(); }
        }
    }
    async sendQuickMessage(message) {
        const loadingMessage = this.addLoadingMessage('正在思考...');
        try { const response = await fetch(`${this.apiBaseUrl}/chat`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ Id: this.sessionId, Question: message }) });
            if (!response.ok) throw new Error(`HTTP错误: ${response.status}`); const data = await response.json();
            if (loadingMessage && loadingMessage.parentNode) loadingMessage.parentNode.removeChild(loadingMessage);
            if (data.code === 200 || data.message === 'success') { const chatResponse = data.data;
                if (chatResponse && chatResponse.success) this.addMessage('assistant', chatResponse.answer || '（无回复内容）');
                else if (chatResponse && chatResponse.errorMessage) throw new Error(chatResponse.errorMessage);
                else this.addMessage('assistant', chatResponse?.answer || chatResponse?.errorMessage || '服务返回了空内容');
            } else throw new Error(data.message || '请求失败');
        } catch (error) { if (loadingMessage && loadingMessage.parentNode) loadingMessage.parentNode.removeChild(loadingMessage); throw error; }
    }
    async sendStreamMessage(message) {
        try { const response = await fetch(`${this.apiBaseUrl}/chat_stream`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ Id: this.sessionId, Question: message }) });
            if (!response.ok) throw new Error(`HTTP错误: ${response.status}`);
            const assistantMessageElement = this.addMessage('assistant', '', true); let fullResponse = '';
            const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = '';
            try { while (true) { const { done, value } = await reader.read();
                if (done) { this.handleStreamComplete(assistantMessageElement, fullResponse); break; }
                buffer += decoder.decode(value, { stream: true }); const lines = buffer.split('\n'); buffer = lines.pop() || '';
                for (const line of lines) { if (line.trim() === '') continue;
                    if (line.startsWith('event:')) continue; else if (line.startsWith('data:')) {
                        const rawData = line.substring(5).trim(); if (rawData === '[DONE]') { this.handleStreamComplete(assistantMessageElement, fullResponse); return; }
                        try { const sseMessage = JSON.parse(rawData);
                            if (sseMessage.type === 'content') { fullResponse += sseMessage.data || ''; if (assistantMessageElement) { assistantMessageElement.querySelector('.message-content').innerHTML = this.renderMarkdown(fullResponse); this.highlightCodeBlocks(assistantMessageElement.querySelector('.message-content')); this.scrollToBottom(); } }
                            else if (sseMessage.type === 'done') { this.handleStreamComplete(assistantMessageElement, fullResponse); return; }
                            else if (sseMessage.type === 'error') { if (assistantMessageElement) assistantMessageElement.querySelector('.message-content').innerHTML = this.renderMarkdown('错误: ' + (sseMessage.data || '未知错误')); return; }
                        } catch (e) { fullResponse += rawData; if (assistantMessageElement) { assistantMessageElement.querySelector('.message-content').innerHTML = this.renderMarkdown(fullResponse); this.highlightCodeBlocks(assistantMessageElement.querySelector('.message-content')); this.scrollToBottom(); } }
                    }
                }
            } } finally { reader.releaseLock(); }
        } catch (error) { throw error; }
    }
    addMessage(type, content, isStreaming = false, saveToHistory = true) {
        const isFirstMessage = this.chatMessages && this.chatMessages.querySelectorAll('.message').length === 0;
        if (!isStreaming && saveToHistory && content) this.currentChatHistory.push({ type, content, timestamp: new Date().toISOString() });
        const messageDiv = document.createElement('div'); messageDiv.className = `message ${type}${isStreaming ? ' streaming' : ''}`;
        if (type === 'assistant') { const avatar = document.createElement('div'); avatar.className = 'message-avatar'; avatar.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" fill="white"/></svg>'; messageDiv.appendChild(avatar); }
        const wrapper = document.createElement('div'); wrapper.className = 'message-content-wrapper';
        const messageContent = document.createElement('div'); messageContent.className = 'message-content';
        if (type === 'assistant' && !isStreaming) { messageContent.innerHTML = this.renderMarkdown(content); this.highlightCodeBlocks(messageContent); } else { messageContent.textContent = content; }
        wrapper.appendChild(messageContent); messageDiv.appendChild(wrapper);
        if (this.chatMessages) { this.chatMessages.appendChild(messageDiv); if (isFirstMessage && this.chatContainer) this.chatContainer.classList.remove('centered'); this.scrollToBottom(); }
        return messageDiv;
    }
    addLoadingMessage(content) {
        const messageDiv = document.createElement('div'); messageDiv.className = 'message assistant';
        const avatar = document.createElement('div'); avatar.className = 'message-avatar'; avatar.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" fill="white"/></svg>'; messageDiv.appendChild(avatar);
        const wrapper = document.createElement('div'); wrapper.className = 'message-content-wrapper';
        const messageContent = document.createElement('div'); messageContent.className = 'message-content loading-message-content';
        const textSpan = document.createElement('span'); textSpan.textContent = content;
        const loadingIcon = document.createElement('span'); loadingIcon.className = 'loading-spinner-icon'; loadingIcon.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8z" fill="currentColor" opacity="0.2"/><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10c1.54 0 3-.36 4.28-1l-1.5-2.6C13.64 19.62 12.84 20 12 20c-4.41 0-8-3.59-8-8s3.59-8 8-8c.84 0 1.64.38 2.18 1l1.5-2.6C13 2.36 12.54 2 12 2z" fill="currentColor"/></svg>';
        messageContent.appendChild(textSpan); messageContent.appendChild(loadingIcon); wrapper.appendChild(messageContent); messageDiv.appendChild(wrapper);
        if (this.chatMessages) { this.chatMessages.appendChild(messageDiv); this.scrollToBottom(); }
        return messageDiv;
    }
    checkAndSetCentered() { if (this.chatMessages && this.chatContainer) { const hasMessages = this.chatMessages.querySelectorAll('.message').length > 0; this.chatContainer.classList.toggle('centered', !hasMessages); } }
    scrollToBottom() { if (this.chatMessages) this.chatMessages.scrollTop = this.chatMessages.scrollHeight; }
    handleStreamComplete(assistantMessageElement, fullResponse) {
        if (assistantMessageElement) { assistantMessageElement.classList.remove('streaming'); const mc = assistantMessageElement.querySelector('.message-content'); if (mc) { mc.innerHTML = this.renderMarkdown(fullResponse); this.highlightCodeBlocks(mc); } }
        if (fullResponse) { this.currentChatHistory.push({ type: 'assistant', content: fullResponse, timestamp: new Date().toISOString() });
            if (this.isCurrentChatFromHistory) { this.updateCurrentChatHistory(); this.renderChatHistory(); } }
    }
    showNotification(message, type = 'info') {
        const notification = document.createElement('div'); notification.className = `notification ${type}`; notification.textContent = message;
        notification.style.cssText = 'position:fixed;top:20px;right:20px;padding:15px 20px;border-radius:8px;color:white;font-weight:500;z-index:10000;animation:slideIn 0.3s ease;max-width:300px;';
        const colors = { info: '#1a73e8', success: '#34a853', warning: '#fbbc04', error: '#ea4335' };
        notification.style.backgroundColor = colors[type] || colors.info; document.body.appendChild(notification);
        setTimeout(() => { notification.style.animation = 'slideOut 0.3s ease'; setTimeout(() => { if (notification.parentNode) notification.parentNode.removeChild(notification); }, 300); }, 3000);
    }
    handleFileSelect(event) { const file = event.target.files[0]; if (file) { if (!this.validateFileType(file)) { this.showNotification('只支持上传 TXT 或 Markdown (.md) 格式的文件', 'error'); this.fileInput.value = ''; return; } this.uploadFile(file); } }
    validateFileType(file) { return ['.txt', '.md', '.markdown'].some(ext => file.name.toLowerCase().endsWith(ext)); }
    async uploadFile(file) {
        if (!this.validateFileType(file)) { this.showNotification('只支持上传 TXT 或 Markdown (.md) 格式的文件', 'error'); return; }
        if (file.size > 50 * 1024 * 1024) { this.showNotification('文件大小不能超过50MB', 'error'); return; }
        this.isStreaming = true; this.updateUI(); this.showUploadOverlay(true, file.name);
        try { const formData = new FormData(); formData.append('file', file); const response = await fetch(`${this.apiBaseUrl}/upload`, { method: 'POST', body: formData });
            if (!response.ok) throw new Error(`HTTP错误: ${response.status}`); const data = await response.json();
            if ((data.code === 200 || data.message === 'success') && data.data) this.addMessage('assistant', `${file.name} 上传到知识库成功`, false, true);
            else throw new Error(data.message || '上传失败');
        } catch (error) { this.showNotification('文件上传失败: ' + error.message, 'error'); }
        finally { if (this.fileInput) this.fileInput.value = ''; this.isStreaming = false; this.showUploadOverlay(false); this.updateUI(); }
    }
    formatFileSize(bytes) { if (bytes === 0) return '0 Bytes'; const k = 1024; const sizes = ['Bytes', 'KB', 'MB', 'GB']; const i = Math.floor(Math.log(bytes) / Math.log(k)); return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]; }
    async sendAIOpsRequest(loadingMessageElement) {
        try { const response = await fetch(`${this.apiBaseUrl}/aiops`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ session_id: this.sessionId }) });
            if (!response.ok) throw new Error(`HTTP错误: ${response.status}`); let fullResponse = '';
            const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = '';
            try { while (true) { const { done, value } = await reader.read();
                if (done) { if (fullResponse) this.updateAIOpsMessage(loadingMessageElement, fullResponse, []); break; }
                buffer += decoder.decode(value, { stream: true }); const lines = buffer.split('\n'); buffer = lines.pop() || '';
                for (const line of lines) { if (line.trim() === '') continue;
                    if (line.startsWith('event:')) continue; else if (line.startsWith('data:')) {
                        const rawData = line.substring(5).trim();
                        try { const sseMessage = JSON.parse(rawData); if (sseMessage && sseMessage.type) {
                            if (sseMessage.type === 'content') fullResponse += sseMessage.data || '';
                            else if (sseMessage.type === 'plan') fullResponse += `\n\n## 📋 执行计划\n${sseMessage.message}\n\n`;
                            else if (sseMessage.type === 'step_complete') fullResponse += `\n✅ ${sseMessage.message}\n`;
                            else if (sseMessage.type === 'status') fullResponse += `\n⏳ ${sseMessage.message}\n`;
                            else if (sseMessage.type === 'report') fullResponse += `\n\n## 🎯 诊断报告\n\n${sseMessage.report || ''}\n`;
                            else if (sseMessage.type === 'complete' || sseMessage.type === 'done') { if (sseMessage.response) fullResponse += `\n\n${sseMessage.response}`; this.updateAIOpsMessage(loadingMessageElement, fullResponse, []); return; }
                            else if (sseMessage.type === 'error') throw new Error(sseMessage.data || sseMessage.message || '智能运维分析失败');
                            if (loadingMessageElement) this.updateAIOpsStreamContent(loadingMessageElement, fullResponse);
                        } } catch (e) { if (e.message.includes('智能运维')) throw e; fullResponse += rawData; if (loadingMessageElement) this.updateAIOpsStreamContent(loadingMessageElement, fullResponse); }
                    }
                }
            } } finally { reader.releaseLock(); }
        } catch (error) { throw error; }
    }
    updateAIOpsStreamContent(messageElement, content) { if (!messageElement) return; messageElement.classList.add('aiops-message'); const wrapper = messageElement.querySelector('.message-content-wrapper'); if (wrapper) { let mc = wrapper.querySelector('.message-content'); if (!mc) { mc = document.createElement('div'); mc.className = 'message-content'; wrapper.appendChild(mc); } mc.textContent = content; this.scrollToBottom(); } }
    updateAIOpsMessage(messageElement, response, details) {
        if (!messageElement) return this.addAIOpsMessage(response, details);
        messageElement.classList.add('aiops-message'); const wrapper = messageElement.querySelector('.message-content-wrapper'); if (!wrapper) return;
        const mc = wrapper.querySelector('.message-content'); if (!mc) return; mc.classList.remove('loading-message-content'); mc.textContent = '';
        if (details && details.length > 0) { let dc = messageElement.querySelector('.aiops-details');
            if (!dc) { dc = document.createElement('div'); dc.className = 'aiops-details'; wrapper.insertBefore(dc, mc); } else dc.innerHTML = '';
            const toggle = document.createElement('div'); toggle.className = 'details-toggle'; toggle.innerHTML = `<svg class="toggle-icon" viewBox="0 0 24 24" fill="none"><path d="M9 18L15 12L9 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg><span>查看详细步骤 (${details.length}条)</span>`;
            const content = document.createElement('div'); content.className = 'details-content';
            details.forEach((d, i) => { const item = document.createElement('div'); item.className = 'detail-item'; item.innerHTML = `<strong>步骤 ${i + 1}:</strong> ${this.escapeHtml(d)}`; content.appendChild(item); });
            toggle.addEventListener('click', () => { content.classList.toggle('expanded'); toggle.classList.toggle('expanded'); });
            dc.appendChild(toggle); dc.appendChild(content); }
        mc.innerHTML = this.renderMarkdown(response); this.highlightCodeBlocks(mc);
        this.currentChatHistory.push({ type: 'assistant', content: response, timestamp: new Date().toISOString() }); this.scrollToBottom(); return messageElement;
    }
    addAIOpsMessage(response, details) {
        const div = document.createElement('div'); div.className = 'message assistant aiops-message';
        const avatar = document.createElement('div'); avatar.className = 'message-avatar'; avatar.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" fill="white"/></svg>'; div.appendChild(avatar);
        const wrapper = document.createElement('div'); wrapper.className = 'message-content-wrapper';
        if (details && details.length > 0) { const dc = document.createElement('div'); dc.className = 'aiops-details'; const toggle = document.createElement('div'); toggle.className = 'details-toggle'; toggle.innerHTML = `<svg class="toggle-icon" viewBox="0 0 24 24" fill="none"><path d="M9 18L15 12L9 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg><span>查看详细步骤 (${details.length}条)</span>`; const content = document.createElement('div'); content.className = 'details-content'; details.forEach((d, i) => { const item = document.createElement('div'); item.className = 'detail-item'; item.innerHTML = `<strong>步骤 ${i + 1}:</strong> ${this.escapeHtml(d)}`; content.appendChild(item); }); toggle.addEventListener('click', () => { content.classList.toggle('expanded'); toggle.classList.toggle('expanded'); }); dc.appendChild(toggle); dc.appendChild(content); wrapper.appendChild(dc); }
        const mc = document.createElement('div'); mc.className = 'message-content'; mc.innerHTML = this.renderMarkdown(response); this.highlightCodeBlocks(mc); wrapper.appendChild(mc); div.appendChild(wrapper);
        if (this.chatMessages) { this.chatMessages.appendChild(div); this.scrollToBottom(); }
        return div;
    }
    escapeHtml(text) { const div = document.createElement('div'); div.textContent = text; return div.innerHTML; }
    async triggerAIOps() {
        if (this.isStreaming) { this.showNotification('请等待当前操作完成', 'warning'); return; }
        this.newChat(); const loadingMessage = this.addLoadingMessage('分析中...'); this.currentAIOpsMessage = loadingMessage;
        this.isStreaming = true; this.updateUI();
        try { await this.sendAIOpsRequest(loadingMessage); }
        catch (error) { if (loadingMessage) { const mc = loadingMessage.querySelector('.message-content'); if (mc) mc.textContent = '抱歉，智能运维分析时出现错误：' + error.message; } }
        finally { this.isStreaming = false; this.currentAIOpsMessage = null; this.updateUI(); }
    }
    showLoadingOverlay(show) { if (this.loadingOverlay) { if (show) { this.loadingOverlay.style.display = 'flex'; document.body.style.overflow = 'hidden'; } else { this.loadingOverlay.style.display = 'none'; document.body.style.overflow = ''; } } }
    showUploadOverlay(show, fileName = '') { if (this.loadingOverlay) { if (show) { this.loadingOverlay.style.display = 'flex'; const lt = this.loadingOverlay.querySelector('.loading-text'); const ls = this.loadingOverlay.querySelector('.loading-subtext'); if (lt) lt.textContent = '正在上传文件...'; if (ls) ls.textContent = fileName ? `上传: ${fileName}` : '请稍候'; document.body.style.overflow = 'hidden'; } else { this.loadingOverlay.style.display = 'none'; document.body.style.overflow = ''; } } }
}

const style = document.createElement('style');
style.textContent = `@keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } } @keyframes slideOut { from { transform: translateX(0); opacity: 1; } to { transform: translateX(100%); opacity: 0; } }`;
document.head.appendChild(style);

document.addEventListener('DOMContentLoaded', () => { new OPSAgentApp(); });