import json
import sys
import re

def find_tokenizer_info(notebook_path):
    with open(notebook_path, 'r') as f:
        notebook = json.load(f)
    
    tokenizer_init = ""
    model_init = ""
    tokenize_function = ""
    
    for cell in notebook['cells']:
        if cell['cell_type'] != 'code':
            continue
            
        content = ''.join(cell['source'])
        
        # Look for tokenizer initialization
        if 'tokenizer =' in content and 'from_pretrained' in content:
            tokenizer_init = content
            
        # Look for model initialization 
        if 'model =' in content and 'from_pretrained' in content:
            model_init = content
            
        # Look for tokenize_function
        if 'def tokenize_function' in content:
            tokenize_function = content

    # Extract MODEL_NAME constant
    model_name_pattern = re.compile(r'MODEL_NAME\s*=\s*[\'"]([^\'"]+)[\'"]')
    model_name_matches = []
    
    for cell in notebook['cells']:
        if cell['cell_type'] != 'code':
            continue
        content = ''.join(cell['source'])
        matches = model_name_pattern.findall(content)
        if matches:
            model_name_matches.extend(matches)
    
    # Extract max_length / model_max_length values
    max_length_pattern = re.compile(r'max_length\s*=\s*(\d+)')
    model_max_length_pattern = re.compile(r'model_max_length\s*=\s*(\d+)')
    
    max_length_matches = []
    model_max_length_matches = []
    
    for cell in notebook['cells']:
        if cell['cell_type'] != 'code':
            continue
        content = ''.join(cell['source'])
        max_length_matches.extend(max_length_pattern.findall(content))
        model_max_length_matches.extend(model_max_length_pattern.findall(content))
    
    return {
        'tokenizer_init': tokenizer_init,
        'model_init': model_init,
        'tokenize_function': tokenize_function,
        'model_name': model_name_matches[0] if model_name_matches else "Not found",
        'max_length': max_length_matches[0] if max_length_matches else "Not found",
        'model_max_length': model_max_length_matches[0] if model_max_length_matches else "Not found"
    }

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python find_tokenizer_max_length.py <notebook_path>")
        sys.exit(1)
        
    notebook_path = sys.argv[1]
    info = find_tokenizer_info(notebook_path)
    
    print("===== MODEL NAME =====")
    print(info['model_name'])
    print("\n===== MAX LENGTH =====")
    print(info['max_length'])
    print("\n===== MODEL MAX LENGTH =====")
    print(info['model_max_length'])
    print("\n===== TOKENIZER INITIALIZATION =====")
    print(info['tokenizer_init'])
    print("\n===== MODEL INITIALIZATION =====")
    print(info['model_init'])
    print("\n===== TOKENIZE FUNCTION =====")
    print(info['tokenize_function'])
