import json
import sys

def find_constants_cell(notebook_path):
    with open(notebook_path, 'r') as f:
        notebook = json.load(f)
    
    for cell in notebook['cells']:
        if cell['cell_type'] != 'code':
            continue
            
        content = ''.join(cell['source'])
        
        # Look for a cell that defines multiple constants
        constants = ['MAX_LENGTH', 'BATCH_SIZE', 'SEED', 'NUM_EPOCHS']
        count = sum(1 for const in constants if const in content)
        
        # If multiple constants are defined in this cell, it's likely our target
        if count >= 2:
            return content
    
    return "Constants cell not found"

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python extract_constants_cell.py <notebook_path>")
        sys.exit(1)
        
    notebook_path = sys.argv[1]
    constants_cell = find_constants_cell(notebook_path)
    
    print("===== CONSTANTS CELL =====")
    print(constants_cell)
