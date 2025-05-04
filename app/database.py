"""
Database configuration for Backdoor AI.

This module sets up the SQLAlchemy database connection and provides
utility functions for working with the database. It includes production-ready
configuration for PostgreSQL on Render.com.
"""

import logging
import os
import time
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine, exc
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar, Union

# Configure logging
logger = logging.getLogger('database')

# Create SQLAlchemy instance
db = SQLAlchemy()

T = TypeVar('T')

def init_app(app):
    """
    Initialize the database with the Flask app.
    
    This function sets up SQLAlchemy with the Flask app and configures
    appropriate connection pooling for production environments.
    """
    # Handle Render.com's PostgreSQL connection string format
    if app.config['SQLALCHEMY_DATABASE_URI'] and app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
        app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)
        logger.info("PostgreSQL connection string format corrected for SQLAlchemy")
    
    # Configure connection pooling for production environments
    if app.config.get('BACKDOOR_ENV') == 'production' or os.environ.get('BACKDOOR_ENV') == 'production':
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_size': 10,  # Maximum number of connections to keep active
            'max_overflow': 15,  # Maximum overflow allowed beyond pool_size
            'pool_timeout': 30,  # Seconds to wait before timeout on connection pool checkout
            'pool_recycle': 1800,  # Recycle connections after 1800 seconds (30 minutes)
            'pool_pre_ping': True,  # Enable connection health checks
        }
        logger.info("Configured PostgreSQL connection pooling for production")
    
    # Initialize SQLAlchemy with app
    db.init_app(app)
    
    # Test the database connection
    with app.app_context():
        db_check_connection()

def db_check_connection(max_retries=5, retry_delay=2):
    """
    Test the database connection and retry if it fails.
    
    Args:
        max_retries: Maximum number of connection attempts
        retry_delay: Delay between retries in seconds
        
    Returns:
        bool: True if connected successfully
        
    Raises:
        OperationalError: If the database connection fails after retries
    """
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # Attempt to execute a simple query
            db.session.execute("SELECT 1")
            logger.info("Database connection test successful")
            return True
        except OperationalError as e:
            retry_count += 1
            logger.warning(f"Database connection test failed (attempt {retry_count}/{max_retries}): {e}")
            
            if retry_count >= max_retries:
                logger.error(f"Failed to connect to database after {max_retries} attempts")
                raise
            
            # Wait before retrying
            time.sleep(retry_delay)
        except SQLAlchemyError as e:
            logger.error(f"Unexpected database error: {e}")
            raise

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
    
    try:
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
    except OperationalError as e:
        # Handle connection errors and retry
        db.session.rollback()
        logger.error(f"Database operation error: {e}")
        
        # Try to reconnect
        db.session.close()
        instance = db.session.query(model).filter_by(**kwargs).first()
        if instance:
            return instance, False
        
        # Retry creation once more
        kwargs.update(defaults)
        instance = model(**kwargs)
        db.session.add(instance)
        db.session.commit()
        return instance, True

def db_health_check():
    """
    Perform a health check on the database connection.
    
    Returns:
        dict: Health check results
    """
    try:
        start_time = time.time()
        db.session.execute("SELECT 1")
        elapsed = time.time() - start_time
        
        return {
            "status": "healthy",
            "message": "Database connection successful",
            "latency_ms": round(elapsed * 1000, 2)
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "message": f"Database connection failed: {str(e)}"
        }
