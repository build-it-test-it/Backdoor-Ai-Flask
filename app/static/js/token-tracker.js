/**
 * Token usage tracking and agent status functionality
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
            this.updateTokenDisplay();
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
     * Update the token usage display in the UI
     */
    updateTokenDisplay() {
        const tokenDisplay = document.getElementById('token-usage');
        if (!tokenDisplay) return;
        
        tokenDisplay.innerHTML = `
            <div class="d-flex justify-content-between">
                <span>Prompt tokens:</span>
                <span>${this.tokenUsage.prompt_tokens.toLocaleString()}</span>
            </div>
            <div class="d-flex justify-content-between">
                <span>Completion tokens:</span>
                <span>${this.tokenUsage.completion_tokens.toLocaleString()}</span>
            </div>
            <div class="d-flex justify-content-between fw-bold">
                <span>Total tokens:</span>
                <span>${this.tokenUsage.total_tokens.toLocaleString()}</span>
            </div>
        `;
    }

    /**
     * Update the agent status display in the UI
     */
    updateAgentStatusDisplay() {
        const statusIndicator = document.getElementById('agent-status');
        if (!statusIndicator) return;
        
        if (this.agentStatus.ready) {
            statusIndicator.innerHTML = '<span class="badge bg-success">Ready</span>';
            statusIndicator.title = 'Agent is ready to assist';
            
            // Also update the typing indicator
            const typingIndicator = document.getElementById('typing-indicator');
            if (typingIndicator) {
                typingIndicator.classList.remove('d-none');
            }
        } else {
            let statusText = 'Not Ready';
            let statusClass = 'bg-danger';
            let statusTitle = 'Agent is not ready';
            
            if (!this.agentStatus.api_key_set) {
                statusText = 'API Key Missing';
                statusTitle = 'Together AI API key is not set';
            } else if (!this.agentStatus.initialized) {
                statusText = 'Initializing';
                statusClass = 'bg-warning';
                statusTitle = 'Agent is initializing';
            }
            
            statusIndicator.innerHTML = `<span class="badge ${statusClass}">${statusText}</span>`;
            statusIndicator.title = statusTitle;
            
            // Hide the typing indicator
            const typingIndicator = document.getElementById('typing-indicator');
            if (typingIndicator) {
                typingIndicator.classList.add('d-none');
            }
        }
    }
}

// Initialize the token tracker
const tokenTracker = new TokenTracker();

// Initialize when the DOM is loaded
document.addEventListener('DOMContentLoaded', async () => {
    await tokenTracker.init();
});