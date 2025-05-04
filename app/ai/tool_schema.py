"""
Tool Schema Validation for Backdoor AI

This module provides schema validation for tools in the Backdoor AI system,
inspired by the Cloudflare AI tool calling implementation but adapted for
Python and SQLAlchemy integration.
"""

import json
import inspect
import logging
from typing import Dict, List, Any, Optional, Union, Callable, Type, TypeVar, Generic, get_type_hints
from enum import Enum
from pydantic import BaseModel, Field, create_model, ValidationError

from app.database import db
from app.ai.mcp_models import ToolUsage, ToolResult

# Set up logging
logger = logging.getLogger("tool_schema")

class ToolError(Exception):
    """Base error class for tool-related errors."""
    pass

class ToolValidationError(ToolError):
    """Error raised when tool parameters fail validation."""
    pass

class ToolExecutionError(ToolError):
    """Error raised when tool execution fails."""
    pass

class ToolDefinition(BaseModel):
    """Definition of a tool in the Backdoor AI system."""
    name: str
    description: str
    schema_model: Type[BaseModel]
    execute_func: Callable
    required_permissions: List[str] = Field(default_factory=list)
    
    class Config:
        arbitrary_types_allowed = True

class ToolParameterValidator:
    """Validates parameters for tool execution against a schema."""
    
    @staticmethod
    def create_model_from_function(
        func: Callable, 
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> Type[BaseModel]:
        """
        Create a Pydantic model from a function's type hints.
        
        Args:
            func: The function to create a model for
            name: Optional name for the model
            description: Optional description for the model
            
        Returns:
            A Pydantic model class for the function parameters
        """
        if name is None:
            name = f"{func.__name__}Parameters"
        
        # Get function signature and type hints
        sig = inspect.signature(func)
        type_hints = get_type_hints(func)
        
        # Create field definitions
        fields = {}
        for param_name, param in sig.parameters.items():
            # Skip self parameter
            if param_name == 'self':
                continue
            
            # Get type annotation
            annotation = type_hints.get(param_name, Any)
            
            # Get default value
            if param.default is not inspect.Parameter.empty:
                fields[param_name] = (annotation, param.default)
            else:
                fields[param_name] = (annotation, ...)
        
        # Create the model
        model = create_model(
            name,
            **fields,
            __doc__=description or func.__doc__
        )
        
        return model
    
    @staticmethod
    def validate_parameters(schema_model: Type[BaseModel], parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate parameters against a schema model.
        
        Args:
            schema_model: The Pydantic model to validate against
            parameters: The parameters to validate
            
        Returns:
            Validated and potentially transformed parameters
            
        Raises:
            ToolValidationError: If validation fails
        """
        try:
            # Validate parameters against schema
            validated = schema_model(**parameters)
            return validated.dict()
        except ValidationError as e:
            raise ToolValidationError(f"Parameter validation failed: {str(e)}")

class ToolRegistry:
    """Registry of available tools in the Backdoor AI system."""
    
    def __init__(self):
        """Initialize the tool registry."""
        self.tools: Dict[str, ToolDefinition] = {}
    
    def register_tool(self, 
                     name: str, 
                     description: str, 
                     execute_func: Callable, 
                     schema_model: Optional[Type[BaseModel]] = None,
                     required_permissions: Optional[List[str]] = None) -> None:
        """
        Register a tool in the registry.
        
        Args:
            name: Unique name for the tool
            description: Description of what the tool does
            execute_func: Function that implements the tool's functionality
            schema_model: Optional Pydantic model for parameter validation
            required_permissions: Optional list of permissions required to use this tool
        """
        if name in self.tools:
            logger.warning(f"Tool {name} already registered, overwriting")
        
        # Create schema model from function if not provided
        if schema_model is None:
            schema_model = ToolParameterValidator.create_model_from_function(
                execute_func, 
                name=f"{name}Parameters",
                description=description
            )
        
        # Create tool definition
        tool_def = ToolDefinition(
            name=name,
            description=description,
            schema_model=schema_model,
            execute_func=execute_func,
            required_permissions=required_permissions or []
        )
        
        # Register the tool
        self.tools[name] = tool_def
        logger.info(f"Registered tool: {name}")
    
    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """
        Get a tool definition by name.
        
        Args:
            name: Name of the tool
            
        Returns:
            Tool definition or None if not found
        """
        return self.tools.get(name)
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """
        List all registered tools.
        
        Returns:
            List of tool definitions as dictionaries
        """
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "required_permissions": tool.required_permissions,
                "schema": json.loads(tool.schema_model.schema_json())
            }
            for tool in self.tools.values()
        ]
    
    def execute_tool(self, 
                    name: str, 
                    parameters: Dict[str, Any],
                    agent_id: Optional[str] = None,
                    record: bool = True) -> Dict[str, Any]:
        """
        Execute a tool with the given parameters.
        
        Args:
            name: Name of the tool to execute
            parameters: Parameters for the tool
            agent_id: Optional ID of the agent executing the tool
            record: Whether to record the tool execution in the database
            
        Returns:
            Result of the tool execution
            
        Raises:
            ToolError: If tool not found or execution fails
        """
        # Get the tool
        tool = self.get_tool(name)
        if not tool:
            raise ToolError(f"Tool not found: {name}")
        
        try:
            # Validate parameters
            validated_params = ToolParameterValidator.validate_parameters(
                tool.schema_model, 
                parameters
            )
            
            # Execute the tool
            result = tool.execute_func(**validated_params)
            
            # Record execution if requested
            if record:
                self._record_execution(
                    name=name,
                    parameters=parameters,
                    result=result,
                    success=True,
                    agent_id=agent_id
                )
            
            return result
        except ToolValidationError as e:
            # Validation error
            error_result = {
                "success": False,
                "error": str(e),
                "error_type": "validation"
            }
            
            # Record failure if requested
            if record:
                self._record_execution(
                    name=name,
                    parameters=parameters,
                    result=error_result,
                    success=False,
                    agent_id=agent_id
                )
            
            raise
        except Exception as e:
            # Execution error
            logger.exception(f"Error executing tool {name}: {e}")
            error_result = {
                "success": False,
                "error": str(e),
                "error_type": "execution"
            }
            
            # Record failure if requested
            if record:
                self._record_execution(
                    name=name,
                    parameters=parameters,
                    result=error_result,
                    success=False,
                    agent_id=agent_id
                )
            
            raise ToolExecutionError(f"Tool execution failed: {e}")
    
    def _record_execution(self,
                         name: str,
                         parameters: Dict[str, Any],
                         result: Dict[str, Any],
                         success: bool,
                         agent_id: Optional[str] = None) -> None:
        """
        Record a tool execution in the database.
        
        Args:
            name: Name of the tool
            parameters: Parameters used
            result: Result of the execution
            success: Whether the execution was successful
            agent_id: Optional ID of the agent that executed the tool
        """
        try:
            # Create tool result
            tool_result = ToolResult(
                result_data=result,
                output_text=str(result.get('output', '')),
                exit_code=result.get('exit_code')
            )
            
            db.session.add(tool_result)
            db.session.flush()  # Get the ID without committing
            
            # Create tool usage
            tool_usage = ToolUsage(
                tool_type=name,
                params=parameters,
                success=success,
                error_message=result.get('error') if not success else None,
                agent_id=agent_id,
                result_id=tool_result.id
            )
            
            db.session.add(tool_usage)
            db.session.commit()
            
            logger.debug(f"Recorded tool execution: {name} (success={success})")
        except Exception as e:
            logger.error(f"Error recording tool execution: {e}")
            db.session.rollback()

# Create singleton instance
tool_registry = ToolRegistry()
