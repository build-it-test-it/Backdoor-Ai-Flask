/**
 * Ollama integration for Backdoor AI
 * This file contains JavaScript functions for managing Ollama LLM settings
 */

// Check Ollama status and display it
async function checkOllamaStatus() {
    try {
        const response = await fetch('/api/ollama/status');
        const data = await response.json();
        
        if (data.status === 'success') {
            // Update status indicators
            const isInstalled = data.is_installed;
            const isRunning = data.is_running;
            
            const installedEl = document.getElementById('ollama-installed');
            const runningEl = document.getElementById('ollama-running');
            const installBtn = document.getElementById('install-ollama');
            const startBtn = document.getElementById('start-ollama');
            
            if (installedEl) {
                installedEl.textContent = isInstalled ? 'Yes' : 'No';
                installedEl.className = isInstalled ? 'text-success' : 'text-danger';
            }
            
            if (runningEl) {
                runningEl.textContent = isRunning ? 'Yes' : 'No';
                runningEl.className = isRunning ? 'text-success' : 'text-danger';
            }
            
            // Show appropriate action buttons
            if (installBtn) {
                installBtn.classList.toggle('d-none', isInstalled);
            }
            
            if (startBtn) {
                startBtn.classList.toggle('d-none', !isInstalled || isRunning);
            }
            
            // If Ollama is running, get models
            if (isRunning) {
                await getOllamaModels();
            }
            
            return true;
        } else {
            console.error('Error checking Ollama status:', data.error);
            showToast('Error checking Ollama status', data.error, 'danger');
            return false;
        }
    } catch (error) {
        console.error('Error checking Ollama status:', error);
        showToast('Connection Error', 'Failed to connect to Ollama service', 'danger');
        return false;
    }
}

// Get available Ollama models
async function getOllamaModels() {
    try {
        const modelSelect = document.getElementById('ollama_model');
        if (!modelSelect) return;
        
        // Clear current options except the placeholder
        while (modelSelect.options.length > 1) {
            modelSelect.remove(1);
        }
        
        modelSelect.options[0].text = 'Loading models...';
        
        const response = await fetch('/api/ollama/models');
        const data = await response.json();
        
        // Clear all options
        while (modelSelect.options.length) {
            modelSelect.remove(0);
        }
        
        if (data.status === 'success' && Array.isArray(data.models)) {
            const models = data.models;
            
            // Add placeholder if no models
            if (models.length === 0) {
                const option = document.createElement('option');
                option.value = '';
                option.text = 'No models available';
                option.disabled = true;
                option.selected = true;
                modelSelect.add(option);
                return;
            }
            
            // Group models into installed and recommended
            const installedModels = models.filter(model => model.installed);
            const recommendedModels = models.filter(model => !model.installed && model.recommended);
            
            // Add option groups
            if (installedModels.length > 0) {
                const installedGroup = document.createElement('optgroup');
                installedGroup.label = 'Installed Models';
                
                installedModels.forEach(model => {
                    const option = document.createElement('option');
                    option.value = model.id;
                    option.text = model.id;
                    installedGroup.appendChild(option);
                });
                
                modelSelect.add(installedGroup);
            }
            
            if (recommendedModels.length > 0) {
                const recommendedGroup = document.createElement('optgroup');
                recommendedGroup.label = 'Recommended Models';
                
                recommendedModels.forEach(model => {
                    const option = document.createElement('option');
                    option.value = model.id;
                    option.text = `${model.id} (Not installed)`;
                    option.dataset.recommended = 'true';
                    recommendedGroup.appendChild(option);
                });
                
                modelSelect.add(recommendedGroup);
            }
            
            // Try to select current model if available
            const currentModel = modelSelect.dataset.currentModel || 'llama4:latest';
            let found = false;
            
            for (let i = 0; i < modelSelect.options.length; i++) {
                if (modelSelect.options[i].value === currentModel) {
                    modelSelect.selectedIndex = i;
                    found = true;
                    break;
                }
            }
            
            // If current model not found, select first available model
            if (!found && modelSelect.options.length > 0) {
                for (let i = 0; i < modelSelect.options.length; i++) {
                    if (modelSelect.options[i].value) {
                        modelSelect.selectedIndex = i;
                        break;
                    }
                }
            }
        } else {
            // Add placeholder for error
            const option = document.createElement('option');
            option.value = '';
            option.text = 'Failed to load models';
            option.disabled = true;
            option.selected = true;
            modelSelect.add(option);
            
            if (data.error) {
                console.error('Error loading models:', data.error);
                showToast('Error', `Failed to load Ollama models: ${data.error}`, 'danger');
            }
        }
    } catch (error) {
        console.error('Error loading models:', error);
        
        const modelSelect = document.getElementById('ollama_model');
        if (modelSelect) {
            // Clear options
            while (modelSelect.options.length) {
                modelSelect.remove(0);
            }
            
            // Add error placeholder
            const option = document.createElement('option');
            option.value = '';
            option.text = 'Error loading models';
            option.disabled = true;
            option.selected = true;
            modelSelect.add(option);
        }
        
        showToast('Connection Error', 'Failed to load Ollama models', 'danger');
    }
}

// Install Ollama
async function installOllama() {
    try {
        const button = document.getElementById('install-ollama');
        if (button) {
            button.disabled = true;
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Installing...';
        }
        
        const response = await fetch('/api/ollama/install', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            showToast('Success', 'Ollama installed successfully', 'success');
            await checkOllamaStatus();
        } else if (data.status === 'warning') {
            showToast('Warning', data.message, 'warning');
            
            // Show installation instructions if available
            if (data.instructions) {
                const testResult = document.getElementById('test-result');
                const testOutput = document.getElementById('test-output');
                
                if (testResult && testOutput) {
                    testResult.classList.remove('d-none');
                    testOutput.innerHTML = `<pre>${data.instructions}</pre>`;
                }
            }
            
            await checkOllamaStatus();
        } else {
            showToast('Error', data.error || 'Failed to install Ollama', 'danger');
        }
    } catch (error) {
        console.error('Error installing Ollama:', error);
        showToast('Connection Error', 'Failed to install Ollama', 'danger');
    } finally {
        const button = document.getElementById('install-ollama');
        if (button) {
            button.disabled = false;
            button.innerHTML = '<i class="fas fa-download"></i> Install';
        }
    }
}

// Start Ollama server
async function startOllama() {
    try {
        const button = document.getElementById('start-ollama');
        if (button) {
            button.disabled = true;
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Starting...';
        }
        
        const response = await fetch('/api/ollama/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            showToast('Success', 'Ollama started successfully', 'success');
            await checkOllamaStatus();
        } else {
            showToast('Error', data.error || 'Failed to start Ollama', 'danger');
        }
    } catch (error) {
        console.error('Error starting Ollama:', error);
        showToast('Connection Error', 'Failed to start Ollama', 'danger');
    } finally {
        const button = document.getElementById('start-ollama');
        if (button) {
            button.disabled = false;
            button.innerHTML = '<i class="fas fa-play"></i> Start';
        }
    }
}

// Download Ollama model
async function downloadOllamaModel(modelName) {
    try {
        const button = document.getElementById('download-model');
        const progressContainer = document.getElementById('download-progress-container');
        const progressBar = document.getElementById('download-progress');
        
        if (!modelName) {
            const select = document.getElementById('ollama_model');
            if (select) {
                modelName = select.value;
            }
        }
        
        if (!modelName) {
            showToast('Error', 'No model selected', 'danger');
            return;
        }
        
        // Update UI
        if (button) {
            button.disabled = true;
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Downloading...';
        }
        
        if (progressContainer) {
            progressContainer.classList.remove('d-none');
        }
        
        if (progressBar) {
            progressBar.style.width = '0%';
            progressBar.setAttribute('aria-valuenow', '0');
        }
        
        // Start download
        const response = await fetch(`/api/ollama/models/${modelName}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            showToast('Success', `Model ${modelName} downloaded successfully`, 'success');
            await getOllamaModels();
        } else {
            showToast('Error', data.error || `Failed to download model ${modelName}`, 'danger');
        }
    } catch (error) {
        console.error('Error downloading model:', error);
        showToast('Connection Error', 'Failed to download model', 'danger');
    } finally {
        const button = document.getElementById('download-model');
        const progressContainer = document.getElementById('download-progress-container');
        
        if (button) {
            button.disabled = false;
            button.innerHTML = '<i class="fas fa-download"></i> Download Selected Model';
        }
        
        if (progressContainer) {
            progressContainer.classList.add('d-none');
        }
    }
}

// Test Ollama model
async function testOllamaModel(modelName) {
    try {
        const button = document.getElementById('test-ollama-model');
        const testResult = document.getElementById('test-result');
        const testOutput = document.getElementById('test-output');
        
        if (!modelName) {
            const select = document.getElementById('ollama_model');
            if (select) {
                modelName = select.value;
            }
        }
        
        if (!modelName) {
            showToast('Error', 'No model selected', 'danger');
            return;
        }
        
        // Update UI
        if (button) {
            button.disabled = true;
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Testing...';
        }
        
        if (testResult) {
            testResult.classList.add('d-none');
        }
        
        // Test model
        const response = await fetch('/api/ollama/test', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                model: modelName,
                prompt: 'Hello, I am testing if you are working properly. Please respond with a brief greeting.'
            })
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            if (testResult) testResult.classList.remove('d-none');
            if (testOutput) testOutput.textContent = data.content || 'Test successful but no content returned';
        } else {
            showToast('Error', data.error || 'Test failed', 'danger');
            
            if (testResult) testResult.classList.remove('d-none');
            if (testOutput) testOutput.innerHTML = `<p class="text-danger">Error: ${data.error || 'Test failed'}</p>`;
        }
    } catch (error) {
        console.error('Error testing model:', error);
        showToast('Connection Error', 'Failed to test model', 'danger');
        
        const testResult = document.getElementById('test-result');
        const testOutput = document.getElementById('test-output');
        
        if (testResult) testResult.classList.remove('d-none');
        if (testOutput) testOutput.innerHTML = `<p class="text-danger">Error: ${error.message}</p>`;
    } finally {
        const button = document.getElementById('test-ollama-model');
        if (button) {
            button.disabled = false;
            button.innerHTML = '<i class="fas fa-vial"></i> Test Model';
        }
    }
}

// Initialize Ollama UI components
function initOllamaUI() {
    // Add event listeners for Ollama-related buttons
    const refreshStatusBtn = document.getElementById('refresh-ollama-status');
    const installBtn = document.getElementById('install-ollama');
    const startBtn = document.getElementById('start-ollama');
    const refreshModelsBtn = document.getElementById('refresh-ollama-models');
    const downloadModelBtn = document.getElementById('download-model');
    const testModelBtn = document.getElementById('test-ollama-model');
    const providerSelect = document.getElementById('llm_provider');
    
    // Check initial status
    checkOllamaStatus();
    
    if (refreshStatusBtn) {
        refreshStatusBtn.addEventListener('click', () => {
            refreshStatusBtn.disabled = true;
            refreshStatusBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            
            checkOllamaStatus().finally(() => {
                refreshStatusBtn.disabled = false;
                refreshStatusBtn.innerHTML = '<i class="fas fa-sync-alt"></i> Refresh';
            });
        });
    }
    
    if (installBtn) {
        installBtn.addEventListener('click', installOllama);
    }
    
    if (startBtn) {
        startBtn.addEventListener('click', startOllama);
    }
    
    if (refreshModelsBtn) {
        refreshModelsBtn.addEventListener('click', () => {
            refreshModelsBtn.disabled = true;
            refreshModelsBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            
            getOllamaModels().finally(() => {
                refreshModelsBtn.disabled = false;
                refreshModelsBtn.innerHTML = '<i class="fas fa-sync-alt"></i> Refresh Models';
            });
        });
    }
    
    if (downloadModelBtn) {
        downloadModelBtn.addEventListener('click', () => downloadOllamaModel());
    }
    
    if (testModelBtn) {
        testModelBtn.addEventListener('click', () => testOllamaModel());
    }
    
    if (providerSelect) {
        providerSelect.addEventListener('change', function() {
            const togetherSettings = document.getElementById('together-settings');
            const ollamaSettings = document.getElementById('ollama-settings');
            
            if (this.value === 'together') {
                if (togetherSettings) togetherSettings.classList.remove('d-none');
                if (ollamaSettings) ollamaSettings.classList.add('d-none');
            } else if (this.value === 'ollama') {
                if (togetherSettings) togetherSettings.classList.add('d-none');
                if (ollamaSettings) ollamaSettings.classList.remove('d-none');
                
                // Check Ollama status when switching to it
                checkOllamaStatus();
            }
        });
    }
}

// When document is ready, initialize Ollama UI
document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on the settings page
    if (document.getElementById('ollama-settings')) {
        initOllamaUI();
    }
});
