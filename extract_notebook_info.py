import json
import sys

def extract_key_parts(notebook_path):
    with open(notebook_path, 'r') as f:
        notebook = json.load(f)
    
    cells = notebook['cells']
    
    # Look for cells with model loading, tokenizer config, and training
    model_cells = []
    tokenizer_cells = []
    training_cells = []
    dataset_cells = []
    
    keywords = {
        'model': ['model =', 'from transformers import', 'AutoModel', 'BertModel', 'CodeBertModel'],
        'tokenizer': ['tokenizer', 'max_length', 'tokenize'],
        'training': ['trainer', 'Trainer', 'training_args', 'TrainingArguments'],
        'dataset': ['Dataset', 'dataset', 'from datasets import']
    }
    
    for i, cell in enumerate(cells):
        if cell['cell_type'] != 'code':
            continue
            
        source = ''.join(cell['source'])
        
        for category, kws in keywords.items():
            if any(kw in source for kw in kws):
                cell_info = {
                    'index': i,
                    'content': source,
                    'category': category
                }
                
                if category == 'model':
                    model_cells.append(cell_info)
                elif category == 'tokenizer':
                    tokenizer_cells.append(cell_info)
                elif category == 'training':
                    training_cells.append(cell_info)
                elif category == 'dataset':
                    dataset_cells.append(cell_info)
    
    return {
        'model_cells': model_cells,
        'tokenizer_cells': tokenizer_cells,
        'training_cells': training_cells,
        'dataset_cells': dataset_cells
    }

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python extract_notebook_info.py <notebook_path>")
        sys.exit(1)
        
    notebook_path = sys.argv[1]
    key_parts = extract_key_parts(notebook_path)
    
    print(f"===== MODEL CELLS ({len(key_parts['model_cells'])}) =====")
    for cell in key_parts['model_cells']:
        print(f"\n--- Cell {cell['index']} ---")
        print(cell['content'])
        
    print(f"\n\n===== TOKENIZER CELLS ({len(key_parts['tokenizer_cells'])}) =====")
    for cell in key_parts['tokenizer_cells']:
        print(f"\n--- Cell {cell['index']} ---")
        print(cell['content'])
        
    print(f"\n\n===== TRAINING CELLS ({len(key_parts['training_cells'])}) =====")
    for cell in key_parts['training_cells']:
        print(f"\n--- Cell {cell['index']} ---")
        print(cell['content'])
        
    print(f"\n\n===== DATASET CELLS ({len(key_parts['dataset_cells'])}) =====")
    for cell in key_parts['dataset_cells']:
        print(f"\n--- Cell {cell['index']} ---")
        print(cell['content'])
