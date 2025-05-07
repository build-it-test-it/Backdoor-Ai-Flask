"""
Test script to validate the CodeBERT notebook functionality.
This checks for common issues and ensures the core components work properly.
"""

import os
import sys
import time
import traceback
from collections import Counter

# First test basic imports
try:
    print("Testing basic imports...")
    import torch
    import numpy as np
    from transformers import (
        AutoTokenizer, 
        AutoModelForSequenceClassification,
        Trainer, 
        TrainingArguments
    )
    from datasets import load_dataset
    print("✅ Basic imports successful")
except Exception as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

# Test dataset loading
try:
    print("\nTesting dataset loading...")
    print("Loading a small sample to verify structure...")
    # Try to load just a small sample first for faster testing
    dataset = load_dataset('mvasiliniuc/iva-swift-codeint', 
                           trust_remote_code=True, 
                           split='train[:10]')
    
    print(f"✅ Dataset sample loaded successfully with {len(dataset)} examples")
    print(f"Dataset features: {list(dataset.features.keys())}")
    
    # Check for required columns
    required_cols = ['repo_name', 'path', 'content']
    for col in required_cols:
        if col not in dataset.features:
            print(f"❌ Missing required column: {col}")
        else:
            print(f"✅ Found required column: {col}")
    
    # Check the first example
    print("\nFirst example details:")
    example = dataset[0]
    for key, value in example.items():
        if isinstance(value, str) and len(value) > 100:
            print(f"{key}: {value[:100]}...")
        else:
            print(f"{key}: {value}")
    
except Exception as e:
    print(f"❌ Dataset loading failed: {e}")
    traceback.print_exc()

# Test tokenizer
try:
    print("\nTesting tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained('microsoft/codebert-base')
    print(f"✅ CodeBERT tokenizer loaded successfully: {tokenizer.__class__.__name__}")
    
    # Test with a simple code example
    code_sample = '// Example Swift code\nfunc hello() { print("Hello World") }'
    
    # Test single sample tokenization
    encoded = tokenizer(code_sample, 
                        padding='max_length',
                        truncation=True, 
                        max_length=512)
    print(f"✅ Single sample tokenization successful, output shape: {len(encoded['input_ids'])}")
    
    # Test batched tokenization
    samples = [code_sample, "import Foundation\nprint(\"Another example\")"]
    
    # First without tensors
    encoded_batch = tokenizer(samples, 
                             padding='max_length',
                             truncation=True, 
                             max_length=512)
    print(f"✅ Batch tokenization without tensors successful")
    
    # Now with tensors
    encoded_batch_pt = tokenizer(samples, 
                                padding='max_length',
                                truncation=True, 
                                max_length=512,
                                return_tensors='pt')
    print(f"✅ Batch tokenization with tensors successful, output shape: {encoded_batch_pt['input_ids'].shape}")
    
    # Test dataset mapping - important part for the notebook
    def tokenize_function(examples):
        # First test without return_tensors
        results = tokenizer(
            examples["content"] if "content" in examples else ["// test code"],
            padding='max_length',
            truncation=True,
            max_length=512
        )
        return results
    
    if len(dataset) > 0:
        # Apply the tokenization function to the dataset
        tokenized_dataset = dataset.map(tokenize_function, batched=True)
        print(f"✅ Dataset tokenization without tensors successful")
        
        # Add label column for testing the full pipeline
        def add_labels(example):
            example['label'] = 1 if 'Package.swift' in example.get('path', '') else 0
            return example
        
        labeled_dataset = tokenized_dataset.map(add_labels)
        print(f"✅ Adding labels successful")
        
        # Check label distribution
        if 'label' in labeled_dataset.features:
            labels = labeled_dataset['label']
            label_counts = Counter(labels)
            print(f"Label distribution: {dict(label_counts)}")
            
            # Try train-test split
            try:
                splits = labeled_dataset.train_test_split(test_size=0.2, seed=42)
                print(f"✅ Train-test split successful: {len(splits['train'])} train, {len(splits['test'])} test")
            except Exception as e:
                print(f"❌ Train-test split failed: {e}")
        else:
            print("❌ Label column not found after mapping")
        
except Exception as e:
    print(f"❌ Tokenizer testing failed: {e}")
    traceback.print_exc()

# Test model loading and very basic forward pass
try:
    print("\nTesting model loading...")
    model = AutoModelForSequenceClassification.from_pretrained('microsoft/codebert-base', num_labels=2)
    print(f"✅ CodeBERT model loaded successfully: {model.__class__.__name__}")
    
    # Test with a simple forward pass
    if 'encoded_batch_pt' in locals():
        # Set model to evaluation mode
        model.eval()
        
        # Pass input through model
        with torch.no_grad():
            outputs = model(**encoded_batch_pt)
            print(f"✅ Forward pass successful, output shape: {outputs.logits.shape}")
    
except Exception as e:
    print(f"❌ Model loading failed: {e}")
    traceback.print_exc()

# Test Dropbox imports - we won't actually connect to the API
try:
    print("\nTesting Dropbox imports...")
    import dropbox
    from dropbox.files import WriteMode
    from dropbox.exceptions import ApiError, AuthError
    print("✅ Dropbox imports successful")
    
    # Additional suggestions for improving the notebook
    print("\nSuggested improvements for the notebook:")
    print("1. Add error handling around dataset loading")
    print("2. Don't use return_tensors='pt' in map functions as it can cause issues")
    print("3. Add validation for content length and truncate long files")
    print("4. Check for Dropbox credentials before attempting upload")
    print("5. Add more robust error handling throughout")
    
except Exception as e:
    print(f"❌ Dropbox import testing failed: {e}")
    traceback.print_exc()

print("\nTest script completed.")
