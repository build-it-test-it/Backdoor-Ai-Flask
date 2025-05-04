from flask import Blueprint, render_template, jsonify, request, current_app
import logging
import time
import json
import os
from datetime import datetime, timedelta
from sqlalchemy import func, extract

from app.database import db
from app.models.token_usage import TokenUsage

# Set up logging
logger = logging.getLogger("performance")

# Create a Blueprint for performance-related routes
performance_bp = Blueprint('performance', __name__)

# Route for the performance dashboard page
@performance_bp.route('/performance')
def performance():
    return render_template('performance.html', active_tab='performance')

# API route to get token usage stats
@performance_bp.route('/api/performance/token-stats')
def token_stats():
    try:
        # Get session ID from query params or session
        session_id = request.args.get('session_id')
        
        # Get token usage summary directly with our new TokenUsage model
        totals = TokenUsage.get_total_usage(session_id=session_id)
        
        # Get daily usage for the past 7 days
        daily_usage = TokenUsage.get_daily_usage(days=7, session_id=session_id)
        
        # Get model distribution
        model_usage = TokenUsage.get_model_usage(limit=5, session_id=session_id)
        
        # Get recent requests
        recent_usage = TokenUsage.get_recent_usage(limit=10, session_id=session_id)
        
        # Calculate change percentage (comparing last 24h to previous 24h)
        # Get usage for last 24 hours
        now = datetime.utcnow()
        yesterday = now - timedelta(days=1)
        day_before = yesterday - timedelta(days=1)
        
        # Query for last day
        last_day_query = db.session.query(
            func.sum(TokenUsage.prompt_tokens).label('prompt_tokens'),
            func.sum(TokenUsage.completion_tokens).label('completion_tokens')
        ).filter(TokenUsage.timestamp >= yesterday)
        
        if session_id:
            last_day_query = last_day_query.filter(TokenUsage.session_id == session_id)
            
        last_day_result = last_day_query.first()
        
        # Query for previous day
        previous_day_query = db.session.query(
            func.sum(TokenUsage.prompt_tokens).label('prompt_tokens'),
            func.sum(TokenUsage.completion_tokens).label('completion_tokens')
        ).filter(TokenUsage.timestamp >= day_before, TokenUsage.timestamp < yesterday)
        
        if session_id:
            previous_day_query = previous_day_query.filter(TokenUsage.session_id == session_id)
            
        previous_day_result = previous_day_query.first()
        
        # Calculate changes
        changes = {
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_tokens': 0,
            'response_time': 0
        }
        
        # Safety check to avoid division by zero
        if (previous_day_result.prompt_tokens and last_day_result.prompt_tokens and
            previous_day_result.prompt_tokens > 0):
            prompt_change = ((last_day_result.prompt_tokens - previous_day_result.prompt_tokens) / 
                           previous_day_result.prompt_tokens) * 100
            changes['prompt_tokens'] = round(prompt_change, 1)
        
        if (previous_day_result.completion_tokens and last_day_result.completion_tokens and
            previous_day_result.completion_tokens > 0):
            completion_change = ((last_day_result.completion_tokens - previous_day_result.completion_tokens) / 
                               previous_day_result.completion_tokens) * 100
            changes['completion_tokens'] = round(completion_change, 1)
        
        # Format dates for chart display
        chart_dates = []
        chart_prompt_data = []
        chart_completion_data = []
        
        # Create a dictionary of daily usage for easier lookup
        daily_usage_dict = {item['date']: item for item in daily_usage}
        
        # Get past 7 days with 0s for missing dates
        for i in range(6, -1, -1):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            chart_dates.append(date)
            
            # Check if we have data for this date
            if date in daily_usage_dict:
                chart_prompt_data.append(daily_usage_dict[date]['prompt_tokens'])
                chart_completion_data.append(daily_usage_dict[date]['completion_tokens'])
            else:
                chart_prompt_data.append(0)
                chart_completion_data.append(0)
        
        return jsonify({
            'success': True,
            'token_stats': {
                'total_tokens': totals['total_tokens'],
                'prompt_tokens': totals['prompt_tokens'],
                'completion_tokens': totals['completion_tokens'],
                'changes': changes
            },
            'chart_data': {
                'dates': chart_dates,
                'prompt_tokens': chart_prompt_data,
                'completion_tokens': chart_completion_data
            },
            'model_usage': model_usage,
            'recent_usage': recent_usage
        })
        
    except Exception as e:
        logger.error(f"Error getting token stats: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# API route to get performance metrics
@performance_bp.route('/api/performance/metrics')
def performance_metrics():
    try:
        # Get session ID from query params or session
        session_id = request.args.get('session_id')
        
        # Use TokenUsage model for metrics
        metrics_query = db.session.query(
            func.avg(TokenUsage.response_time).label('avg_response_time')
        ).filter(TokenUsage.response_time != None)
        
        if session_id:
            metrics_query = metrics_query.filter(TokenUsage.session_id == session_id)
            
        metrics_result = metrics_query.first()
        avg_response_time = metrics_result.avg_response_time or 0
        
        # Get daily response times
        now = datetime.utcnow()
        seven_days_ago = now - timedelta(days=7)
        
        daily_metrics_query = db.session.query(
            func.date_trunc('day', TokenUsage.timestamp).label('date'),
            func.avg(TokenUsage.response_time).label('avg_time')
        ).filter(
            TokenUsage.timestamp >= seven_days_ago,
            TokenUsage.response_time != None
        ).group_by(
            func.date_trunc('day', TokenUsage.timestamp)
        ).order_by(
            func.date_trunc('day', TokenUsage.timestamp)
        )
        
        if session_id:
            daily_metrics_query = daily_metrics_query.filter(TokenUsage.session_id == session_id)
            
        daily_metrics = daily_metrics_query.all()
        
        # Create a dictionary for easier lookup
        daily_metrics_dict = {
            result.date.strftime('%Y-%m-%d'): round(result.avg_time, 2) 
            for result in daily_metrics
        }
        
        # Format dates for chart display
        chart_dates = []
        chart_response_times = []
        
        # Get past 7 days with 0s for missing dates
        for i in range(6, -1, -1):
            date = (now - timedelta(days=i)).strftime('%Y-%m-%d')
            chart_dates.append(date)
            
            # Check if we have data for this date
            if date in daily_metrics_dict:
                chart_response_times.append(daily_metrics_dict[date])
            else:
                chart_response_times.append(0)
        
        return jsonify({
            'success': True,
            'metrics': {
                'avg_response_time': round(avg_response_time, 2) if avg_response_time else 0
            },
            'chart_data': {
                'dates': chart_dates,
                'response_times': chart_response_times
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting performance metrics: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
