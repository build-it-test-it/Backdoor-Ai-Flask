"""
Fix for CodeBERT notebook to properly handle RoBERTa position embeddings and token_type_ids

The issue: When trying to use a RoBERTa model with long sequence lengths (MAX_LENGTH=10000),
the model's forward function fails when trying to expand token_type_ids from a length of 514
to the batch size * sequence length (16x10000).

This script demonstrates the proper way to extend position embeddings for RoBERTa models
and fixes the token_type_ids issue.
"""

import torch
import torch.nn as nn
from transformers import AutoModelForSequenceClassification

def fix_position_embeddings(model, max_length=10000):
    """
    Properly extends position embeddings for either BERT or RoBERTa models
    and fixes token_type_ids for RoBERTa to handle longer sequences.
    
    Args:
        model: The model to modify
        max_length: The new maximum sequence length
    
    Returns:
        The modified model
    """
    print(f"Extending position embeddings from {model.config.max_position_embeddings} to {max_length}")
    
    # Get current position embeddings max length
    current_max_pos = model.config.max_position_embeddings
    
    # Detect if we're using RoBERTa or BERT model
    is_roberta = hasattr(model, 'roberta')
    embeddings = model.roberta.embeddings if is_roberta else model.bert.embeddings
    
    # Initialize new position embeddings for the extended range
    new_pos_embed = embeddings.position_embeddings.weight.new_empty(max_length, model.config.hidden_size)
    
    # Copy existing weights
    new_pos_embed[:current_max_pos] = embeddings.position_embeddings.weight
    
    # Initialize remaining weights using Xavier initialization
    nn.init.xavier_uniform_(new_pos_embed[current_max_pos:])
    
    # Update the model config
    model.config.max_position_embeddings = max_length
    
    # Replace the position embeddings weights
    embeddings.position_embeddings = nn.Embedding.from_pretrained(new_pos_embed, freeze=False)
    
    # Update the position_ids in the model to work with new length
    embeddings.register_buffer(
        "position_ids", torch.arange(max_length).expand((1, -1))
    )
    
    # For RoBERTa models, we need to ensure token_type_ids are properly handled
    if is_roberta and hasattr(embeddings, "token_type_ids"):
        # Create a new token_type_ids buffer with the expanded size
        embeddings.register_buffer(
            "token_type_ids",
            torch.zeros(1, max_length, dtype=torch.long),
            persistent=False,
        )
    
    print("Successfully extended position embeddings")
    return model

"""
When using this in a notebook, replace the existing position embeddings extension code with:

# Extend position embeddings to support longer sequences
if MAX_LENGTH > 512:
    model = fix_position_embeddings(model, MAX_LENGTH)
"""
