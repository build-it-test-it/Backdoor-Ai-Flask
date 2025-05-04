import json
import os
import uuid
from datetime import datetime
from flask import current_app, session

class UserBehavior:
    """Class to represent user behavior within the app, based on Backdoor-signer's AILearningManager"""
    def __init__(self, action, screen, duration=0, details=None):
        self.id = str(uuid.uuid4())
        self.timestamp = datetime.now()
        self.action = action
        self.screen = screen
        self.duration = duration
        self.details = details or {}
    
    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'action': self.action,
            'screen': self.screen,
            'duration': self.duration,
            'details': self.details
        }

class AIInteraction:
    """Class to represent an AI interaction, based on Backdoor-signer's AIInteraction"""
    def __init__(self, user_message, ai_response, intent=None, confidence=0.0, context=None):
        self.id = str(uuid.uuid4())
        self.timestamp = datetime.now()
        self.user_message = user_message
        self.ai_response = ai_response
        self.intent = intent or self._extract_intent(ai_response)
        self.confidence = confidence
        self.context = context or {}
        self.feedback = None
    
    def _extract_intent(self, response):
        """Extract intent from AI response, similar to Backdoor-signer's implementation"""
        # Look for intent in square brackets like [navigate to:settings]
        import re
        pattern = r'\[([a-zA-Z0-9_\s]+):.*?\]'
        match = re.search(pattern, response)
        if match:
            return match.group(1)
        return "conversation"
    
    def add_feedback(self, rating, comment=None):
        """Add user feedback to this interaction"""
        self.feedback = {
            'rating': rating,
            'comment': comment,
            'timestamp': datetime.now().isoformat()
        }
    
    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'user_message': self.user_message,
            'ai_response': self.ai_response,
            'intent': self.intent,
            'confidence': self.confidence,
            'context': self.context,
            'feedback': self.feedback
        }

class BehaviorTracker:
    """Tracks user behavior within the app for AI context, inspired by Backdoor-signer's AILearningManager"""
    
    def __init__(self):
        self.behaviors = []
        self.interactions = []
        self.load_data()
    
    def record_behavior(self, action, screen, duration=0, details=None):
        """Record a user behavior"""
        behavior = UserBehavior(action, screen, duration, details)
        self.behaviors.append(behavior)
        self._save_behaviors()
        return behavior
    
    def record_interaction(self, user_message, ai_response, intent=None, confidence=0.0, context=None):
        """Record an AI interaction"""
        interaction = AIInteraction(user_message, ai_response, intent, confidence, context)
        self.interactions.append(interaction)
        self._save_interactions()
        return interaction
    
    def record_feedback(self, interaction_id, rating, comment=None):
        """Record feedback for an interaction"""
        for interaction in self.interactions:
            if interaction.id == interaction_id:
                interaction.add_feedback(rating, comment)
                self._save_interactions()
                return True
        return False
    
    def get_recent_behaviors(self, limit=10):
        """Get the most recent behaviors"""
        return self.behaviors[-limit:] if self.behaviors else []
    
    def get_recent_interactions(self, limit=10):
        """Get the most recent interactions"""
        return self.interactions[-limit:] if self.interactions else []
    
    def get_interaction_by_id(self, interaction_id):
        """Get an interaction by ID"""
        for interaction in self.interactions:
            if interaction.id == interaction_id:
                return interaction
        return None
    
    def _save_behaviors(self):
        """Save behaviors to disk"""
        session_id = session.get('session_id')
        if not session_id:
            return
        
        session_dir = os.path.join(current_app.config['CHAT_HISTORY_DIR'], session_id)
        os.makedirs(session_dir, exist_ok=True)
        
        behavior_file = os.path.join(session_dir, 'user_behaviors.json')
        
        behaviors_dict = [b.to_dict() for b in self.behaviors]
        
        with open(behavior_file, 'w') as f:
            json.dump(behaviors_dict, f, indent=2)
    
    def _save_interactions(self):
        """Save interactions to disk"""
        session_id = session.get('session_id')
        if not session_id:
            return
        
        session_dir = os.path.join(current_app.config['CHAT_HISTORY_DIR'], session_id)
        os.makedirs(session_dir, exist_ok=True)
        
        interactions_file = os.path.join(session_dir, 'ai_interactions.json')
        
        interactions_dict = [i.to_dict() for i in self.interactions]
        
        with open(interactions_file, 'w') as f:
            json.dump(interactions_dict, f, indent=2)
    
    def load_data(self):
        """Load behaviors and interactions from disk"""
        self.load_behaviors()
        self.load_interactions()
    
    def load_behaviors(self):
        """Load behaviors from disk"""
        try:
            session_id = session.get('session_id')
            if not session_id:
                return
            
            session_dir = os.path.join(current_app.config['CHAT_HISTORY_DIR'], session_id)
            behavior_file = os.path.join(session_dir, 'user_behaviors.json')
        except RuntimeError:
            # Working outside of request context, use default behavior file
            behavior_file = os.path.join(os.getcwd(), 'data', 'user_behaviors.json')
        
        if os.path.exists(behavior_file):
            try:
                with open(behavior_file, 'r') as f:
                    behaviors_dict = json.load(f)
                
                self.behaviors = []
                for b_dict in behaviors_dict:
                    behavior = UserBehavior(
                        action=b_dict['action'],
                        screen=b_dict['screen'],
                        duration=b_dict.get('duration', 0),
                        details=b_dict.get('details', {})
                    )
                    behavior.id = b_dict['id']
                    behavior.timestamp = datetime.fromisoformat(b_dict['timestamp'])
                    self.behaviors.append(behavior)
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Error loading behaviors: {e}")
    
    def load_interactions(self):
        """Load interactions from disk"""
        try:
            session_id = session.get('session_id')
            if not session_id:
                return
            
            session_dir = os.path.join(current_app.config['CHAT_HISTORY_DIR'], session_id)
            interactions_file = os.path.join(session_dir, 'ai_interactions.json')
        except RuntimeError:
            # Working outside of request context, use default interaction file
            interactions_file = os.path.join(os.getcwd(), 'data', 'ai_interactions.json')
        
        if os.path.exists(interactions_file):
            try:
                with open(interactions_file, 'r') as f:
                    interactions_dict = json.load(f)
                
                self.interactions = []
                for i_dict in interactions_dict:
                    interaction = AIInteraction(
                        user_message=i_dict['user_message'],
                        ai_response=i_dict['ai_response'],
                        intent=i_dict.get('intent'),
                        confidence=i_dict.get('confidence', 0.0),
                        context=i_dict.get('context', {})
                    )
                    interaction.id = i_dict['id']
                    interaction.timestamp = datetime.fromisoformat(i_dict['timestamp'])
                    interaction.feedback = i_dict.get('feedback')
                    self.interactions.append(interaction)
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Error loading interactions: {e}")

# Singleton instance
behavior_tracker = BehaviorTracker()