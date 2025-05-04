"""
Code Context Manager for Backdoor AI

This module provides a more sophisticated code context management system
based on Mentat's code_context.py. It helps agents understand and navigate
codebases more effectively.

Features:
- Better file scanning and filtering
- Improved context management
- Code feature extraction
- Diff context handling
"""

import os
import re
import logging
import fnmatch
import subprocess
from pathlib import Path
from typing import Dict, List, Set, Optional, Any, Tuple, Union
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("code_context_manager")

class CodeInterval:
    """
    Represents a specific interval within a file.
    Based on Mentat's interval.py.
    """
    
    def __init__(self, start: int, end: int):
        """
        Initialize a code interval.
        
        Args:
            start: Start line number (1-indexed)
            end: End line number (1-indexed, inclusive)
        """
        if start < 1:
            raise ValueError("Start line must be at least 1")
        if end < start:
            raise ValueError("End line must be greater than or equal to start line")
        
        self.start = start
        self.end = end
    
    def __repr__(self) -> str:
        return f"CodeInterval({self.start}, {self.end})"
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, CodeInterval):
            return False
        return self.start == other.start and self.end == other.end
    
    def __hash__(self) -> int:
        return hash((self.start, self.end))
    
    def overlaps(self, other: 'CodeInterval') -> bool:
        """Check if this interval overlaps with another."""
        return max(self.start, other.start) <= min(self.end, other.end)
    
    def contains(self, line: int) -> bool:
        """Check if this interval contains a specific line."""
        return self.start <= line <= self.end
    
    def merge(self, other: 'CodeInterval') -> 'CodeInterval':
        """Merge this interval with another, if they overlap."""
        if not self.overlaps(other):
            raise ValueError("Cannot merge non-overlapping intervals")
        
        return CodeInterval(
            min(self.start, other.start),
            max(self.end, other.end)
        )
    
    def to_dict(self) -> Dict[str, int]:
        """Convert to dictionary for serialization."""
        return {
            'start': self.start,
            'end': self.end
        }

class CodeFeature:
    """
    Represents a code feature (file or directory) in the codebase.
    Based on Mentat's code_feature.py.
    """
    
    def __init__(self, path: Path, intervals: Optional[List[CodeInterval]] = None):
        self.path = path
        self.intervals = intervals or []
        self.is_directory = path.is_dir() if path.exists() else False
        self.size = path.stat().st_size if path.exists() and not self.is_directory else 0
        self.last_modified = datetime.fromtimestamp(path.stat().st_mtime) if path.exists() else datetime.now()
        self._content = None
        self._lines = None
    
    def __repr__(self) -> str:
        return f"CodeFeature({self.path}, intervals={self.intervals})"
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, CodeFeature):
            return False
        return self.path == other.path and self.intervals == other.intervals
    
    def __hash__(self) -> int:
        return hash((str(self.path), tuple(self.intervals)))
    
    @property
    def content(self) -> str:
        """Get the content of the file."""
        if self._content is None:
            self.load_content()
        return self._content or ""
    
    @property
    def lines(self) -> List[str]:
        """Get the lines of the file."""
        if self._lines is None:
            self.load_content()
        return self._lines or []
    
    def load_content(self) -> None:
        """Load the content of the file."""
        if self.is_directory or not self.path.exists():
            self._content = ""
            self._lines = []
            return
        
        try:
            with open(self.path, 'r', encoding='utf-8', errors='replace') as f:
                self._content = f.read()
                self._lines = self._content.splitlines()
        except Exception as e:
            logger.error(f"Error loading content for {self.path}: {e}")
            self._content = f"Error loading content: {str(e)}"
            self._lines = [self._content]
    
    def get_interval_content(self, interval: CodeInterval) -> str:
        """Get the content of a specific interval."""
        if self.is_directory or not self.path.exists():
            return ""
        
        if not self._lines:
            self.load_content()
        
        # Adjust for 0-indexed list
        start_idx = max(0, interval.start - 1)
        end_idx = min(len(self._lines), interval.end)
        
        return "\n".join(self._lines[start_idx:end_idx])
    
    def get_all_intervals_content(self) -> str:
        """Get the content of all intervals."""
        if not self.intervals:
            return self.content
        
        result = []
        for interval in self.intervals:
            result.append(self.get_interval_content(interval))
        
        return "\n".join(result)
    
    def add_interval(self, interval: CodeInterval) -> None:
        """Add an interval to this feature."""
        # Check for overlaps and merge if needed
        merged = False
        for i, existing in enumerate(self.intervals):
            if existing.overlaps(interval):
                self.intervals[i] = existing.merge(interval)
                merged = True
                break
        
        if not merged:
            self.intervals.append(interval)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'path': str(self.path),
            'is_directory': self.is_directory,
            'size': self.size,
            'last_modified': self.last_modified.isoformat(),
            'intervals': [interval.to_dict() for interval in self.intervals]
        }

class DiffContext:
    """
    Manages diff context for code changes.
    Based on Mentat's diff_context.py.
    """
    
    def __init__(self, base_path: Path):
        self.base_path = base_path
    
    def get_git_diff(self, staged: bool = False) -> str:
        """Get the git diff for the current changes."""
        try:
            cmd = ["git", "diff", "--unified=3"]
            if staged:
                cmd.append("--staged")
            
            result = subprocess.run(
                cmd,
                cwd=str(self.base_path),
                capture_output=True,
                text=True,
                check=True
            )
            
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.error(f"Error getting git diff: {e}")
            return ""
    
    def parse_diff(self, diff_text: str) -> Dict[str, List[Tuple[int, int, str]]]:
        """
        Parse a diff and extract changed lines.
        
        Returns:
            Dict mapping file paths to lists of (start_line, line_count, change_type) tuples.
            change_type is one of 'added', 'removed', or 'context'.
        """
        result = {}
        current_file = None
        current_line = 0
        
        # Regular expressions for parsing diff
        file_pattern = re.compile(r'^--- a/(.+)$')
        hunk_pattern = re.compile(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@')
        
        lines = diff_text.splitlines()
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # Check for file header
            file_match = file_pattern.match(line)
            if file_match:
                current_file = file_match.group(1)
                result[current_file] = []
                i += 2  # Skip the +++ line
                continue
            
            # Check for hunk header
            hunk_match = hunk_pattern.match(line)
            if hunk_match:
                current_line = int(hunk_match.group(1))
                i += 1
                continue
            
            # Process diff lines
            if current_file is not None:
                if line.startswith('+'):
                    result[current_file].append((current_line, 1, 'added'))
                    current_line += 1
                elif line.startswith('-'):
                    result[current_file].append((current_line, 1, 'removed'))
                    # Don't increment current_line for removed lines
                elif line.startswith(' '):
                    result[current_file].append((current_line, 1, 'context'))
                    current_line += 1
            
            i += 1
        
        return result
    
    def get_changed_features(self, staged: bool = False) -> List[CodeFeature]:
        """Get code features for changed files."""
        diff_text = self.get_git_diff(staged)
        parsed_diff = self.parse_diff(diff_text)
        
        features = []
        
        for file_path, changes in parsed_diff.items():
            path = self.base_path / file_path
            
            if not path.exists() or path.is_dir():
                continue
            
            feature = CodeFeature(path)
            
            # Add intervals for changed lines
            for start_line, line_count, change_type in changes:
                if change_type in ('added', 'context'):
                    # Add some context around the change
                    context_start = max(1, start_line - 3)
                    context_end = start_line + line_count + 2
                    
                    feature.add_interval(CodeInterval(context_start, context_end))
            
            if feature.intervals:
                features.append(feature)
        
        return features

class CodeContextManager:
    """
    Manages code context for agents.
    Based on Mentat's code_context.py.
    """
    
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.features: Dict[str, CodeFeature] = {}
        self.ignored_patterns: List[str] = [
            '.git', '.github', '__pycache__', '*.pyc', '*.pyo', '*.pyd',
            '.DS_Store', '.env', '.venv', 'env', 'venv', 'ENV', 'env.bak',
            'venv.bak', '.idea', '.vscode', '*.so', '*.dylib', '*.dll',
            'node_modules', 'bower_components', '.pytest_cache', '.coverage',
            'htmlcov', '.tox', '.nox', '.hypothesis', '.egg-info', 'dist',
            'build', '*.egg', '*.whl', '*.log'
        ]
        
        # Initialize diff context
        self.diff_context = DiffContext(base_path)
    
    def is_ignored(self, path: Path) -> bool:
        """Check if a path should be ignored."""
        # Convert to relative path for pattern matching
        rel_path = path.relative_to(self.base_path) if path.is_absolute() else path
        rel_path_str = str(rel_path)
        
        # Check against ignored patterns
        for pattern in self.ignored_patterns:
            if fnmatch.fnmatch(rel_path_str, pattern) or fnmatch.fnmatch(rel_path.name, pattern):
                return True
        
        return False
    
    def add_feature(self, path: Path, intervals: Optional[List[CodeInterval]] = None) -> Optional[CodeFeature]:
        """Add a file or directory to the context."""
        # Normalize path
        if not path.is_absolute():
            path = self.base_path / path
        
        # Check if path exists
        if not path.exists():
            logger.warning(f"Path does not exist: {path}")
            return None
        
        # Check if path should be ignored
        if self.is_ignored(path):
            logger.info(f"Path ignored: {path}")
            return None
        
        # Create feature
        feature = CodeFeature(path, intervals)
        
        # Load content for files
        if not feature.is_directory:
            feature.load_content()
        
        # Add to features
        self.features[str(path)] = feature
        
        return feature
    
    def add_directory(self, path: Path, recursive: bool = True, max_depth: int = 3) -> List[CodeFeature]:
        """Add a directory and its contents to the context."""
        # Normalize path
        if not path.is_absolute():
            path = self.base_path / path
        
        # Check if path exists and is a directory
        if not path.exists() or not path.is_dir():
            logger.warning(f"Path does not exist or is not a directory: {path}")
            return []
        
        # Check if path should be ignored
        if self.is_ignored(path):
            logger.info(f"Path ignored: {path}")
            return []
        
        # Add the directory itself
        self.add_feature(path)
        
        added_features = []
        
        # Add contents
        if recursive:
            self._add_directory_recursive(path, added_features, 0, max_depth)
        else:
            for item in path.iterdir():
                if not self.is_ignored(item):
                    feature = self.add_feature(item)
                    if feature:
                        added_features.append(feature)
        
        return added_features
    
    def _add_directory_recursive(self, path: Path, added_features: List[CodeFeature], 
                               current_depth: int, max_depth: int) -> None:
        """Recursively add directory contents to the context."""
        if current_depth > max_depth:
            return
        
        for item in path.iterdir():
            if self.is_ignored(item):
                continue
            
            feature = self.add_feature(item)
            if feature:
                added_features.append(feature)
            
            if item.is_dir():
                self._add_directory_recursive(item, added_features, current_depth + 1, max_depth)
    
    def remove_feature(self, path: Path) -> bool:
        """Remove a feature from the context."""
        # Normalize path
        if not path.is_absolute():
            path = self.base_path / path
        
        path_str = str(path)
        
        if path_str in self.features:
            del self.features[path_str]
            return True
        
        return False
    
    def get_feature(self, path: Path) -> Optional[CodeFeature]:
        """Get a feature from the context."""
        # Normalize path
        if not path.is_absolute():
            path = self.base_path / path
        
        return self.features.get(str(path))
    
    def get_all_features(self) -> List[CodeFeature]:
        """Get all features in the context."""
        return list(self.features.values())
    
    def get_file_content(self, path: Path) -> Optional[str]:
        """Get the content of a file."""
        feature = self.get_feature(path)
        if feature and not feature.is_directory:
            return feature.content
        
        return None
    
    def get_changed_features(self, staged: bool = False) -> List[CodeFeature]:
        """Get features for changed files."""
        return self.diff_context.get_changed_features(staged)
    
    def scan_repository(self, max_depth: int = 5) -> List[CodeFeature]:
        """Scan the repository for files."""
        # Clear existing features
        self.features = {}
        
        # Add the base directory
        return self.add_directory(self.base_path, recursive=True, max_depth=max_depth)
    
    def find_files_by_pattern(self, pattern: str) -> List[CodeFeature]:
        """Find files matching a pattern."""
        result = []
        
        for feature in self.features.values():
            if feature.is_directory:
                continue
            
            if fnmatch.fnmatch(str(feature.path), pattern) or fnmatch.fnmatch(feature.path.name, pattern):
                result.append(feature)
        
        return result
    
    def find_files_by_content(self, content_pattern: str) -> List[CodeFeature]:
        """Find files containing a specific pattern."""
        result = []
        
        try:
            pattern = re.compile(content_pattern)
            
            for feature in self.features.values():
                if feature.is_directory:
                    continue
                
                if pattern.search(feature.content):
                    result.append(feature)
        
        except re.error:
            # If the pattern is invalid, fall back to simple string search
            for feature in self.features.values():
                if feature.is_directory:
                    continue
                
                if content_pattern in feature.content:
                    result.append(feature)
        
        return result
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'base_path': str(self.base_path),
            'features': {path: feature.to_dict() for path, feature in self.features.items()},
            'ignored_patterns': self.ignored_patterns
        }

# Create a dictionary to store context managers
context_managers: Dict[str, CodeContextManager] = {}