"""
Enhanced Data Preparation for CodeBERT Training

This script provides an improved data preparation approach for training CodeBERT
on Swift code, utilizing the entire dataset rather than focusing on a single file type.
"""

import re
import collections
from datasets import ClassLabel

def extract_file_type(path):
    """
    Extract the file type/category based on the file path and naming conventions in Swift projects.
    
    Args:
        path (str): The file path
        
    Returns:
        int: The category label (0-5)
    """
    path_lower = path.lower()
    filename = path.split('/')[-1].lower()
    
    # Category 0: Models - Data structures and model definitions
    if ('model' in path_lower or 
        'struct' in path_lower or 
        'entity' in path_lower or
        'data' in path_lower and 'class' in path_lower):
        return 0
    
    # Category 1: Views - UI related files
    elif ('view' in path_lower or 
          'ui' in path_lower or 
          'screen' in path_lower or 
          'page' in path_lower or
          'controller' in path_lower and 'view' in path_lower):
        return 1
    
    # Category 2: Controllers - Application logic
    elif ('controller' in path_lower or 
          'manager' in path_lower or 
          'coordinator' in path_lower or
          'service' in path_lower):
        return 2
    
    # Category 3: Utilities - Helper functions and extensions
    elif ('util' in path_lower or 
          'helper' in path_lower or 
          'extension' in path_lower or
          'common' in path_lower):
        return 3
    
    # Category 4: Tests - Test files
    elif ('test' in path_lower or 
          'spec' in path_lower or 
          'mock' in path_lower):
        return 4
    
    # Category 5: Configuration - Package and configuration files
    elif ('package.swift' in path_lower or 
          'config' in path_lower or 
          'settings' in path_lower or
          'info.plist' in path_lower):
        return 5
    
    # Default to category 3 (Utilities) if no clear category is found
    return 3

def analyze_content_for_category(content):
    """
    Analyze file content to help determine its category when path-based classification is ambiguous.
    
    Args:
        content (str): The file content
        
    Returns:
        int: The suggested category based on content analysis
    """
    content_lower = content.lower()
    
    # Check for model patterns
    if (re.search(r'struct\s+\w+', content) or 
        re.search(r'class\s+\w+\s*:\s*\w*codable', content_lower) or
        'encodable' in content_lower or 'decodable' in content_lower):
        return 0
    
    # Check for view patterns
    elif ('uiview' in content_lower or 
          'uitableview' in content_lower or 
          'uicollectionview' in content_lower or
          'swiftui' in content_lower or
          'view {' in content_lower):
        return 1
    
    # Check for controller patterns
    elif ('viewcontroller' in content_lower or 
          'uiviewcontroller' in content_lower or
          'navigationcontroller' in content_lower or
          'viewdidload' in content_lower):
        return 2
    
    # Check for utility patterns
    elif ('extension' in content_lower or 
          'func ' in content and not 'class' in content_lower[:100] or
          'protocol' in content_lower):
        return 3
    
    # Check for test patterns
    elif ('xctest' in content_lower or 
          'testcase' in content_lower or
          'func test' in content_lower):
        return 4
    
    # Check for configuration patterns
    elif ('package(' in content_lower or 
          'dependencies' in content_lower and 'package' in content_lower or
          'products' in content_lower and 'targets' in content_lower):
        return 5
    
    # Default to -1 (undetermined)
    return -1

def enhanced_add_labels(example):
    """
    Enhanced labeling function that categorizes Swift files based on their purpose.
    
    Categories:
    0: Models - Data structures and model definitions
    1: Views - UI related files
    2: Controllers - Application logic
    3: Utilities - Helper functions and extensions
    4: Tests - Test files
    5: Configuration - Package and configuration files
    
    Args:
        example: Dataset example with 'path' and 'content' fields
        
    Returns:
        example: The example with added 'label' field
    """
    # First try to determine category from path
    path_category = extract_file_type(example['path'])
    
    # If the path-based category is ambiguous (category 3 - Utilities is our default),
    # try to analyze the content for a more specific category
    if path_category == 3:
        content_category = analyze_content_for_category(example['content'])
        # Only use content category if it's determined (-1 means undetermined)
        if content_category != -1:
            example['label'] = content_category
        else:
            example['label'] = path_category
    else:
        example['label'] = path_category
    
    return example

def prepare_dataset(dataset):
    """
    Prepare the dataset by adding labels and splitting into train/val/test sets.
    
    Args:
        dataset: The original dataset
        
    Returns:
        tuple: (train_data, val_data, test_data)
    """
    # Apply the enhanced labeling function
    labeled_data = dataset['train'].map(enhanced_add_labels)
    
    # Check the distribution of labels
    all_labels = labeled_data['label']
    label_counter = collections.Counter(all_labels)
    
    print("Label distribution:")
    for label, count in label_counter.items():
        category_names = {
            0: "Models",
            1: "Views",
            2: "Controllers",
            3: "Utilities",
            4: "Tests",
            5: "Configuration"
        }
        category_name = category_names.get(label, f"Category {label}")
        print(f"Label {label} ({category_name}): {count} examples ({count/len(labeled_data)*100:.2f}%)")
    
    # Check for label imbalance
    min_label_count = min(label_counter.values())
    max_label_count = max(label_counter.values())
    imbalance_ratio = max_label_count / min_label_count if min_label_count > 0 else float('inf')
    
    if imbalance_ratio > 10:
        print(f"WARNING: Severe label imbalance detected (ratio: {imbalance_ratio:.2f}). Consider using class weights or resampling.")
    elif imbalance_ratio > 3:
        print(f"WARNING: Moderate label imbalance detected (ratio: {imbalance_ratio:.2f}). Consider using class weights.")
    
    # Get unique labels
    unique_labels = sorted(set(labeled_data["label"]))
    num_labels = len(unique_labels)
    
    # Create a new dataset with ClassLabel feature
    labeled_data = labeled_data.cast_column("label", ClassLabel(num_classes=num_labels, names=[str(i) for i in unique_labels]))
    
    # First split: Create train and temp sets (temp will be split into val and test)  
    train_temp_split = labeled_data.train_test_split(test_size=0.2, seed=42, stratify_by_column='label')
    train_data = train_temp_split['train']
    
    # Second split: Split temp into validation and test sets
    val_test_split = train_temp_split['test'].train_test_split(test_size=0.5, seed=42, stratify_by_column='label')
    val_data = val_test_split['train']
    test_data = val_test_split['test']
    
    # Verify label distribution after split
    train_label_counter = collections.Counter(train_data['label'])
    val_label_counter = collections.Counter(val_data['label'])
    test_label_counter = collections.Counter(test_data['label'])
    
    print(f"Training set size: {len(train_data)}")
    print(f"Training label distribution: {dict(train_label_counter)}")
    
    print(f"Validation set size: {len(val_data)}")
    print(f"Validation label distribution: {dict(val_label_counter)}")
    
    print(f"Test set size: {len(test_data)}")
    print(f"Test label distribution: {dict(test_label_counter)}")
    
    return train_data, val_data, test_data

# Usage example:
# train_data, val_data, test_data = prepare_dataset(data)