"""
Tools implementation for AI model function calling, inspired by OpenHands.
"""
import json
import os
import subprocess
import sys
from enum import Enum
from typing import Any, Dict, List, Optional, Union

import requests
from flask import current_app, session
from pydantic import BaseModel, Field

from app.ai.behavior_tracker import behavior_tracker


class ToolType(str, Enum):
    """Types of tools available to the AI model."""
    EXECUTE_BASH = "execute_bash"
    THINK = "think"
    FINISH = "finish"
    WEB_READ = "web_read"
    BROWSER = "browser"
    EXECUTE_IPYTHON_CELL = "execute_ipython_cell"
    STR_REPLACE_EDITOR = "str_replace_editor"


class BaseTool(BaseModel):
    """Base class for all tools."""
    name: str
    description: str
    parameters: Dict[str, Any]
    required: List[str]
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the tool with the given parameters."""
        raise NotImplementedError("Tool execution not implemented")


class ExecuteBashTool(BaseTool):
    """Tool for executing bash commands."""
    name: str = ToolType.EXECUTE_BASH
    description: str = """Execute a bash command in the terminal within a persistent shell session.

### Command Execution
* One command at a time: You can only execute one bash command at a time. If you need to run multiple commands sequentially, use `&&` or `;` to chain them together.
* Persistent session: Commands execute in a persistent shell session where environment variables, virtual environments, and working directory persist between commands.
* Timeout: Commands have a soft timeout of 120 seconds, once that's reached, you have the option to continue or interrupt the command (see section below for details)

### Running and Interacting with Processes
* Long running commands: For commands that may run indefinitely, run them in the background and redirect output to a file, e.g. `python3 app.py > server.log 2>&1 &`.
* Interact with running process: If a bash command returns exit code `-1`, this means the process is not yet finished. By setting `is_input` to `true`, you can:
  - Send empty `command` to retrieve additional logs
  - Send text (set `command` to the text) to STDIN of the running process
  - Send control commands like `C-c` (Ctrl+C), `C-d` (Ctrl+D), or `C-z` (Ctrl+Z) to interrupt the process

### Best Practices
* Directory verification: Before creating new directories or files, first verify the parent directory exists and is the correct location.
* Directory management: Try to maintain working directory by using absolute paths and avoiding excessive use of `cd`.

### Output Handling
* Output truncation: If the output exceeds a maximum length, it will be truncated before being returned.
"""
    parameters: Dict[str, Any] = {
        "properties": {
            "command": {
                "description": "The bash command to execute. Can be empty string to view additional logs when previous exit code is `-1`. Can be `C-c` (Ctrl+C) to interrupt the currently running process. Note: You can only execute one bash command at a time. If you need to run multiple commands sequentially, you can use `&&` or `;` to chain them together.",
                "type": "string"
            },
            "is_input": {
                "description": "If True, the command is an input to the running process. If False, the command is a bash command to be executed in the terminal. Default is False.",
                "enum": ["true", "false"],
                "type": "string"
            }
        },
        "required": ["command"],
        "type": "object"
    }
    required: List[str] = ["command"]
    
    def execute(self, command: str, is_input: str = "false") -> Dict[str, Any]:
        """Execute a bash command."""
        # Record the command execution
        behavior_tracker.record_behavior(
            action="execute_bash",
            screen="AI Chat",
            details={"command": command, "is_input": is_input}
        )
        
        try:
            # Execute the command
            is_input_bool = is_input.lower() == "true"
            
            if is_input_bool:
                # This would be for interactive processes
                # In a real implementation, you'd need to handle this differently
                return {
                    "output": f"Interactive input '{command}' sent to process",
                    "exit_code": 0
                }
            else:
                # Execute the command
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True
                )
                
                return {
                    "output": result.stdout + result.stderr,
                    "exit_code": result.returncode
                }
        except Exception as e:
            return {
                "output": f"Error executing command: {str(e)}",
                "exit_code": 1
            }


class ThinkTool(BaseTool):
    """Tool for thinking about a problem."""
    name: str = ToolType.THINK
    description: str = """Use the tool to think about something. It will not obtain new information or make any changes to the repository, but just log the thought. Use it when complex reasoning or brainstorming is needed.

Common use cases:
1. When exploring a repository and discovering the source of a bug, call this tool to brainstorm several unique ways of fixing the bug, and assess which change(s) are likely to be simplest and most effective.
2. After receiving test results, use this tool to brainstorm ways to fix failing tests.
3. When planning a complex refactoring, use this tool to outline different approaches and their tradeoffs.
4. When designing a new feature, use this tool to think through architecture decisions and implementation details.
5. When debugging a complex issue, use this tool to organize your thoughts and hypotheses.

The tool simply logs your thought process for better transparency and does not execute any code or make changes."""
    parameters: Dict[str, Any] = {
        "properties": {
            "thought": {
                "description": "The thought to log.",
                "type": "string"
            }
        },
        "required": ["thought"],
        "type": "object"
    }
    required: List[str] = ["thought"]
    
    def execute(self, thought: str) -> Dict[str, Any]:
        """Log a thought."""
        # Record the thought
        behavior_tracker.record_behavior(
            action="think",
            screen="AI Chat",
            details={"thought": thought}
        )
        
        return {
            "thought": thought
        }


class FinishTool(BaseTool):
    """Tool for signaling task completion."""
    name: str = ToolType.FINISH
    description: str = """Signals the completion of the current task or conversation.

Use this tool when:
- You have successfully completed the user's requested task
- You cannot proceed further due to technical limitations or missing information

The message should include:
- A clear summary of actions taken and their results
- Any next steps for the user
- Explanation if you're unable to complete the task
- Any follow-up questions if more information is needed

The task_completed field should be set to True if you believed you have completed the task, and False otherwise.
"""
    parameters: Dict[str, Any] = {
        "properties": {
            "message": {
                "description": "Final message to send to the user",
                "type": "string"
            },
            "task_completed": {
                "description": "Whether you have completed the task.",
                "enum": ["true", "false", "partial"],
                "type": "string"
            }
        },
        "required": ["message", "task_completed"],
        "type": "object"
    }
    required: List[str] = ["message", "task_completed"]
    
    def execute(self, message: str, task_completed: str) -> Dict[str, Any]:
        """Signal task completion."""
        # Record the finish action
        behavior_tracker.record_behavior(
            action="finish",
            screen="AI Chat",
            details={"message": message, "task_completed": task_completed}
        )
        
        return {
            "message": message,
            "task_completed": task_completed
        }


class WebReadTool(BaseTool):
    """Tool for reading web content."""
    name: str = ToolType.WEB_READ
    description: str = """Read (convert to markdown) content from a webpage. You should prefer using the `web_read` tool over the `browser` tool, but do use the `browser` tool if you need to interact with a webpage (e.g., click a button, fill out a form, etc.) OR read a webpage that contains images.

You may use the `web_read` tool to read text content from a webpage, and even search the webpage content using a Google search query (e.g., url=`https://www.google.com/search?q=YOUR_QUERY`).
"""
    parameters: Dict[str, Any] = {
        "properties": {
            "url": {
                "description": "The URL of the webpage to read. You can also use a Google search query here (e.g., `https://www.google.com/search?q=YOUR_QUERY`).",
                "type": "string"
            }
        },
        "required": ["url"],
        "type": "object"
    }
    required: List[str] = ["url"]
    
    def execute(self, url: str) -> Dict[str, Any]:
        """Read content from a webpage."""
        # Record the web read action
        behavior_tracker.record_behavior(
            action="web_read",
            screen="AI Chat",
            details={"url": url}
        )
        
        try:
            # Make the request
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                return {
                    "error": f"Failed to fetch URL: {response.status_code}",
                    "content": ""
                }
            
            # For a real implementation, you'd want to convert HTML to markdown
            # Here we'll just return the raw HTML
            return {
                "content": response.text[:10000]  # Limit content size
            }
        except Exception as e:
            return {
                "error": f"Error fetching URL: {str(e)}",
                "content": ""
            }


class BrowserTool(BaseTool):
    """Tool for browser interaction."""
    name: str = ToolType.BROWSER
    description: str = """Interact with the browser using Python code. Use it ONLY when you need to interact with a webpage.

See the description of "code" parameter for more details.

Multiple actions can be provided at once, but will be executed sequentially without any feedback from the page.
More than 2-3 actions usually leads to failure or unexpected behavior. Example:
fill('a12', 'example with \"quotes\"')
click('a51')
click('48', button='middle', modifiers=['Shift'])

You can also use the browser to view pdf, png, jpg files.
You should first check the content of /tmp/oh-server-url to get the server url, and then use it to view the file by `goto(\"{server_url}/view?path={absolute_file_path}\")`.
For example: `goto(\"http://localhost:8000/view?path=/workspace/test_document.pdf\")`
Note: The file should be downloaded to the local machine first before using the browser to view it.
"""
    parameters: Dict[str, Any] = {
        "properties": {
            "code": {
                "description": "The Python code that interacts with the browser.",
                "type": "string"
            }
        },
        "required": ["code"],
        "type": "object"
    }
    required: List[str] = ["code"]
    
    def execute(self, code: str) -> Dict[str, Any]:
        """Execute browser interaction code."""
        # Record the browser action
        behavior_tracker.record_behavior(
            action="browser",
            screen="AI Chat",
            details={"code": code}
        )
        
        # In a real implementation, you'd need to integrate with a browser automation tool
        return {
            "result": "Browser interaction is not fully implemented in this version. Code received: " + code[:100] + "..."
        }


class ExecuteIPythonCellTool(BaseTool):
    """Tool for executing Python code in IPython."""
    name: str = ToolType.EXECUTE_IPYTHON_CELL
    description: str = """Run a cell of Python code in an IPython environment.
* The assistant should define variables and import packages before using them.
* The variable defined in the IPython environment will not be available outside the IPython environment (e.g., in terminal).
"""
    parameters: Dict[str, Any] = {
        "properties": {
            "code": {
                "description": "The Python code to execute. Supports magic commands like %pip.",
                "type": "string"
            }
        },
        "required": ["code"],
        "type": "object"
    }
    required: List[str] = ["code"]
    
    def execute(self, code: str) -> Dict[str, Any]:
        """Execute Python code."""
        # Record the code execution
        behavior_tracker.record_behavior(
            action="execute_ipython_cell",
            screen="AI Chat",
            details={"code": code}
        )
        
        try:
            # Create a temporary file
            temp_file = "/tmp/ipython_code.py"
            with open(temp_file, "w") as f:
                f.write(code)
            
            # Execute the code
            result = subprocess.run(
                [sys.executable, temp_file],
                capture_output=True,
                text=True
            )
            
            # Clean up
            os.remove(temp_file)
            
            return {
                "output": result.stdout,
                "error": result.stderr,
                "exit_code": result.returncode
            }
        except Exception as e:
            return {
                "output": "",
                "error": f"Error executing code: {str(e)}",
                "exit_code": 1
            }


class StrReplaceEditorTool(BaseTool):
    """Tool for editing files."""
    name: str = ToolType.STR_REPLACE_EDITOR
    description: str = """Custom editing tool for viewing, creating and editing files in plain-text format
* State is persistent across command calls and discussions with the user
* If `path` is a file, `view` displays the result of applying `cat -n`. If `path` is a directory, `view` lists non-hidden files and directories up to 2 levels deep
* The `create` command cannot be used if the specified `path` already exists as a file
* If a `command` generates a long output, it will be truncated and marked with `<response clipped>`
* The `undo_edit` command will revert the last edit made to the file at `path`


Before using this tool:
1. Use the view tool to understand the file's contents and context
2. Verify the directory path is correct (only applicable when creating new files):
   - Use the view tool to verify the parent directory exists and is the correct location

When making edits:
   - Ensure the edit results in idiomatic, correct code
   - Do not leave the code in a broken state
   - Always use absolute file paths (starting with /)

CRITICAL REQUIREMENTS FOR USING THIS TOOL:

1. EXACT MATCHING: The `old_str` parameter must match EXACTLY one or more consecutive lines from the file, including all whitespace and indentation. The tool will fail if `old_str` matches multiple locations or doesn't match exactly with the file content.

2. UNIQUENESS: The `old_str` must uniquely identify a single instance in the file:
   - Include sufficient context before and after the change point (3-5 lines recommended)
   - If not unique, the replacement will not be performed

3. REPLACEMENT: The `new_str` parameter should contain the edited lines that replace the `old_str`. Both strings must be different.

Remember: when making multiple file edits in a row to the same file, you should prefer to send all edits in a single message with multiple calls to this tool, rather than multiple messages with a single call each.
"""
    parameters: Dict[str, Any] = {
        "properties": {
            "command": {
                "description": "The commands to run. Allowed options are: `view`, `create`, `str_replace`, `insert`, `undo_edit`.",
                "enum": ["view", "create", "str_replace", "insert", "undo_edit"],
                "type": "string"
            },
            "file_text": {
                "description": "Required parameter of `create` command, with the content of the file to be created.",
                "type": "string"
            },
            "insert_line": {
                "description": "Required parameter of `insert` command. The `new_str` will be inserted AFTER the line `insert_line` of `path`.",
                "type": "integer"
            },
            "new_str": {
                "description": "Optional parameter of `str_replace` command containing the new string (if not given, no string will be added). Required parameter of `insert` command containing the string to insert.",
                "type": "string"
            },
            "old_str": {
                "description": "Required parameter of `str_replace` command containing the string in `path` to replace.",
                "type": "string"
            },
            "path": {
                "description": "Absolute path to file or directory, e.g. `/workspace/file.py` or `/workspace`.",
                "type": "string"
            },
            "view_range": {
                "description": "Optional parameter of `view` command when `path` points to a file. If none is given, the full file is shown. If provided, the file will be shown in the indicated line number range, e.g. [11, 12] will show lines 11 and 12. Indexing at 1 to start. Setting `[start_line, -1]` shows all lines from `start_line` to the end of the file.",
                "items": {"type": "integer"},
                "type": "array"
            }
        },
        "required": ["command", "path"],
        "type": "object"
    }
    required: List[str] = ["command", "path"]
    
    def execute(self, command: str, path: str, **kwargs) -> Dict[str, Any]:
        """Execute file operations."""
        # Record the file operation
        behavior_tracker.record_behavior(
            action="str_replace_editor",
            screen="AI Chat",
            details={"command": command, "path": path, **kwargs}
        )
        
        try:
            if command == "view":
                # View file or directory
                if os.path.isfile(path):
                    view_range = kwargs.get("view_range")
                    with open(path, "r") as f:
                        lines = f.readlines()
                    
                    if view_range:
                        start = view_range[0] - 1  # Convert to 0-indexed
                        end = view_range[1] if view_range[1] != -1 else len(lines)
                        lines = lines[start:end]
                    
                    content = "".join(lines)
                    return {
                        "content": content,
                        "is_file": True
                    }
                elif os.path.isdir(path):
                    # List directory contents
                    files = []
                    for root, dirs, filenames in os.walk(path, topdown=True, followlinks=False):
                        level = root.replace(path, '').count(os.sep)
                        if level <= 2:  # Only go 2 levels deep
                            for filename in filenames:
                                if not filename.startswith('.'):
                                    files.append(os.path.join(root, filename))
                            for dirname in dirs:
                                if not dirname.startswith('.'):
                                    files.append(os.path.join(root, dirname))
                    
                    return {
                        "content": "\n".join(files),
                        "is_file": False
                    }
                else:
                    return {
                        "error": f"Path does not exist: {path}"
                    }
            
            elif command == "create":
                # Create a new file
                file_text = kwargs.get("file_text")
                if not file_text:
                    return {
                        "error": "file_text parameter is required for create command"
                    }
                
                if os.path.exists(path):
                    return {
                        "error": f"File already exists: {path}"
                    }
                
                # Create parent directories if they don't exist
                os.makedirs(os.path.dirname(path), exist_ok=True)
                
                with open(path, "w") as f:
                    f.write(file_text)
                
                return {
                    "message": f"File created: {path}"
                }
            
            elif command == "str_replace":
                # Replace text in a file
                old_str = kwargs.get("old_str")
                new_str = kwargs.get("new_str", "")
                
                if not old_str:
                    return {
                        "error": "old_str parameter is required for str_replace command"
                    }
                
                if not os.path.isfile(path):
                    return {
                        "error": f"File does not exist: {path}"
                    }
                
                with open(path, "r") as f:
                    content = f.read()
                
                if old_str not in content:
                    return {
                        "error": f"old_str not found in file: {path}"
                    }
                
                # Count occurrences to ensure uniqueness
                if content.count(old_str) > 1:
                    return {
                        "error": f"old_str matches multiple locations in file: {path}"
                    }
                
                # Replace the text
                new_content = content.replace(old_str, new_str)
                
                # Backup the file
                backup_path = f"{path}.bak"
                with open(backup_path, "w") as f:
                    f.write(content)
                
                # Write the new content
                with open(path, "w") as f:
                    f.write(new_content)
                
                return {
                    "message": f"File updated: {path}"
                }
            
            elif command == "insert":
                # Insert text at a specific line
                insert_line = kwargs.get("insert_line")
                new_str = kwargs.get("new_str")
                
                if insert_line is None:
                    return {
                        "error": "insert_line parameter is required for insert command"
                    }
                
                if not new_str:
                    return {
                        "error": "new_str parameter is required for insert command"
                    }
                
                if not os.path.isfile(path):
                    return {
                        "error": f"File does not exist: {path}"
                    }
                
                with open(path, "r") as f:
                    lines = f.readlines()
                
                if insert_line < 0 or insert_line > len(lines):
                    return {
                        "error": f"insert_line out of range: {insert_line}, file has {len(lines)} lines"
                    }
                
                # Backup the file
                backup_path = f"{path}.bak"
                with open(backup_path, "w") as f:
                    f.write("".join(lines))
                
                # Insert the text
                lines.insert(insert_line, new_str if new_str.endswith("\n") else new_str + "\n")
                
                with open(path, "w") as f:
                    f.write("".join(lines))
                
                return {
                    "message": f"Text inserted at line {insert_line} in file: {path}"
                }
            
            elif command == "undo_edit":
                # Undo the last edit
                backup_path = f"{path}.bak"
                
                if not os.path.isfile(backup_path):
                    return {
                        "error": f"No backup file found for: {path}"
                    }
                
                with open(backup_path, "r") as f:
                    content = f.read()
                
                with open(path, "w") as f:
                    f.write(content)
                
                os.remove(backup_path)
                
                return {
                    "message": f"Edit undone for file: {path}"
                }
            
            else:
                return {
                    "error": f"Unknown command: {command}"
                }
        
        except Exception as e:
            return {
                "error": f"Error executing {command} on {path}: {str(e)}"
            }


class ToolRegistry:
    """Registry for all available tools."""
    
    def __init__(self):
        """Initialize the tool registry."""
        self.tools = {}
        self._register_default_tools()
    
    def _register_default_tools(self):
        """Register the default tools."""
        self.register_tool(ExecuteBashTool())
        self.register_tool(ThinkTool())
        self.register_tool(FinishTool())
        self.register_tool(WebReadTool())
        self.register_tool(BrowserTool())
        self.register_tool(ExecuteIPythonCellTool())
        self.register_tool(StrReplaceEditorTool())
    
    def register_tool(self, tool: BaseTool):
        """Register a tool."""
        self.tools[tool.name] = tool
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self.tools.get(name)
    
    def get_all_tools(self) -> List[BaseTool]:
        """Get all registered tools."""
        return list(self.tools.values())
    
    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Get the JSON schemas for all tools."""
        schemas = []
        for tool in self.tools.values():
            schema = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": tool.parameters["properties"],
                        "required": tool.required
                    }
                }
            }
            schemas.append(schema)
        return schemas
    
    def execute_tool(self, name: str, **kwargs) -> Dict[str, Any]:
        """Execute a tool by name with the given parameters."""
        tool = self.get_tool(name)
        if not tool:
            return {"error": f"Tool not found: {name}"}
        
        return tool.execute(**kwargs)


# Singleton instance
tool_registry = ToolRegistry()