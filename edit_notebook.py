import json

# Read the notebook
with open('notebooks/train-codebert.ipynb', 'r') as f:
    notebook = json.load(f)

# Define the new source code for the cell
new_source = [
    "# Create the Trainer without the EarlyStoppingCallback\n",
    "try:\n",
    "    # Removed EarlyStoppingCallback because it requires metric_for_best_model parameter\n",
    "    # which isn't compatible with older versions of transformers\n",
    "    trainer = Trainer(\n",
    "        model=model,\n",
    "        args=training_args,\n",
    "        train_dataset=tokenized_train_data,\n",
    "        eval_dataset=tokenized_val_data,\n",
    "        compute_metrics=compute_metrics,\n",
    "        tokenizer=tokenizer,\n",
    "        data_collator=data_collator,  # Added data collator for dynamic padding\n",
    "        # No callbacks - removed EarlyStoppingCallback to fix training error\n",
    "    )\n",
    "    \n",
    "    print(\"Trainer initialized successfully without early stopping.\")\n",
    "except Exception as e:\n",
    "    print(f\"Error creating trainer: {e}\")\n",
    "    raise"
]

# Find and update the cell with id 'create-trainer'
for cell in notebook['cells']:
    if cell.get('id') == 'create-trainer':
        cell['source'] = new_source
        break

# Write the updated notebook
with open('notebooks/train-codebert.ipynb.fixed', 'w') as f:
    json.dump(notebook, f, indent=1)

print("Notebook updated successfully.")
