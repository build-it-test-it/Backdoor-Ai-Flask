/**
 * Providers management for Backdoor AI
 * This file contains JavaScript functions for managing LLM provider settings
 */

document.addEventListener('DOMContentLoaded', function() {
    // Provider tabs
    const providerTabs = document.querySelectorAll('#provider-tabs button');
    const providerInput = document.getElementById('llm_provider');
    
    // Password toggle buttons
    const toggleButtons = {
        'together': document.getElementById('toggle-together-key'),
        'openai': document.getElementById('toggle-openai-key'),
        'anthropic': document.getElementById('toggle-anthropic-key'),
        'google': document.getElementById('toggle-google-key'),
        'mistral': document.getElementById('toggle-mistral-key'), 
        'cohere': document.getElementById('toggle-cohere-key'),
        'custom': document.getElementById('toggle-custom-key')
    };
    
    // Ollama elements
    const ollamaModelSelect = document.getElementById('ollama_model');
    const customModelContainer = document.getElementById('custom-model-container');
    const testOllamaBtn = document.getElementById('test-ollama-connection');
    const ollamaTestResult = document.getElementById('ollama-test-result');
    const modelCards = document.querySelectorAll('.model-card');
    
    // Custom model toggle
    if (ollamaModelSelect) {
        ollamaModelSelect.addEventListener('change', function() {
            if (this.value === 'custom') {
                customModelContainer.classList.remove('d-none');
            } else {
                customModelContainer.classList.add('d-none');
            }
        });
    }
    
    // Provider tab selection
    providerTabs.forEach(function(tab) {
        tab.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Get provider from tab ID
            const tabId = this.id;
            const provider = tabId.replace('-tab', '');
            
            // Update hidden input
            if (providerInput) {
                providerInput.value = provider;
            }
            
            // Activate tab
            this.classList.add('active');
            this.setAttribute('aria-selected', 'true');
            
            // Show corresponding panel
            const panelId = this.getAttribute('data-bs-target');
            const panel = document.querySelector(panelId);
            if (panel) {
                // Hide all panels
                document.querySelectorAll('.tab-pane').forEach(function(p) {
                    p.classList.remove('show', 'active');
                });
                
                // Show selected panel
                panel.classList.add('show', 'active');
            }
        });
    });
    
    // Password visibility toggles
    Object.keys(toggleButtons).forEach(function(provider) {
        const toggleBtn = toggleButtons[provider];
        const inputId = `${provider}_api_key`;
        const input = document.getElementById(inputId);
        
        if (toggleBtn && input) {
            toggleBtn.addEventListener('click', function() {
                const icon = this.querySelector('i');
                
                if (input.type === 'password') {
                    input.type = 'text';
                    icon.classList.remove('fa-eye');
                    icon.classList.add('fa-eye-slash');
                } else {
                    input.type = 'password';
                    icon.classList.remove('fa-eye-slash');
                    icon.classList.add('fa-eye');
                }
            });
        }
    });
    
    // Ollama model cards
    if (modelCards) {
        modelCards.forEach(function(card) {
            card.addEventListener('click', function() {
                // Highlight selected card
                modelCards.forEach(function(c) {
                    c.classList.remove('border-primary', 'bg-light');
                });
                this.classList.add('border-primary', 'bg-light');
                
                // Update model selection
                const model = this.getAttribute('data-model');
                if (ollamaModelSelect && model) {
                    // Find and select the option
                    let optionFound = false;
                    
                    for (let i = 0; i < ollamaModelSelect.options.length; i++) {
                        if (ollamaModelSelect.options[i].value === model) {
                            ollamaModelSelect.selectedIndex = i;
                            optionFound = true;
                            
                            // Hide custom model input
                            customModelContainer.classList.add('d-none');
                            break;
                        }
                    }
                    
                    // If not found, set as custom model
                    if (!optionFound) {
                        // Find the custom option
                        for (let i = 0; i < ollamaModelSelect.options.length; i++) {
                            if (ollamaModelSelect.options[i].value === 'custom') {
                                ollamaModelSelect.selectedIndex = i;
                                
                                // Show and set custom model input
                                customModelContainer.classList.remove('d-none');
                                const customModelInput = document.getElementById('custom_ollama_model');
                                if (customModelInput) {
                                    customModelInput.value = model;
                                }
                                break;
                            }
                        }
                    }
                    
                    // Save the selection to ensure it persists
                    const apiBase = document.getElementById('ollama_api_base').value;
                    if (apiBase) {
                        fetch('/api/ollama/config', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify({
                                model: ollamaModelSelect.value,
                                custom_model: ollamaModelSelect.value === 'custom' ? 
                                    document.getElementById('custom_ollama_model').value : null,
                                api_base: apiBase
                            })
                        }).catch(error => console.error('Error saving model selection:', error));
                    }
                }
            });
        });
    }
    
    // Test Ollama connection
    if (testOllamaBtn) {
        testOllamaBtn.addEventListener('click', function() {
            const apiBase = document.getElementById('ollama_api_base').value;
            const model = ollamaModelSelect.value;
            
            if (!apiBase) {
                showToast('Error', 'Please enter the Ollama API URL first', 'danger');
                return;
            }
            
            if (!model || (model === 'custom' && !document.getElementById('custom_ollama_model').value)) {
                showToast('Error', 'Please select a model first', 'danger');
                return;
            }
            
            const customModel = model === 'custom' ? document.getElementById('custom_ollama_model').value : null;
            const modelToTest = customModel || model;
            
            // Save the settings first to ensure we're testing with the correct configuration
            fetch('/api/ollama/config', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    model: model,
                    custom_model: customModel,
                    api_base: apiBase
                })
            }).then(response => response.json())
              .catch(error => console.error('Error saving settings:', error));
            
            // Update button state
            this.disabled = true;
            this.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Testing...';
            
            // Clear previous results
            if (ollamaTestResult) {
                ollamaTestResult.classList.add('d-none');
                ollamaTestResult.classList.remove('alert-success', 'alert-danger');
            }
            
            // Test connection
            fetch('/api/ollama/test', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    model: modelToTest,
                    api_base: apiBase,
                    prompt: 'Hello, this is a test message from Backdoor AI. Please respond with a short greeting.'
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    if (ollamaTestResult) {
                        ollamaTestResult.classList.remove('d-none', 'alert-danger');
                        ollamaTestResult.classList.add('alert-success');
                        ollamaTestResult.innerHTML = `
                            <strong><i class="fas fa-check-circle me-1"></i> Connection successful!</strong>
                            <div class="mt-2 p-2 bg-light rounded">
                                <strong>Model response:</strong>
                                <div class="mt-1">${data.content}</div>
                            </div>
                        `;
                    }
                    showToast('Success', 'Connected to Ollama successfully', 'success');
                } else {
                    if (ollamaTestResult) {
                        ollamaTestResult.classList.remove('d-none', 'alert-success');
                        ollamaTestResult.classList.add('alert-danger');
                        ollamaTestResult.innerHTML = `
                            <strong><i class="fas fa-exclamation-circle me-1"></i> Connection failed!</strong>
                            <div class="mt-2">
                                <strong>Error:</strong> ${data.error || 'Unknown error'}
                            </div>
                            <div class="mt-2">
                                <ul>
                                    <li>Make sure your Colab notebook is running</li>
                                    <li>Check that you entered the correct tunnel URL</li>
                                    <li>Verify that you selected the same model you downloaded in Colab</li>
                                </ul>
                            </div>
                        `;
                    }
                    showToast('Error', 'Failed to connect to Ollama', 'danger');
                }
            })
            .catch(error => {
                console.error('Error testing Ollama connection:', error);
                if (ollamaTestResult) {
                    ollamaTestResult.classList.remove('d-none', 'alert-success');
                    ollamaTestResult.classList.add('alert-danger');
                    ollamaTestResult.innerHTML = `
                        <strong><i class="fas fa-exclamation-circle me-1"></i> Connection failed!</strong>
                        <div class="mt-2">
                            <strong>Error:</strong> ${error.message || 'Network error'}
                        </div>
                    `;
                }
                showToast('Error', 'Network error when connecting to Ollama', 'danger');
            })
            .finally(() => {
                // Reset button
                this.disabled = false;
                this.innerHTML = '<i class="fas fa-vial me-1"></i> Test Connection';
            });
        });
    }
});
