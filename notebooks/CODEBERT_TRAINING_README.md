# CodeBERT Training Setup

This directory contains notebooks and utilities for training CodeBERT models on Swift code classification.

## Training Options

There are two main training modes available:

1. **Full Training Mode**: Uses the entire dataset and optimized training parameters for production-quality models.
2. **Debug Training Mode**: Uses a smaller dataset sample and enhanced logging for troubleshooting training issues.

## Files

- `codebert_trainer.py`: Core module that provides trainer implementations for both full and debug training.
- `full-codebert-train-fixed.ipynb`: Notebook for full training with proper configuration.
- `debug-codebert-train.ipynb`: Notebook specifically for debug training with enhanced logging.

## How to Use

### For Full Training

1. Open `full-codebert-train-fixed.ipynb`
2. Ensure `DEBUG_MODE = False` is set
3. Run all cells to perform a complete training run

```python
# Training mode configuration
DEBUG_MODE = False  # Set to False for full training
```

### For Debug Training

1. Open `debug-codebert-train.ipynb`
2. Ensure `DEBUG_MODE = True` is set
3. Adjust `DEBUG_SAMPLE_SIZE` as needed
4. Run all cells to perform a debug training run

```python
# Training mode configuration
DEBUG_MODE = True  # Enable debug mode
DEBUG_SAMPLE_SIZE = 10000  # Small sample size for debugging
```

## Key Differences

### Full Training Mode:
- Uses the entire dataset
- Evaluates once per epoch
- Optimized for performance
- Uses multiprocessing when available
- Less frequent logging

### Debug Training Mode:
- Uses a smaller dataset sample
- Evaluates more frequently (every 50-100 steps)
- Logs memory usage and timing information
- Disables multiprocessing for easier debugging
- More frequent logging (every 10 steps)

## Trainer Implementation

The `codebert_trainer.py` module provides two trainer implementations:

1. `StandardTrainer`: For full training runs, optimized for performance.
2. `DebugTrainer`: For debug runs, with additional logging and monitoring.

The `get_trainer()` factory function automatically selects the appropriate trainer based on the `debug_mode` parameter:

```python
# Create the appropriate trainer based on debug mode
trainer = get_trainer(
    debug_mode=DEBUG_MODE,
    class_weights=class_weights,
    model=model,
    args=training_args,
    # ... other parameters
)
```

## Troubleshooting

If you encounter memory issues during training:
- Reduce batch size
- Reduce gradient accumulation steps
- Use a smaller sample size in debug mode

If you need more detailed logging:
- Enable debug mode
- Reduce the logging_steps parameter in training_args