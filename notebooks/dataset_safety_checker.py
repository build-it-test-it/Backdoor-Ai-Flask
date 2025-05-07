"""
Dataset safety checker for CodeBERT training notebook.

This module contains improved dataset loading code with safety checks
to prevent "name not defined" errors and add fallback options.

Usage:
    Copy and paste this code into your notebook to replace the existing
    dataset loading code that doesn't have proper safety checks.
"""

import time
from datasets import load_dataset

def load_dataset_with_retry(dataset_id, subset=None, max_retries=3, retry_delay=5):
    """Load a dataset with retry logic.
    
    Args:
        dataset_id: The Hugging Face dataset ID
        subset: Optional subset name for datasets with multiple configurations
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds
        
    Returns:
        Loaded dataset
    """
    for attempt in range(max_retries):
        try:
            print(f"Loading dataset (attempt {attempt+1}/{max_retries})...")
            if subset:
                data = load_dataset(dataset_id, subset, trust_remote_code=True)
            else:
                data = load_dataset(dataset_id, trust_remote_code=True)
                
            # Check if dataset has a train split
            if 'train' in data:
                print(f"Dataset loaded successfully with {len(data['train'])} examples in train split")
            else:
                print(f"Dataset loaded successfully but has no 'train' split. Available splits: {list(data.keys())}")
            return data
            
        except Exception as e:
            print(f"Error loading dataset (attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print("Maximum retries reached. Could not load dataset.")
                raise

# Insert this block at the beginning of your dataset loading code
"""
# Make sure dataset ID is defined (in case previous cell didn't execute)
if 'DATASET_ID' not in globals():
    print("Warning: DATASET_ID not found. Using default value.")
    DATASET_ID = "mvasiliniuc/iva-swift-codeint"  # Default value as fallback
    MAX_LENGTH = 384
    MODEL_ID = "microsoft/codebert-base"
    TRAIN_BATCH_SIZE = 8
    EVAL_BATCH_SIZE = 16
    GRADIENT_ACCUMULATION_STEPS = 4
    print("Using default configuration values.")

# Load the dataset with retry logic and fallback options
try:
    print(f"Loading dataset: {DATASET_ID}")
    data = load_dataset_with_retry(DATASET_ID)
    print("Dataset structure:")
    print(data)
except Exception as e:
    print(f"Fatal error loading dataset: {e}")
    # Try a fallback dataset if main one fails
    try:
        if DATASET_ID != "huggingface/code_search_net":
            print("Attempting to load fallback dataset: huggingface/code_search_net (python subset)")
            data = load_dataset_with_retry("huggingface/code_search_net", subset="python", max_retries=2)
            print("Fallback dataset loaded successfully.")
            # Update dataset ID to reflect the change
            DATASET_ID = "huggingface/code_search_net"
        else:
            raise e  # Re-raise if we were already trying the fallback
    except Exception as fallback_e:
        print(f"Fallback dataset also failed: {fallback_e}")
        raise e  # Raise the original error
"""
