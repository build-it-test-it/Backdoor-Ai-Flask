import json
import sys
import re

def find_constants_and_tokenizer(notebook_path):
    with open(notebook_path, 'r') as f:
        notebook = json.load(f)
    
    max_length_def = ""
    tokenizer_init = ""
    
    # Look for the specific constants definition cell
    for cell in notebook['cells']:
        if cell['cell_type'] != 'code':
            continue
            
        content = ''.join(cell['source'])
        
        # Find MAX_LENGTH definition
        if 'MAX_LENGTH' in content and '=' in content:
            lines = content.split('\n')
            for line in lines:
                if 'MAX_LENGTH' in line and '=' in line:
                    max_length_def = line.strip()
        
        # Find tokenizer initialization
        if 'tokenizer =' in content and 'from_pretrained' in content:
            tokenizer_init = content

    return max_length_def, tokenizer_init

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python find_constants.py <notebook_path>")
        sys.exit(1)
        
    notebook_path = sys.argv[1]
    max_length_def, tokenizer_init = find_constants_and_tokenizer(notebook_path)
    
    print("===== MAX_LENGTH DEFINITION =====")
    print(max_length_def)
    print("\n===== TOKENIZER INITIALIZATION =====")
    print(tokenizer_init)

    # Extract all cells with setup/constants
    print("\n===== CONSTANTS/SETUP CELLS =====")
    with open(notebook_path, 'r') as f:
        notebook = json.load(f)
        
    for i, cell in enumerate(notebook['cells']):
        if cell['cell_type'] != 'code':
            continue
            
        content = ''.join(cell['source'])
        # Look for cells that define constants
        if any(const in content for const in ['MAX_LENGTH', 'MODEL_NAME', 'SEED', 'BATCH_SIZE']):
            print(f"\n--- Cell {i} ---")
            print(content)
