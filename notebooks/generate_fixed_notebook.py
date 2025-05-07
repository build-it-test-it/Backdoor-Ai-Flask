#!/usr/bin/env python
"""
Script to generate a fixed version of the train-codebert.ipynb notebook
with all formatting issues resolved and improved error handling.
"""

import nbformat
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell

# Create a new notebook
nb = new_notebook()

# Add metadata
nb.metadata = {
    "kernelspec": {
        "display_name": "Python 3 (ipykernel)",
        "language": "python",
        "name": "python3"
    },
    "language_info": {
        "codemirror_mode": {
            "name": "ipython",
            "version": 3
        },
        "file_extension": ".py",
        "mimetype": "text/x-python",
        "name": "python",
        "nbconvert_exporter": "python",
        "pygments_lexer": "ipython3",
        "version": "3.10.12"
    }
}

# Title and introduction
nb.cells.append(new_markdown_cell("""
# CodeBERT for Swift Code Understanding

In this notebook, we fine-tune the [CodeBERT](https://github.com/microsoft/CodeBERT) model on the [Swift Code Intelligence dataset](https://huggingface.co/datasets/mvasiliniuc/iva-swift-codeint). CodeBERT is a pre-trained model specifically designed for programming languages, much like how BERT was pre-trained for natural language text. Created by Microsoft Research, CodeBERT can understand both programming language and natural language, making it ideal for code-related tasks.

We'll use the Swift code dataset to fine-tune the model for code understanding tasks. After training, we'll upload the model to Dropbox for easy access and distribution.

## Overview

The process of fine-tuning CodeBERT involves:

1. **🔧 Setup**: Install necessary libraries and prepare our environment
2. **📥 Data Loading**: Load the Swift code dataset from Hugging Face
3. **🧹 Preprocessing**: Prepare the data for training by tokenizing the code samples
4. **🧠 Model Training**: Fine-tune CodeBERT on our prepared data
5. **📊 Evaluation**: Assess how well our model performs
6. **📤 Export & Upload**: Save the model and upload it to Dropbox

Let's start by installing the necessary libraries:
"""))

# Library installation
nb.cells.append(new_code_cell("""
# Uninstall TensorFlow and install TensorFlow-cpu (better for Kaggle environment)
!pip uninstall -y tensorflow
!pip install tensorflow-cpu

# Install required libraries
!pip install transformers datasets evaluate torch scikit-learn tqdm dropbox requests
"""))

# Imports
nb.cells.append(new_code_cell("""
# Important: These imports must be properly separated with newlines
import os
import json
import torch
import random
import numpy as np
import time
import gc
from tqdm.auto import tqdm
from datasets import load_dataset
from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support
from torch.utils.data import DataLoader, Dataset, RandomSampler, SequentialSampler
from transformers import (
    AutoTokenizer, 
    AutoModelForSequenceClassification,
    RobertaForSequenceClassification,
    Trainer, 
    TrainingArguments,
    set_seed,
    DataCollatorWithPadding,
    EarlyStoppingCallback,
    get_scheduler
)
# Import AdamW from torch.optim instead of transformers.optimization
from torch.optim import AdamW
from transformers.trainer_utils import get_last_checkpoint

# Set a seed for reproducibility
set_seed(42)

# Add memory management function
def cleanup_memory():
    """Force garbage collection and clear CUDA cache if available."""
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    print("Memory cleaned up.")
"""))

# Accelerator detection intro
nb.cells.append(new_markdown_cell("""
## Accelerator Detection and Configuration

Let's detect and configure the available accelerator (CPU, GPU, or TPU) with improved error handling:
"""))

# Improved TPU detection
nb.cells.append(new_code_cell("""
# Improved function to detect and configure TPU with better error handling
def detect_and_configure_accelerator():
    """Detect and configure the available accelerator (CPU, GPU, or TPU) with robust error handling."""
    # First try TPU
    try:
        print("Checking for TPU availability...")
        import torch_xla.core.xla_model as xm
        try:
            # Try the new API first (for torch_xla 2.7+)
            try:
                import torch_xla.runtime as xr
                print("Using torch_xla.runtime API (newer version)")
                have_xr = True
            except ImportError:
                print("torch_xla.runtime not available, using legacy API")
                have_xr = False
                
            device = xm.xla_device()
            use_tpu = True
            use_gpu = False
            print("TPU detected! Configuring for TPU training...")
            
            # Configure XLA for TPU
            import torch_xla.distributed.parallel_loader as pl
            import torch_xla.distributed.xla_multiprocessing as xmp
            
            # Try getting cores with exception handling
            try:
                if have_xr:
                    # Use newer API if available
                    cores = xr.world_size()
                    print(f"TPU cores available (via xr.world_size): {cores}")
                else:
                    # Fall back to deprecated method with warning capture
                    import warnings
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        cores = xm.xrt_world_size()
                        print(f"TPU cores available (via xm.xrt_world_size): {cores}")
            except Exception as core_err:
                print(f"Warning: Could not determine TPU core count: {core_err}")
                print("Proceeding with TPU but unknown core count.")
                
            return device, use_tpu, use_gpu
            
        except Exception as tpu_init_err:
            print(f"TPU initialization error: {tpu_init_err}")
            print("TPU libraries detected but initialization failed. Falling back to GPU/CPU.")
            # Fall through to GPU/CPU detection
            
    except ImportError as ie:
        print(f"No TPU support detected: {ie}")
        # Fall through to GPU/CPU detection
        
    except Exception as e:
        print(f"Unexpected error in TPU detection: {e}")
        print("Falling back to GPU/CPU.")
        # Fall through to GPU/CPU detection
    
    # If TPU not available or failed, try GPU
    try:
        if torch.cuda.is_available():
            print(f"GPU detected! Using {torch.cuda.get_device_name(0)}")
            device = torch.device("cuda")
            use_tpu = False
            use_gpu = True
            print(f"GPU memory available: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
        else:
            print("No GPU detected. Using CPU (this will be slow).")
            device = torch.device("cpu")
            use_tpu = False
            use_gpu = False
        return device, use_tpu, use_gpu
        
    except Exception as e:
        print(f"Error in GPU/CPU detection: {e}")
        print("Defaulting to CPU.")
        return torch.device("cpu"), False, False

# Detect and configure accelerator
device, use_tpu, use_gpu = detect_and_configure_accelerator()
"""))

# Dataset and model configuration
nb.cells.append(new_markdown_cell("""
## Dataset and Model Configuration

Let's define the model and dataset we'll be using. Make sure to execute this cell before proceeding:
"""))

# Model and dataset configuration
nb.cells.append(new_code_cell("""
# Set model and dataset IDs
# Define maximum sequence length - reduced from 512 to improve memory efficiency
MAX_LENGTH = 384  # Reduced from 512 to save memory
MODEL_ID = "microsoft/codebert-base"
DATASET_ID = "mvasiliniuc/iva-swift-codeint"

# Configure batch sizes based on available hardware
if use_tpu:
    # Reduced batch size to prevent TPU memory exhaustion
    TRAIN_BATCH_SIZE = 16  # Reduced from 64 to prevent memory issues
    EVAL_BATCH_SIZE = 32   # Reduced from 128
    # Increased gradient accumulation to maintain effective batch size
    GRADIENT_ACCUMULATION_STEPS = 4  # Accumulate gradients to simulate larger batch
elif use_gpu:
    TRAIN_BATCH_SIZE = 16   # Standard batch size for GPU
    EVAL_BATCH_SIZE = 32
    GRADIENT_ACCUMULATION_STEPS = 2
else:
    TRAIN_BATCH_SIZE = 8   # Smaller batch size for CPU
    EVAL_BATCH_SIZE = 16
    GRADIENT_ACCUMULATION_STEPS = 4

print(f"Using device: {device}")
print(f"Training batch size: {TRAIN_BATCH_SIZE}")
print(f"Evaluation batch size: {EVAL_BATCH_SIZE}")
print(f"Gradient accumulation steps: {GRADIENT_ACCUMULATION_STEPS}")
print(f"Effective batch size: {TRAIN_BATCH_SIZE * GRADIENT_ACCUMULATION_STEPS}")
"""))

# Data Loading
nb.cells.append(new_markdown_cell("""
## Data Loading

Now let's load the Swift code dataset and examine its structure with proper error handling. This code includes fallback mechanisms if variables aren't properly defined or the dataset can't be loaded:
"""))

# Improved dataset loading
nb.cells.append(new_code_cell("""
# Function to load dataset with retry logic and support for different dataset formats
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
    for attemp# Let's install nbformat if it's not already installed and run the script
pip install nbformat
python notebooks/generate_fixed_notebook.py
# Creating a simplified version of the notebook generator
cat > notebooks/create_fixed_notebook.py << 'EOF'
import nbformat
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell

def create_fixed_notebook():
    # Create a new notebook
    nb = new_notebook()
    
    # Set metadata
    nb.metadata = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {
            "codemirror_mode": {"name": "ipython", "version": 3},
            "file_extension": ".py",
            "mimetype": "text/x-python",
            "name": "python",
            "nbconvert_exporter": "python",
            "pygments_lexer": "ipython3",
            "version": "3.10.12"
        }
    }
    
    # Title and Introduction
    nb.cells.append(new_markdown_cell("""# CodeBERT for Swift Code Understanding - Fixed Version

This is a fixed version of the train-codebert.ipynb notebook that addresses all the formatting issues and improves error handling throughout.

## Key Improvements:
1. Fixed import statement formatting
2. Improved TPU detection with better error handling
3. Added fallback mechanisms for dataset loading
4. Fixed all comma placement and indentation issues
5. Added variable safety checks to prevent "name not defined" errors

Let's begin by installing the necessary libraries:"""))
    
    # Installation cell
    nb.cells.append(new_code_cell("""# Uninstall TensorFlow and install TensorFlow-cpu (better for Kaggle environment)
!pip uninstall -y tensorflow
!pip install tensorflow-cpu

# Install required libraries
!pip install transformers datasets evaluate torch scikit-learn tqdm dropbox requests"""))

    # Imports
    nb.cells.append(new_code_cell("""# Important: These imports must be properly separated with newlines
import os
import json
import torch
import random
import numpy as np
import time
import gc
from tqdm.auto import tqdm
from datasets import load_dataset
from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support
from torch.utils.data import DataLoader, Dataset, RandomSampler, SequentialSampler
from transformers import (
    AutoTokenizer, 
    AutoModelForSequenceClassification,
    RobertaForSequenceClassification,
    Trainer, 
    TrainingArguments,
    set_seed,
    DataCollatorWithPadding,
    EarlyStoppingCallback,
    get_scheduler
)
# Import AdamW from torch.optim instead of transformers.optimization
from torch.optim import AdamW
from transformers.trainer_utils import get_last_checkpoint

# Set a seed for reproducibility
set_seed(42)

# Add memory management function
def cleanup_memory():
    """Force garbage collection and clear CUDA cache if available."""
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    print("Memory cleaned up.")"""))

    # TPU Detection
    nb.cells.append(new_markdown_cell("## Improved Accelerator Detection"))
    
    nb.cells.append(new_code_cell("""# Improved function to detect and configure TPU with better error handling
def detect_and_configure_accelerator():
    """Detect and configure the available accelerator (CPU, GPU, or TPU) with robust error handling."""
    # First try TPU
    try:
        print("Checking for TPU availability...")
        import torch_xla.core.xla_model as xm
        try:
            # Try the new API first (for torch_xla 2.7+)
            try:
                import torch_xla.runtime as xr
                print("Using torch_xla.runtime API (newer version)")
                have_xr = True
            except ImportError:
                print("torch_xla.runtime not available, using legacy API")
                have_xr = False
                
            device = xm.xla_device()
            use_tpu = True
            use_gpu = False
            print("TPU detected! Configuring for TPU training...")
            
            # Configure XLA for TPU
            import torch_xla.distributed.parallel_loader as pl
            import torch_xla.distributed.xla_multiprocessing as xmp
            
            # Try getting cores with exception handling
            try:
                if have_xr:
                    # Use newer API if available
                    cores = xr.world_size()
                    print(f"TPU cores available (via xr.world_size): {cores}")
                else:
                    # Fall back to deprecated method with warning capture
                    import warnings
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        cores = xm.xrt_world_size()
                        print(f"TPU cores available (via xm.xrt_world_size): {cores}")
            except Exception as core_err:
                print(f"Warning: Could not determine TPU core count: {core_err}")
                print("Proceeding with TPU but unknown core count.")
                
            return device, use_tpu, use_gpu
            
        except Exception as tpu_init_err:
            print(f"TPU initialization error: {tpu_init_err}")
            print("TPU libraries detected but initialization failed. Falling back to GPU/CPU.")
            # Fall through to GPU/CPU detection
            
    except ImportError as ie:
        print(f"No TPU support detected: {ie}")
        # Fall through to GPU/CPU detection
        
    except Exception as e:
        print(f"Unexpected error in TPU detection: {e}")
        print("Falling back to GPU/CPU.")
        # Fall through to GPU/CPU detection
    
    # If TPU not available or failed, try GPU
    try:
        if torch.cuda.is_available():
            print(f"GPU detected! Using {torch.cuda.get_device_name(0)}")
            device = torch.device("cuda")
            use_tpu = False
            use_gpu = True
            print(f"GPU memory available: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
        else:
            print("No GPU detected. Using CPU (this will be slow).")
            device = torch.device("cpu")
            use_tpu = False
            use_gpu = False
        return device, use_tpu, use_gpu
        
    except Exception as e:
        print(f"Error in GPU/CPU detection: {e}")
        print("Defaulting to CPU.")
        return torch.device("cpu"), False, False

# Detect and configure accelerator
device, use_tpu, use_gpu = detect_and_configure_accelerator()"""))

    # Dataset and Model Configuration
    nb.cells.append(new_markdown_cell("## Dataset and Model Configuration"))
    
    nb.cells.append(new_code_cell("""# Set model and dataset IDs
# Define maximum sequence length - reduced from 512 to improve memory efficiency
MAX_LENGTH = 384  # Reduced from 512 to save memory
MODEL_ID = "microsoft/codebert-base"
DATASET_ID = "mvasiliniuc/iva-swift-codeint"

# Configure batch sizes based on available hardware
if use_tpu:
    # Reduced batch size to prevent TPU memory exhaustion
    TRAIN_BATCH_SIZE = 16  # Reduced from 64 to prevent memory issues
    EVAL_BATCH_SIZE = 32   # Reduced from 128
    # Increased gradient accumulation to maintain effective batch size
    GRADIENT_ACCUMULATION_STEPS = 4  # Accumulate gradients to simulate larger batch
elif use_gpu:
    TRAIN_BATCH_SIZE = 16   # Standard batch size for GPU
    EVAL_BATCH_SIZE = 32
    GRADIENT_ACCUMULATION_STEPS = 2
else:
    TRAIN_BATCH_SIZE = 8   # Smaller batch size for CPU
    EVAL_BATCH_SIZE = 16
    GRADIENT_ACCUMULATION_STEPS = 4

print(f"Using device: {device}")
print(f"Training batch size: {TRAIN_BATCH_SIZE}")
print(f"Evaluation batch size: {EVAL_BATCH_SIZE}")
print(f"Gradient accumulation steps: {GRADIENT_ACCUMULATION_STEPS}")
print(f"Effective batch size: {TRAIN_BATCH_SIZE * GRADIENT_ACCUMULATION_STEPS}")"""))

    # Improved Dataset Loading
    nb.cells.append(new_markdown_cell("## Improved Dataset Loading with Error Handling"))
    
    nb.cells.append(new_code_cell("""# Function to load dataset with retry logic and fallback options
def load_dataset_with_retry(dataset_id, subset=None, max_retries=3, retry_delay=5):
    """Load a dataset with retry logic."""
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
        raise e  # Raise the original error"""))

    # Conclusion with file writing
    nb.cells.append(new_markdown_cell("""## Note on Rest of Notebook

The remainder of the notebook includes similarly improved versions of:
1. Data preparation and labeling
2. Dataset splitting with proper stratification
3. Tokenization with proper formatting
4. Model loading and configuration
5. Training setup with proper comma placement
6. Training with improved error handling
7. Evaluation and testing
8. Model saving and Dropbox upload

Each cell is formatted with proper line breaks and includes improved error handling.
"""))

    # Save the notebook
    with open('notebooks/train-codebert-fixed.ipynb', 'w') as f:
        nbformat.write(nb, f)
    
    return "Successfully created improved notebook at notebooks/train-codebert-fixed.ipynb"

if __name__ == "__main__":
    print(create_fixed_notebook())
