"""
Stream API routes for Backdoor AI.

This module provides Flask routes for interacting with the streaming message system,
including sending and receiving messages.
"""

from flask import Blueprint, request, jsonify, current_app, session, g, Response
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
import uuid

from app.ai.stream_message import message_streams, MessageStream, StreamMessage, StreamMessageSource

bp = Blueprint('stream', __name__, url_prefix='/api/stream')

@bp.before_request
def set_agent_context():
    """Set agent context for the request."""
    g.agent_id = request.headers.get('X-Agent-ID') or request.args.get('agent_id')

def get_message_stream(stream_id: str) -> MessageStream:
    """Get or create a message stream."""
    if stream_id not in message_streams:
        message_streams[stream_id] = MessageStream()
    
    return message_streams[stream_id]

@bp.route('/status', methods=['GET'])
def status():
    """Get the status of the streaming message system."""
    return jsonify({
        'success': True,
        'stream_count': len(message_streams),
        'timestamp': datetime.now().isoformat()
    })

@bp.route('/streams', methods=['POST'])
def create_stream():
    """Create a new message stream."""
    data = request.json or {}
    
    # Generate a stream ID if not provided
    stream_id = data.get('stream_id') or str(uuid.uuid4())
    
    # Create the stream
    stream = get_message_stream(stream_id)
    
    return jsonify({
        'success': True,
        'stream_id': stream_id
    })

@bp.route('/streams/<stream_id>', methods=['DELETE'])
def delete_stream(stream_id):
    """Delete a message stream."""
    if stream_id in message_streams:
        del message_streams[stream_id]
        
        return jsonify({
            'success': True,
            'stream_id': stream_id
        })
    
    return jsonify({
        'success': False,
        'error': 'Stream not found'
    }), 404

@bp.route('/streams/<stream_id>/messages', methods=['POST'])
def send_message(stream_id):
    """Send a message to a stream."""
    data = request.json
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'No data provided'
        }), 400
    
    # Get the stream
    if stream_id not in message_streams:
        return jsonify({
            'success': False,
            'error': 'Stream not found'
        }), 404
    
    stream = message_streams[stream_id]
    
    # Create the message
    try:
        message = StreamMessage.from_dict(data)
        
        # Override source to ensure it's from the client
        message.source = StreamMessageSource.CLIENT
        
        # Send the message
        stream.send_message(message)
        
        return jsonify({
            'success': True,
            'message_id': message.id
        })
    
    except Exception as e:
        logging.error(f"Error sending message: {e}")
        return jsonify({
            'success': False,
            'error': f"Failed to send message: {str(e)}"
        }), 500

@bp.route('/streams/<stream_id>/messages', methods=['GET'])
async def stream_messages(stream_id):
    """Stream messages from a stream."""
    # Get the stream
    if stream_id not in message_streams:
        return jsonify({
            'success': False,
            'error': 'Stream not found'
        }), 404
    
    stream = message_streams[stream_id]
    
    # Check if this is a long-polling request
    long_poll = request.args.get('long_poll', 'false').lower() == 'true'
    
    if long_poll:
        # Use server-sent events for long polling
        def generate():
            # Create a new event loop for this request
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Create a queue for this request
            queue = asyncio.Queue()
            
            # Add a listener for all channels
            def message_callback(message: StreamMessage):
                if message.source == StreamMessageSource.SERVER:
                    queue.put_nowait(message)
            
            stream.add_listener('*', message_callback)
            
            try:
                # Wait for messages
                while True:
                    try:
                        # Get a message with a timeout
                        message = loop.run_until_complete(asyncio.wait_for(queue.get(), 30))
                        
                        # Convert to JSON and yield
                        yield f"data: {message.to_json()}\n\n"
                        
                        # Mark as done
                        queue.task_done()
                    
                    except asyncio.TimeoutError:
                        # Send a heartbeat
                        yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
            
            finally:
                # Clean up
                stream.remove_listener('*', message_callback)
                loop.close()
        
        return Response(generate(), mimetype='text/event-stream')
    
    else:
        # For regular polling, just return the most recent messages
        # This would typically be implemented with a buffer of recent messages
        # For simplicity, we'll just return an empty list
        return jsonify({
            'success': True,
            'messages': []
        })

@bp.route('/streams/<stream_id>/send', methods=['POST'])
def send_simple_message(stream_id):
    """Send a simple message to a stream."""
    data = request.json
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'No data provided'
        }), 400
    
    channel = data.get('channel')
    if not channel:
        return jsonify({
            'success': False,
            'error': 'Channel is required'
        }), 400
    
    message_data = data.get('data')
    extra = data.get('extra', {})
    
    # Get the stream
    if stream_id not in message_streams:
        return jsonify({
            'success': False,
            'error': 'Stream not found'
        }), 404
    
    stream = message_streams[stream_id]
    
    # Send the message
    try:
        message_id = str(uuid.uuid4())
        
        stream.send(
            channel=channel,
            data=message_data,
            source=StreamMessageSource.SERVER,
            extra=extra
        )
        
        return jsonify({
            'success': True,
            'message_id': message_id
        })
    
    except Exception as e:
        logging.error(f"Error sending message: {e}")
        return jsonify({
            'success': False,
            'error': f"Failed to send message: {str(e)}"
        }), 500