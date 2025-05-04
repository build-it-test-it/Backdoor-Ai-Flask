"""
GitHub service for interacting with GitHub repositories.
"""
import json
import os
import requests
from flask import current_app, session
from typing import Dict, List, Optional, Any

class GitHubService:
    """Service for interacting with GitHub repositories."""

    def __init__(self, token=None):
        self.token = token
        self.api_base_url = "https://api.github.com"
        self.current_repo = None
        self.repos_cache = {}
        self.branches_cache = {}
        self.files_cache = {}

    def set_token(self, token):
        """Set the GitHub token."""
        self.token = token

    def get_token(self):
        """Get the GitHub token from session if not set."""
        if not self.token:
            self.token = session.get('github_token')
        return self.token

    def set_current_repo(self, repo_full_name):
        """Set the current repository."""
        self.current_repo = repo_full_name
        session['current_repo'] = repo_full_name
        return True

    def get_current_repo(self):
        """Get the current repository."""
        if not self.current_repo:
            self.current_repo = session.get('current_repo')
        return self.current_repo

    def _make_request(self, endpoint, method="GET", params=None, data=None):
        """Make a request to the GitHub API."""
        token = self.get_token()
        if not token:
            return {"error": "GitHub token not set"}

        url = f"{self.api_base_url}/{endpoint.lstrip('/')}"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }

        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=params)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data)
            elif method == "PUT":
                response = requests.put(url, headers=headers, json=data)
            elif method == "PATCH":
                response = requests.patch(url, headers=headers, json=data)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers)
            else:
                return {"error": f"Unsupported method: {method}"}

            if response.status_code >= 400:
                return {"error": f"GitHub API error: {response.status_code}", "details": response.text}

            return response.json() if response.content else {"success": True}
        except Exception as e:
            return {"error": f"Request error: {str(e)}"}

    def get_user_info(self):
        """Get information about the authenticated user."""
        return self._make_request("user")

    def get_user_repos(self, force_refresh=False):
        """Get repositories for the authenticated user."""
        if not force_refresh and "user_repos" in self.repos_cache:
            return self.repos_cache["user_repos"]

        result = self._make_request("user/repos?sort=updated&per_page=100")
        if "error" not in result:
            self.repos_cache["user_repos"] = result
        return result

    def get_org_repos(self, org, force_refresh=False):
        """Get repositories for an organization."""
        cache_key = f"org_repos_{org}"
        if not force_refresh and cache_key in self.repos_cache:
            return self.repos_cache[cache_key]

        result = self._make_request(f"orgs/{org}/repos?sort=updated&per_page=100")
        if "error" not in result:
            self.repos_cache[cache_key] = result
        return result

    def get_repo_info(self, repo_full_name=None):
        """Get information about a repository."""
        if not repo_full_name:
            repo_full_name = self.get_current_repo()
            if not repo_full_name:
                return {"error": "No repository selected"}

        cache_key = f"repo_info_{repo_full_name}"
        if cache_key in self.repos_cache:
            return self.repos_cache[cache_key]

        result = self._make_request(f"repos/{repo_full_name}")
        if "error" not in result:
            self.repos_cache[cache_key] = result
        return result

    def get_repo_branches(self, repo_full_name=None):
        """Get branches for a repository."""
        if not repo_full_name:
            repo_full_name = self.get_current_repo()
            if not repo_full_name:
                return {"error": "No repository selected"}

        cache_key = f"branches_{repo_full_name}"
        if cache_key in self.branches_cache:
            return self.branches_cache[cache_key]

        result = self._make_request(f"repos/{repo_full_name}/branches")
        if "error" not in result:
            self.branches_cache[cache_key] = result
        return result

    def get_repo_contents(self, path="", repo_full_name=None, ref=None):
        """Get contents of a repository at a specific path."""
        if not repo_full_name:
            repo_full_name = self.get_current_repo()
            if not repo_full_name:
                return {"error": "No repository selected"}

        params = {}
        if ref:
            params["ref"] = ref

        cache_key = f"contents_{repo_full_name}_{path}_{ref or 'default'}"
        if cache_key in self.files_cache:
            return self.files_cache[cache_key]

        result = self._make_request(f"repos/{repo_full_name}/contents/{path}", params=params)
        if "error" not in result:
            self.files_cache[cache_key] = result
        return result

    def get_file_content(self, path, repo_full_name=None, ref=None):
        """Get the content of a specific file."""
        if not repo_full_name:
            repo_full_name = self.get_current_repo()
            if not repo_full_name:
                return {"error": "No repository selected"}

        params = {}
        if ref:
            params["ref"] = ref

        result = self._make_request(f"repos/{repo_full_name}/contents/{path}", params=params)
        if "error" in result:
            return result

        if isinstance(result, dict) and "content" in result:
            import base64
            try:
                content = base64.b64decode(result["content"]).decode("utf-8")
                return {"content": content, "sha": result.get("sha")}
            except Exception as e:
                return {"error": f"Failed to decode content: {str(e)}"}
        else:
            return {"error": "Not a file or content not available"}

    def create_fork(self, repo_full_name):
        """Create a fork of a repository."""
        result = self._make_request(f"repos/{repo_full_name}/forks", method="POST")
        return result

    def create_branch(self, branch_name, from_branch="main", repo_full_name=None):
        """Create a new branch in a repository."""
        if not repo_full_name:
            repo_full_name = self.get_current_repo()
            if not repo_full_name:
                return {"error": "No repository selected"}

        # Get the SHA of the source branch
        branches = self.get_repo_branches(repo_full_name)
        if "error" in branches:
            return branches

        source_branch = None
        for branch in branches:
            if branch["name"] == from_branch:
                source_branch = branch
                break

        if not source_branch:
            return {"error": f"Source branch '{from_branch}' not found"}

        # Create the new branch
        data = {
            "ref": f"refs/heads/{branch_name}",
            "sha": source_branch["commit"]["sha"]
        }
        result = self._make_request(f"repos/{repo_full_name}/git/refs", method="POST", data=data)
        return result

    def create_file(self, path, content, message, branch=None, repo_full_name=None):
        """Create a new file in a repository."""
        if not repo_full_name:
            repo_full_name = self.get_current_repo()
            if not repo_full_name:
                return {"error": "No repository selected"}

        import base64
        data = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("utf-8")
        }

        if branch:
            data["branch"] = branch

        result = self._make_request(f"repos/{repo_full_name}/contents/{path}", method="PUT", data=data)
        return result

    def update_file(self, path, content, message, sha, branch=None, repo_full_name=None):
        """Update an existing file in a repository."""
        if not repo_full_name:
            repo_full_name = self.get_current_repo()
            if not repo_full_name:
                return {"error": "No repository selected"}

        import base64
        data = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
            "sha": sha
        }

        if branch:
            data["branch"] = branch

        result = self._make_request(f"repos/{repo_full_name}/contents/{path}", method="PUT", data=data)
        return result

    def create_pull_request(self, title, body, head, base="main", repo_full_name=None):
        """Create a pull request in a repository."""
        if not repo_full_name:
            repo_full_name = self.get_current_repo()
            if not repo_full_name:
                return {"error": "No repository selected"}

        data = {
            "title": title,
            "body": body,
            "head": head,
            "base": base
        }

        result = self._make_request(f"repos/{repo_full_name}/pulls", method="POST", data=data)
        return result

    def search_repositories(self, query, sort="updated", order="desc"):
        """Search for repositories."""
        params = {
            "q": query,
            "sort": sort,
            "order": order
        }
        result = self._make_request("search/repositories", params=params)
        return result

    def clear_cache(self):
        """Clear the cache."""
        self.repos_cache = {}
        self.branches_cache = {}
        self.files_cache = {}
        return True
        
    def get_status(self):
        """Get the status of the GitHub service."""
        token = self.get_token()
        if not token:
            return {
                "connected": False,
                "message": "GitHub token not set",
                "user": None
            }
            
        # Check if we can connect to GitHub
        user_info = self.get_user_info()
        if "error" in user_info:
            return {
                "connected": False,
                "message": user_info.get("error", "Failed to connect to GitHub"),
                "user": None
            }
            
        return {
            "connected": True,
            "message": "Connected to GitHub",
            "user": user_info.get("login"),
            "avatar_url": user_info.get("avatar_url"),
            "html_url": user_info.get("html_url")
        }

# Singleton instance
github_service = GitHubService()