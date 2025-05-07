#!/usr/bin/env python
"""
Script to update the train-codebert.ipynb notebook with memory optimizations.
"""
import json
import os
import re

def update_notebook(notebook_path):
    """Update the notebook with memory optimizations."""
    
    # Load the notebook
    with open(notebook_path, 'r') as f:
        notebook = json.load(f)
    
    # Find cells to modify
    for i, cell in enumerate(notebook['cells']):
        if cell['cell_type'] == 'code':
            source = ''.join(cell['source'])
            
            # 1. Add memory management function
            if "import time" in source and "import gc" not in source:
                source = source.replace(
                    "import time",
                    "import time\nimport gc"
                )
                source = source.replace(
                    "# Set a seed for reproducibility\nset_seed(42)",
                    """# Set a seed for reproducibility
set_seed(42)

# Add memory management function
def cleanup_memory():
    \"\"\"Force garbage collection and clear CUDA cache if available.\"\"\"
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    print("Memory cleaned up.")"""
                )
                notebook['cells'][i]['source'] = source.split('\n')
            
            # 2. Update TPU batch sizes and add MAX_LENGTH
            if "# Configure batch sizes based on available hardware" in source:
                # Add MAX_LENGTH definition
                source = source.replace(
                    "# Set model and dataset IDs",
                    """# Set model and dataset IDs
# Define maximum sequence length - reduced from 512 to improve memory efficiency
MAX_LENGTH = 384  # Reduced from 512 to save memory"""
                )
                
                # Optimize batch sizes and add gradient accumulation
                source = re.sub(
                    r"if use_tpu:\s+TRAIN_BATCH_SIZE = 64.*?GRADIENT_ACCUMULATION_STEPS = 1",
                    """if use_tpu:
    # Reduced batch size to prevent TPU memory exhaustion
    TRAIN_BATCH_SIZE = 16  # Reduced from 64 to prevent memory issues
    EVAL_BATCH_SIZE = 32   # Reduced from 128
    # Increased gradient accumulation to maintain effective batch size
    GRADIENT_ACCUMULATION_STEPS = 4  # Accumulate gradients to simulate larger batch""",
                    source,
                    flags=re.DOTALL
                )
                
                # Add effective batch size calculation
                source = source.replace(
                    "print(f\"Gradient accumulation steps: {GRADIENT_ACCUMULATION_STEPS}\")",
                    """print(f\"Gradient accumulation steps: {GRADIENT_ACCUMULATION_STEPS}\")
print(f\"Effective batch size: {TRAIN_BATCH_SIZE * GRADIENT_ACCUMULATION_STEPS}\")"""
                )
                
                notebook['cells'][i]['source'] = source.split('\n')
            
            # 3. Update tokenization to use MAX_LENGTH
            if "def tokenize_function(examples):" in source and "max_length=512" in source:
                source = source.replace(
                    "max_length=512",
                    "max_length=MAX_LENGTH"
                )
                source = source.replace(
                    "padding=\"max_length\"",
                    "padding=False  # No padding during preprocessing saves memory"
                )
                notebook['cells'][i]['source'] = source.split('\n')
            
            # 4. Update data processing to reduce memory usage
            if "tokenized_train_data = train_data.map(" in source:
                # Reduce processing batch size
                source = source.replace(
                    "batch_size=64",
                    "batch_size=32  # Reduced for lower memory usage"
                )
                
                # Add memory cleanup at the end
                if "except Exception as e:" in source and "del train_data" not in source:
                    source = source.replace(
                        "except Exception as e:",
                        """    # Clean up memory
    del train_data
    del val_data
    cleanup_memory()
    
except Exception as e:"""
                    )
                
                notebook['cells'][i]['source'] = source.split('\n')
            
            # 5. Enable gradient checkpointing
            if "# Load the CodeBERT model for sequence classification" in source:
                source = source.replace(
                    "model = AutoModelForSequenceClassification.from_pretrained(MODEL_ID, num_labels=2)",
                    """model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_ID, 
        num_labels=2,
        low_cpu_mem_usage=True  # For memory efficiency
    )
    
    # Enable gradient checkpointing for better memory efficiency
    try:
        model.gradient_checkpointing_enable()
        print("Gradient checkpointing enabled for memory efficiency.")
    except Exception as e:
        print(f"Could not enable gradient checkpointing: {e}")
        print("Will train without gradient checkpointing.")"""
                )
                notebook['cells'][i]['source'] = source.split('\n')
            
            # 6. Update TrainingArguments for better memory efficiency
            if "training_args = TrainingArguments(" in source:
                source = source.replace(
                    "per_device_train_batch_size=TRAIN_BATCH_SIZE",
                    "per_device_train_batch_size=TRAIN_BATCH_SIZE,  # Reduced batch size for memory efficiency"
                )
                source = source.replace(
                    "gradient_accumulation_steps=GRADIENT_ACCUMULATION_STEPS",
                    "gradient_accumulation_steps=GRADIENT_ACCUMULATION_STEPS,  # Critical for memory efficiency"
                )
                source = source.replace(
                    "num_train_epochs=3",
                    "num_train_epochs=2,  # Reduced to 2 epochs for faster training"
                )
                source = source.replace(
                    "dataloader_num_workers=4 if use_gpu or use_tpu else 2",
                    "dataloader_num_workers=2,  # Reduced for less memory overhead"
                )
                
                # Add note about the effective batch size
                if "print(\"Training arguments configured successfully.\")" in source:
                    source = source.replace(
                        "print(\"Training arguments configured successfully.\")",
                        """print("Training arguments configured successfully.")
    print(f"Effective batch size: {TRAIN_BATCH_SIZE * GRADIENT_ACCUMULATION_STEPS}")"""
                    )
                
                notebook['cells'][i]['source'] = source.split('\n')
            
            # 7. Improve error handling for memory issues in training
            if "# Start training with checkpoint recovery" in source:
                # Add memory cleanup before training
                source = source.replace(
                    "try:",
                    """try:
    # Clean up memory before training
    cleanup_memory()"""
                )
                
                # Add improved error handling for memory issues
                if "except Exception as e:" in source and "RuntimeError as e:" not in source:
                    source = re.sub(
                        r"except Exception as e:(.*?)raise",
                        """except RuntimeError as e:
    # Handle memory-related errors specially
    error_msg = str(e)
    print(f"Runtime error during training: {error_msg}")
    
    if "memory" in error_msg.lower() or "cuda out of memory" in error_msg.lower() or "resource exhausted" in error_msg.lower():
        print("\\nMEMORY ERROR DETECTED! Try further reducing these parameters:")
        print(f"1. Reduce MAX_LENGTH (currently {MAX_LENGTH}). Try 256 or 192.")
        print(f"2. Reduce TRAIN_BATCH_SIZE (currently {TRAIN_BATCH_SIZE}). Try 8 or 4.")
        print(f"3. Increase GRADIENT_ACCUMULATION_STEPS (currently {GRADIENT_ACCUMULATION_STEPS}). Try 8 or 16.")
    
    # Try to save the current state if possible
    try:
        print("Attempting to save current model state...")
        trainer.save_model("./results/codebert-swift-emergency-save")
        print("Emergency model save completed.")
    except Exception as save_err:
        print(f"Could not perform emergency save: {save_err}")
    
    # Re-raise the exception for proper error handling
    raise
except Exception as e:\\1raise""",
                        source,
                        flags=re.DOTALL
                    )
                
                notebook['cells'][i]['source'] = source.split('\n')
                
            # 8. Add memory cleanup before evaluation
            if "# Evaluate the model " in source and "cleanup_memory()" not in source:
                source = source.replace(
                    "try:",
                    """try:
    # Clean up memory before evaluation
    cleanup_memory()"""
                )
                notebook['cells'][i]['source'] = source.split('\n')
    
    # Save the updated notebook
    with open(notebook_path, 'w') as f:
        json.dump(notebook, f, indent=1)
    
    print(f"Successfully updated {notebook_path} with memory optimizations")

if __name__ == "__main__":
    update_notebook("notebooks/train-codebert.ipynb")
