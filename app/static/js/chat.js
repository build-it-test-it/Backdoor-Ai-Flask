// Enhanced Chat functionality for Backdoor AI

document.addEventListener('DOMContentLoaded', function() {
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');
    const chatMessages = document.getElementById('chat-messages');
    const apiKeyForm = document.getElementById('api-key-form');
    const tokenUsageContainer = document.getElementById('token-usage-container');
    const agentStatusContainer = document.getElementById('agent-status-container');
    const darkModeToggle = document.getElementById('dark-mode-toggle');
    
    // Initialize highlight.js for code syntax highlighting
    hljs.highlightAll();
    
    // Initialize token usage display
    updateTokenUsage();
    
    // Initialize agent status
    updateAgentStatus();
    
    // Set up polling for agent status and token usage
    setInterval(updateAgentStatus, 10000); // Every 10 seconds
    setInterval(updateTokenUsage, 30000);  // Every 30 seconds
    
    // Handle dark mode toggle
    if (darkModeToggle) {
        darkModeToggle.addEventListener('click', function() {
            document.body.classList.toggle('dark-mode');
            
            // Save preference to localStorage
            if (document.body.classList.contains('dark-mode')) {
                localStorage.setItem('darkMode', 'enabled');
                darkModeToggle.innerHTML = '<i class="fas fa-sun"></i>';
            } else {
                localStorage.setItem('darkMode', 'disabled');
                darkModeToggle.innerHTML = '<i class="fas fa-moon"></i>';
            }
        });
        
        // Check for saved preference
        if (localStorage.getItem('darkMode') === 'enabled') {
            document.body.classList.add('dark-mode');
            darkModeToggle.innerHTML = '<i class="fas fa-sun"></i>';
        } else {
            darkModeToggle.innerHTML = '<i class="fas fa-moon"></i>';
        }
    }
    
    // Handle chat form submission
    if (chatForm) {
        chatForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const userMessage = userInput.value.trim();
            if (userMessage === '') return;
            
            // Add user message to chat
            addMessage('user', userMessage);
            
            // Clear input field
            userInput.value = '';
            
            // Show typing indicator
            showTypingIndicator();
            
            // Send message to backend
            fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: userMessage }),
            })
            .then(response => response.json())
            .then(data => {
                // Hide typing indicator
                hideTypingIndicator();
                
                if (data.error) {
                    addMessage('assistant', `Error: ${data.error}`);
                } else {
                    addMessage('assistant', data.response);
                    
                    // Apply syntax highlighting to code blocks
                    document.querySelectorAll('pre code').forEach((block) => {
                        hljs.highlightElement(block);
                    });
                    
                    // Update token usage after response
                    updateTokenUsage();
                }
            })
            .catch(error => {
                // Hide typing indicator
                hideTypingIndicator();
                
                console.error('Error:', error);
                addMessage('assistant', 'Sorry, there was an error processing your request.');
            });
        });
    }
    
    // Handle API key form submission
    if (apiKeyForm) {
        apiKeyForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const apiKey = document.getElementById('api-key').value.trim();
            if (apiKey === '') return;
            
            // Show loading state
            const submitBtn = apiKeyForm.querySelector('button[type="submit"]');
            const originalBtnText = submitBtn.innerHTML;
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Setting API Key...';
            
            fetch('/api/set-api-key', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ api_key: apiKey }),
            })
            .then(response => response.json())
            .then(data => {
                // Reset button state
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalBtnText;
                
                if (data.success) {
                    // Show success message
                    const alertContainer = document.getElementById('alert-container');
                    alertContainer.innerHTML = `
                        <div class="alert alert-success alert-dismissible fade show slide-in" role="alert">
                            <i class="fas fa-check-circle me-2"></i> API key set successfully!
                            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                        </div>
                    `;
                    
                    // Clear input field
                    document.getElementById('api-key').value = '';
                    
                    // Update agent status
                    updateAgentStatus();
                } else {
                    // Show error message
                    const alertContainer = document.getElementById('alert-container');
                    alertContainer.innerHTML = `
                        <div class="alert alert-danger alert-dismissible fade show slide-in" role="alert">
                            <i class="fas fa-exclamation-circle me-2"></i> Error: ${data.error}
                            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                        </div>
                    `;
                }
            })
            .catch(error => {
                // Reset button state
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalBtnText;
                
                console.error('Error:', error);
                // Show error message
                const alertContainer = document.getElementById('alert-container');
                alertContainer.innerHTML = `
                    <div class="alert alert-danger alert-dismissible fade show slide-in" role="alert">
                        <i class="fas fa-exclamation-triangle me-2"></i> Error: Could not connect to server
                        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                    </div>
                `;
            });
        });
    }
    
    // Function to add a message to the chat
    function addMessage(sender, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message p-3 mb-3`;
        
        // Ensure content is a string
        if (content === null || content === undefined) {
            content = '';
        }
        
        if (typeof content !== 'string') {
            content = String(content);
        }
        
        // Convert markdown to HTML if it's an assistant message
        if (sender === 'assistant') {
            content = marked.parse(content);
        }
        
        messageDiv.innerHTML = `
            <div class="${sender === 'assistant' ? 'markdown-content' : ''}">${content}</div>
            <div class="message-time text-muted small">${new Date().toLocaleTimeString()}</div>
        `;
        
        chatMessages.appendChild(messageDiv);
        
        // Scroll to bottom of chat
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    // Function to show typing indicator
    function showTypingIndicator() {
        const typingIndicator = document.getElementById('typing-indicator');
        if (typingIndicator) {
            typingIndicator.style.display = 'block';
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    }
    
    // Function to hide typing indicator
    function hideTypingIndicator() {
        const typingIndicator = document.getElementById('typing-indicator');
        if (typingIndicator) {
            typingIndicator.style.display = 'none';
        }
    }
    
    // Function to update token usage display
    function updateTokenUsage() {
        if (!tokenUsageContainer) return;
        
        fetch('/api/token-usage')
            .then(response => response.json())
            .then(data => {
                if (data.success && data.token_usage) {
                    const usage = data.token_usage;
                    tokenUsageContainer.innerHTML = `
                        <div class="token-usage-title">Token Usage</div>
                        <div class="token-usage-stats">
                            <div class="token-stat">
                                <div class="token-value">${usage.prompt_tokens.toLocaleString()}</div>
                                <div class="token-label">Prompt</div>
                            </div>
                            <div class="token-stat">
                                <div class="token-value">${usage.completion_tokens.toLocaleString()}</div>
                                <div class="token-label">Completion</div>
                            </div>
                            <div class="token-stat">
                                <div class="token-value">${usage.total_tokens.toLocaleString()}</div>
                                <div class="token-label">Total</div>
                            </div>
                        </div>
                    `;
                }
            })
            .catch(error => {
                console.error('Error fetching token usage:', error);
            });
    }
    
    // Function to update agent status
    function updateAgentStatus() {
        if (!agentStatusContainer) return;
        
        fetch('/api/agent-status')
            .then(response => response.json())
            .then(data => {
                if (data.success && data.status) {
                    const status = data.status;
                    let statusClass = status.ready ? 'ready' : 'warning';
                    let statusText = status.ready ? 'Agent Ready' : 'Agent Not Ready';
                    
                    if (!status.api_key_set) {
                        statusClass = 'error';
                        statusText = 'API Key Missing';
                    } else if (!status.initialized) {
                        statusText = 'Initializing...';
                    }
                    
                    agentStatusContainer.innerHTML = `
                        <div class="status-indicator ${statusClass}"></div>
                        <div class="status-text">${statusText}</div>
                    `;
                }
            })
            .catch(error => {
                console.error('Error fetching agent status:', error);
                agentStatusContainer.innerHTML = `
                    <div class="status-indicator error"></div>
                    <div class="status-text">Connection Error</div>
                `;
            });
    }
});