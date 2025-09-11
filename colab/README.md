# Running Chartelier with GPT-OSS-20B on Google Colab

This directory contains scripts and notebooks for running Chartelier with OpenAI's GPT-OSS-20B model on Google Colab.

## Prerequisites

- Google Colab Pro+ account (for A100 GPU access)
- Basic familiarity with Jupyter notebooks

## Quick Start

1. **Open the notebook in Google Colab**:
   - Upload `run_gpt_oss_test.ipynb` to Google Colab
   - Or open it directly from GitHub after the PR is merged

2. **Enable GPU Runtime**:
   - Go to Runtime → Change runtime type
   - Select GPU: A100 (requires Pro+)
   - Click Save

3. **Run the notebook cells**:
   - Follow the step-by-step instructions in the notebook
   - The first run will download the GPT-OSS-20B model (~14GB)

## Files in this Directory

### `setup_gpt_oss.py`
Sets up the Colab environment with required dependencies:
- Installs vLLM for model serving
- Configures environment variables
- Verifies GPU availability

### `start_vllm_server.py`
Starts a vLLM server to serve GPT-OSS-20B:
- Configures optimal settings for A100
- Provides health check endpoints
- Handles model loading

### `run_gpt_oss_test.ipynb`
Main Jupyter notebook for running tests:
- Step-by-step guide for setup
- Example visualizations
- Troubleshooting tips

### Configuration

The setup creates a `.env.colab` file with:
```bash
CHARTELIER_LLM_MODEL=openai/gpt-oss-20b
CHARTELIER_LLM_API_BASE=http://localhost:8000/v1
CHARTELIER_LLM_API_KEY=dummy
CHARTELIER_LLM_TIMEOUT=30
```

## Architecture

```
Google Colab (A100 GPU)
    ├── vLLM Server (localhost:8000)
    │   └── GPT-OSS-20B Model
    └── Chartelier
        └── LiteLLM Client → vLLM API
```

## Performance

- **Model Size**: ~14GB (MXFP4 quantized)
- **Memory Usage**: Fits within 16GB VRAM
- **First Run**: 2-5 minutes (model download)
- **Subsequent Runs**: ~30 seconds startup
- **Inference Speed**: Faster than cloud APIs

## Advantages of GPT-OSS-20B

1. **No API Costs**: Run unlimited requests without per-token charges
2. **Low Latency**: Local inference eliminates network roundtrips
3. **Privacy**: Data never leaves the Colab environment
4. **Open Source**: Apache 2.0 licensed model

## Troubleshooting

### GPU Not Available
- Ensure you have Colab Pro+ subscription
- Check Runtime → Change runtime type → GPU

### Out of Memory
- The A100 40GB should be sufficient
- Try restarting the runtime if issues persist

### Model Download Slow
- First run downloads ~14GB
- Model is cached for future sessions

### Server Not Starting
- Check the server logs for specific errors
- Ensure no other process is using port 8000

## Alternative Deployment Options

While this guide focuses on Google Colab, GPT-OSS-20B can also run on:
- Local machines with 16GB+ VRAM GPUs
- Cloud providers (AWS, GCP, Azure)
- Dedicated ML platforms (Vast.ai, RunPod)

## Support

For issues specific to:
- **Chartelier**: Open an issue on the main repository
- **GPT-OSS-20B**: Refer to OpenAI's documentation
- **vLLM**: Check vLLM's documentation
- **Google Colab**: Consult Colab's help resources
