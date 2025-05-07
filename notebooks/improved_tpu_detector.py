# Improved TPU detection and configuration
import torch

def improved_detect_and_configure_accelerator():
    """Detect and configure the available accelerator (CPU, GPU, or TPU) with enhanced error handling."""
    # First try TPU
    try:
        print("Checking for TPU availability...")
        import torch_xla.core.xla_model as xm
        try:
            # Try the new API first (for torch_xla 2.7+)
            try:
                import torch_xla.runtime as xr
                print("Using torch_xla.runtime API")
            except ImportError:
                print("torch_xla.runtime not available, using legacy API")
                
            device = xm.xla_device()
            use_tpu = True
            use_gpu = False
            print("TPU detected! Configuring for TPU training...")
            
            # Try getting cores with exception handling
            try:
                # Try new API first
                try:
                    cores = xr.world_size()
                    print(f"TPU cores available (via xr.world_size): {cores}")
                except (NameError, AttributeError):
                    # Fall back to deprecated method
                    try:
                        cores = xm.xrt_world_size()
                        print(f"TPU cores available (via xm.xrt_world_size): {cores}")
                    except Exception as core_err:
                        print(f"Error getting TPU core count: {core_err}")
                        print("Could not determine TPU core count, assuming 1.")
            except Exception as core_count_err:
                print(f"TPU core detection error: {core_count_err}")
                print("Proceeding with TPU but unknown core count.")
                
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

# Usage example:
# device, use_tpu, use_gpu = improved_detect_and_configure_accelerator()
