# RoBERTa Position Embeddings Fix

## Issue
When using CodeBERT with a long MAX_LENGTH setting (e.g., 10000), the notebook fails with the error:

```
RuntimeError: The expanded size of the tensor (10000) must match the existing size (514) at non-singleton dimension 1. 
Target sizes: [16, 10000]. Tensor sizes: [1, 514]
```

This happens because:
1. RoBERTa uses `model.roberta.embeddings` instead of `model.bert.embeddings`
2. The token_type_ids buffer needs to be properly expanded for longer sequences

## Fix

1. Use the provided `fix_position_embeddings` function in `roberta_position_embeddings_fix.py`
2. OR apply the patch in `codebert-train-v2-patch.txt` to the notebook

Both solutions detect if the model is RoBERTa or BERT and handle the embeddings accordingly, properly creating a new token_type_ids buffer with the correct dimensions.
