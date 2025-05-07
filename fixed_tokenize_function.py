import json

# Load the notebook
with open('notebooks/train-codebert.ipynb', 'r') as f:
    notebook = json.load(f)

# Find the cell with the tokenize_function and fix it
for cell in notebook['cells']:
    if cell['cell_type'] == 'code':
        source = ''.join(cell['source'])
        if 'def tokenize_function' in source and 'return_tensors="pt"' in source:
            # Found the problematic cell, fix it
            fixed_source = source.replace('return_tensors="pt"', '# return_tensors="pt" removed to avoid Arrow serialization issues')
            cell['source'] = fixed_source.split('\n')
            print("Fixed tokenize_function!")
            break

# Save the fixed notebook
with open('notebooks/fixed_train_codebert.ipynb', 'w') as f:
    json.dump(notebook, f, indent=1)
    print("Saved fixed notebook to fixed_train_codebert.ipynb")
