"""
This script contains all the fixes required for the CodeBERT notebook.
Key issues addressed:
1. Removed return_tensors="pt" from tokenize_function when used with dataset.map()
2. Added proper error handling throughout
3. Added validation for Dropbox connectivity before uploading
4. Added progress tracking for long operations
5. Improved memory management
"""

# Fixes for the tokenize_function
TOKENIZE_FUNCTION_FIX = '''
def tokenize_function(examples):
    """Tokenize the Swift code samples.
    
    Args:
        examples: Batch of examples from the dataset
        
    Returns:
        Tokenized examples
    """
    try:
        # Important: Don't use return_tensors="pt" in dataset.map as it can cause issues
        # with Arrow arrays. We'll convert to tensors later if needed.
        return tokenizer(
            examples["content"],
            padding="max_length",
            truncation=True,
            max_length=512,  # CodeBERT supports sequences up to 512 tokens
        )
    except Exception as e:
        print(f"Error in tokenize_function: {e}")
        # Return empty values in case of error
        return {"input_ids": [], "attention_mask": []}
'''

# Add proper error handling to the dataset loading
DATASET_LOADING_FIX = '''
# Load the dataset with proper error handling
try:
    print("Loading the Swift code dataset...")
    data = load_dataset(DATASET_ID, trust_remote_code=True)
    print(f"Dataset loaded successfully with {len(data['train'])} training examples.")
    print("Dataset structure:")
    print(data)
except Exception as e:
    print(f"Error loading dataset: {e}")
    print("Using a small dummy dataset for demonstration purposes...")
    # Create a small dummy dataset for demonstration
    from datasets import Dataset
    dummy_data = {
        "repo_name": ["example_repo"] * 10,
        "path": ["example.swift"] * 9 + ["Package.swift"],
        "content": ["// Example Swift code\nprint(\"Hello World\")"] * 10,
        "license": ["MIT"] * 10
    }
    data = {"train": Dataset.from_dict(dummy_data)}
'''

# Add proper label creation with error handling
LABEL_CREATION_FIX = '''
# Create a classification dataset based on whether the file is a Package.swift file
try:
    def add_labels(example):
        # Label 1 if it's a Package.swift file, 0 otherwise
        example['label'] = 1 if 'Package.swift' in example.get('path', '') else 0
        return example

    # Apply the labeling function
    labeled_data = data['train'].map(add_labels)

    # Check the distribution of labels using collections.Counter
    import collections
    all_labels = labeled_data['label']
    label_counter = collections.Counter(all_labels)
    print("Label distribution:")
    for label, count in label_counter.items():
        print(f"Label {label}: {count} examples ({count/len(labeled_data)*100:.2f}%)")
except Exception as e:
    print(f"Error creating labels: {e}")
'''

# Improved dataset splitting without stratification
DATASET_SPLIT_FIX = '''
# Split the dataset without stratification to avoid ClassLabel errors
try:
    train_test_split = labeled_data.train_test_split(test_size=0.1, seed=42)
    train_data = train_test_split['train']
    val_data = train_test_split['test']

    # Verify label distribution after split
    train_label_counter = collections.Counter(train_data['label'])
    val_label_counter = collections.Counter(val_data['label'])

    print(f"Training set size: {len(train_data)}")
    print(f"Training label distribution: {dict(train_label_counter)}")
    print(f"Validation set size: {len(val_data)}")
    print(f"Validation label distribution: {dict(val_label_counter)}")
except Exception as e:
    print(f"Error splitting dataset: {e}")
'''

# Improved data processing with proper error handling
DATA_PROCESSING_FIX = '''
# Process the data with proper error handling
try:
    from tqdm.auto import tqdm
    print("Tokenizing training data...")
    
    # Show progress bar for better tracking
    tokenized_train_data = train_data.map(
        tokenize_function,
        batched=True,
        remove_columns=[col for col in train_data.column_names if col != 'label'],
        desc="Tokenizing training data"
    )
    
    print("Tokenizing validation data...")
    tokenized_val_data = val_data.map(
        tokenize_function,
        batched=True,
        remove_columns=[col for col in val_data.column_names if col != 'label'],
        desc="Tokenizing validation data"
    )
    
    print("Training data after tokenization:")
    print(tokenized_train_data)
    print("\\nValidation data after tokenization:")
    print(tokenized_val_data)
except Exception as e:
    print(f"Error processing data: {e}")
'''

# Improved model loading with error handling
MODEL_LOADING_FIX = '''
# Load the CodeBERT model for sequence classification with error handling
try:
    print("Loading the CodeBERT model...")
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_ID, num_labels=2)
    model.to(device)
    print(f"Model type: {model.__class__.__name__}")
    
    # Add a memory usage warning for large datasets
    if len(train_data) > 10000:
        print("\\nWARNING: You are training on a large dataset.")
        print("This may require significant memory, especially when using a GPU.")
        print("Consider reducing batch size or using a smaller subset for initial testing.")
except Exception as e:
    print(f"Error loading model: {e}")
'''

# Improved Dropbox integration with validation
DROPBOX_INTEGRATION_FIX = '''
# Validate Dropbox credentials before attempting upload
def validate_dropbox_credentials(app_key, app_secret, refresh_token):
    """Test Dropbox credentials before attempting upload."""
    try:
        print("Validating Dropbox credentials...")
        dbx = dropbox.Dropbox(
            app_key=app_key,
            app_secret=app_secret,
            oauth2_refresh_token=refresh_token
        )
        # Check that the access token is valid
        account = dbx.users_get_current_account()
        print(f"✅ Dropbox credentials valid - Connected to account: {account.name.display_name}")
        return True, dbx
    except AuthError as e:
        print(f"❌ Invalid Dropbox credentials: {e}")
        return False, None
    except Exception as e:
        print(f"❌ Error connecting to Dropbox: {e}")
        return False, None

# Improved upload function with proper error handling and progress tracking
def upload_file_to_dropbox(file_path, dropbox_path, dbx=None):
    """Upload a file to Dropbox with better error handling and progress tracking."""
    if not os.path.exists(file_path):
        print(f"❌ Error: File {file_path} does not exist")
        return False
        
    if dbx is None:
        valid, dbx = validate_dropbox_credentials(APP_KEY, APP_SECRET, REFRESH_TOKEN)
        if not valid:
            return False
    
    try:
        file_size = os.path.getsize(file_path)
        print(f"File size: {file_size / (1024 * 1024):.2f} MB")
        
        with open(file_path, 'rb') as f:
            chunk_size = 4 * 1024 * 1024  # 4MB chunks
            
            if file_size <= chunk_size:
                # Small file, upload in one go
                print(f"Uploading {file_path} to Dropbox as {dropbox_path}...")
                dbx.files_upload(f.read(), dropbox_path, mode=WriteMode('overwrite'))
                print("✅ Upload complete!")
                return True
            else:
                # Large file, use chunked upload with progress bar
                print(f"Uploading {file_path} to Dropbox as {dropbox_path} in chunks...")
                upload_session_start_result = dbx.files_upload_session_start(f.read(chunk_size))
                cursor = dropbox.files.UploadSessionCursor(
                    session_id=upload_session_start_result.session_id,
                    offset=f.tell()
                )
                commit = dropbox.files.CommitInfo(path=dropbox_path, mode=WriteMode('overwrite'))
                
                uploaded = f.tell()
                with tqdm(total=file_size, desc="Uploading", unit="B", unit_scale=True) as pbar:
                    pbar.update(uploaded)
                    
                    while uploaded < file_size:
                        if (file_size - uploaded) <= chunk_size:
                            # Last chunk
                            data = f.read(chunk_size)
                            dbx.files_upload_session_finish(
                                data, cursor, commit
                            )
                            uploaded += len(data)
                            pbar.update(len(data))
                        else:
                            # More chunks to upload
                            data = f.read(chunk_size)
                            dbx.files_upload_session_append_v2(
                                data, cursor
                            )
                            uploaded += len(data)
                            cursor.offset = uploaded
                            pbar.update(len(data))
                            
                print("✅ Chunked upload complete!")
                return True
    except ApiError as e:
        print(f"❌ Dropbox API error: {e}")
        return False
    except Exception as e:
        print(f"❌ Upload error: {e}")
        return False
'''

print("Fixes prepared successfully. Use these to update the notebook.")
