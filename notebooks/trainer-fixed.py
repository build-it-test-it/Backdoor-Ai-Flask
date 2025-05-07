# Create the Trainer without the EarlyStoppingCallback
try:
    # Removed EarlyStoppingCallback because it requires metric_for_best_model parameter
    # which isn't compatible with older versions of transformers
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_train_data,
        eval_dataset=tokenized_val_data,
        compute_metrics=compute_metrics,
        tokenizer=tokenizer,
        data_collator=data_collator,  # Added data collator for dynamic padding
        # No callbacks - removed EarlyStoppingCallback to fix training error
    )
    
    print("Trainer initialized successfully without early stopping.")
except Exception as e:
    print(f"Error creating trainer: {e}")
    raise
