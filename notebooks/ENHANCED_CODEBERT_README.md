# Enhanced CodeBERT Training for Swift Code Understanding

This directory contains an enhanced version of the CodeBERT training notebook that improves the data preparation process to utilize the entire Swift code dataset instead of focusing on a single file type.

## Enhancements Made

### Original Approach (`train-codebert.ipynb`)
- Created a binary classification task focused only on identifying Package.swift files
- Limited the model's learning to a single specific file type
- Didn't fully utilize the available dataset
- Resulted in a model with limited code understanding capabilities

### Enhanced Approach (`train-codebert-enhanced.ipynb`)
- Created a multi-class classification task that categorizes Swift files based on their purpose in a codebase
- Utilizes the entire dataset for training
- Classifies files into 6 meaningful categories:
  1. **Models** - Data structures and model definitions
  2. **Views** - UI related files
  3. **Controllers** - Application logic
  4. **Utilities** - Helper functions and extensions
  5. **Tests** - Test files
  6. **Configuration** - Package and configuration files
- Implements a two-step classification approach:
  - First attempts to classify based on file path and naming conventions
  - For ambiguous cases, analyzes file content to determine the most likely category
- Maintains proper stratification during dataset splitting to ensure balanced representation of all categories

## Implementation Details

The enhanced data preparation approach is implemented in two files:

1. `enhanced_data_preparation.py` - A standalone module containing the enhanced data preparation functions
2. `train-codebert-enhanced.ipynb` - A complete notebook that incorporates the enhanced approach

### Key Functions

- `extract_file_type(path)` - Extracts the file category based on the file path and naming conventions
- `analyze_content_for_category(content)` - Analyzes file content to determine its category when path-based classification is ambiguous
- `enhanced_add_labels(example)` - Main labeling function that combines path and content analysis to assign category labels

## Benefits of the Enhanced Approach

1. **Better Data Utilization** - Uses the entire dataset instead of a subset
2. **More Meaningful Classification** - Creates a task that better represents real-world code understanding challenges
3. **Richer Model Learning** - Allows the model to learn patterns across different types of Swift code files
4. **Practical Applications** - The resulting model can be used for:
   - Automatically categorizing new code files
   - Suggesting file organization in large codebases
   - Identifying misplaced code (e.g., model logic in controller files)
   - Assisting in code navigation and understanding

## Usage

To use the enhanced approach, run the `train-codebert-enhanced.ipynb` notebook. The notebook includes all necessary steps from data loading to model training and evaluation.

Alternatively, you can import the functions from `enhanced_data_preparation.py` into your own notebooks or scripts.