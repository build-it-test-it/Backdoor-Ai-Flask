import json
import sys

def extract_tokenizer_info(notebook_path):
    with open(notebook_path, 'r') as f:
        notebook = json.load(f)
    
    tokenizer_code = ""
    model_initialization = ""
    
    for cell in notebook['cells']:
        if cell['cell_type'] != 'code':
            continue
            
        content = ''.join(cell['source'])
        
        # Look for tokenizer configuration
        if 'tokenizer' in content and ('max_length' in content or 'model_max_length' in content):
            tokenizer_code += content + "\n\n"
            
        # Look for model loading/initialization
        if ('model =' in content or 'model=' in content) and 'from_pretrained' in content:
            model_initialization += content + "\n\n"
    
    return tokenizer_code, model_initialization

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python extract_tokenizer_info.py <notebook_path>")
        sys.exit(1)
        
    notebook_path = sys.argv[1]
    tokenizer_code, model_initialization = extract_tokenizer_info(notebook_path)
    
    print("===== TOKENIZER CONFIGURATION =====")
    print(tokenizer_code)
    
    print("===== MODEL INITIALIZATION =====")
    print(model_initialization)
