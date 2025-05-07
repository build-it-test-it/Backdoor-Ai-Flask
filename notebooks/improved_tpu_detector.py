"""
Improved TPU detector for CodeBERT training notebook.

This module contains an improved version of the TPU detection function
that handles errors properly and provides graceful fallbacks.

Usage:
    Copy and paste this function into your notebook to replace the existing
    detect_and_configure_accelerator function.
"""

import torch

def improved_detect_and_configure_accelerator():
    """Detect and configure the available accelerator (CPU, GPU, or TPU) with robust error handling."""
    # First try TPU
    try:
        print("Checking for TPU availability...")
        import torch_xla.core.xla_model as xm
        try:
            # Try the new API first (for torch_xla 2.7+)
            try:
                import torch_xla.runtime as xr
                print("Using torch_xla.runtime API")
                have_xr = True
            except ImportError:
                print("torch_xla.runtime not available, using legacy API")
                have_xr = False
                
            device = xm.xla_device()
            use_tpu = True
            use_gpu = False
            print("TPU detected! Configuring for TPU training...")
            
            # Try getting cores with exception handling
            try:
                if have_xr:
                    # Use newer API if available
                    cores = xr.world_size()
                    print(f"TPU cores available (via xr.world_size): {cores}")
                else:
                    # Fall back to deprecated method with warning capture
                    import warnings
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        cores = xm.xrt_world_size()
                        print(f"TPU cores available (via xm.xrt_world_size): {cores}")
            except Exception as core_err:
                print(f"Warning: Could not determine TPU core count: {core_err}")
                print("Proceeding with TPU but unknown core count.")
                
            # Configure XLA for TPU - with error handling
            try:
                import torch_xla.distributed.parallel_loader as pl
                import torch_xla.distributed.xla_multiprocessing as xmp
                print("Successfully imported TPU distributed libraries")
            except ImportError as imp_err:
                print(f"Warning: Could not import some TPU libraries: {imp_err}")
                print("Continuing with basic TPU support")
            
            return device, use_tpu, use_gpu
            
        except Exception as tpu_init_err:
            print(f"TPU initialization error: {tpu_init_err}")
            print("TPU libraries detected but initialization failed. Falling back to GPU/CPU.")
            # Fall through to GPU/CPU detection
            
    except ImportError as ie:
        print(f"No TPU support detected: {ie}")
        # Fall through to GPU/CPU detection
        
    except Exception as e:
        print(f"Unexpected error in TPU detection: {e}")
        print("Falling back to GPU/CPU.")
        # Fall through to GPU/CPU detection
    
    # If TPU not available or failed, try GPU
    try:
        if torch.cuda.is_available():
            print(f"GPU detected! Using {torch.cuda.get_device_name(0)}")
            device = torch.device("cuda")
            use_tpu = False
            use_gpu = True
            print(f"GPU memory available: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
        else:
            print("No GPU detected. Using CPU (this will be slow).")
            device = torch.device("cpu")
            use_tpu = False
            use_gpu = False
        return device, use_tpu, use_gpu
        
    except Exception as e:
        print(f"Error in GPU/CPU detection: {e}")
        print("Defaulting to CPU.")
        return torch.device("cpu"), False, False
