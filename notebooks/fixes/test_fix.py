"""
Simple test to verify the fix for RoBERTa position embeddings.
"""
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from roberta_position_embeddings_fix import fix_position_embeddings

# Configuration
MODEL_NAME = "Ct1tz/Codebert-Base-B2D4G5"
MAX_LENGTH = 10000
BATCH_SIZE = 16

# Load model and tokenizer
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=6)

# Apply the fix
model = fix_position_embeddings(model, MAX_LENGTH)

# Test with a batch of random inputs
input_ids = torch.randint(0, 1000, (BATCH_SIZE, MAX_LENGTH))
attention_mask = torch.ones_like(input_ids)

# This should work without errors
outputs = model(input_ids=input_ids, attention_mask=attention_mask)
print("Test passed successfully!")
print(f"Output shape: {outputs.logits.shape}")
