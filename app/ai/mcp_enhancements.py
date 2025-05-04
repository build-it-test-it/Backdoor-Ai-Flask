"""
Enhancements for the Model Context Protocol (MCP) Server

This module provides enhancements to the MCP server based on concepts from Cloudflare AI,
including improved context prioritization, context chaining, and integration with the 
enhanced agent system.
"""

import json
import logging
import time
import asyncio
from typing import Dict, List, Any, Optional, Union, Callable, TypeVar, Generic
from datetime import datetime, timedelta
import traceback

from app.database import db
from app.ai.mcp_models import ContextItem, Agent, ToolUsage, ToolResult, Task
from app.ai.mcp_server import mcp_server
from app.ai.enhanced_agents import enhanced_agent_manager, EnhancedAgent

# Set up logging
logger = logging.getLogger("mcp_enhancements")

class ContextPrioritizer:
    """
    Prioritizes context items based on various factors like recency,
    relevance, type, and user interactions.
    """
    
    @staticmethod
    def calculate_priority(
        item_type: str, 
        creation_time: datetime,
        update_time: datetime,
        ttl: int,
        user_interaction_count: int = 0,
        agent_interaction_count: int = 0,
        relevance_score: float = 0.0
    ) -> float:
        """
        Calculate a priority score for a context item.
        
        Args:
            item_type: Type of the context item
            creation_time: When the item was created
            update_time: When the item was last updated
            ttl: Time to live in seconds
            user_interaction_count: Number of interactions from users
            agent_interaction_count: Number of interactions from agents
            relevance_score: Optional relevance score from semantic search
            
        Returns:
            Priority score between 0.0 and 1.0
        """
        # Base type priorities (0.0 to 1.0)
        type_priority = {
            'user_info': 0.9,       # User profile and preferences
            'session': 0.85,        # Session-specific context
            'behavior': 0.8,        # User behavior patterns
            'interaction': 0.75,    # User-AI interactions
            'github': 0.7,          # GitHub repository context
            'environment': 0.65,    # System environment
            'tool_usage': 0.6,      # Tool usage history
            'tool_result': 0.6,     # Tool execution results
            'task': 0.7,            # Task information
            'agent': 0.85,          # Agent information
            'decision': 0.7,        # Decision information
            'metadata': 0.5,        # Metadata
            'request': 0.75         # Current request
        }.get(item_type, 0.5)       # Default priority for unknown types
        
        # Recency factor (0.0 to 1.0) - higher for more recent items
        # For items updated very recently, this will be close to 1.0
        # For items approaching their TTL, this will approach 0.0
        now = datetime.utcnow()
        age_seconds = (now - update_time).total_seconds()
        recency_factor = max(0.0, 1.0 - (age_seconds / ttl))
        
        # Interaction factor (0.0 to 1.0) - higher for items with more interactions
        # We use a logarithmic scale to avoid items with many interactions dominating
        interaction_count = user_interaction_count + agent_interaction_count
        interaction_factor = min(1.0, 0.1 * interaction_count ** 0.5)
        
        # Combine factors with appropriate weights
        # Type is most important, then recency, then interactions
        # If relevance score is provided, it's factored in
        priority = (
            (0.5 * type_priority) +           # 50% weight for type
            (0.3 * recency_factor) +          # 30% weight for recency
            (0.1 * interaction_factor) +      # 10% weight for interactions
            (0.1 * relevance_score)           # 10% weight for relevance
        )
        
        # Ensure priority is between 0.0 and 1.0
        return max(0.0, min(1.0, priority))
    
    @staticmethod
    def update_context_priorities():
        """Update priorities for all context items in the database."""
        try:
            # Get all non-expired context items
            items = db.session.query(ContextItem).filter(
                ContextItem.is_expired == False
            ).all()
            
            for item in items:
                # Calculate new priority
                # We don't have interaction counts in the current model
                # Could be added in future enhancements
                priority = ContextPrioritizer.calculate_priority(
                    item_type=item.item_type,
                    creation_time=item.created_at,
                    update_time=item.updated_at,
                    ttl=item.ttl
                )
                
                # Convert priority to integer in range 0-100 for database storage
                item.priority = int(priority * 100)
            
            # Commit changes
            db.session.commit()
            logger.info(f"Updated priorities for {len(items)} context items")
        
        except Exception as e:
            logger.error(f"Error updating context priorities: {e}")
            db.session.rollback()

class ContextChain:
    """
    Manages chains of related context items, allowing for structured
    context relationships and reasoning chains.
    """
    
    @staticmethod
    def create_chain(
        root_item_id: str,
        chain_name: str,
        description: str,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new context chain.
        
        Args:
            root_item_id: ID of the root context item
            chain_name: Name for the chain
            description: Description of the chain
            session_id: Optional session ID
            
        Returns:
            Chain metadata
        """
        try:
            # Get the root item
            root_item = db.session.query(ContextItem).filter(
                ContextItem.id == root_item_id
            ).first()
            
            if not root_item:
                logger.error(f"Root item not found: {root_item_id}")
                return {"success": False, "error": "Root item not found"}
            
            # Create chain metadata
            chain_id = f"chain_{int(time.time())}_{root_item_id[:8]}"
            
            chain_data = {
                "chain_id": chain_id,
                "name": chain_name,
                "description": description,
                "root_item_id": root_item_id,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
                "items": [
                    {
                        "item_id": root_item_id,
                        "position": 0,
                        "added_at": datetime.utcnow().isoformat()
                    }
                ]
            }
            
            # Store chain metadata as a context item
            mcp_server.add_context_item(
                item_type="context_chain",
                data=chain_data,
                ttl=root_item.ttl,  # Use same TTL as root item
                session_id=session_id
            )
            
            # Update root item to reference the chain
            root_item_data = root_item.data
            if not isinstance(root_item_data, dict):
                root_item_data = {}
            
            # Add chain reference to the item
            if "chains" not in root_item_data:
                root_item_data["chains"] = []
            
            root_item_data["chains"].append({
                "chain_id": chain_id,
                "position": 0
            })
            
            root_item.data = root_item_data
            db.session.add(root_item)
            db.session.commit()
            
            return {
                "success": True,
                "chain_id": chain_id, 
                "message": f"Chain '{chain_name}' created successfully"
            }
        
        except Exception as e:
            logger.error(f"Error creating context chain: {e}")
            db.session.rollback()
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def add_to_chain(
        chain_id: str,
        item_id: str,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Add a context item to an existing chain.
        
        Args:
            chain_id: ID of the chain
            item_id: ID of the item to add
            session_id: Optional session ID
            
        Returns:
            Result of the operation
        """
        try:
            # Get the chain metadata
            chain_items = mcp_server.get_context_by_type(
                item_type="context_chain",
                session_id=session_id
            )
            
            # Find the specific chain
            chain_data = None
            for item in chain_items:
                if item.get("chain_id") == chain_id:
                    chain_data = item
                    break
            
            if not chain_data:
                logger.error(f"Chain not found: {chain_id}")
                return {"success": False, "error": "Chain not found"}
            
            # Get the item to add
            item = db.session.query(ContextItem).filter(
                ContextItem.id == item_id
            ).first()
            
            if not item:
                logger.error(f"Item not found: {item_id}")
                return {"success": False, "error": "Item not found"}
            
            # Calculate position (end of chain)
            position = len(chain_data.get("items", []))
            
            # Add item to chain
            chain_data["items"].append({
                "item_id": item_id,
                "position": position,
                "added_at": datetime.utcnow().isoformat()
            })
            
            chain_data["updated_at"] = datetime.utcnow().isoformat()
            
            # Update chain metadata
            # We need to get the context item ID for the chain metadata
            chain_context_id = chain_data.get("_context_id")
            if chain_context_id:
                mcp_server.update_context_item(
                    item_id=chain_context_id,
                    data=chain_data,
                    session_id=session_id
                )
            
            # Update item to reference the chain
            item_data = item.data
            if not isinstance(item_data, dict):
                item_data = {}
            
            # Add chain reference to the item
            if "chains" not in item_data:
                item_data["chains"] = []
            
            item_data["chains"].append({
                "chain_id": chain_id,
                "position": position
            })
            
            item.data = item_data
            db.session.add(item)
            db.session.commit()
            
            return {
                "success": True, 
                "message": f"Item added to chain at position {position}"
            }
        
        except Exception as e:
            logger.error(f"Error adding to context chain: {e}")
            db.session.rollback()
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def get_chain(
        chain_id: str,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get a context chain with all its items.
        
        Args:
            chain_id: ID of the chain
            session_id: Optional session ID
            
        Returns:
            Chain data with items
        """
        try:
            # Get the chain metadata
            chain_items = mcp_server.get_context_by_type(
                item_type="context_chain",
                session_id=session_id
            )
            
            # Find the specific chain
            chain_data = None
            for item in chain_items:
                if item.get("chain_id") == chain_id:
                    chain_data = item
                    break
            
            if not chain_data:
                logger.error(f"Chain not found: {chain_id}")
                return {"success": False, "error": "Chain not found"}
            
            # Get all items in the chain
            chain_items_expanded = []
            for chain_item in chain_data.get("items", []):
                item_id = chain_item.get("item_id")
                position = chain_item.get("position")
                
                # Get the actual item
                item = mcp_server.get_context_item(item_id, session_id)
                
                if item:
                    chain_items_expanded.append({
                        "position": position,
                        "item_id": item_id,
                        "item_type": item.get("item_type"),
                        "data": item.get("data"),
                        "created_at": item.get("created_at"),
                        "updated_at": item.get("updated_at")
                    })
            
            # Sort by position
            chain_items_expanded.sort(key=lambda x: x.get("position", 0))
            
            # Return the chain with expanded items
            return {
                "success": True,
                "chain_id": chain_id,
                "name": chain_data.get("name"),
                "description": chain_data.get("description"),
                "created_at": chain_data.get("created_at"),
                "updated_at": chain_data.get("updated_at"),
                "items": chain_items_expanded
            }
        
        except Exception as e:
            logger.error(f"Error getting context chain: {e}")
            return {"success": False, "error": str(e)}

class AgentContextIntegration:
    """
    Provides integration between the enhanced agent system and the MCP server,
    allowing agents to access and manipulate context in a standardized way.
    """
    
    @staticmethod
    async def get_agent_context(
        agent_id: str,
        context_types: Optional[List[str]] = None,
        token_limit: int = 2000
    ) -> Dict[str, Any]:
        """
        Get context relevant to a specific agent.
        
        Args:
            agent_id: ID of the agent
            context_types: Optional list of context types to include
            token_limit: Maximum number of tokens to include
            
        Returns:
            Context data organized by type
        """
        try:
            # Get the agent
            agent = enhanced_agent_manager.get_agent(agent_id)
            if not agent:
                logger.error(f"Agent not found: {agent_id}")
                return {"success": False, "error": "Agent not found"}
            
            # Get session ID from agent
            session_id = agent.session_id
            
            # Get full context from MCP server
            context = mcp_server.get_full_context(
                session_id=session_id,
                token_limit=token_limit
            )
            
            # Filter by context types if specified
            if context_types:
                filtered_context = {}
                for context_type, items in context.get("context", {}).items():
                    if context_type in context_types:
                        filtered_context[context_type] = items
                
                context["context"] = filtered_context
            
            # Add agent's current state and confirmations
            if "agent" not in context["context"]:
                context["context"]["agent"] = []
            
            # Add agent state
            agent_state = {
                "id": agent.id,
                "name": agent.name,
                "role": agent.role,
                "state": agent.fsm.get_current_state(),
                "confirmations": agent.get_pending_confirmations()
            }
            
            context["context"]["agent"].append(agent_state)
            
            return {
                "success": True,
                "context": context
            }
        
        except Exception as e:
            logger.error(f"Error getting agent context: {e}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def add_agent_context(
        agent_id: str,
        item_type: str,
        data: Dict[str, Any],
        ttl: int = 3600
    ) -> Dict[str, Any]:
        """
        Add context data for an agent.
        
        Args:
            agent_id: ID of the agent
            item_type: Type of context item
            data: Context data
            ttl: Time to live in seconds
            
        Returns:
            Result of the operation
        """
        try:
            # Get the agent
            agent = enhanced_agent_manager.get_agent(agent_id)
            if not agent:
                logger.error(f"Agent not found: {agent_id}")
                return {"success": False, "error": "Agent not found"}
            
            # Get session ID from agent
            session_id = agent.session_id
            
            # Add context item
            item_id = mcp_server.add_context_item(
                item_type=item_type,
                data=data,
                ttl=ttl,
                session_id=session_id,
                agent_id=agent_id
            )
            
            return {
                "success": True,
                "item_id": item_id,
                "message": f"Context item added for agent {agent_id}"
            }
        
        except Exception as e:
            logger.error(f"Error adding agent context: {e}")
            return {"success": False, "error": str(e)}

class MCPMaintenanceScheduler:
    """
    Scheduler for MCP maintenance tasks like updating priorities,
    cleaning up expired items, and optimizing the database.
    """
    
    def __init__(self):
        """Initialize the maintenance scheduler."""
        self.maintenance_task = None
        self.running = False
    
    async def start_maintenance_loop(self):
        """Start the maintenance loop."""
        if self.running:
            logger.warning("Maintenance loop already running")
            return
        
        self.running = True
        self.maintenance_task = asyncio.create_task(self._maintenance_loop())
    
    async def stop_maintenance_loop(self):
        """Stop the maintenance loop."""
        if not self.running:
            return
        
        self.running = False
        if self.maintenance_task:
            self.maintenance_task.cancel()
            try:
                await self.maintenance_task
            except asyncio.CancelledError:
                pass
    
    async def _maintenance_loop(self):
        """Main maintenance loop."""
        try:
            while self.running:
                # Run maintenance tasks
                await self._run_maintenance()
                
                # Wait for next maintenance cycle (hourly)
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            logger.info("Maintenance loop cancelled")
        except Exception as e:
            logger.error(f"Error in maintenance loop: {e}")
            self.running = False
    
    async def _run_maintenance(self):
        """Run all maintenance tasks."""
        try:
            # Update context priorities
            ContextPrioritizer.update_context_priorities()
            
            # Clean up expired items
            expired_count = mcp_server.cleanup_expired_items()
            logger.info(f"Marked {expired_count} items as expired")
            
            # Delete very old expired items (older than 30 days)
            deleted_count = mcp_server.delete_expired_items(older_than_days=30)
            logger.info(f"Deleted {deleted_count} old expired items")
            
            # Get database stats
            stats = mcp_server.get_database_stats()
            logger.info(f"Database stats: {json.dumps(stats, indent=2)}")
        
        except Exception as e:
            logger.error(f"Error during maintenance: {e}")

# Create singleton instances
context_prioritizer = ContextPrioritizer()
context_chain = ContextChain()
agent_context_integration = AgentContextIntegration()
maintenance_scheduler = MCPMaintenanceScheduler()
