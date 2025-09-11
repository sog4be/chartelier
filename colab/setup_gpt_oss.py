#!/usr/bin/env python3
"""Setup script for GPT-OSS-20B on Google Colab with A100."""

import os
import subprocess
import sys
from pathlib import Path


def check_gpu():
    """Check if A100 GPU is available."""
    try:
        import torch

        if not torch.cuda.is_available():
            print("❌ No GPU detected. Please ensure GPU runtime is enabled in Colab.")
            print("   Runtime -> Change runtime type -> Hardware accelerator -> GPU (A100)")
            return False

        gpu_name = torch.cuda.get_device_name(0)
        gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)  # GB

        print(f"✅ GPU detected: {gpu_name}")
        print(f"   Memory: {gpu_memory:.1f} GB")

        if "A100" not in gpu_name:
            print("⚠️  Warning: Not an A100 GPU. GPT-OSS-20B may still work but performance may vary.")

        return True
    except ImportError:
        print("⚠️  PyTorch not installed. Proceeding with setup...")
        return True


def install_dependencies():
    """Install required dependencies for GPT-OSS-20B."""
    print("\n📦 Installing dependencies...")

    # Core dependencies
    dependencies = [
        "torch",  # PyTorch for GPU support
        "vllm==0.7.0",  # vLLM for serving (using stable version)
        "transformers>=4.40.0",  # For tokenizer
        "accelerate",  # For model loading
        "sentencepiece",  # For tokenization
        "protobuf",  # For model serialization
        "numpy<2.0",  # Compatibility
    ]

    for dep in dependencies:
        print(f"   Installing {dep}...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", dep],
            check=False,  # Continue even if some fail
        )

    # Install Chartelier dependencies
    print("\n📦 Installing Chartelier dependencies...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", "."],
        check=True,
    )

    print("✅ Dependencies installed")


def download_model():
    """Download GPT-OSS-20B model if not already cached."""
    print("\n📥 Preparing GPT-OSS-20B model...")
    print("   Note: Model will be downloaded on first use by vLLM (14GB)")
    print("   This may take several minutes on first run.")

    # Create cache directory
    cache_dir = Path.home() / ".cache" / "huggingface"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Check if model might already be cached
    model_cache = cache_dir / "hub"
    if model_cache.exists() and any(model_cache.iterdir()):
        print("   ℹ️  Hugging Face cache found. Model may already be downloaded.")

    return True


def setup_environment():
    """Set up environment variables for vLLM."""
    print("\n🔧 Configuring environment...")

    # vLLM optimizations for A100
    os.environ["CUDA_VISIBLE_DEVICES"] = "0"
    os.environ["VLLM_ATTENTION_BACKEND"] = "FLASHINFER"  # Use FlashAttention if available
    os.environ["TOKENIZERS_PARALLELISM"] = "false"  # Avoid tokenizer warnings

    # Create .env.colab for Chartelier
    env_content = """# Colab-specific environment for GPT-OSS-20B
CHARTELIER_LLM_MODEL=openai/gpt-oss-20b
CHARTELIER_LLM_API_BASE=http://localhost:8000/v1
CHARTELIER_LLM_API_KEY=dummy
CHARTELIER_LLM_TIMEOUT=30
CHARTELIER_LLM_MAX_RETRIES=3
"""

    with open(".env.colab", "w") as f:
        f.write(env_content)

    print("✅ Environment configured")
    print("   Created .env.colab with vLLM endpoint configuration")


def verify_installation():
    """Verify that all components are properly installed."""
    print("\n🔍 Verifying installation...")

    # Check vLLM
    try:
        import vllm

        print(f"   ✅ vLLM version: {vllm.__version__}")
    except ImportError:
        print("   ❌ vLLM not found")
        return False

    # Check transformers
    try:
        import transformers

        print(f"   ✅ Transformers version: {transformers.__version__}")
    except ImportError:
        print("   ❌ Transformers not found")
        return False

    # Check Chartelier
    try:
        import chartelier

        print("   ✅ Chartelier installed")
    except ImportError:
        print("   ❌ Chartelier not found")
        return False

    return True


def main():
    """Main setup function."""
    print("=" * 60)
    print("🚀 GPT-OSS-20B Setup for Google Colab")
    print("=" * 60)

    # Check if we're in the right directory
    if not Path("pyproject.toml").exists():
        print("❌ Error: Not in Chartelier root directory")
        print("   Please run this script from the Chartelier repository root")
        return 1

    # Step 1: Check GPU
    if not check_gpu():
        return 1

    # Step 2: Install dependencies
    try:
        install_dependencies()
    except Exception as e:
        print(f"❌ Failed to install dependencies: {e}")
        return 1

    # Step 3: Prepare model
    if not download_model():
        return 1

    # Step 4: Setup environment
    setup_environment()

    # Step 5: Verify
    if not verify_installation():
        print("\n⚠️  Some components may not be properly installed")
        print("   You can still try to proceed, but errors may occur")

    print("\n" + "=" * 60)
    print("✅ Setup complete!")
    print("\nNext steps:")
    print("1. Run the vLLM server:")
    print("   python colab/start_vllm_server.py")
    print("2. In another cell, run the test:")
    print("   python temp/test_e2e.py --env .env.colab")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
