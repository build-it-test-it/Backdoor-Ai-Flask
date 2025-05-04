#!/usr/bin/env python3
import json
import glob

# Find all notebook files
notebook_files = glob.glob("notebooks/ollama_config/*.ipynb")
notebook_files.append("notebooks/ollama_colab.ipynb")

for notebook_file in notebook_files:
    print(f"Processing {notebook_file}...")
    
    # Read the notebook
    with open(notebook_file, "r") as f:
        notebook = json.load(f)
    
    # Flag to track if we fixed this notebook
    fixed = False
    
    # Look for cells with Ollama installation
    for cell in notebook["cells"]:
        if cell.get("cell_type") == "code":
            source = "".join(cell.get("source", []))
            
            # Check if this is an Ollama installation cell
            if "curl -fsSL https://ollama.com/install.sh" in source and "apt-get install -y lspci lshw" not in source:
                # This is the cell we need to modify
                new_source = []
                
                # Look for the right place to insert our fix - before the Ollama install line
                for line in cell.get("source", []):
                    if "curl -fsSL https://ollama.com/install.sh" in line:
                        # Add the GPU detection tools installation before Ollama installation
                        new_source.append("# Install GPU detection tools first\n")
                        new_source.append("!apt-get update && apt-get install -y lspci lshw pciutils\n")
                        new_source.append("\n")
                        # Keep the original Ollama installation line
                        new_source.append(line)
                    else:
                        new_source.append(line)
                
                # Update the cell source
                cell["source"] = new_source
                fixed = True
    
    # Save the notebook if we made changes
    if fixed:
        with open(notebook_file, "w") as f:
            json.dump(notebook, f, indent=2)
        print(f"  Fixed GPU detection issue in {notebook_file}")
    else:
        print(f"  No Ollama installation cell found or already fixed in {notebook_file}")

print("All notebooks processed!")
