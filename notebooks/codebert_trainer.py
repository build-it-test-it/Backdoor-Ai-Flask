"""
CodeBERT Trainer Module

This module provides trainer implementations for CodeBERT model training,
with support for both full training and debug training modes.
"""

import time
import psutil
import torch
from transformers import Trainer

class StandardTrainer(Trainer):
    """
    Standard trainer for full training runs.
    Uses weighted loss but without the additional debugging overhead.
    """
    def __init__(self, class_weights=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.class_weights = class_weights
        
    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        # Extract labels
        labels = inputs.pop("labels")
        
        # Forward pass
        outputs = model(**inputs)
        logits = outputs.logits
        
        # Use class weights in the loss calculation if provided
        if self.class_weights is not None:
            loss_fct = torch.nn.CrossEntropyLoss(weight=self.class_weights)
        else:
            loss_fct = torch.nn.CrossEntropyLoss()
            
        loss = loss_fct(logits.view(-1, self.model.config.num_labels), labels.view(-1))
        
        return (loss, outputs) if return_outputs else loss


class DebugTrainer(Trainer):
    """
    Debug trainer with additional logging and monitoring capabilities.
    Useful for troubleshooting training issues.
    """
    def __init__(self, class_weights=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.step_counter = 0
        self.last_log_time = time.time()
        self.class_weights = class_weights
        
    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        # Track progress
        self.step_counter += 1
        current_time = time.time()
        
        # Log every 10 steps or if more than 30 seconds have passed
        if self.step_counter % 10 == 0 or (current_time - self.last_log_time) > 30:
            process = psutil.Process()
            memory_info = process.memory_info()
            print(f"Step {self.step_counter}: Memory usage: {memory_info.rss / 1024 / 1024:.2f} MB, "
                  f"Time since last log: {current_time - self.last_log_time:.2f}s")
            self.last_log_time = current_time
        
        # Extract labels
        labels = inputs.pop("labels")
        
        # Forward pass
        outputs = model(**inputs)
        logits = outputs.logits
        
        # Use class weights in the loss calculation if provided
        if self.class_weights is not None:
            loss_fct = torch.nn.CrossEntropyLoss(weight=self.class_weights)
        else:
            loss_fct = torch.nn.CrossEntropyLoss()
            
        loss = loss_fct(logits.view(-1, self.model.config.num_labels), labels.view(-1))
        
        return (loss, outputs) if return_outputs else loss


def get_trainer(debug_mode=False, *args, **kwargs):
    """
    Factory function to get the appropriate trainer based on debug mode.
    
    Args:
        debug_mode (bool): Whether to use the debug trainer
        *args, **kwargs: Arguments to pass to the trainer
        
    Returns:
        Trainer: Either StandardTrainer or DebugTrainer based on debug_mode
    """
    if debug_mode:
        print("Using DebugTrainer with enhanced logging and monitoring")
        return DebugTrainer(*args, **kwargs)
    else:
        print("Using StandardTrainer for full training")
        return StandardTrainer(*args, **kwargs)


def monitor_resources():
    """
    Monitor and print system resource usage.
    """
    process = psutil.Process()
    memory_info = process.memory_info()
    mem = psutil.virtual_memory()
    cpu_percent = psutil.cpu_percent(interval=0.1)
    
    print(f"\nSystem Resources:")
    print(f"CPU Usage: {cpu_percent}%")
    print(f"Process Memory: {memory_info.rss / 1024 / 1024:.2f} MB")
    print(f"System Memory: {mem.percent}% used, {mem.available / 1024 / 1024:.2f} MB available\n")


def cleanup_memory():
    """
    Force garbage collection and clear CUDA cache if available.
    """
    import gc
    
    # Get memory usage before cleanup
    process = psutil.Process()
    before = process.memory_info().rss / 1024 ** 2
    
    # Perform cleanup
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    
    # Get memory usage after cleanup
    after = process.memory_info().rss / 1024 ** 2
    print(f"Memory cleaned up. Before: {before:.2f} MB, After: {after:.2f} MB, Freed: {before - after:.2f} MB")
    
    # Print system memory info
    mem = psutil.virtual_memory()
    print(f"System memory: {mem.percent}% used, {mem.available / 1024 / 1024:.2f} MB available")