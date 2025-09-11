#!/usr/bin/env python3
"""Simplified setup script for GPT-OSS-20B on Google Colab."""

import subprocess
import sys


def main():
    """Simple setup for vLLM and GPT-OSS-20B."""
    print("=" * 60)
    print("🚀 Simple vLLM Setup for Google Colab")
    print("=" * 60)

    # Check GPU
    try:
        import torch

        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            print(f"✅ GPU: {gpu_name}")
        else:
            print("❌ No GPU detected")
            return 1
    except ImportError:
        print("⚠️  PyTorch not installed, installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "torch"], check=False)

    print("\n📦 Installing vLLM and dependencies...")

    # Install in specific order to avoid conflicts
    commands = [
        # Fix numpy version first
        "pip install -q 'numpy<2.0'",
        # Install vLLM dependencies
        "pip install -q fastapi uvicorn ray",
        # Install vLLM
        "pip install -q vllm",
        # Install additional dependencies
        "pip install -q transformers accelerate sentencepiece",
        # Install Chartelier (if in the repo)
        "pip install -q -e . || echo 'Chartelier not found, skipping'",
    ]

    for i, cmd in enumerate(commands, 1):
        print(f"   Step {i}/{len(commands)}: {cmd.split()[2] if len(cmd.split()) > 2 else 'Processing'}...")
        subprocess.run(cmd, check=False, shell=True, capture_output=True)

    # Verify vLLM installation
    print("\n🔍 Verifying installation...")
    try:
        import vllm

        print(f"✅ vLLM {vllm.__version__} installed successfully!")
    except ImportError:
        print("❌ vLLM installation failed")
        print("\nTry running manually:")
        print("  !pip install vllm")
        return 1

    # Create simple environment file
    print("\n📝 Creating environment configuration...")
    env_content = """CHARTELIER_LLM_MODEL=openai/gpt-oss-20b
CHARTELIER_LLM_API_BASE=http://localhost:8000/v1
CHARTELIER_LLM_API_KEY=dummy
CHARTELIER_LLM_TIMEOUT=30"""

    with open(".env.colab", "w") as f:
        f.write(env_content)

    print("✅ Environment configured")

    print("\n" + "=" * 60)
    print("✅ Setup complete!")
    print("\nNext steps:")
    print("1. Start vLLM server:")
    print("   python colab/start_vllm_server.py")
    print("2. Test the setup:")
    print("   python temp/test_e2e.py --env .env.colab")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
