"""
Database configuration for Backdoor AI.

This module sets up the SQLAlchemy database connection and provides
utility functions for working with the database.
"""

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar, Union

# Create SQLAlchemy instance
db = SQLAlchemy()

T = TypeVar('T')

def init_app(app):
    """Initialize the database with the Flask app."""
    db.init_app(app)

def get_or_create(model: Type[T], **kwargs) -> Tuple[T, bool]:
    """
    Get an existing record or create a new one.
    
    Args:
        model: The SQLAlchemy model class
        **kwargs: Attributes to filter by and defaults to use if creating
        
    Returns:
        Tuple of (instance, created) where created is True if a new instance was created
    """
    defaults = kwargs.pop('defaults', {})
    
    # Try to find the instance
    instance = db.session.query(model).filter_by(**kwargs).first()
    
    if instance:
        return instance, False
    
    # Create new instance
    kwargs.update(defaults)
    instance = model(**kwargs)
    
    try:
        db.session.add(instance)
        db.session.commit()
        return instance, True
    except IntegrityError:
        db.session.rollback()
        
        # Try again in case of a race condition
        instance = db.session.query(model).filter_by(**kwargs).first()
        if instance:
            return instance, False
        else:
            raise
