"""Simple test script focusing on the key issues in the notebook."""

import sys
print("Starting simple test script...")

# Test basic imports
try:
    import collections
    import datasets
    from datasets import load_dataset
    from transformers import AutoTokenizer
    print("✅ Basic imports successful")
except Exception as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

# Test the Counter functionality vs count_values()
print("\nTesting Counter vs count_values()...")
test_list = [0, 1, 0, 0, 1, 1, 0, 1]
counter = collections.Counter(test_list)
print(f"Counter result: {dict(counter)}")
print("✅ Counter works correctly")

# Test loading a small dataset sample
try:
    print("\nTesting minimal dataset loading...")
    dataset = load_dataset('mvasiliniuc/iva-swift-codeint', trust_remote_code=True, split='train[:3]')
    print(f"Loaded {len(dataset)} examples")
    print(f"Example keys: {list(dataset[0].keys())}")

    # Test adding labels
    def add_labels(example):
        example['label'] = 1 if 'Package.swift' in example.get('path', '') else 0
        return example
    
    print("\nTesting label addition...")
    labeled_dataset = dataset.map(add_labels)
    if 'label' in labeled_dataset.features:
        print("✅ Label column added successfully")
        
        # Try to use count_values() vs Counter
        try:
            label_counts = labeled_dataset['label'].count_values()
            print(f"count_values() result: {label_counts}")
        except Exception as e:
            print(f"❌ count_values() failed: {e}")
            
        # Use Counter instead
        counter = collections.Counter(labeled_dataset['label'])
        print(f"Counter result: {dict(counter)}")
    
    # Test train_test_split with and without stratification
    print("\nTesting train_test_split...")
    try:
        # Try without stratification first
        splits = labeled_dataset.train_test_split(test_size=0.5, seed=42)
        print(f"✅ Basic split worked: {len(splits['train'])} train, {len(splits['test'])} test")
        
        # Now try with stratification (this should fail in the original notebook)
        try:
            strat_splits = labeled_dataset.train_test_split(test_size=0.5, seed=42, stratify_by_column='label')
            print(f"Stratified split result: {len(strat_splits['train'])} train, {len(strat_splits['test'])} test")
        except Exception as e:
            print(f"❌ Stratified split failed as expected: {e}")
    except Exception as e:
        print(f"❌ Basic split failed: {e}")

    # Test tokenizer
    print("\nTesting tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained('microsoft/codebert-base')
    
    # Check the return_tensors='pt' in batched mode
    try:
        print("Testing tokenization with return_tensors='pt' in batched mode...")
        contents = [example.get('content', '')[:100] for example in labeled_dataset[:2]]
        
        # This is what's in the original notebook - might cause issues
        tokenized = tokenizer(
            contents,
            padding='max_length',
            truncation=True,
            max_length=128,
            return_tensors='pt'
        )
        print(f"✅ Tokenization with return_tensors='pt' worked")
        
    except Exception as e:
        print(f"❌ Tokenization with return_tensors='pt' failed: {e}")
        
    # Test dataset map with tokenizer
    try:
        print("\nTesting dataset.map with tokenizer...")
        
        def tokenize_function(examples):
            return tokenizer(
                examples["content"],
                padding="max_length",
                truncation=True,
                max_length=128,
                # The potential issue is here:
                return_tensors="pt"
            )
        
        tokenized_dataset = labeled_dataset.map(tokenize_function, batched=True)
        print(f"✅ dataset.map with tokenizer worked")
    except Exception as e:
        print(f"❌ dataset.map with tokenizer failed: {e}")
        print("This confirms there's an issue with return_tensors='pt' in dataset.map")
        
        # Try the fixed version
        try:
            print("\nTesting dataset.map with fixed tokenizer...")
            
            def fixed_tokenize_function(examples):
                return tokenizer(
                    examples["content"],
                    padding="max_length",
                    truncation=True,
                    max_length=128,
                    # Removed the problematic parameter:
                    # return_tensors="pt"
                )
            
            fixed_tokenized_dataset = labeled_dataset.map(fixed_tokenize_function, batched=True)
            print(f"✅ dataset.map with fixed tokenizer worked")
        except Exception as e:
            print(f"❌ dataset.map with fixed tokenizer also failed: {e}")

except Exception as e:
    print(f"❌ Dataset testing failed: {e}")
    import traceback
    traceback.print_exc()

print("\nSimple test script completed.")
