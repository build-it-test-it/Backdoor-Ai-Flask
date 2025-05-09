import json
import sys

def update_codebert_notebook(notebook_path):
    """Updates the CodeBERT notebook to extend token limit from 512 to 10,000"""
    
    # Load the notebook
    with open(notebook_path, 'r') as f:
        notebook = json.load(f)
    
    # Track changes
    changes_made = []
    
    # Process each cell
    for cell in notebook['cells']:
        if cell['cell_type'] != 'code':
            continue
        
        source = ''.join(cell['source'])
        
        # Update MAX_LENGTH constant
        if 'MAX_LENGTH = 512' in source:
            new_source = source.replace('MAX_LENGTH = 512', 'MAX_LENGTH = 10000  # Extended from 512 to 10000 tokens')
            cell['source'] = new_source.split('\n')
            changes_made.append("Updated MAX_LENGTH from 512 to 10000")
        
        # Add position embedding extension code after model initialization
        if 'model = AutoModelForSequenceClassification.from_pretrained(' in source and 'extend_position_embeddings' not in source:
            lines = source.split('\n')
            insert_index = None
            
            for i, line in enumerate(lines):
                if 'model.to(device)' in line:
                    insert_index = i + 1
                    break
            
            if insert_index is not None:
                extension_code = [
                    "",
                    "    # Extend position embeddings to support longer sequences",
                    "    if MAX_LENGTH > 512:",
                    "        print(f\"Extending position embeddings from {model.config.max_position_embeddings} to {MAX_LENGTH}\")",
                    "        # Get current position embeddings",
                    "        current_max_pos = model.config.max_position_embeddings",
                    "        # Initialize new position embeddings for the extended range",
                    "        new_pos_embed = model.bert.embeddings.position_embeddings.weight.new_empty(MAX_LENGTH, model.config.hidden_size)",
                    "        # Copy existing weights",
                    "        new_pos_embed[:current_max_pos] = model.bert.embeddings.position_embeddings.weight",
                    "        # Initialize remaining weights (interpolation, repeating pattern, or just xavier init)",
                    "        # Using Xavier initialization for the remainder",
                    "        import torch.nn as nn",
                    "        nn.init.xavier_uniform_(new_pos_embed[current_max_pos:])",
                    "        # Update the model config",
                    "        model.config.max_position_embeddings = MAX_LENGTH",
                    "        # Replace the position embeddings weights",
                    "        model.bert.embeddings.position_embeddings = nn.Embedding.from_pretrained(new_pos_embed, freeze=False)",
                    "        # Update the position_ids in the model to work with new length",
                    "        model.bert.embeddings.register_buffer(",
                    "            \"position_ids\", torch.arange(MAX_LENGTH).expand((1, -1)))",
                    "        print(\"Successfully extended position embeddings\")",
                    ""
                ]
                
                # Insert the extension code
                for i, line in enumerate(extension_code):
                    lines.insert(insert_index + i, line)
                
                # Update cell source
                cell['source'] = lines
                changes_made.append("Added position embedding extension code")
                
        # Update tokenizer initialization if needed
        if 'tokenizer = AutoTokenizer.from_pretrained(' in source and 'model_max_length' not in source:
            lines = source.split('\n')
            for i, line in enumerate(lines):
                if 'tokenizer = AutoTokenizer.from_pretrained(' in line:
                    # Replace with version that includes model_max_length
                    new_line = line.strip()
                    if new_line.endswith(')'):
                        new_line = new_line[:-1] + ', model_max_length=MAX_LENGTH)'
                    else:
                        # Handle case where it's split across lines
                        new_line = new_line + ', model_max_length=MAX_LENGTH'
                    
                    lines[i] = new_line
                    cell['source'] = lines
                    changes_made.append("Updated tokenizer initialization to set model_max_length")
                    break
    
    # Save the updated notebook
    output_path = notebook_path
    with open(output_path, 'w') as f:
        json.dump(notebook, f, indent=2)
    
    return changes_made

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python update_notebook.py <notebook_path>")
        sys.exit(1)
        
    notebook_path = sys.argv[1]
    changes = update_codebert_notebook(notebook_path)
    
    print(f"Updated notebook: {notebook_path}")
    print("Changes made:")
    for change in changes:
        print(f"- {change}")
