from flask import Blueprint, render_template, jsonify, request, current_app
import time
from app.database import get_db
import json
import os
from datetime import datetime, timedelta

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
        db = get_db()
        
        # Get token usage summary
        cursor = db.cursor()
        cursor.execute('''
            SELECT 
                SUM(prompt_tokens) as total_prompt, 
                SUM(completion_tokens) as total_completion,
                SUM(prompt_tokens + completion_tokens) as total_tokens
            FROM token_usage
        ''')
        
        totals = cursor.fetchone()
        
        # Get daily usage for the past 7 days
        cursor.execute('''
            SELECT 
                DATE(timestamp) as date,
                SUM(prompt_tokens) as prompt_tokens,
                SUM(completion_tokens) as completion_tokens
            FROM token_usage
            WHERE timestamp >= DATE('now', '-7 days')
            GROUP BY DATE(timestamp)
            ORDER BY date ASC
        ''')
        
        daily_usage = cursor.fetchall()
        
        # Get model distribution
        cursor.execute('''
            SELECT 
                model,
                COUNT(*) as usage_count,
                SUM(prompt_tokens + completion_tokens) as total_tokens
            FROM token_usage
            GROUP BY model
            ORDER BY total_tokens DESC
            LIMIT 5
        ''')
        
        model_usage = cursor.fetchall()
        
        # Get recent requests
        cursor.execute('''
            SELECT 
                timestamp,
                model,
                prompt_tokens,
                completion_tokens,
                (prompt_tokens + completion_tokens) as total,
                response_time
            FROM token_usage
            ORDER BY timestamp DESC
            LIMIT 10
        ''')
        
        recent_usage = cursor.fetchall()
        
        # Calculate change percentage (comparing last 24h to previous 24h)
        cursor.execute('''
            SELECT 
                SUM(prompt_tokens) as prompt_tokens,
                SUM(completion_tokens) as completion_tokens
            FROM token_usage
            WHERE timestamp >= DATE('now', '-1 day')
        ''')
        
        last_day = cursor.fetchone()
        
        cursor.execute('''
            SELECT 
                SUM(prompt_tokens) as prompt_tokens,
                SUM(completion_tokens) as completion_tokens
            FROM token_usage
            WHERE timestamp >= DATE('now', '-2 days') AND timestamp < DATE('now', '-1 day')
        ''')
        
        previous_day = cursor.fetchone()
        
        # Calculate changes
        changes = {
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_tokens': 0,
            'response_time': 0
        }
        
        if previous_day and previous_day['prompt_tokens'] and last_day and last_day['prompt_tokens']:
            prompt_change = ((last_day['prompt_tokens'] - previous_day['prompt_tokens']) / previous_day['prompt_tokens']) * 100
            changes['prompt_tokens'] = round(prompt_change, 1)
        
        if previous_day and previous_day['completion_tokens'] and last_day and last_day['completion_tokens']:
            completion_change = ((last_day['completion_tokens'] - previous_day['completion_tokens']) / previous_day['completion_tokens']) * 100
            changes['completion_tokens'] = round(completion_change, 1)
        
        if totals:
            total_tokens = totals['total_tokens'] or 0
            prompt_tokens = totals['total_prompt'] or 0
            completion_tokens = totals['total_completion'] or 0
        else:
            total_tokens = 0
            prompt_tokens = 0
            completion_tokens = 0
        
        # Format dates for chart display
        chart_dates = []
        chart_prompt_data = []
        chart_completion_data = []
        
        # Get past 7 days with 0s for missing dates
        for i in range(6, -1, -1):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            chart_dates.append(date)
            
            # Find if we have data for this date
            found = False
            for usage in daily_usage or []:
                if usage['date'] == date:
                    chart_prompt_data.append(usage['prompt_tokens'])
                    chart_completion_data.append(usage['completion_tokens'])
                    found = True
                    break
            
            if not found:
                chart_prompt_data.append(0)
                chart_completion_data.append(0)
        
        return jsonify({
            'success': True,
            'token_stats': {
                'total_tokens': total_tokens,
                'prompt_tokens': prompt_tokens,
                'completion_tokens': completion_tokens,
                'changes': changes
            },
            'chart_data': {
                'dates': chart_dates,
                'prompt_tokens': chart_prompt_data,
                'completion_tokens': chart_completion_data
            },
            'model_usage': [dict(row) for row in (model_usage or [])],
            'recent_usage': [dict(row) for row in (recent_usage or [])]
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting token stats: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# API route to get performance metrics
@performance_bp.route('/api/performance/metrics')
def performance_metrics():
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Get average response time
        cursor.execute('''
            SELECT AVG(response_time) as avg_response_time
            FROM token_usage
            WHERE response_time IS NOT NULL
        ''')
        
        avg_time = cursor.fetchone()
        avg_response_time = avg_time['avg_response_time'] if avg_time else 0
        
        # Get response times for the past 7 days
        cursor.execute('''
            SELECT 
                DATE(timestamp) as date,
                AVG(response_time) as avg_time
            FROM token_usage
            WHERE timestamp >= DATE('now', '-7 days') AND response_time IS NOT NULL
            GROUP BY DATE(timestamp)
            ORDER BY date ASC
        ''')
        
        daily_response_times = cursor.fetchall()
        
        # Format dates for chart display
        chart_dates = []
        chart_response_times = []
        
        # Get past 7 days with 0s for missing dates
        for i in range(6, -1, -1):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            chart_dates.append(date)
            
            # Find if we have data for this date
            found = False
            for usage in daily_response_times or []:
                if usage['date'] == date:
                    chart_response_times.append(round(usage['avg_time'], 2))
                    found = True
                    break
            
            if not found:
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
        current_app.logger.error(f"Error getting performance metrics: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
