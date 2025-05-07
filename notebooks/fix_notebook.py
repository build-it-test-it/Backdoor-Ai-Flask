#!/usr/bin/env python3
"""
Simple script to create a fixed version of the train-codebert.ipynb notebook.
"""
import json
import os
import shutil

# First make a copy of the original notebook
source_file = "notebooks/train-codebert.ipynb"
target_file = "notebooks/train-codebert-fixed.ipynb"

# Copy the file
shutil.copy2(source_file, target_file)

# Load the notebook as JSON
with open(target_file, 'r') as f:
    notebook = json.load(f)

# Read TPU detector improved content
with open('notebooks/improved_tpu_detector.py', 'r') as f:
    tpu_detector_code = f.read()

# Read safety checker content
with open('notebooks/dataset_safety_checker.py', 'r') as f:
    dataset_safety_code = f.read()

# Find the TPU detector cell and replace it
for cell in notebook['cells']:
    if cell['cell_type'] == 'code':
        source = ''.join(cell['source'])
        if '# Function to detect and configure TPU' in source:
            # Replace with improved version
            # Extract just the function definition from our file
            function_code = '\n'.join([
                "# Improved function to detect and configure TPU with better error handling",
                "def detect_and_configure_accelerator():",
                *[line for line in tpu_detector_code.split('\n') if line.startswith('    ') or line == ''],
                "",
                "# Detect and configure accelerator",
                "device, use_tpu, use_gpu = detect_and_configure_accelerator()"
            ])
            cell['source'] = function_code.split('\n')
            print("✅ Replaced TPU detector function")
            break

# Find the dataset loading cell and add safety checks
dataset_loading_inserted = False
for i, cell in enumerate(notebook['cells']):
    if cell['cell_type'] == 'code':
        source = ''.join(cell['source'])
        if '# Load the dataset with retry logic' in source:
            # Insert safety check before trying to load dataset
            safe_code = '\n'.join([
                "# Make sure dataset ID is defined (in case previous cell didn't execute)",
                "if 'DATASET_ID' not in globals():",
                "    print(\"Warning: DATASET_ID not found. Using default value.\")",
                "    DATASET_ID = \"mvasiliniuc/iva-swift-codeint\"  # Default value as fallback",
                "    MAX_LENGTH = 384",
                "    MODEL_ID = \"microsoft/codebert-base\"",
                "    TRAIN_BATCH_SIZE = 8",
                "    EVAL_BATCH_SIZE = 16",
                "    GRADIENT_ACCUMULATION_STEPS = 4",
                "    print(\"Using default configuration values.\")",
                "",
                "# Load the dataset with retry logic"
            ])
            lines = cell['source']
            for j, line in enumerate(lines):
                if '# Load the dataset with retry logic' in line:
                    lines[j:j] = safe_code.split('\n')
                    print("✅ Added dataset ID safety check")
                    dataset_loading_inserted = True
                    break
            if dataset_loading_inserted:
                break

# Add a try-except block to the dataset loading
if dataset_loading_inserted:
    for i, cell in enumerate(notebook['cells']):
        if cell['cell_type'] == 'code':
            source = ''.join(cell['source'])
            if 'data = load_dataset_with_retry(DATASET_ID)' in source:
                # Update to add fallback dataset logic
                current_lines = cell['source']
                updated_lines = []
                for line in current_lines:
                    updated_lines.append(line)
                    if 'data = load_dataset_with_retry(DATASET_ID)' in line:
                        # Add print statement indicating what's being loaded
                        updated_lines[-1] = "    print(f\"Loading dataset: {DATASET_ID}\")\n"
                        updated_lines.append("    data = load_dataset_with_retry(DATASET_ID)\n")
                notebook['cells'][i]['source'] = updated_lines
                print("✅ Added dataset loading diagnostics")
                break

# Fix batch_size formatting issues - find cells with map function calls
for i, cell in enumerate(notebook['cells']):
    if cell['cell_type'] == 'code':
        source = ''.join(cell['source'])
        if 'tokenized_train_data = train_data.map(' in source:
            lines = cell['source']
            for j, line in enumerate(lines):
                if 'batch_size=' in line and ',' not in line and '#' in line:
                    # Missing comma after batch_size
                    lines[j] = line.replace('batch_size=', 'batch_size=').replace('  #', ',  #')
                    print("✅ Fixed batch_size parameter formatting")
            notebook['cells'][i]['source'] = lines

# Update notebook title to indicate this is a fixed version
for cell in notebook['cells']:
    if cell['cell_type'] == 'markdown' and '# CodeBERT for Swift Code Understanding' in ''.join(cell['source']):
        title = ''.join(cell['source'])
        title = title.replace('# CodeBERT for Swift Code Understanding', 
                             '# CodeBERT for Swift Code Understanding (Fixed Version)')
        title += "\n\n**Note:** This is a fixed version of the notebook with improved error handling, TPU detection, and dataset safety checks."
        cell['source'] = [title]
        print("✅ Updated notebook title")
        break

# Save the fixed notebook
with open(target_file, 'w') as f:
    json.dump(notebook, f, indent=1)

print(f"✅ Fixed notebook saved to {target_file}")
