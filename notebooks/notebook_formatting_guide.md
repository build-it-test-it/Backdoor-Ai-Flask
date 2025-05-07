# Notebook Formatting Guide

This guide addresses formatting issues in the CodeBERT training notebook that can cause execution errors.

## Common Issues

1. **Line Continuation Issues**: Code lines that should be on separate lines may be concatenated, causing syntax errors.
2. **Missing Variable Definitions**: Variables used before they're defined, especially when cells are executed out of order.
3. **TPU Detection Failures**: The current TPU detection doesn't handle errors well.

## Fix 1: Proper Import Formatting

Make sure all imports are properly formatted with each import on a separate line:

```python
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
```

## Fix 2: Dataset Configuration

Make sure the dataset configuration section is properly formatted:

```python
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
```

## Fix 3: Batch Size Parameters

In the tokenization section, make sure commas are correctly placed:

```python
tokenized_train_data = train_data.map(
    tokenize_function,
    batched=True,
    batch_size=32,  # Comma is important here
    num_proc=num_proc,  
    remove_columns=[col for col in train_data.column_names if col != 'label'],
    desc="Tokenizing training data"
)
```

## Fix 4: Indentation in Exception Handling

Make sure indentation is consistent, especially in exception handling sections:

```python
try:
    # Clean up memory before training
    cleanup_memory()
    print("Attempting to save current model state...")
    trainer.save_model("./results/codebert-swift-emergency-save")
    print("Emergency model save completed.")
except Exception as save_err:
    print(f"Could not perform emergency save: {save_err}")
```

## Most Important Fixes

1. Replace the TPU detection function with the improved version from `improved_tpu_detector.py`
2. Add the variable safety checks from `dataset_safety_checker.py`
3. Make sure all code cells use proper line breaks and indentation
