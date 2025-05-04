/**
 * Performance Dashboard JavaScript
 * Manages performance metrics, charts, and data visualization
 */

class PerformanceTracker {
    constructor() {
        this.tokenStats = {
            prompt_tokens: 0,
            completion_tokens: 0,
            total_tokens: 0,
            changes: {
                prompt_tokens: 0,
                completion_tokens: 0,
                total_tokens: 0
            }
        };
        this.metrics = {
            avg_response_time: 0
        };
        this.charts = {};
        this.chartData = {
            dates: [],
            prompt_tokens: [],
            completion_tokens: [],
            response_times: []
        };
        this.modelUsage = [];
        this.recentUsage = [];
        this.currentPeriod = 7; // Default to 7 days
    }

    /**
     * Initialize the performance dashboard
     */
    async init() {
        this.showLoading(true);

        try {
            // Fetch initial data
            await this.fetchTokenStats();
            await this.fetchPerformanceMetrics();
            
            // Initialize charts
            this.initCharts();
            
            // Update the UI
            this.updateStatsCards();
            this.updateRecentUsageTable();
            
            // Set up event listeners
            this.setupEventListeners();
            
            // Hide loading overlay
            this.showLoading(false);
        } catch (error) {
            console.error('Error initializing performance dashboard:', error);
            this.showLoading(false);
        }
    }

    /**
     * Show or hide loading overlay
     */
    showLoading(show) {
        const loadingOverlay = document.getElementById('loading-overlay');
        if (loadingOverlay) {
            if (show) {
                loadingOverlay.classList.remove('d-none');
            } else {
                loadingOverlay.classList.add('d-none');
            }
        }
    }

    /**
     * Fetch token statistics from the API
     */
    async fetchTokenStats() {
        try {
            const response = await fetch('/api/performance/token-stats');
            const data = await response.json();
            
            if (data.success) {
                this.tokenStats = data.token_stats;
                this.chartData = data.chart_data;
                this.modelUsage = data.model_usage;
                this.recentUsage = data.recent_usage;
                return true;
            } else {
                console.error('Error fetching token stats:', data.error);
                return false;
            }
        } catch (error) {
            console.error('Error fetching token stats:', error);
            return false;
        }
    }

    /**
     * Fetch performance metrics from the API
     */
    async fetchPerformanceMetrics() {
        try {
            const response = await fetch('/api/performance/metrics');
            const data = await response.json();
            
            if (data.success) {
                this.metrics = data.metrics;
                if (data.chart_data) {
                    this.chartData.response_times = data.chart_data.response_times;
                }
                return true;
            } else {
                console.error('Error fetching performance metrics:', data.error);
                return false;
            }
        } catch (error) {
            console.error('Error fetching performance metrics:', error);
            return false;
        }
    }

    /**
     * Initialize all charts
     */
    initCharts() {
        // Token usage chart
        const tokenUsageCtx = document.getElementById('tokenUsageChart').getContext('2d');
        if (tokenUsageCtx) {
            this.charts.tokenUsage = new Chart(tokenUsageCtx, {
                type: 'line',
                data: {
                    labels: this.chartData.dates,
                    datasets: [
                        {
                            label: 'Prompt Tokens',
                            data: this.chartData.prompt_tokens,
                            borderColor: 'rgba(59, 130, 246, 0.8)',
                            backgroundColor: 'rgba(59, 130, 246, 0.1)',
                            borderWidth: 2,
                            fill: true,
                            tension: 0.4
                        },
                        {
                            label: 'Completion Tokens',
                            data: this.chartData.completion_tokens,
                            borderColor: 'rgba(16, 185, 129, 0.8)',
                            backgroundColor: 'rgba(16, 185, 129, 0.1)',
                            borderWidth: 2,
                            fill: true,
                            tension: 0.4
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'top',
                        },
                        tooltip: {
                            mode: 'index',
                            intersect: false,
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                callback: function(value) {
                                    return value.toLocaleString();
                                }
                            }
                        },
                        x: {
                            grid: {
                                display: false
                            }
                        }
                    }
                }
            });
        }

        // Model distribution chart
        const modelDistributionCtx = document.getElementById('modelDistributionChart').getContext('2d');
        if (modelDistributionCtx && this.modelUsage.length > 0) {
            // Prepare data for the chart
            const labels = this.modelUsage.map(item => item.model);
            const data = this.modelUsage.map(item => item.total_tokens);
            
            // Generate colors based on the number of models
            const colors = this.generateColors(labels.length);
            
            this.charts.modelDistribution = new Chart(modelDistributionCtx, {
                type: 'doughnut',
                data: {
                    labels: labels,
                    datasets: [{
                        data: data,
                        backgroundColor: colors,
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'right',
                            labels: {
                                boxWidth: 12,
                                font: {
                                    size: 10
                                }
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const value = context.raw;
                                    const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                    const percentage = Math.round((value / total) * 100);
                                    return `${context.label}: ${value.toLocaleString()} tokens (${percentage}%)`;
                                }
                            }
                        }
                    },
                    cutout: '65%'
                }
            });
        } else if (modelDistributionCtx) {
            // If no model usage data, show a message
            this.charts.modelDistribution = new Chart(modelDistributionCtx, {
                type: 'doughnut',
                data: {
                    labels: ['No Data'],
                    datasets: [{
                        data: [1],
                        backgroundColor: ['#e5e7eb'],
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            enabled: false
                        }
                    },
                    cutout: '65%'
                }
            });
        }
    }

    /**
     * Generate an array of colors for charts
     */
    generateColors(count) {
        const baseColors = [
            'rgba(59, 130, 246, 0.8)',   // Blue
            'rgba(16, 185, 129, 0.8)',   // Green
            'rgba(245, 158, 11, 0.8)',   // Yellow
            'rgba(239, 68, 68, 0.8)',    // Red
            'rgba(139, 92, 246, 0.8)',   // Purple
            'rgba(236, 72, 153, 0.8)',   // Pink
            'rgba(75, 85, 99, 0.8)'      // Gray
        ];
        
        // If we have fewer colors than needed, repeat the base colors
        const colors = [];
        for (let i = 0; i < count; i++) {
            colors.push(baseColors[i % baseColors.length]);
        }
        
        return colors;
    }

    /**
     * Update token stats cards
     */
    updateStatsCards() {
        // Update prompt tokens
        const promptTokensEl = document.getElementById('prompt-tokens');
        const promptTokensChangeEl = document.getElementById('prompt-tokens-change');
        if (promptTokensEl) {
            promptTokensEl.textContent = this.tokenStats.prompt_tokens.toLocaleString();
        }
        if (promptTokensChangeEl && this.tokenStats.changes) {
            this.updateChangeIndicator(promptTokensChangeEl, this.tokenStats.changes.prompt_tokens);
        }
        
        // Update completion tokens
        const completionTokensEl = document.getElementById('completion-tokens');
        const completionTokensChangeEl = document.getElementById('completion-tokens-change');
        if (completionTokensEl) {
            completionTokensEl.textContent = this.tokenStats.completion_tokens.toLocaleString();
        }
        if (completionTokensChangeEl && this.tokenStats.changes) {
            this.updateChangeIndicator(completionTokensChangeEl, this.tokenStats.changes.completion_tokens);
        }
        
        // Update total tokens
        const totalTokensEl = document.getElementById('total-tokens-display');
        const totalTokensChangeEl = document.getElementById('total-tokens-change');
        if (totalTokensEl) {
            totalTokensEl.textContent = this.tokenStats.total_tokens.toLocaleString();
        }
        if (totalTokensChangeEl && this.tokenStats.changes) {
            this.updateChangeIndicator(totalTokensChangeEl, this.tokenStats.changes.total_tokens);
        }
        
        // Update response time
        const avgResponseTimeEl = document.getElementById('avg-response-time');
        const responseTimeBarEl = document.getElementById('response-time-bar');
        if (avgResponseTimeEl) {
            avgResponseTimeEl.textContent = this.metrics.avg_response_time;
        }
        if (responseTimeBarEl) {
            // Set the width of the progress bar based on some scale
            // Let's assume a 5-second response time is 100%
            const percentage = Math.min(100, (this.metrics.avg_response_time / 5) * 100);
            responseTimeBarEl.style.width = `${percentage}%`;
            
            // Change color based on response time
            if (this.metrics.avg_response_time < 1) {
                responseTimeBarEl.className = 'progress-bar bg-success';
            } else if (this.metrics.avg_response_time < 3) {
                responseTimeBarEl.className = 'progress-bar bg-warning';
            } else {
                responseTimeBarEl.className = 'progress-bar bg-danger';
            }
        }
    }

    /**
     * Update change indicator with appropriate styling
     */
    updateChangeIndicator(element, change) {
        if (!element) return;
        
        // If change is 0 or not available, show as neutral
        if (!change && change !== 0) {
            element.textContent = '-';
            element.className = 'badge rounded-pill token-change neutral';
            return;
        }
        
        const isPositive = change > 0;
        const icon = isPositive ? '↑' : '↓';
        
        element.textContent = `${icon} ${Math.abs(change)}%`;
        
        if (change === 0) {
            element.className = 'badge rounded-pill token-change neutral';
        } else if (isPositive) {
            element.className = 'badge rounded-pill token-change positive';
        } else {
            element.className = 'badge rounded-pill token-change negative';
        }
    }

    /**
     * Update recent usage table
     */
    updateRecentUsageTable() {
        const tableBody = document.getElementById('recent-usage-table');
        if (!tableBody) return;
        
        // Clear existing rows
        tableBody.innerHTML = '';
        
        // Check if we have data
        if (!this.recentUsage || this.recentUsage.length === 0) {
            const row = document.createElement('tr');
            row.innerHTML = `<td colspan="6" class="text-center py-4">No usage data available</td>`;
            tableBody.appendChild(row);
            return;
        }
        
        // Add rows to the table
        this.recentUsage.forEach(usage => {
            const row = document.createElement('tr');
            
            // Format the timestamp
            const timestamp = new Date(usage.timestamp);
            const formattedTime = timestamp.toLocaleString();
            
            // Format response time
            const responseTime = usage.response_time ? `${usage.response_time.toFixed(2)}s` : '-';
            
            row.innerHTML = `
                <td>${formattedTime}</td>
                <td>${usage.model}</td>
                <td>${usage.prompt_tokens.toLocaleString()}</td>
                <td>${usage.completion_tokens.toLocaleString()}</td>
                <td>${usage.total.toLocaleString()}</td>
                <td>${responseTime}</td>
            `;
            tableBody.appendChild(row);
        });
    }

    /**
     * Set up event listeners
     */
    setupEventListeners() {
        // Set up refresh button
        const refreshBtn = document.getElementById('refresh-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', async () => {
                this.showLoading(true);
                await this.fetchTokenStats();
                await this.fetchPerformanceMetrics();
                this.updateStatsCards();
                this.updateRecentUsageTable();
                this.updateCharts();
                this.showLoading(false);
            });
        }
        
        // Set up period buttons
        const periodButtons = document.querySelectorAll('[data-period]');
        periodButtons.forEach(button => {
            button.addEventListener('click', async (e) => {
                // Update active state
                periodButtons.forEach(btn => btn.classList.remove('active'));
                button.classList.add('active');
                
                // Update current period
                this.currentPeriod = parseInt(button.dataset.period);
                
                // Fetch new data and update chart
                this.showLoading(true);
                await this.fetchTokenStats();
                await this.fetchPerformanceMetrics();
                this.updateCharts();
                this.showLoading(false);
            });
        });
    }

    /**
     * Update charts with new data
     */
    updateCharts() {
        // Update token usage chart
        if (this.charts.tokenUsage) {
            this.charts.tokenUsage.data.labels = this.chartData.dates;
            this.charts.tokenUsage.data.datasets[0].data = this.chartData.prompt_tokens;
            this.charts.tokenUsage.data.datasets[1].data = this.chartData.completion_tokens;
            this.charts.tokenUsage.update();
        }
        
        // Update model distribution chart
        if (this.charts.modelDistribution && this.modelUsage.length > 0) {
            const labels = this.modelUsage.map(item => item.model);
            const data = this.modelUsage.map(item => item.total_tokens);
            const colors = this.generateColors(labels.length);
            
            this.charts.modelDistribution.data.labels = labels;
            this.charts.modelDistribution.data.datasets[0].data = data;
            this.charts.modelDistribution.data.datasets[0].backgroundColor = colors;
            this.charts.modelDistribution.update();
        }
    }
}

// Initialize the performance tracker when the DOM is loaded
document.addEventListener('DOMContentLoaded', async () => {
    const performanceTracker = new PerformanceTracker();
    await performanceTracker.init();
    
    // Expose to window for access from other scripts
    window.performanceTracker = performanceTracker;
    
    // If token tracker exists, sync the data
    if (window.tokenTracker) {
        window.tokenTracker.tokenUsage = performanceTracker.tokenStats;
    }
});
