"""
Agent Configuration for Backdoor AI

This module provides configuration classes for Backdoor AI agents, inspired by
the OpenHands agent configuration but adapted for Python, Flask, and
SQLAlchemy integration.
"""

from pydantic import BaseModel, Field
import logging

# Set up logging
logger = logging.getLogger("agent_config")


class AgentConfig(BaseModel):
    """Configuration for a Backdoor AI agent."""
    
    llm_config: str | None = Field(default=None, 
                                  description="The name of the LLM config to use. If specified, this will override global LLM config.")
    
    enable_browsing: bool = Field(default=True,
                                 description="Whether to enable browsing tool")
    
    enable_llm_editor: bool = Field(default=False,
                                   description="Whether to enable LLM editor tool")
    
    enable_editor: bool = Field(default=True,
                               description="Whether to enable the standard editor tool, only has an effect if enable_llm_editor is False.")
    
    enable_jupyter: bool = Field(default=True,
                                description="Whether to enable Jupyter tool")
    
    enable_cmd: bool = Field(default=True,
                            description="Whether to enable bash tool")
    
    enable_think: bool = Field(default=True,
                              description="Whether to enable think tool")
    
    enable_finish: bool = Field(default=True,
                               description="Whether to enable finish tool")
    
    enable_prompt_extensions: bool = Field(default=True,
                                         description="Whether to enable prompt extensions")
    
    disabled_microagents: list[str] = Field(default_factory=list,
                                          description="A list of microagents to disable (by name, without .py extension)")
    
    enable_history_truncation: bool = Field(default=True,
                                          description="Whether history should be truncated to continue the session when hitting LLM context length limit")
    
    model_config = {'extra': 'forbid'}
    
    @classmethod
    def from_dict(cls, data: dict) -> dict[str, 'AgentConfig']:
        """
        Create a mapping of AgentConfig instances from a dictionary.
        
        The default configuration is built from all non-dict keys in data.
        Then, each key with a dict value is treated as a custom agent configuration, and its values override
        the default configuration.
        
        Returns:
            dict[str, AgentConfig]: A mapping where the key "agent" corresponds to the default configuration
            and additional keys represent custom configurations.
        """
        
        # Initialize the result mapping
        agent_mapping: dict[str, AgentConfig] = {}
        
        # Extract base config data (non-dict values)
        base_data = {}
        custom_sections: dict[str, dict] = {}
        for key, value in data.items():
            if isinstance(value, dict):
                custom_sections[key] = value
            else:
                base_data[key] = value
        
        # Try to create the base config
        try:
            base_config = cls.model_validate(base_data)
            agent_mapping['agent'] = base_config
        except Exception as e:
            logger.warning(f'Invalid base agent configuration: {e}. Using defaults.')
            # If base config fails, create a default one
            base_config = cls()
            # Still add it to the mapping
            agent_mapping['agent'] = base_config
        
        # Process each custom section independently
        for name, overrides in custom_sections.items():
            try:
                # Merge base config with overrides
                merged = {**base_config.model_dump(), **overrides}
                custom_config = cls.model_validate(merged)
                agent_mapping[name] = custom_config
            except Exception as e:
                logger.warning(f'Invalid agent configuration for [{name}]: {e}. This section will be skipped.')
                # Skip this custom section but continue with others
                continue
        
        return agent_mapping

