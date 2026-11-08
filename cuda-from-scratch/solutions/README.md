# CUDA Solutions

This directory contains complete, working implementations of all CUDA examples.

## Purpose

These solutions serve as:
1. **Reference implementations** - Check your work against these
2. **Learning resources** - Study the patterns and techniques used
3. **Debugging aids** - Compare when stuck or getting unexpected results

## Philosophy

**Try implementing yourself first!** The solutions are here to help you learn, not to skip the learning process. Use them:
- ✅ After attempting the implementation yourself
- ✅ When stuck on a specific part
- ✅ To verify your approach
- ✅ To learn optimization techniques

Don't:
- ❌ Copy-paste without understanding
- ❌ Skip the template implementation
- ❌ Use as your first attempt

## Solutions Status

All eight solutions are complete and were compiled and run on an NVIDIA
RTX 5060 Laptop GPU (sm_120) with CUDA 13.5 (conda nvcc at
`/home/diego/miniforge3/bin/nvcc`). Every program exits 0 and prints its
verification line.

| # | File | Content | Verified run (default) | Ragged-size check |
|---|------|---------|------------------------|-------------------|
| 01 | `01_vector_addition.cu` | 1D kernel, alloc/copy/launch/free, cudaEvent timing in main | `N=1000000` → PASSED | `N=1000003` (not a multiple of 256) → PASSED |
| 02 | `02_matrix_addition.cu` | 2D `dim3` grid, row-major indexing, timing + bandwidth | `1024x1024` → PASSED | `331x977` (non-square, ragged in both dims) → PASSED |
| 03 | `03_matrix_multiplication.cu` | Naive vs shared-memory tiled GEMM | `1024^3` → Results match: YES | `M=321 N=129 K=257` (all non-multiples of TILE_SIZE=16) → match YES |
| 04 | `04_reduction.cu` | Tree reduction in shared memory + true multi-pass host loop | `N=1000000` → PASSED (sum exact) | `N=1000003`, `999999`, `65537`, `262144`, `7` → PASSED |
| 05 | `05_convolution.cu` | Gaussian 5x5, Sobel magnitude, sharpen + generic `__constant__` filter; all tiled with halos | `512x512` → all 4 filters OK, PASSED | `101x37` image (ragged in both dims) → PASSED |
| 06 | `06_neural_network_forward.cu` | FC forward (grid-stride), ReLU/Sigmoid/Tanh, 784→128→64→10 pipeline | `batch 32` → vs-CPU max diff 9.3e-10, PASSED | `batch 33` → PASSED |
| 07 | `07_neural_network_backward.cu` | FC backward (gradInput/gradWeights/gradBias), ReLU backward, SGD, numerical gradient check | `13x7x5` → analytical + numerical grad checks PASSED | `batch 33, 11x17 layer`, and `1x1x1` → PASSED |
| 08 | `08_complete_neural_network.cu` | Full MNIST training: softmax, cross-entropy, backward, SGD, eval | 20 epochs, batch 100, lr 0.1 → **97.89%** test accuracy, PASSED | `batch 101` (60000/101 leaves a 6-sample final batch; 10000/101 leaves a 1-sample eval chunk) → PASSED |

## Building and Running (verified on this machine)

**The Makefile's default `ARCH=sm_60` is refused by nvcc 13.5**:

```text
$ make 01_vector_addition NVCC=/home/diego/miniforge3/bin/nvcc
nvcc fatal   : Unsupported gpu architecture 'sm_60'
```

Maxwell/Pascal/Volta targets were deprecated in newer CUDA toolkits, so on
this machine you must pass an `sm_120` override. Working invocations (both
verified):

```bash
# Explicit compile (what every solution was built with):
/home/diego/miniforge3/bin/nvcc -arch=sm_120 -O2 04_reduction.cu -o 04
./04            # runs on the GPU; add LD_LIBRARY_PATH=/home/diego/miniforge3/lib
                # only if your shell can't find libcudart (conda env active = fine)

# Or via the Makefile:
make ARCH=sm_120 NVCC=/home/diego/miniforge3/bin/nvcc 01_vector_addition
```

Host gcc 16.2.1 is accepted by nvcc 13.5 as-is — no `-allow-unsupported-compiler`
was needed.

Solution 08 expects the four MNIST IDX files in a data directory (default
`data/`); point it at yours:

```bash
/home/diego/miniforge3/bin/nvcc -arch=sm_120 -O2 08_complete_neural_network.cu -o 08
./08 ~/mnist 20 100 0.1    # dataDir epochs batch lr
```

## Measured Output (actual, pasted from runs on RTX 5060 Laptop, sm_120)

```text
$ ./01_vector_addition
Vector Addition: N = 1000000 elements
Kernel execution time: 3.857 ms
✓ Verification PASSED

$ ./02_matrix_addition
Matrix Addition: 1024 x 1024
Grid: (64, 64) blocks, Block: (16, 16) threads
Kernel execution time: 3.346 ms
✓ Verification PASSED

$ ./03_matrix_multiplication        # warm run (first cold run shows clock ramp)
Naive kernel time: 4.342 ms
Tiled kernel time: 3.648 ms
Speedup: 1.19x
Results match: YES

$ ./04_reduction
Parallel Reduction: N = 1000000 elements
GPU sum: 1000000.00
CPU sum: 1000000.00
Match: YES
✓ Verification PASSED

$ ./05_convolution                  # 512x512
Kernel times: gaussian 0.232 ms, sobel 0.110 ms, sharpen 0.109 ms, generic 0.018 ms
Gaussian blur: OK / Sobel edges: OK / Sharpening: OK / Generic conv (constant filter): OK
✓ Verification PASSED

$ ./06_neural_network_forward       # batch 32
Forward pass (batch 32): 0.193 ms
Max abs diff vs CPU: 9.313e-10
✓ Verification PASSED

$ ./07_neural_network_backward
Backward kernel time: 0.332 ms
gradInput   max diff vs CPU: 1.863e-09
gradWeights max diff vs CPU: 1.490e-08
gradBias    max diff vs CPU: 1.490e-08
Numerical gradient check: worst relative error 1.415e-05 (expect < 1e-3)
SGD update max diff vs CPU: 7.451e-09
✓ Verification PASSED

$ ./08 ~/mnist 20 100 0.1
Epoch  1:  Loss=0.4038, Accuracy=93.38%  (0.2 s)
Epoch  2:  Loss=0.1923, Accuracy=95.37%  (0.2 s)
Epoch  5:  Loss=0.0924, Accuracy=97.08%  (0.2 s)
Epoch 10:  Loss=0.0450, Accuracy=97.58%  (0.2 s)
Epoch 15:  Loss=0.0246, Accuracy=97.70%  (0.2 s)
Epoch 20:  Loss=0.0126, Accuracy=97.89%  (0.2 s)
Final Test Accuracy: 97.89%  (total training wall time 3.6 s)
✓ Verification PASSED
```

Timing notes:
- 01/02/06 wrap the whole host function in events, so the printed time
  includes `cudaMalloc`/`cudaMemcpy`; first run of the process also pays
  context init (hence ~4 ms at 1M floats, then ~2 ms on repeats).
- 03 on a cold/idle GPU reported `Tiled 13.031 ms` on the very first run
  (SM clock ramping from idle); warm runs show the tiled kernel faster.
  At 1024^3 both kernels are already near memory/compute-balanced on this
  GPU, so the classic 5-10x tile speedup does not reproduce; at ragged
  321x129x257 the tiled kernel is ~1.8x faster.
- 05 kernel times are pure launch-to-launch event windows.
- 04's follow-up multi-pass uses ping-pong buffers; the template's single
  second-pass launch cannot reduce more than 256 block partials and sums
  wrong (observed 69376.00 for N=1000000 before the fix).
- The numerical gradient check in 07 must accumulate the MSE loss in
  `double`; in float the `(lp - lm)` cancellation leaves ~2% relative
  error even with a correct analytic gradient.
- 08's final accuracy varies by ~0.01% run to run (97.89%/97.90%) because
  gradBias/loss accumulate via `atomicAdd` in nondeterministic order;
  every run converges to >97% for 20 epochs.

## Solution Structure

Each solution follows this pattern:

```cpp
// 1. Error checking macro
#define CUDA_CHECK(call) { ... }

// 2. CUDA kernel(s)
__global__ void kernel(...) {
    // Optimized implementation
}

// 3. Host function(s)
void hostFunction(...) {
    // Memory management
    // Kernel launch
    // Error checking
}

// 4. Main function with testing
int main() {
    // Input preparation
    // Kernel execution
    // Verification
    // Performance measurement
}
```

## Performance Notes

### Expected Performance (on modern GPU like RTX 3080):

**Example 1 - Vector Addition (10M elements)**:
- Time: ~1-2 ms
- Bandwidth: ~200-400 GB/s

**Example 2 - Matrix Addition (2048x2048)**:
- Time: ~0.5-1 ms
- Bandwidth: ~300-500 GB/s

**Example 3 - Matrix Multiplication (1024x1024)**:
- Naive: ~50-100 ms
- Tiled: ~5-15 ms
- Speedup: 5-10x

**Example 4 - Reduction (10M elements)**:
- Time: ~0.5-1 ms
- Much faster than sequential CPU

**Example 5 - Convolution (1024x1024, 11x11 filter)**:
- Naive: ~10-20 ms
- Optimized: ~2-5 ms

**Example 8 - Neural Network Training (MNIST)**:
- Time per epoch: ~2-5 seconds
- 20 epochs: ~1-2 minutes
- Final accuracy: 96-97%

## Optimization Techniques Used

### Memory Optimizations
1. **Coalesced memory access** - Consecutive threads access consecutive memory
2. **Shared memory** - Reduce global memory bandwidth
3. **Constant memory** - For read-only data (filters, etc.)
4. **Pinned memory** - Faster host-device transfers

### Execution Optimizations
1. **Proper grid/block dimensions** - Maximize occupancy
2. **Avoiding divergence** - Keep threads in a warp on same path
3. **Bank conflict avoidance** - Shared memory access patterns
4. **Register optimization** - Balance register use and occupancy

### Algorithmic Optimizations
1. **Tiling** - Data reuse through shared memory
2. **Loop unrolling** - Reduce loop overhead
3. **Warp-level primitives** - Use warp shuffle for reduction
4. **Multi-pass algorithms** - Handle large data sizes

## Comparing with Your Implementation

When comparing your implementation with the solution:

### 1. Correctness
```bash
# Run both and compare output
./your_implementation 1000
./solutions/solution 1000

# Check numerical accuracy
# Small differences (< 1e-5) are acceptable due to floating-point
```

### 2. Performance
```bash
# Profile both
nvprof ./your_implementation
nvprof ./solutions/solution

# Compare metrics:
# - Kernel execution time
# - Memory throughput
# - Occupancy
```

### 3. Code Quality
- Is your code readable?
- Are error checks present?
- Are memory leaks avoided?
- Is the algorithm correct?

## Common Differences

Your implementation may differ from solutions in:

✅ **Acceptable differences**:
- Variable names
- Code organization
- Comments style
- Block/grid sizes (if both are reasonable)
- Minor performance variations

❌ **Important differences to investigate**:
- Incorrect results
- Significant performance gap (>2x)
- Memory errors
- Missing error checking

## Profiling Solutions

### Using Nsight Compute:
```bash
ncu --set full -o profile ./solution
```

### Using Nsight Systems:
```bash
nsys profile -o timeline ./solution
```

### Key Metrics to Watch:
- **Kernel execution time** - How long the kernel runs
- **Memory throughput** - % of peak bandwidth utilized
- **Occupancy** - % of maximum possible active warps
- **Warp execution efficiency** - % of threads doing useful work

## Learning from Solutions

### Step-by-step approach:

1. **Understand the algorithm**
   - Read the comments
   - Trace through with small example
   - Understand data flow

2. **Analyze memory access patterns**
   - Where does data come from?
   - Is access coalesced?
   - When is shared memory used?

3. **Study optimizations**
   - Why are certain techniques used?
   - What problem do they solve?
   - What's the performance impact?

4. **Experiment**
   - Modify parameters (block size, tile size)
   - Try different optimizations
   - Measure performance changes

5. **Apply to your implementation**
   - Incorporate learned techniques
   - Understand trade-offs
   - Benchmark improvements

## Advanced Experiments

After completing the solutions, try:

### 1. Different Problem Sizes
- Very small (< 100 elements)
- Very large (> 100M elements)
- Non-power-of-2 sizes

### 2. Different GPU Architectures
- Compare performance on different GPUs
- Adjust compute capability
- Understand architectural differences

### 3. Optimization Variations
- Different tile sizes
- Different block configurations
- Alternative algorithms

### 4. Extended Functionality
- Add new features
- Implement variants
- Combine techniques

## Additional Resources

### NVIDIA Documentation
- [CUDA Programming Guide](https://docs.nvidia.com/cuda/cuda-c-programming-guide/)
- [CUDA Best Practices](https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/)
- [Nsight Compute Docs](https://docs.nvidia.com/nsight-compute/)

### Books
- "Programming Massively Parallel Processors" - Kirk & Hwu
- "CUDA by Example" - Sanders & Kandrot

### Online Courses
- [NVIDIA Deep Learning Institute](https://www.nvidia.com/en-us/training/)
- [Udacity: Intro to Parallel Programming](https://www.udacity.com/course/intro-to-parallel-programming--cs344)

## Support

If solutions don't work:

1. **Check CUDA installation**:
   ```bash
   nvcc --version
   nvidia-smi
   ```

2. **Verify compute capability**:
   - Update Makefile ARCH variable
   - Match your GPU's compute capability

3. **Check for errors**:
   - Enable debug mode: `make debug`
   - Use cuda-memcheck: `cuda-memcheck ./solution`

4. **Review dependencies**:
   - CUDA Toolkit version
   - Driver version
   - Compiler version

## Contributing

Found an issue or optimization?
- Solutions can always be improved
- Share your insights
- Contribute better approaches

Happy learning! 🚀
