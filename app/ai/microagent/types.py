"""
Type definitions for the Backdoor Microagent System.
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class MicroagentType(str, Enum):
    """Types of microagents in the Backdoor system."""
    KNOWLEDGE = "knowledge"
    REPO_KNOWLEDGE = "repo_knowledge"
    TASK = "task"


class MicroagentMetadata(BaseModel):
    """Metadata for a microagent, extracted from frontmatter."""
    name: str = Field(..., description="Name of the microagent")
    description: Optional[str] = Field(None, description="Description of the microagent")
    version: Optional[str] = Field("1.0.0", description="Version of the microagent")
    author: Optional[str] = Field(None, description="Author of the microagent")
    triggers: List[str] = Field(default_factory=list, description="List of trigger phrases for knowledge agents")
    type: MicroagentType = Field(default=MicroagentType.KNOWLEDGE, description="Type of microagent")
    priority: int = Field(default=0, description="Priority of the microagent (higher = more important)")
    enabled: bool = Field(default=True, description="Whether the microagent is enabled")
    tags: List[str] = Field(default_factory=list, description="Tags for the microagent")
    
    class Config:
        use_enum_values = True

