import json
import sys

def read_notebook_in_chunks(notebook_path, chunk_size=1000):
    with open(notebook_path, 'r') as f:
        notebook = json.load(f)
    
    cells = notebook['cells']
    
    all_code = ""
    for cell in cells:
        if cell['cell_type'] == 'code':
            all_code += ''.join(cell['source']) + "\n\n# ---- CELL BOUNDARY ---- #\n\n"
    
    # Print in chunks
    chunks = [all_code[i:i+chunk_size] for i in range(0, len(all_code), chunk_size)]
    
    for i, chunk in enumerate(chunks):
        print(f"\n\n===== CHUNK {i+1}/{len(chunks)} =====\n\n")
        print(chunk)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python notebook_chunker.py <notebook_path>")
        sys.exit(1)
        
    notebook_path = sys.argv[1]
    read_notebook_in_chunks(notebook_path, chunk_size=4000)
