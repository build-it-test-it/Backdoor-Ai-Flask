/**
 * Token usage tracking and agent status functionality
 * Enhanced version with performance metrics integration
 */

class TokenTracker {
    constructor() {
        this.tokenUsage = {
            prompt_tokens: 0,
            completion_tokens: 0,
            total_tokens: 0
        };
        this.agentStatus = {
            ready: false,
            api_key_set: false,
            initialized: false
        };
        this.lastUpdateTime = null;
        this.updateInterval = null;
    }

    /**
     * Initialize the token tracker
     */
    async init() {
        // Get initial token usage
        await this.updateTokenUsage();
        
        // Get initial agent status
        await this.updateAgentStatus();
        
        // Set up automatic updates
        this.updateInterval = setInterval(async () => {
            await this.updateTokenUsage();
            await this.updateAgentStatus();
        }, 30000); // Update every 30 seconds
        
        return true;
    }

    /**
     * Update token usage from the API
     */
    async updateTokenUsage() {
        try {
            const response = await fetch('/api/token-usage');
            const data = await response.json();
            
            if (data.error) {
                console.error('Error getting token usage:', data.error);
                return false;
            }
            
            this.tokenUsage = data.token_usage;
            this.lastUpdateTime = new Date();
            
            // Update UI displays
            this.updateTokenDisplay();
            this.updateNavbarTokenCounter();
            
            // Update performance tracker if available
            if (window.performanceTracker) {
                window.performanceTracker.tokenUsage = this.tokenUsage;
            }
            
            return true;
        } catch (error) {
            console.error('Error getting token usage:', error);
            return false;
        }
    }

    /**
     * Update agent status from the API
     */
    async updateAgentStatus() {
        try {
            const response = await fetch('/api/agent-status');
            const data = await response.json();
            
            if (data.error) {
                console.error('Error getting agent status:', data.error);
                return false;
            }
            
            this.agentStatus = data.status;
            this.updateAgentStatusDisplay();
            return true;
        } catch (error) {
            console.error('Error getting agent status:', error);
            return false;
        }
    }

    /**
     * Update the token usage display in sidebar
     */
    updateTokenDisplay() {
        // Find token usage displays in sidebar
        const tokenUsageEl = document.getElementById('token-usage');
        if (!tokenUsageEl) return;
        
        // Create or update token usage display
        tokenUsageEl.innerHTML = `
            <div class="token-usage-title">
                <i class="fas fa-microchip"></i> Token Usage
            </div>
            <div class="token-usage-stats">
                <div class="token-stat">
                    <span class="token-label">
                        <i class="fas fa-arrow-right text-primary"></i> Prompt tokens:
                    </span>
                    <span class="token-value">${this.tokenUsage.prompt_tokens.toLocaleString()}</span>
                </div>
                <div class="token-stat">
                    <span class="token-label">
                        <i class="fas fa-arrow-left text-success"></i> Completion tokens:
                    </span>
                    <span class="token-value">${this.tokenUsage.completion_tokens.toLocaleString()}</span>
                </div>
                <div class="token-stat total">
                    <span class="token-label">
                        <i class="fas fa-calculator"></i> Total tokens:
                    </span>
                    <span class="token-value">${this.tokenUsage.total_tokens.toLocaleString()}</span>
                </div>
            </div>
        `;
        
        // Add timestamp if available
        if (this.lastUpdateTime) {
            const timeEl = document.createElement('div');
            timeEl.className = 'token-timestamp text-muted small mt-2 text-end';
            timeEl.textContent = `Last updated: ${this.lastUpdateTime.toLocaleTimeString()}`;
            tokenUsageEl.appendChild(timeEl);
        }
    }
    
    /**
     * Update the token counter in navbar
     */
    updateNavbarTokenCounter() {
        const counterEl = document.getElementById('total-tokens');
        if (counterEl) {
            counterEl.textContent = this.tokenUsage.total_tokens.toLocaleString();
            
            // Animate the counter to draw attention to it when it changes
            counterEl.classList.add('token-updated');
            setTimeout(() => {
                counterEl.classList.remove('token-updated');
            }, 1000);
        }
    }

    /**
     * Update the agent status display in the UI
     */
    updateAgentStatusDisplay() {
        // Update navbar status indicator
        const statusIndicator = document.getElementById('agent-status');
        if (statusIndicator) {
            if (this.agentStatus.ready) {
                statusIndicator.innerHTML = '<span class="badge bg-success"><i class="fas fa-check-circle me-1"></i>Ready</span>';
                statusIndicator.title = 'Agent is ready to assist';
            } else {
                let statusText = 'Not Ready';
                let statusClass = 'bg-danger';
                let statusIcon = 'times-circle';
                let statusTitle = 'Agent is not ready';
                
                if (!this.agentStatus.api_key_set) {
                    statusText = 'API Key Missing';
                    statusIcon = 'exclamation-circle';
                    statusTitle = 'API key is not set';
                } else if (!this.agentStatus.initialized) {
                    statusText = 'Initializing';
                    statusClass = 'bg-warning';
                    statusIcon = 'sync fa-spin';
                    statusTitle = 'Agent is initializing';
                }
                
                statusIndicator.innerHTML = `<span class="badge ${statusClass}"><i class="fas fa-${statusIcon} me-1"></i>${statusText}</span>`;
                statusIndicator.title = statusTitle;
            }
        }
        
        // Update detailed status display
        const statusDot = document.getElementById('agent-status-dot');
        const statusText = document.getElementById('agent-status-text');
        
        if (statusDot && statusText) {
            if (this.agentStatus.ready) {
                statusDot.className = 'agent-status-dot ready';
                statusText.textContent = 'Agent is ready';
                
                // Show typing indicator if agent is ready and we're waiting for a response
                const typingIndicator = document.getElementById('typing-indicator');
                if (typingIndicator && this.isWaitingForResponse) {
                    typingIndicator.classList.remove('d-none');
                }
            } else {
                if (!this.agentStatus.api_key_set) {
                    statusDot.className = 'agent-status-dot error';
                    statusText.textContent = 'API Key Missing';
                } else if (!this.agentStatus.initialized) {
                    statusDot.className = 'agent-status-dot';
                    statusText.textContent = 'Initializing...';
                } else {
                    statusDot.className = 'agent-status-dot error';
                    statusText.textContent = 'Agent is not ready';
                }
                
                // Hide typing indicator if agent is not ready
                const typingIndicator = document.getElementById('typing-indicator');
                if (typingIndicator) {
                    typingIndicator.classList.add('d-none');
                }
            }
        }
    }
    
    /**
     * Set waiting for response state
     * @param {boolean} isWaiting - Whether we're waiting for a response
     */
    setWaitingForResponse(isWaiting) {
        this.isWaitingForResponse = isWaiting;
        
        // Show or hide typing indicator
        const typingIndicator = document.getElementById('typing-indicator');
        const typingIndicatorMain = document.getElementById('typing-indicator-main');
        
        if (typingIndicator) {
            if (isWaiting && this.agentStatus.ready) {
                typingIndicator.classList.remove('d-none');
            } else {
                typingIndicator.classList.add('d-none');
            }
        }
        
        if (typingIndicatorMain) {
            if (isWaiting) {
                typingIndicatorMain.classList.remove('d-none');
            } else {
                typingIndicatorMain.classList.add('d-none');
            }
        }
    }
}

// Initialize the token tracker
const tokenTracker = new TokenTracker();

// Initialize when the DOM is loaded
document.addEventListener('DOMContentLoaded', async () => {
    await tokenTracker.init();
    
    // Expose to window for access from other scripts
    window.tokenTracker = tokenTracker;
});