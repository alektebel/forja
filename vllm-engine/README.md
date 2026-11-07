# vLLM Engine from Scratch

A from-scratch implementation of a vLLM-style inference serving system. Learn how modern LLM serving engines achieve high throughput with PagedAttention, continuous batching, and efficient memory management.

## Goal

Build a deep understanding of LLM serving systems by implementing:
- **PagedAttention**: Virtual memory-inspired KV cache management
- **Continuous batching**: Dynamic request scheduling and batching
- **Tensor parallelism**: Distribute models across multiple GPUs
- **Quantization**: Support for GPTQ, AWQ, SqueezeLLM
- **Serving optimizations**: Prefix caching, chunked prefill, speculative decoding
- **Production features**: Request routing, resource management, monitoring

## What is vLLM?

vLLM is a high-throughput LLM serving engine that:
- Uses PagedAttention for efficient KV cache management (up to 24x higher throughput)
- Implements continuous batching for optimal GPU utilization
- Supports various quantization methods for memory efficiency
- Provides OpenAI-compatible API
- Scales to multiple GPUs with tensor parallelism

Key innovation: **PagedAttention** - Manage KV cache like virtual memory with paging

## Project Structure

```
vllm-engine/
├── README.md                          # This file
├── IMPLEMENTATION_GUIDE.md            # Detailed implementation guide
├── core/
│   ├── engine.py                     # Main engine orchestration
│   ├── scheduler.py                  # Request scheduler
│   ├── executor.py                   # Model executor
│   └── worker.py                     # GPU worker process
├── attention/
│   ├── paged_attention.py            # PagedAttention implementation
│   ├── paged_attention_kernel.cu     # CUDA kernel for paging
│   ├── block_manager.py              # KV cache block management
│   └── attention_backend.py          # Attention backend interface
├── batching/
│   ├── continuous_batch.py           # Continuous batching scheduler
│   ├── sequence.py                   # Sequence state management
│   ├── sequence_group.py             # Request grouping
│   └── scheduler_config.py           # Scheduling policies
├── memory/
│   ├── block_allocator.py            # Memory block allocator
│   ├── cache_engine.py               # KV cache engine
│   ├── memory_pool.py                # GPU memory pool
│   └── prefix_cache.py               # Automatic prefix caching
├── parallelism/
│   ├── tensor_parallel.py            # Tensor parallelism
│   ├── pipeline_parallel.py          # Pipeline parallelism (optional)
│   ├── distributed.py                # Multi-GPU coordination
│   └── communication.py              # GPU-GPU communication
├── quantization/
│   ├── gptq.py                       # GPTQ quantization
│   ├── awq.py                        # AWQ quantization
│   ├── squeezellm.py                 # SqueezeLLM quantization
│   └── kernels/                      # Quantized GEMM kernels
├── models/
│   ├── llama.py                      # LLaMA model implementation
│   ├── gpt.py                        # GPT model implementation
│   ├── mistral.py                    # Mistral model implementation
│   └── model_registry.py             # Model registration
├── sampling/
│   ├── sampler.py                    # Token sampling
│   ├── logits_processor.py           # Logits processing
│   └── stopping_criteria.py          # Stopping conditions
├── optimization/
│   ├── chunked_prefill.py            # Chunked prefill optimization
│   ├── speculative_decoding.py       # Speculative decoding
│   ├── prefix_cache.py               # Prefix caching
│   └── kernel_fusion.py              # Kernel fusion
├── serving/
│   ├── api_server.py                 # FastAPI server
│   ├── openai_protocol.py            # OpenAI-compatible API
│   ├── request_handler.py            # Request handling
│   └── metrics.py                    # Metrics collection
├── tests/
│   ├── test_paged_attention.py
│   ├── test_scheduler.py
│   ├── test_quantization.py
│   └── benchmarks/
│       ├── throughput.py
│       ├── latency.py
│       ├── memory_usage.py
│       └── end_to_end.py
└── solutions/                        # Complete reference implementations
    ├── README.md
    └── ...
```

## Learning Path

### Phase 1: Core PagedAttention (15-18 hours)

**1.1 Understand the Problem**

Traditional KV cache management issues:
- Memory fragmentation
- Pre-allocated fixed-size caches
- Cannot share KV cache between sequences
- Difficult to handle variable-length sequences

PagedAttention solution:
- Block-based memory management
- On-demand allocation
- Sharing via copy-on-write
- Flexible sequence lengths

**1.2 Block Management**

Implement KV cache block management:
- Fixed-size memory blocks (e.g., 16 tokens per block)
- Block allocation and deallocation
- Logical-to-physical block mapping
- Free block tracking

**Implementation tasks**:
- Create `Block` and `BlockTable` classes
- Implement `BlockAllocator`
- Add reference counting for sharing
- Test with various sequence lengths

**1.3 PagedAttention Kernel**

Build the core attention CUDA kernel:
- Block-based attention computation
- Gather KV from non-contiguous blocks
- Efficient memory access patterns
- Support for multi-head attention

**Implementation tasks**:
- Write CUDA kernel for paged attention
- Implement block gathering logic
- Optimize memory access
- Test correctness against standard attention

**1.4 Attention Manager**

Integrate paging into attention layer:
- Manage block tables per sequence
- Coordinate with memory allocator
- Handle sequence prefill vs. decode
- Support variable sequence lengths

**Implementation tasks**:
- Create `CacheEngine` class
- Integrate with attention layers
- Add block table management
- Test memory usage improvements

**Skills learned**:
- Virtual memory concepts applied to ML
- CUDA kernel programming
- Memory management strategies
- Attention mechanism optimization

---

### Phase 2: Continuous Batching (12-15 hours)

**2.1 Sequence State Management**

Track sequence generation state:
- Sequence ID and metadata
- Generated tokens
- Sampling parameters
- Completion status

**Implementation tasks**:
- Create `Sequence` class
- Add token tracking
- Implement state updates
- Handle sequence completion

**2.2 Request Scheduler**

Build dynamic batching scheduler:
- New request queuing
- Running sequence management
- Preemption for fairness
- Priority scheduling

**Implementation tasks**:
- Implement `Scheduler` class
- Add request queuing
- Implement scheduling policies (FCFS, priority)
- Add preemption logic

**2.3 Continuous Batching Algorithm**

Core batching algorithm:
- Add new sequences to running batch
- Remove completed sequences
- Handle variable decode lengths
- Maximize GPU utilization

**Implementation tasks**:
- Implement continuous batching loop
- Add sequence addition/removal
- Handle padding efficiently
- Optimize for throughput

**2.4 Swapping and Preemption**

Handle memory overflow:
- Swap sequences to CPU memory
- Preempt low-priority sequences
- Implement swapping heuristics
- Restore swapped sequences

**Implementation tasks**:
- Add swap-out/swap-in logic
- Implement preemption policy
- Track swapped sequences
- Test under memory pressure

**Skills learned**:
- Dynamic batching strategies
- Request scheduling algorithms
- Resource management
- System-level optimization

---

### Phase 3: Model Parallelism (12-15 hours)

**3.1 Tensor Parallelism**

Distribute model across GPUs:
- Column-parallel linear layers
- Row-parallel linear layers
- Attention head parallelism
- All-reduce for aggregation

**Implementation tasks**:
- Implement tensor parallel layers
- Add NCCL communication
- Partition model weights
- Test multi-GPU correctness

**3.2 Model Executor**

Coordinate distributed execution:
- Worker process management
- Weight distribution
- Forward pass coordination
- Gradient-free inference optimization

**Implementation tasks**:
- Create `Executor` class
- Implement worker pool
- Add weight broadcasting
- Coordinate forward passes

**3.3 Communication Optimization**

Optimize GPU-GPU communication:
- Overlapping compute and communication
- Pipeline communication
- Reduce synchronization points
- Optimize NCCL collectives

**Implementation tasks**:
- Profile communication overhead
- Implement async communication
- Add computation/communication overlap
- Measure scalability

**Skills learned**:
- Distributed systems for ML
- GPU-GPU communication
- Parallel algorithm design
- Scalability optimization

---

### Phase 4: Quantization Support (10-12 hours)

**4.1 GPTQ Quantization**

Implement GPTQ inference:
- Weight-only quantization
- Group-wise quantization
- Custom CUDA kernels for quantized GEMM
- Activation quantization

**Implementation tasks**:
- Implement GPTQ weight loading
- Write quantized GEMM kernel
- Add activation quantization
- Test accuracy vs. FP16

**4.2 AWQ Quantization**

Add AWQ support:
- Activation-aware quantization
- Per-channel scaling
- Zero-point quantization
- Optimized kernel implementations

**Implementation tasks**:
- Implement AWQ weight format
- Create AWQ GEMM kernels
- Add per-channel scaling
- Benchmark performance

**4.3 SqueezeLLM**

Implement sparse quantization:
- Sparse weight representation
- Non-uniform quantization
- Sparse GEMM kernels
- Memory-efficient storage

**Implementation tasks**:
- Implement sparse weight loading
- Create sparse GEMM kernel
- Add non-uniform quantization
- Compare with dense methods

**Skills learned**:
- Quantization techniques
- Custom CUDA kernels
- Sparse operations
- Memory-compute tradeoffs

---

### Phase 5: Advanced Optimizations (12-15 hours)

**5.1 Chunked Prefill**

Optimize long prompt processing:
- Split prefill into chunks
- Interleave prefill and decode
- Balance latency and throughput
- Prevent decode starvation

**Implementation tasks**:
- Implement chunked prefill
- Add chunk size tuning
- Balance prefill/decode ratio
- Test with long prompts

**5.2 Automatic Prefix Caching**

Reuse common prompt prefixes:
- Detect common prefixes
- Share KV cache blocks
- Implement copy-on-write
- Measure cache hit rates

**Implementation tasks**:
- Add prefix matching
- Implement block sharing
- Add copy-on-write logic
- Test with shared prompts

**5.3 Speculative Decoding**

Speed up with draft model:
- Small draft model generation
- Parallel verification
- Tree attention for multiple candidates
- Adaptive speculation

**Implementation tasks**:
- Integrate draft model
- Implement parallel verification
- Add tree attention
- Benchmark speedup

**5.4 Kernel Fusion**

Reduce kernel launch overhead:
- Fuse attention operations
- Combine elementwise operations
- Flash attention integration
- Custom fused kernels

**Implementation tasks**:
- Implement fused kernels
- Add FlashAttention
- Profile kernel overhead
- Measure improvement

**Skills learned**:
- Advanced optimization techniques
- Cache-aware algorithms
- Kernel fusion strategies
- Performance engineering

---

### Phase 6: Production Serving (10-12 hours)

**6.1 API Server**

Build FastAPI-based server:
- OpenAI-compatible endpoints
- Streaming responses
- Request validation
- Error handling

**Implementation tasks**:
- Create FastAPI server
- Implement /v1/completions
- Add streaming support
- Handle errors gracefully

**6.2 Request Processing**

Handle concurrent requests:
- Request queuing
- Load balancing
- Request cancellation
- Timeout management

**Implementation tasks**:
- Implement request queue
- Add cancellation support
- Handle timeouts
- Load balance across workers

**6.3 Monitoring and Metrics**

Add observability:
- Request latency (TTFT, TPOT)
- Throughput metrics
- GPU utilization
- KV cache usage

**Implementation tasks**:
- Collect metrics
- Add Prometheus exporter
- Create monitoring dashboard
- Set up alerts

**6.4 Resource Management**

Optimize resource usage:
- Adaptive batching
- Memory limit enforcement
- GPU memory monitoring
- Request admission control

**Implementation tasks**:
- Implement admission control
- Add memory monitoring
- Tune batch sizes dynamically
- Handle OOM gracefully

**Skills learned**:
- Production serving systems
- API design
- Monitoring and observability
- Resource management

---

**Total Time**: ~70-85 hours for complete implementation

## Features to Implement

### Core Features
- [x] PagedAttention (block-based KV cache)
- [x] Continuous batching
- [x] Tensor parallelism
- [x] Multiple quantization methods
- [x] OpenAI-compatible API

### Optimizations
- [x] Chunked prefill
- [x] Automatic prefix caching
- [x] Speculative decoding
- [x] Kernel fusion
- [x] FlashAttention integration

### Production Features
- [x] Request scheduling
- [x] Memory management
- [x] Monitoring and metrics
- [x] Multi-model serving
- [x] Load balancing

## Testing Your Implementation

### Unit Tests

Test individual components:
```bash
# Test PagedAttention
python -m pytest tests/test_paged_attention.py -v

# Test scheduler
python -m pytest tests/test_scheduler.py -v

# Test quantization
python -m pytest tests/test_quantization.py -v

# Test parallelism
python -m pytest tests/test_tensor_parallel.py -v
```

### Integration Tests

Test complete workflows:
```bash
# Test single sequence generation
python tests/integration/test_generation.py

# Test continuous batching
python tests/integration/test_batching.py

# Test multi-GPU
python tests/integration/test_distributed.py
```

### Benchmarks

Measure performance:
```bash
# Throughput benchmark
python tests/benchmarks/throughput.py \
    --model llama-7b \
    --input-len 128 \
    --output-len 256 \
    --batch-size 32

# Latency benchmark
python tests/benchmarks/latency.py \
    --model llama-7b \
    --percentiles 50,90,99

# Memory usage
python tests/benchmarks/memory_usage.py \
    --model llama-7b \
    --compare-with-baseline

# End-to-end serving
python tests/benchmarks/end_to_end.py \
    --concurrent-requests 100 \
    --duration 300
```

## Example Usage

### Basic Generation

```python
from vllm_engine import Engine, SamplingParams

# Initialize engine
engine = Engine(model="llama-7b", tensor_parallel_size=1)

# Create sampling parameters
sampling_params = SamplingParams(
    temperature=0.8,
    top_p=0.95,
    max_tokens=256
)

# Generate
prompts = ["Once upon a time", "The meaning of life is"]
outputs = engine.generate(prompts, sampling_params)

for output in outputs:
    print(output.text)
```

### Multi-GPU Serving

```python
# Initialize with tensor parallelism
engine = Engine(
    model="llama-70b",
    tensor_parallel_size=4,  # 4 GPUs
    max_num_seqs=256,
    max_num_batched_tokens=8192
)

# Serve requests
async def serve_request(prompt):
    output = await engine.generate_async(prompt, sampling_params)
    return output.text
```

### With Quantization

```python
# Use GPTQ quantization
engine = Engine(
    model="llama-7b",
    quantization="gptq",
    dtype="float16",
    max_model_len=4096
)

# Generate with quantized model
output = engine.generate(prompt, sampling_params)
```

### OpenAI-Compatible API

```python
from vllm_engine.serving import create_api_server

# Create API server
app = create_api_server(
    model="llama-7b",
    tensor_parallel_size=2
)

# Start server
import uvicorn
uvicorn.run(app, host="0.0.0.0", port=8000)
```

```bash
# Use with OpenAI client
curl http://localhost:8000/v1/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "llama-7b",
        "prompt": "Once upon a time",
        "max_tokens": 256,
        "temperature": 0.8
    }'
```

## Performance Goals

Your implementation should achieve:

### Throughput (vs. HuggingFace Transformers)
- ✅ 10-24x higher throughput with PagedAttention
- ✅ >2000 tokens/sec for LLaMA-7B (A100)
- ✅ >500 tokens/sec for LLaMA-70B (4xA100)
- ✅ Continuous batching: 2-3x improvement

### Latency
- ✅ TTFT (Time To First Token): <100ms
- ✅ TPOT (Time Per Output Token): <20ms
- ✅ P99 latency: <500ms

### Memory Efficiency
- ✅ 3-5x more sequences in memory vs. traditional
- ✅ <5% memory fragmentation
- ✅ 80%+ KV cache utilization
- ✅ GPTQ/AWQ: 3-4x memory reduction

### Scalability
- ✅ Linear scaling to 8 GPUs
- ✅ Handle 100+ concurrent requests
- ✅ Support sequences up to 32K tokens
- ✅ >90% GPU utilization

## Resources

### Papers
- **vLLM**: "Efficient Memory Management for Large Language Model Serving with PagedAttention" (2023)
- **FlashAttention**: "FlashAttention: Fast and Memory-Efficient Exact Attention" (2022)
- **Continuous Batching**: "Orca: A Distributed Serving System for Transformer-Based Generative Models" (2022)
- **GPTQ**: "GPTQ: Accurate Post-Training Quantization for GPT" (2022)
- **AWQ**: "AWQ: Activation-aware Weight Quantization for LLM Compression" (2023)
- **Speculative Decoding**: "Fast Inference from Transformers via Speculative Decoding" (2023)

### Official Documentation
- [vLLM Documentation](https://docs.vllm.ai/)
- [vLLM GitHub](https://github.com/vllm-project/vllm)
- [FlashAttention](https://github.com/Dao-AILab/flash-attention)
- [NCCL Documentation](https://docs.nvidia.com/deeplearning/nccl/)

### The Hardware Beneath
- [Modal's GPU Glossary](https://modal.com/gpu-glossary/readme/) — PagedAttention's
  block tables and FlashAttention's SRAM tiling both argue about one resource: GPU RAM
  and the memory hierarchy it sits in. The glossary's Device Hardware pages (HBM,
  L2, shared memory) and Performance pages (memory bandwidth, arithmetic intensity,
  the roofline model) are the ground truth the policies in this course schedule against.

### Related Projects
- [vLLM](https://github.com/vllm-project/vllm) - Original vLLM
- [TensorRT-LLM](https://github.com/NVIDIA/TensorRT-LLM) - NVIDIA's LLM engine
- [Text Generation Inference](https://github.com/huggingface/text-generation-inference) - HuggingFace serving
- [Triton Inference Server](https://github.com/triton-inference-server) - NVIDIA Triton

### Books & Courses
- "Designing Data-Intensive Applications" by Martin Kleppmann
- "High Performance Python" by Micha Gorelick

### Video Courses
- [Deep Learning Courses](https://github.com/Developer-Y/cs-video-courses#deep-learning)
- [Generative AI and LLMs](https://github.com/Developer-Y/cs-video-courses#generative-ai-and-llms)
- [Natural Language Processing](https://github.com/Developer-Y/cs-video-courses#natural-language-processing)
- [Systems Programming](https://github.com/Developer-Y/cs-video-courses#systems-programming)
- GPU programming courses
- Distributed systems courses

## Common Pitfalls

1. **Memory leaks**: Always deallocate blocks when sequences complete
2. **Fragmentation**: Use appropriate block sizes (16-64 tokens)
3. **Scheduling fairness**: Balance TTFT and throughput
4. **Communication overhead**: Overlap computation and communication
5. **Quantization errors**: Validate accuracy after quantization
6. **OOM handling**: Implement proper memory limits and admission control

## Debug Tips

### PagedAttention Debugging

```python
# Visualize block allocation
def visualize_blocks(block_table):
    print("Block Table:")
    for seq_id, blocks in block_table.items():
        print(f"Seq {seq_id}: {[b.id for b in blocks]}")

# Check memory fragmentation
def check_fragmentation(allocator):
    total_blocks = allocator.total_blocks
    free_blocks = len(allocator.free_blocks)
    fragmentation = 1 - (free_blocks / total_blocks)
    print(f"Fragmentation: {fragmentation:.2%}")
```

### Scheduler Debugging

```python
# Log scheduling decisions
def log_schedule(scheduler):
    print(f"Running: {len(scheduler.running)}")
    print(f"Waiting: {len(scheduler.waiting)}")
    print(f"Swapped: {len(scheduler.swapped)}")
    
# Profile batch formation
def profile_batching(scheduler):
    import time
    start = time.time()
    batch = scheduler.schedule()
    duration = time.time() - start
    print(f"Batch size: {len(batch)}, Time: {duration*1000:.2f}ms")
```

### Performance Profiling

```bash
# Profile CUDA kernels
nsys profile -o profile python inference.py

# Check GPU utilization
nvidia-smi dmon -s pucvmet -d 1

# Profile memory usage
python -m memory_profiler inference.py

# Check communication overhead
ncu --metrics nccl_* python distributed_inference.py
```

## Advanced Topics

After completing the core implementation, explore:

### Advanced Features
- Pipeline parallelism for very large models
- Mixture of Experts (MoE) serving
- Multi-model serving on same GPUs
- Dynamic model loading/unloading
- Request prioritization and SLO enforcement

### Advanced Optimizations
- Multi-query attention (MQA)
- Grouped-query attention (GQA)
- Flash-decoding for long context
- Prompt compression techniques
- Lossless attention approximation

### Production Enhancements
- Kubernetes deployment
- Auto-scaling based on load
- Model versioning and A/B testing
- Distributed tracing
- Cost optimization

## Contributing

This is a learning project focused on understanding LLM serving systems. Areas for exploration:
- Novel memory management strategies
- Better scheduling algorithms
- More quantization methods
- Performance optimizations

## License

Educational purposes. Use freely for learning.

## Acknowledgments

Inspired by:
- vLLM's PagedAttention innovation
- TensorRT-LLM's optimization techniques
- HuggingFace TGI's serving architecture
- Flash Attention's memory efficiency
- Distributed systems literature
