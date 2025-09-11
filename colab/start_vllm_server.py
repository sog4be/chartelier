#!/usr/bin/env python3
"""Start vLLM server for GPT-OSS-20B on Google Colab."""

import asyncio
import signal
import sys

import requests


def check_server_health(base_url="http://localhost:8000", timeout=5):
    """Check if vLLM server is healthy."""
    try:
        response = requests.get(f"{base_url}/health", timeout=timeout)
        return response.status_code == 200
    except requests.RequestException:
        return False


def check_model_loaded(base_url="http://localhost:8000", timeout=5):
    """Check if model is loaded in vLLM."""
    try:
        response = requests.get(f"{base_url}/v1/models", timeout=timeout)
        if response.status_code == 200:
            models = response.json().get("data", [])
            return len(models) > 0
        return False
    except requests.RequestException:
        return False


async def start_vllm_server():
    """Start vLLM server with GPT-OSS-20B."""
    print("=" * 60)
    print("🚀 Starting vLLM Server for GPT-OSS-20B")
    print("=" * 60)

    # Check if server is already running
    if check_server_health():
        print("ℹ️  vLLM server is already running")
        if check_model_loaded():
            print("✅ Model is loaded and ready")
            return 0
        print("⚠️  Server is running but model is not loaded")
        print("   Attempting to restart...")

    # Server configuration
    model_name = "openai/gpt-oss-20b"
    host = "0.0.0.0"
    port = 8000

    # vLLM arguments optimized for A100 and GPT-OSS-20B
    vllm_args = [
        "python",
        "-m",
        "vllm.entrypoints.openai.api_server",
        "--model",
        model_name,
        "--host",
        host,
        "--port",
        str(port),
        "--dtype",
        "auto",  # Let vLLM choose optimal dtype
        "--max-model-len",
        "8192",  # Reasonable context for testing
        "--gpu-memory-utilization",
        "0.9",  # Use most of A100's 40GB
        "--max-num-seqs",
        "8",  # Balance between throughput and latency
        "--disable-log-stats",  # Reduce log noise
        "--trust-remote-code",  # Required for some models
    ]

    # Add async scheduling if available (better performance)
    try:
        import vllm

        if hasattr(vllm, "__version__") and vllm.__version__ >= "0.5.0":
            vllm_args.append("--enable-prefix-caching")  # Cache common prefixes
    except ImportError:
        pass

    print("📊 Configuration:")
    print(f"   Model: {model_name}")
    print(f"   Endpoint: http://{host}:{port}")
    print("   Max context: 8192 tokens")
    print("   GPU utilization: 90%")
    print()
    print("⏳ Starting server (this may take 2-5 minutes on first run)...")
    print("   The model (14GB) will be downloaded if not cached")

    # Start the server process
    process = await asyncio.create_subprocess_exec(
        *vllm_args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # Wait for server to be ready
    max_wait = 300  # 5 minutes max
    check_interval = 5
    elapsed = 0

    print("\n⏳ Waiting for server to be ready...")
    while elapsed < max_wait:
        # Check if process has failed
        if process.returncode is not None:
            print(f"❌ Server process exited with code {process.returncode}")
            stderr = await process.stderr.read()
            print(f"Error output: {stderr.decode()}")
            return 1

        # Check health
        if check_server_health():
            print("✅ Server is responding")

            # Wait a bit more for model to load
            print("⏳ Waiting for model to load...")
            model_wait = 0
            while model_wait < 60:
                if check_model_loaded():
                    print("✅ Model is loaded and ready!")
                    break
                await asyncio.sleep(5)
                model_wait += 5
                print(f"   Still loading... ({model_wait}s)")

            if check_model_loaded():
                break
            print("⚠️  Server is up but model failed to load")
            return 1

        await asyncio.sleep(check_interval)
        elapsed += check_interval

        if elapsed % 30 == 0:
            print(f"   Still starting... ({elapsed}s elapsed)")

    if elapsed >= max_wait:
        print(f"❌ Server failed to start within {max_wait} seconds")
        process.terminate()
        await process.wait()
        return 1

    print("\n" + "=" * 60)
    print("✅ vLLM Server is ready!")
    print(f"   Endpoint: http://localhost:{port}/v1")
    print(f"   Model: {model_name}")
    print("\nYou can now run the test in another cell:")
    print("   python temp/test_e2e.py --env .env.colab")
    print("\nTo stop the server, interrupt this cell (Runtime -> Interrupt execution)")
    print("=" * 60)

    # Keep the server running
    try:
        # Wait for the process to complete (it won't unless terminated)
        await process.wait()
    except KeyboardInterrupt:
        print("\n⏹️  Shutting down server...")
        process.terminate()
        await process.wait()
        print("✅ Server stopped")

    return 0


def main():
    """Main entry point."""

    # Set up signal handling for graceful shutdown
    def signal_handler(signum, frame):
        print("\n⏹️  Received interrupt signal")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run the async server
    try:
        return asyncio.run(start_vllm_server())
    except KeyboardInterrupt:
        print("\n✅ Server stopped by user")
        return 0


if __name__ == "__main__":
    sys.exit(main())
