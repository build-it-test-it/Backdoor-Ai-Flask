/**
 * GitHub repository management functionality
 */

class GitHubManager {
    constructor() {
        this.currentRepo = null;
        this.repositories = [];
        this.initialized = false;
        this.token = null;
    }

    /**
     * Initialize the GitHub manager
     */
    async init() {
        if (this.initialized) return;
        
        try {
            // Check if we have a GitHub token
            const response = await fetch('/api/github/current-repo');
            const data = await response.json();
            
            if (data.error) {
                console.warn('GitHub token not set or invalid:', data.error);
                return false;
            }
            
            if (data.has_repo) {
                this.currentRepo = data.repository;
                this.updateRepoDisplay();
            }
            
            this.initialized = true;
            return true;
        } catch (error) {
            console.error('Error initializing GitHub manager:', error);
            return false;
        }
    }

    /**
     * Load user repositories
     */
    async loadUserRepos() {
        try {
            const response = await fetch('/api/github/repos');
            const data = await response.json();
            
            if (data.error) {
                console.error('Error loading repositories:', data.error);
                return [];
            }
            
            this.repositories = data.repositories;
            return this.repositories;
        } catch (error) {
            console.error('Error loading repositories:', error);
            return [];
        }
    }

    /**
     * Search for repositories
     * @param {string} query - Search query
     */
    async searchRepos(query) {
        try {
            const response = await fetch(`/api/github/search-repos?q=${encodeURIComponent(query)}`);
            const data = await response.json();
            
            if (data.error) {
                console.error('Error searching repositories:', data.error);
                return [];
            }
            
            return data.search_results.items || [];
        } catch (error) {
            console.error('Error searching repositories:', error);
            return [];
        }
    }

    /**
     * Set the current repository
     * @param {string} repoFullName - Full name of the repository (owner/repo)
     */
    async setCurrentRepo(repoFullName) {
        try {
            const response = await fetch('/api/github/set-repo', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    repo_full_name: repoFullName
                })
            });
            
            const data = await response.json();
            
            if (data.error) {
                console.error('Error setting repository:', data.error);
                return false;
            }
            
            this.currentRepo = data.repository;
            this.updateRepoDisplay();
            return true;
        } catch (error) {
            console.error('Error setting repository:', error);
            return false;
        }
    }

    /**
     * Get repository contents
     * @param {string} path - Path within the repository
     * @param {string} repoFullName - Full name of the repository (optional)
     * @param {string} ref - Branch or commit reference (optional)
     */
    async getRepoContents(path = '', repoFullName = null, ref = null) {
        try {
            let url = `/api/github/repo-contents?path=${encodeURIComponent(path)}`;
            
            if (repoFullName) {
                url += `&repo_full_name=${encodeURIComponent(repoFullName)}`;
            }
            
            if (ref) {
                url += `&ref=${encodeURIComponent(ref)}`;
            }
            
            const response = await fetch(url);
            const data = await response.json();
            
            if (data.error) {
                console.error('Error getting repository contents:', data.error);
                return null;
            }
            
            return data.contents;
        } catch (error) {
            console.error('Error getting repository contents:', error);
            return null;
        }
    }

    /**
     * Get file content
     * @param {string} path - Path to the file
     * @param {string} repoFullName - Full name of the repository (optional)
     * @param {string} ref - Branch or commit reference (optional)
     */
    async getFileContent(path, repoFullName = null, ref = null) {
        try {
            let url = `/api/github/file-content?path=${encodeURIComponent(path)}`;
            
            if (repoFullName) {
                url += `&repo_full_name=${encodeURIComponent(repoFullName)}`;
            }
            
            if (ref) {
                url += `&ref=${encodeURIComponent(ref)}`;
            }
            
            const response = await fetch(url);
            const data = await response.json();
            
            if (data.error) {
                console.error('Error getting file content:', data.error);
                return null;
            }
            
            return data.content;
        } catch (error) {
            console.error('Error getting file content:', error);
            return null;
        }
    }

    /**
     * Update the repository display in the UI
     */
    updateRepoDisplay() {
        const repoDisplay = document.getElementById('current-repo');
        if (!repoDisplay) return;
        
        if (this.currentRepo) {
            repoDisplay.textContent = this.currentRepo.full_name;
            repoDisplay.classList.remove('text-muted');
            
            // Show the repository info
            const repoInfo = document.getElementById('repo-info');
            if (repoInfo) {
                repoInfo.classList.remove('d-none');
                
                // Update repository details
                const repoName = document.getElementById('repo-name');
                const repoDescription = document.getElementById('repo-description');
                const repoStars = document.getElementById('repo-stars');
                const repoForks = document.getElementById('repo-forks');
                const repoLanguage = document.getElementById('repo-language');
                
                if (repoName) repoName.textContent = this.currentRepo.name;
                if (repoDescription) repoDescription.textContent = this.currentRepo.description || 'No description';
                if (repoStars) repoStars.textContent = this.currentRepo.stargazers_count || 0;
                if (repoForks) repoForks.textContent = this.currentRepo.forks_count || 0;
                if (repoLanguage) repoLanguage.textContent = this.currentRepo.language || 'Unknown';
            }
        } else {
            repoDisplay.textContent = 'No repository selected';
            repoDisplay.classList.add('text-muted');
            
            // Hide the repository info
            const repoInfo = document.getElementById('repo-info');
            if (repoInfo) {
                repoInfo.classList.add('d-none');
            }
        }
    }

    /**
     * Initialize the repository selector UI
     */
    initRepoSelector() {
        const repoSelector = document.getElementById('repo-selector');
        if (!repoSelector) return;
        
        // Load repositories when the selector is clicked
        repoSelector.addEventListener('click', async () => {
            const repoList = document.getElementById('repo-list');
            if (!repoList) return;
            
            // Clear the list
            repoList.innerHTML = '<div class="text-center"><div class="spinner-border spinner-border-sm" role="status"></div> Loading repositories...</div>';
            
            // Load repositories
            const repos = await this.loadUserRepos();
            
            // Update the list
            repoList.innerHTML = '';
            
            if (repos.length === 0) {
                repoList.innerHTML = '<div class="text-center text-muted">No repositories found</div>';
                return;
            }
            
            repos.forEach(repo => {
                const item = document.createElement('a');
                item.href = '#';
                item.className = 'list-group-item list-group-item-action';
                item.innerHTML = `
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <strong>${repo.name}</strong>
                            <small class="text-muted d-block">${repo.full_name}</small>
                        </div>
                        <span class="badge bg-primary rounded-pill">${repo.stargazers_count} ★</span>
                    </div>
                `;
                
                item.addEventListener('click', async (e) => {
                    e.preventDefault();
                    await this.setCurrentRepo(repo.full_name);
                    
                    // Close the modal
                    const modal = bootstrap.Modal.getInstance(document.getElementById('repo-modal'));
                    if (modal) modal.hide();
                });
                
                repoList.appendChild(item);
            });
        });
        
        // Initialize the search form
        const searchForm = document.getElementById('repo-search-form');
        if (searchForm) {
            searchForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const searchInput = document.getElementById('repo-search-input');
                if (!searchInput) return;
                
                const query = searchInput.value.trim();
                if (!query) return;
                
                const repoList = document.getElementById('repo-list');
                if (!repoList) return;
                
                // Show loading indicator
                repoList.innerHTML = '<div class="text-center"><div class="spinner-border spinner-border-sm" role="status"></div> Searching repositories...</div>';
                
                // Search repositories
                const repos = await this.searchRepos(query);
                
                // Update the list
                repoList.innerHTML = '';
                
                if (repos.length === 0) {
                    repoList.innerHTML = '<div class="text-center text-muted">No repositories found</div>';
                    return;
                }
                
                repos.forEach(repo => {
                    const item = document.createElement('a');
                    item.href = '#';
                    item.className = 'list-group-item list-group-item-action';
                    item.innerHTML = `
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <strong>${repo.name}</strong>
                                <small class="text-muted d-block">${repo.full_name}</small>
                            </div>
                            <span class="badge bg-primary rounded-pill">${repo.stargazers_count} ★</span>
                        </div>
                    `;
                    
                    item.addEventListener('click', async (e) => {
                        e.preventDefault();
                        await this.setCurrentRepo(repo.full_name);
                        
                        // Close the modal
                        const modal = bootstrap.Modal.getInstance(document.getElementById('repo-modal'));
                        if (modal) modal.hide();
                    });
                    
                    repoList.appendChild(item);
                });
            });
        }
    }
}

// Initialize the GitHub manager
const githubManager = new GitHubManager();

// Initialize when the DOM is loaded
document.addEventListener('DOMContentLoaded', async () => {
    await githubManager.init();
    githubManager.initRepoSelector();
});