#!/usr/bin/env python3
"""
Memory Optimization Helper for Ollama in Google Colab
This script cleans up disk space and optimizes memory usage for running
large language models in Google Colab environments.
"""

import os
import shutil
import subprocess
import gc
import time
import psutil
from IPython.display import display, HTML, clear_output

def clear_disk_space():
    """Clean up disk space by removing unnecessary files."""
    print("🧹 Cleaning up disk space...")
    
    # Clean apt cache
    subprocess.run("apt-get clean", shell=True)
    
    # Remove unnecessary packages
    subprocess.run("apt-get -y autoremove", shell=True)
    
    # Clean pip cache
    subprocess.run("rm -rf ~/.cache/pip", shell=True)
    
    # Remove temporary files
    temp_dirs = ['/tmp', '/var/tmp']
    for temp_dir in temp_dirs:
        if os.path.exists(temp_dir):
            try:
                for item in os.listdir(temp_dir):
                    item_path = os.path.join(temp_dir, item)
                    # Skip our ollama directories
                    if item.startswith('ollama') or item.startswith('backdoor'):
                        continue
                    
                    try:
                        if os.path.isdir(item_path):
                            shutil.rmtree(item_path)
                        else:
                            os.remove(item_path)
                    except Exception as e:
                        pass  # Skip files that can't be removed
            except Exception as e:
                print(f"Warning: Could not clean {temp_dir}: {e}")
    
    # Remove unused Docker images/containers if Docker is installed
    try:
        subprocess.run("docker system prune -af", shell=True, stderr=subprocess.DEVNULL)
    except:
        pass
    
    print("✅ Disk cleanup complete!")
    
    # Show disk space
    show_disk_usage()

def show_disk_usage():
    """Show current disk usage."""
    try:
        df_output = subprocess.check_output("df -h /", shell=True, text=True)
        print("\n📊 Disk Space Available:")
        for line in df_output.split('\n'):
            print(line)
    except:
        print("Could not retrieve disk usage information")

def show_memory_usage():
    """Show current memory usage."""
    try:
        memory = psutil.virtual_memory()
        total_gb = memory.total / (1024 ** 3)
        available_gb = memory.available / (1024 ** 3)
        used_gb = memory.used / (1024 ** 3)
        percent = memory.percent
        
        print(f"\n📊 Memory Usage:")
        print(f"Total Memory: {total_gb:.2f} GB")
        print(f"Available: {available_gb:.2f} GB")
        print(f"Used: {used_gb:.2f} GB ({percent}%)")
    except:
        print("Could not retrieve memory usage information")

def clear_memory():
    """Clear Python memory."""
    gc.collect()
    torch_available = False
    
    try:
        import torch
        torch_available = True
    except ImportError:
        pass
    
    if torch_available:
        try:
            import torch
            torch.cuda.empty_cache()
            print("✅ PyTorch CUDA cache cleared")
        except:
            pass
    
    print("✅ Python memory cleared")

def optimize_for_large_models():
    """Optimize the environment for running large models."""
    print("🚀 Optimizing environment for large language models...")
    
    # Clear disk space
    clear_disk_space()
    
    # Clear memory
    clear_memory()
    
    # Set environment variables for improved performance
    os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:512"
    
    # Tell the user to restart the runtime if they continue to have memory issues
    print("\n💡 If you encounter 'Out of Memory' errors:")
    print("1. Try Runtime > Restart runtime")
    print("2. Consider using a smaller model")
    print("3. Make sure you've selected a high-RAM runtime")
    
    # Show current resource usage
    show_memory_usage()
    show_disk_usage()
    
    print("\n✅ Optimization complete! Ready to download and run models.")

def clean_model_files(keep_models=None):
    """Clean up model files to free space, optionally keeping specified models."""
    if keep_models is None:
        keep_models = []
    
    print(f"🧹 Cleaning model files (keeping: {', '.join(keep_models) if keep_models else 'none'})...")
    
    # Clean Ollama model files (except the ones specified to keep)
    ollama_dirs = ['/root/.ollama', '/tmp/ollama']
    
    for ollama_dir in ollama_dirs:
        if os.path.exists(ollama_dir):
            models_path = os.path.join(ollama_dir, 'models')
            if os.path.exists(models_path):
                for model_file in os.listdir(models_path):
                    should_keep = False
                    for keep_model in keep_models:
                        if keep_model in model_file:
                            should_keep = True
                            break
                    
                    if not should_keep:
                        try:
                            model_path = os.path.join(models_path, model_file)
                            if os.path.isdir(model_path):
                                shutil.rmtree(model_path)
                            else:
                                os.remove(model_path)
                            print(f"  - Removed: {model_file}")
                        except Exception as e:
                            print(f"  - Could not remove {model_file}: {e}")
    
    print("✅ Model cleanup complete!")
    show_disk_usage()

def display_optimization_options():
    """Display a user-friendly interface for optimization options."""
    display(HTML('''
    <div style="background-color:#f8f9fa; padding:15px; border-radius:5px; margin:10px 0; border:1px solid #ddd;">
        <h3 style="color:#0366d6;">Memory Optimization Options</h3>
        <p>Choose from the following optimization functions:</p>
        <ul>
            <li><code>clear_disk_space()</code> - Remove temporary files and clear package caches</li>
            <li><code>clear_memory()</code> - Free Python memory and CUDA cache if available</li>
            <li><code>optimize_for_large_models()</code> - Full optimization for large models</li>
            <li><code>clean_model_files(keep_models=['llama4'])</code> - Remove model files except those specified</li>
            <li><code>show_disk_usage()</code> - Show current disk space usage</li>
            <li><code>show_memory_usage()</code> - Show current memory usage</li>
        </ul>
        <p><strong>Example:</strong> <code>optimize_for_large_models()</code></p>
    </div>
    '''))

# Functions to monitor model download progress
def monitor_download_progress(model_name):
    """Monitor the download progress of a model."""
    last_size = 0
    download_dir = '/root/.ollama/models'
    
    print(f"🔄 Monitoring download progress for {model_name}")
    
    try:
        while True:
            if not os.path.exists(download_dir):
                time.sleep(1)
                continue
                
            total_size = 0
            for root, dirs, files in os.walk(download_dir):
                for file in files:
                    if model_name.lower() in file.lower():
                        try:
                            file_path = os.path.join(root, file)
                            total_size += os.path.getsize(file_path)
                        except:
                            pass
            
            if total_size > last_size:
                clear_output(wait=True)
                print(f"Downloading {model_name}...")
                print(f"Downloaded: {total_size / (1024**3):.2f} GB")
                last_size = total_size
            
            time.sleep(2)
    except KeyboardInterrupt:
        print("Download monitoring stopped")

# When imported, display the optimization options
if __name__ != "__main__":
    display_optimization_options()
