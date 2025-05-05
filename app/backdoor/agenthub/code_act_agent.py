"""
CodeActAgent implementation for Backdoor.
Adapted from OpenHands with modifications for Backdoor Flask app.
"""
import json
import os
import time
from typing import Any, Dict, List, Optional, Union

from app.backdoor.agenthub.agent import Agent
from app.backdoor.core.config import AppConfig
from app.backdoor.core.exceptions import (
    AgentRuntimeError,
    ToolExecutionError,
    ToolNotFoundError,
)
from app.backdoor.core.logger import get_logger
from app.backdoor.llm.together_client import TogetherClient
from app.backdoor.runtime.docker_runtime import DockerRuntime

logger = get_logger("agenthub.code_act_agent")

class CodeActAgent(Agent):
    """CodeActAgent for Backdoor.
    
    This agent is designed to execute code and other actions in a sandboxed environment.
    """
    
    def __init__(self, config: AppConfig, session_id: str):
        """Initialize the CodeActAgent.
        
        Args:
            config: The application configuration.
            session_id: The session ID.
        """
        super().__init__(config, session_id)
        
        # Initialize LLM client
        self.llm = TogetherClient(
            api_key=config.llm.api_key,
            model=config.llm.model
        )
        
        # Initialize runtime
        self.runtime = None
        if config.docker.enabled:
            try:
                self.runtime = DockerRuntime(
                    config=config,
                    sid=session_id,
                    env_vars={
                        "TOGETHER_API_KEY": config.llm.api_key,
                        "GITHUB_TOKEN": config.github.token,
                    },
                    headless_mode=True
                )
            except Exception as e:
                logger.error(f"Failed to initialize Docker runtime: {e}")
        
        # Load tools
        self._load_tools()
        
        # Load microagents
        self._load_microagents()
        
        self.initialized = True
    
    def _load_tools(self):
        """Load tools for the agent."""
        # Define standard tools
        standard_tools = [
            {
                "name": "execute_bash",
                "description": "Execute a bash command in the terminal within a persistent shell session.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "The bash command to execute."
                        },
                        "is_input": {
                            "type": "boolean",
                            "description": "If True, the command is an input to the running process."
                        }
                    },
                    "required": ["command"]
                }
            },
            {
                "name": "str_replace_editor",
                "description": "Custom editing tool for viewing, creating and editing files in plain-text format.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "enum": ["view", "create", "str_replace", "insert", "undo_edit"],
                            "description": "The commands to run."
                        },
                        "path": {
                            "type": "string",
                            "description": "Absolute path to file or directory."
                        },
                        "old_str": {
                            "type": "string",
                            "description": "Required parameter of `str_replace` command containing the string in `path` to replace."
                        },
                        "new_str": {
                            "type": "string",
                            "description": "Optional parameter of `str_replace` command containing the new string."
                        },
                        "file_text": {
                            "type": "string",
                            "description": "Required parameter of `create` command, with the content of the file to be created."
                        },
                        "insert_line": {
                            "type": "integer",
                            "description": "Required parameter of `insert` command."
                        },
                        "view_range": {
                            "type": "array",
                            "items": {
                                "type": "integer"
                            },
                            "description": "Optional parameter of `view` command when `path` points to a file."
                        }
                    },
                    "required": ["command", "path"]
                }
            },
            {
                "name": "browser",
                "description": "Interact with the browser using Python code.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "The Python code that interacts with the browser."
                        }
                    },
                    "required": ["code"]
                }
            },
            {
                "name": "execute_ipython_cell",
                "description": "Run a cell of Python code in an IPython environment.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "The Python code to execute."
                        }
                    },
                    "required": ["code"]
                }
            },
            {
                "name": "think",
                "description": "Use the tool to think about something.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "thought": {
                            "type": "string",
                            "description": "The thought to log."
                        }
                    },
                    "required": ["thought"]
                }
            },
            {
                "name": "web_read",
                "description": "Read content from a webpage.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The URL of the webpage to read."
                        }
                    },
                    "required": ["url"]
                }
            },
            {
                "name": "finish",
                "description": "Signals the completion of the current task or conversation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "Final message to send to the user."
                        },
                        "task_completed": {
                            "type": "boolean",
                            "description": "Whether you have completed the task."
                        }
                    },
                    "required": ["message", "task_completed"]
                }
            }
        ]
        
        # Register standard tools
        self.register_tools(standard_tools)
    
    def _load_microagents(self):
        """Load microagents for the agent."""
        microagents_dir = self.config.agent.microagents_dir
        
        if not os.path.exists(microagents_dir):
            logger.warning(f"Microagents directory not found: {microagents_dir}")
            return
        
        # Copy microagents from OpenHands if available
        openhands_microagents_dir = os.path.join(os.path.dirname(__file__), "../../../OpenHands/microagents")
        if os.path.exists(openhands_microagents_dir):
            import shutil
            for filename in os.listdir(openhands_microagents_dir):
                if filename.endswith(".md") and filename != "README.md":
                    src_path = os.path.join(openhands_microagents_dir, filename)
                    dst_path = os.path.join(microagents_dir, filename)
                    
                    # Read the file and replace "openhands" with "backdoor"
                    with open(src_path, "r") as src_file:
                        content = src_file.read()
                    
                    content = content.replace("openhands", "backdoor")
                    content = content.replace("OpenHands", "Backdoor")
                    
                    # Write the modified content to the destination
                    with open(dst_path, "w") as dst_file:
                        dst_file.write(content)
                    
                    logger.info(f"Copied and adapted microagent: {filename}")
        
        # Load microagents
        microagent_files = [f for f in os.listdir(microagents_dir) if f.endswith(".md")]
        
        for filename in microagent_files:
            try:
                with open(os.path.join(microagents_dir, filename), "r") as f:
                    content = f.read()
                
                # Extract metadata from frontmatter
                import re
                frontmatter_match = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
                
                if frontmatter_match:
                    frontmatter = frontmatter_match.group(1)
                    
                    # Parse frontmatter
                    metadata = {}
                    for line in frontmatter.split("\n"):
                        if ":" in line:
                            key, value = line.split(":", 1)
                            metadata[key.strip()] = value.strip()
                    
                    logger.info(f"Loaded microagent: {metadata.get('name', filename)}")
                
            except Exception as e:
                logger.error(f"Failed to load microagent {filename}: {e}")
    
    def initialize(self):
        """Initialize the agent."""
        if self.initialized:
            return
        
        # Initialize LLM
        if not self.llm.get_api_key():
            api_key = self.config.llm.api_key
            if api_key:
                self.llm.set_api_key(api_key)
        
        # Initialize runtime
        if not self.runtime and self.config.docker.enabled:
            try:
                self.runtime = DockerRuntime(
                    config=self.config,
                    sid=self.session_id,
                    env_vars={
                        "TOGETHER_API_KEY": self.config.llm.api_key,
                        "GITHUB_TOKEN": self.config.github.token,
                    },
                    headless_mode=True
                )
            except Exception as e:
                logger.error(f"Failed to initialize Docker runtime: {e}")
        
        self.initialized = True
    
    def process_message(self, message: str) -> Dict[str, Any]:
        """Process a message.
        
        Args:
            message: The message to process.
            
        Returns:
            The response.
        """
        if not self.initialized:
            self.initialize()
        
        # Add user message to conversation
        self.add_to_conversation("user", message)
        
        # Prepare messages for LLM
        messages = self.get_conversation_history()
        
        # Add system message with tools
        system_message = {
            "role": "system",
            "content": self._get_system_prompt()
        }
        
        messages = [system_message] + messages
        
        # Generate response
        try:
            response = self.llm.chat_completion(
                messages=messages,
                temperature=self.config.agent.temperature,
                max_tokens=self.config.agent.max_tokens,
                tools=self.tools,
                tool_choice="auto"
            )
            
            # Process response
            assistant_message = response["choices"][0]["message"]
            content = assistant_message.get("content", "")
            
            # Check for tool calls
            tool_calls = assistant_message.get("tool_calls", [])
            
            if tool_calls:
                # Execute tools
                for tool_call in tool_calls:
                    tool_name = tool_call["function"]["name"]
                    tool_args = json.loads(tool_call["function"]["arguments"])
                    
                    try:
                        tool_result = self.execute_tool(tool_name, tool_args)
                        
                        # Save tool result
                        self.save_tool_result(tool_name, tool_args, tool_result)
                        
                        # Add tool call and result to conversation
                        self.add_to_conversation("assistant", f"I'll use the {tool_name} tool.")
                        self.add_to_conversation("tool", json.dumps(tool_result))
                        
                    except Exception as e:
                        error_message = f"Error executing tool {tool_name}: {e}"
                        logger.error(error_message)
                        self.add_to_conversation("tool", error_message)
                
                # Generate follow-up response
                follow_up_response = self.llm.chat_completion(
                    messages=self.get_conversation_history(),
                    temperature=self.config.agent.temperature,
                    max_tokens=self.config.agent.max_tokens
                )
                
                content = follow_up_response["choices"][0]["message"]["content"]
            
            # Add assistant response to conversation
            self.add_to_conversation("assistant", content)
            
            return {
                "role": "assistant",
                "content": content,
                "tool_calls": tool_calls
            }
            
        except Exception as e:
            error_message = f"Error processing message: {e}"
            logger.error(error_message)
            
            # Add error to conversation
            self.add_to_conversation("system", error_message)
            
            return {
                "role": "assistant",
                "content": f"I encountered an error: {e}",
                "error": str(e)
            }
    
    def execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool.
        
        Args:
            tool_name: The name of the tool to execute.
            tool_args: The arguments for the tool.
            
        Returns:
            The tool execution result.
        """
        # Check if tool exists
        tool_exists = any(tool["name"] == tool_name for tool in self.tools)
        if not tool_exists:
            raise ToolNotFoundError(f"Tool not found: {tool_name}")
        
        # Execute tool based on name
        if tool_name == "execute_bash":
            return self._execute_bash_tool(tool_args)
        elif tool_name == "str_replace_editor":
            return self._execute_editor_tool(tool_args)
        elif tool_name == "browser":
            return self._execute_browser_tool(tool_args)
        elif tool_name == "execute_ipython_cell":
            return self._execute_ipython_tool(tool_args)
        elif tool_name == "think":
            return self._execute_think_tool(tool_args)
        elif tool_name == "web_read":
            return self._execute_web_read_tool(tool_args)
        elif tool_name == "finish":
            return self._execute_finish_tool(tool_args)
        else:
            raise ToolNotFoundError(f"Tool implementation not found: {tool_name}")
    
    def _execute_bash_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the bash tool.
        
        Args:
            args: The tool arguments.
            
        Returns:
            The tool execution result.
        """
        if not self.runtime:
            raise AgentRuntimeError("Runtime not available")
        
        command = args.get("command", "")
        is_input = args.get("is_input", False)
        
        if not command:
            raise ToolExecutionError("Command is required")
        
        # Execute command in runtime
        result = self.runtime.execute_command(f"bash -c '{command}'")
        
        return {
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
            "exit_code": result.get("exit_code", -1)
        }
    
    def _execute_editor_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the editor tool.
        
        Args:
            args: The tool arguments.
            
        Returns:
            The tool execution result.
        """
        if not self.runtime:
            raise AgentRuntimeError("Runtime not available")
        
        command = args.get("command", "")
        path = args.get("path", "")
        
        if not command:
            raise ToolExecutionError("Command is required")
        
        if not path:
            raise ToolExecutionError("Path is required")
        
        # Execute different commands based on the command type
        if command == "view":
            view_range = args.get("view_range", [])
            
            if view_range:
                range_str = f"{view_range[0]},{view_range[1]}"
                result = self.runtime.execute_command(f"sed -n '{range_str}p' {path}")
            else:
                result = self.runtime.execute_command(f"cat -n {path}")
            
            return {
                "content": result.get("stdout", ""),
                "error": result.get("stderr", "")
            }
            
        elif command == "create":
            file_text = args.get("file_text", "")
            
            if not file_text:
                raise ToolExecutionError("File text is required for create command")
            
            # Create parent directory if it doesn't exist
            parent_dir = os.path.dirname(path)
            self.runtime.execute_command(f"mkdir -p {parent_dir}")
            
            # Write file
            echo_command = f"cat > {path} << 'EOT'\n{file_text}\nEOT"
            result = self.runtime.execute_command(echo_command)
            
            return {
                "success": result.get("exit_code", -1) == 0,
                "error": result.get("stderr", "")
            }
            
        elif command == "str_replace":
            old_str = args.get("old_str", "")
            new_str = args.get("new_str", "")
            
            if not old_str:
                raise ToolExecutionError("Old string is required for str_replace command")
            
            # Create a sed command to replace the string
            # Fix backslash escaping for sed command
            old_str_escaped = old_str.replace('/', r'\/').replace('\\', r'\\')
            new_str_escaped = new_str.replace('/', r'\/').replace('\\', r'\\')
            sed_command = f"sed -i 's/{old_str_escaped}/{new_str_escaped}/g' {path}"
            result = self.runtime.execute_command(sed_command)
            
            return {
                "success": result.get("exit_code", -1) == 0,
                "error": result.get("stderr", "")
            }
            
        elif command == "insert":
            insert_line = args.get("insert_line", 0)
            new_str = args.get("new_str", "")
            
            if insert_line <= 0:
                raise ToolExecutionError("Insert line must be a positive integer")
            
            if not new_str:
                raise ToolExecutionError("New string is required for insert command")
            
            # Create a sed command to insert the string
            # Escape special characters in the new string
            new_str_escaped = new_str.replace("'", "'\\''")
            sed_command = f"sed -i '{insert_line}a {new_str_escaped}' {path}"
            result = self.runtime.execute_command(sed_command)
            
            return {
                "success": result.get("exit_code", -1) == 0,
                "error": result.get("stderr", "")
            }
            
        elif command == "undo_edit":
            # Not implemented
            return {
                "success": False,
                "error": "Undo edit not implemented"
            }
            
        else:
            raise ToolExecutionError(f"Unknown command: {command}")
    
    def _execute_browser_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the browser tool.
        
        Args:
            args: The tool arguments.
            
        Returns:
            The tool execution result.
        """
        # Not implemented in this version
        return {
            "success": False,
            "error": "Browser tool not implemented"
        }
    
    def _execute_ipython_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the IPython tool.
        
        Args:
            args: The tool arguments.
            
        Returns:
            The tool execution result.
        """
        if not self.runtime:
            raise AgentRuntimeError("Runtime not available")
        
        code = args.get("code", "")
        
        if not code:
            raise ToolExecutionError("Code is required")
        
        # Create a temporary Python file
        temp_file = f"/tmp/backdoor_ipython_{int(time.time())}.py"
        
        # Write code to file
        echo_command = f"cat > {temp_file} << 'EOT'\n{code}\nEOT"
        self.runtime.execute_command(echo_command)
        
        # Execute the Python file
        result = self.runtime.execute_command(f"python3 {temp_file}")
        
        # Clean up
        self.runtime.execute_command(f"rm {temp_file}")
        
        return {
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
            "exit_code": result.get("exit_code", -1)
        }
    
    def _execute_think_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the think tool.
        
        Args:
            args: The tool arguments.
            
        Returns:
            The tool execution result.
        """
        thought = args.get("thought", "")
        
        if not thought:
            raise ToolExecutionError("Thought is required")
        
        logger.info(f"Agent thought: {thought}")
        
        return {
            "thought": thought
        }
    
    def _execute_web_read_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the web read tool.
        
        Args:
            args: The tool arguments.
            
        Returns:
            The tool execution result.
        """
        url = args.get("url", "")
        
        if not url:
            raise ToolExecutionError("URL is required")
        
        try:
            import httpx
            from bs4 import BeautifulSoup
            import markdown
            
            response = httpx.get(url, timeout=30)
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Failed to fetch URL: {response.status_code}"
                }
            
            # Parse HTML
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.extract()
            
            # Get text
            text = soup.get_text()
            
            # Break into lines and remove leading and trailing space
            lines = (line.strip() for line in text.splitlines())
            # Break multi-headlines into a line each
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            # Drop blank lines
            text = "\n".join(chunk for chunk in chunks if chunk)
            
            # Convert to markdown
            markdown_text = markdown.markdown(text)
            
            return {
                "success": True,
                "content": markdown_text,
                "url": url
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Error reading URL: {e}",
                "url": url
            }
    
    def _execute_finish_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the finish tool.
        
        Args:
            args: The tool arguments.
            
        Returns:
            The tool execution result.
        """
        message = args.get("message", "")
        task_completed = args.get("task_completed", False)
        
        return {
            "message": message,
            "task_completed": task_completed
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get the agent status.
        
        Returns:
            The agent status.
        """
        runtime_status = {}
        if self.runtime:
            runtime_status = self.runtime.get_status()
        
        llm_status = self.llm.get_status()
        
        return {
            "initialized": self.initialized,
            "session_id": self.session_id,
            "runtime": runtime_status,
            "llm": llm_status,
            "tools_count": len(self.tools),
            "conversation_length": len(self.conversation_history),
            "tool_results_count": len(self.tool_results)
        }
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for the agent.
        
        Returns:
            The system prompt.
        """
        return """
You are Backdoor agent, a helpful AI assistant that can interact with a computer to solve tasks.

<ROLE>
Your primary role is to assist users by executing commands, modifying code, and solving technical problems effectively. You should be thorough, methodical, and prioritize quality over speed.
* If the user asks a question, like "why is X happening", don't try to fix the problem. Just give an answer to the question.
</ROLE>

<EFFICIENCY>
* Each action you take is somewhat expensive. Wherever possible, combine multiple actions into a single action, e.g. combine multiple bash commands into one, using sed and grep to edit/view multiple files at once.
* When exploring the codebase, use efficient tools like find, grep, and git commands with appropriate filters to minimize unnecessary operations.
</EFFICIENCY>

<FILE_SYSTEM_GUIDELINES>
* When a user provides a file path, do NOT assume it's relative to the current working directory. First explore the file system to locate the file before working on it.
* If asked to edit a file, edit the file directly, rather than creating a new file with a different filename.
* For global search-and-replace operations, consider using `sed` instead of opening file editors multiple times.
</FILE_SYSTEM_GUIDELINES>

<CODE_QUALITY>
* Write clean, efficient code with minimal comments. Avoid redundancy in comments: Do not repeat information that can be easily inferred from the code itself.
* When implementing solutions, focus on making the minimal changes needed to solve the problem.
* Before implementing any changes, first thoroughly understand the codebase through exploration.
* If you are adding a lot of code to a function or file, consider splitting the function or file into smaller pieces when appropriate.
</CODE_QUALITY>

<VERSION_CONTROL>
* When configuring git credentials, use "backdoor" as the user.name and "backdoor@example.com" as the user.email by default, unless explicitly instructed otherwise.
* Exercise caution with git operations. Do NOT make potentially dangerous changes (e.g., pushing to main, deleting repositories) unless explicitly asked to do so.
* When committing changes, use `git status` to see all modified files, and stage all files necessary for the commit. Use `git commit -a` whenever possible.
* Do NOT commit files that typically shouldn't go into version control (e.g., node_modules/, .env files, build directories, cache files, large binaries) unless explicitly instructed by the user.
* If unsure about committing certain files, check for the presence of .gitignore files or ask the user for clarification.
</VERSION_CONTROL>

<PROBLEM_SOLVING_WORKFLOW>
1. EXPLORATION: Thoroughly explore relevant files and understand the context before proposing solutions
2. ANALYSIS: Consider multiple approaches and select the most promising one
3. TESTING:
   * For bug fixes: Create tests to verify issues before implementing fixes
   * For new features: Consider test-driven development when appropriate
   * If the repository lacks testing infrastructure and implementing tests would require extensive setup, consult with the user before investing time in building testing infrastructure
   * If the environment is not set up to run tests, consult with the user first before investing time to install all dependencies
4. IMPLEMENTATION: Make focused, minimal changes to address the problem
5. VERIFICATION: If the environment is set up to run tests, test your implementation thoroughly, including edge cases. If the environment is not set up to run tests, consult with the user first before investing time to run tests.
</PROBLEM_SOLVING_WORKFLOW>

<SECURITY>
* Only use GITHUB_TOKEN and other credentials in ways the user has explicitly requested and would expect.
* Use APIs to work with GitHub or other platforms, unless the user asks otherwise or your task requires browsing.
</SECURITY>

<ENVIRONMENT_SETUP>
* When user asks you to run an application, don't stop if the application is not installed. Instead, please install the application and run the command again.
* If you encounter missing dependencies:
  1. First, look around in the repository for existing dependency files (requirements.txt, pyproject.toml, package.json, Gemfile, etc.)
  2. If dependency files exist, use them to install all dependencies at once (e.g., `pip install -r requirements.txt`, `npm install`, etc.)
  3. Only install individual packages directly if no dependency files are found or if only specific packages are needed
* Similarly, if you encounter missing dependencies for essential tools requested by the user, install them when possible.
</ENVIRONMENT_SETUP>

<TROUBLESHOOTING>
* If you've made repeated attempts to solve a problem but tests still fail or the user reports it's still broken:
  1. Step back and reflect on 5-7 different possible sources of the problem
  2. Assess the likelihood of each possible cause
  3. Methodically address the most likely causes, starting with the highest probability
  4. Document your reasoning process
* When you run into any major issue while executing a plan from the user, please don't try to directly work around it. Instead, propose a new plan and confirm with the user before proceeding.
</TROUBLESHOOTING>
"""