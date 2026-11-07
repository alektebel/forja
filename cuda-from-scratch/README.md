# CUDA Programming from Scratch

A comprehensive from-scratch implementation guide for CUDA parallel programming. This project provides a structured learning path from basic GPU programming to building a complete neural network in CUDA.

## Goal

Build a deep understanding of GPU parallel programming and CUDA by implementing:
- **Basic GPU operations**: Vector and matrix operations
- **Memory management**: Host-device transfers, shared memory optimization
- **Parallel patterns**: Reduction, scan, convolution
- **Neural networks**: Complete implementation from scratch on GPU
- **CUDA compiler**: Tiny compiler that translates CUDA kernels to PTX assembly

## Project Structure

```
cuda-from-scratch/
├── README.md                          # This file
├── IMPLEMENTATION_GUIDE.md            # Detailed step-by-step guide
├── Makefile                           # Build system for all examples
├── 01_vector_addition.cu              # Basic parallel addition
├── 02_matrix_addition.cu              # 2D parallelization
├── 03_matrix_multiplication.cu        # Tiled matrix multiplication
├── 04_reduction.cu                    # Parallel reduction patterns
├── 05_convolution.cu                  # Image convolution
├── 06_neural_network_forward.cu      # NN forward propagation
├── 07_neural_network_backward.cu     # NN backpropagation
├── 08_complete_neural_network.cu     # Full NN training from scratch
├── cuda-compiler/                     # Tiny CUDA → PTX compiler (from scratch)
│   ├── README.md
│   ├── Makefile
│   ├── lexer.h / lexer.c              # CUDA tokenizer
│   ├── ast.h                          # Abstract Syntax Tree definitions
│   ├── parser.c                       # Recursive-descent parser
│   ├── codegen.c                      # PTX code generator
│   ├── main.c                         # Compiler entry point
│   └── tests/                         # Test CUDA kernel inputs
├── tests/                             # Test programs and datasets
│   ├── test_vector_addition.cu
│   ├── test_matrix_multiplication.cu
│   └── test_neural_network.cu
└── solutions/                         # Complete reference implementations
    ├── README.md
    ├── 01_vector_addition.cu
    └── ...
```

## Features

### Learning Progression

1. **Fundamentals (Examples 1-2)**
   - CUDA kernel basics
   - Thread/block organization
   - Memory transfers (host ↔ device)
   - Error handling

2. **Intermediate Patterns (Examples 3-5)**
   - Shared memory optimization
   - Thread synchronization
   - Tiled algorithms
   - Parallel reduction
   - 2D/3D grid configurations

3. **Advanced Applications (Examples 6-8)**
   - Neural network layers
   - Forward propagation
   - Backpropagation
   - Gradient descent
   - Complete training pipeline

### CUDA Concepts Covered

**Memory Hierarchy**:
- Global memory
- Shared memory (on-chip)
- Registers
- Constant memory
- Texture memory

**Execution Model**:
- Kernels and launch configurations
- Thread hierarchy (threads, blocks, grids)
- Warps and SIMT execution
- Occupancy optimization

**Optimization Techniques**:
- Memory coalescing
- Bank conflict avoidance
- Shared memory tiling
- Register usage optimization
- Asynchronous operations

## Quick Start

### Prerequisites

```bash
# Check CUDA installation
nvcc --version

# Check GPU availability
nvidia-smi
```

**Requirements**:
- NVIDIA GPU (compute capability 3.0+)
- CUDA Toolkit (11.0+)
- GCC/Clang compiler
- Make build system

### Building

Build individual examples:
```bash
make vector_add      # Build example 1
make matrix_mul      # Build example 3
make neural_net      # Build example 8
```

Build everything:
```bash
make all            # Build all examples
```

### Testing

Run tests for each example:
```bash
make test-vector    # Test vector addition
make test-matrix    # Test matrix operations
make test-nn        # Test neural network
make test           # Run all tests
```

### Usage Example

#### Example 1: Vector Addition

```bash
# Build
make vector_add

# Run
./vector_add 1000000

# Expected output:
# Allocating memory...
# Launching kernel with 1954 blocks, 512 threads per block
# Vector addition completed in 0.523 ms
# Verification: PASSED
```

## Learning Path

### Stage 1: GPU Basics (2-3 hours)

**Example 1: Vector Addition** (`01_vector_addition.cu`)

**Goal**: Understand basic CUDA kernel structure

**Topics**:
- Writing your first kernel
- Thread indexing (`threadIdx`, `blockIdx`, `blockDim`)
- Memory allocation (`cudaMalloc`, `cudaFree`)
- Memory transfers (`cudaMemcpy`)
- Kernel launch syntax `<<<blocks, threads>>>`
- Error checking

**Implementation steps**:
1. Allocate device memory
2. Copy data from host to device
3. Write kernel: `__global__ void vectorAdd()`
4. Launch kernel with proper grid/block dimensions
5. Copy results back to host
6. Verify correctness
7. Free memory

**Skills learned**:
- CUDA program structure
- Basic parallelization
- Memory management
- Performance measurement

---

**Example 2: Matrix Addition** (`02_matrix_addition.cu`)

**Goal**: Extend to 2D data structures

**Topics**:
- 2D thread indexing
- 2D grid configuration
- Row-major vs column-major layout
- Boundary checking

**Implementation steps**:
1. Calculate 2D thread indices
2. Map threads to matrix elements
3. Handle non-square matrices
4. Optimize grid dimensions
5. Test with various matrix sizes

**Skills learned**:
- Multi-dimensional indexing
- Memory layout considerations
- Grid configuration strategies

---

### Stage 2: Optimization Patterns (3-4 hours)

**Example 3: Matrix Multiplication** (`03_matrix_multiplication.cu`)

**Goal**: Implement tiled matrix multiplication with shared memory

**Topics**:
- Shared memory usage
- Thread synchronization (`__syncthreads()`)
- Tiling for data reuse
- Memory coalescing
- Performance comparison (naive vs optimized)

**Implementation steps**:
1. Implement naive version (global memory only)
2. Implement tiled version with shared memory
3. Handle tile size and matrix dimensions
4. Add synchronization barriers
5. Benchmark both versions
6. Compare with cuBLAS

**Skills learned**:
- Shared memory optimization
- Tiling techniques
- Performance analysis
- Memory bandwidth optimization

---

**Example 4: Reduction Operations** (`04_reduction.cu`)

**Goal**: Master parallel reduction patterns

**Topics**:
- Tree-based reduction
- Warp-level primitives
- Multiple kernel launches
- Atomic operations
- Sequential addressing

**Implementation steps**:
1. Implement basic reduction (sum)
2. Optimize with shared memory
3. Avoid divergence and bank conflicts
4. Use warp shuffle instructions
5. Extend to min/max/avg operations

**Skills learned**:
- Parallel reduction algorithms
- Warp-level programming
- Divergence avoidance
- Advanced synchronization

---

**Example 5: Convolution** (`05_convolution.cu`)

**Goal**: Implement 2D convolution for image processing

**Topics**:
- Constant memory for kernels
- Halo/ghost cells
- Boundary handling
- Separable convolution
- Texture memory (optional)

**Implementation steps**:
1. Implement basic 2D convolution
2. Use constant memory for filter
3. Handle boundaries (clamp/wrap)
4. Optimize with shared memory (tiling with halos)
5. Test with various filter sizes

**Skills learned**:
- Constant memory usage
- Stencil operations
- Boundary handling strategies
- Real-world GPU algorithms

---

### Stage 3: Neural Networks (6-8 hours)

**Example 6: Neural Network Forward Pass** (`06_neural_network_forward.cu`)

**Goal**: Implement forward propagation layers

**Topics**:
- Matrix-vector operations
- Activation functions (ReLU, Sigmoid, Tanh)
- Batch processing
- Layer composition

**Implementation steps**:
1. Implement fully connected layer kernel
2. Implement activation function kernels
3. Combine layers for forward pass
4. Support mini-batches
5. Test with known weights and inputs

**Skills learned**:
- Neural network fundamentals
- CUDA for deep learning
- Batch processing patterns

---

**Example 7: Neural Network Backward Pass** (`07_neural_network_backward.cu`)

**Goal**: Implement backpropagation and gradient computation

**Topics**:
- Gradient computation
- Chain rule implementation
- Weight updates
- Mini-batch gradient descent

**Implementation steps**:
1. Implement backward pass for FC layer
2. Implement activation derivative kernels
3. Compute gradients via chain rule
4. Implement SGD weight update
5. Test gradient correctness (numerical gradients)

**Skills learned**:
- Backpropagation algorithm
- Gradient computation
- Optimization algorithms

---

**Example 8: Complete Neural Network** (`08_complete_neural_network.cu`)

**Goal**: Build a complete trainable neural network from scratch

**Topics**:
- Full training loop
- Loss functions (MSE, Cross-entropy)
- Model evaluation
- Data loading and batching
- Training on real datasets (MNIST)

**Implementation steps**:
1. Combine forward and backward passes
2. Implement loss function kernels
3. Create training loop
4. Add evaluation/testing
5. Load and preprocess MNIST dataset
6. Train multi-layer network
7. Achieve >95% accuracy on MNIST

**Architecture**:
```
Input (784) → FC(128) → ReLU → FC(64) → ReLU → FC(10) → Softmax
```

**Skills learned**:
- End-to-end deep learning system
- Training pipeline
- Performance optimization
- Real-world GPU programming

---

**Total Time**: ~12-16 hours for complete implementation

## Documentation

### Comprehensive Guides

- **[IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)**: Detailed step-by-step implementation instructions with code snippets, optimization tips, and debugging strategies
- **Template Files**: Each `.cu` file contains extensive TODO comments and implementation guidelines
- **Solutions**: Complete working implementations with explanations

### CUDA Resources

**Official Documentation**:
- [CUDA Programming Guide](https://docs.nvidia.com/cuda/cuda-c-programming-guide/)
- [CUDA Best Practices Guide](https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/)
- [CUDA Toolkit Documentation](https://docs.nvidia.com/cuda/)

**Glossaries**:
- [Modal's GPU Glossary](https://modal.com/gpu-glossary/readme/) — the CUDA stack in one
  hypertext: streaming multiprocessors and tensor cores (device hardware), warps, kernels,
  PTX/SASS and the memory hierarchy (device software), `nvcc`, `nvidia-smi`, CUPTI/Nsight
  and cuBLAS/CUTLASS (host software), and a Performance section — roofline model,
  compute-bound vs memory-bound, arithmetic intensity, occupancy, warp divergence, memory
  coalescing and bank conflicts — that maps one-to-one onto this repo's kernels and
  profilers. Cross-linked throughout, unlike a PDF.

**Books**:
- "Programming Massively Parallel Processors" by Kirk & Hwu
- "CUDA by Example" by Sanders & Kandrot
- "Professional CUDA C Programming" by Cheng et al.

**Online Courses**:
- [NVIDIA DLI: Fundamentals of Accelerated Computing](https://www.nvidia.com/en-us/training/)
- [Udacity: Intro to Parallel Programming](https://www.udacity.com/course/intro-to-parallel-programming--cs344)
- [Coursera: GPU Programming](https://www.coursera.org/specializations/gpu-programming)

**Video Courses**:
- [Computer Organization and Architecture](https://github.com/Developer-Y/cs-video-courses#computer-organization-and-architecture)
- [Systems Programming](https://github.com/Developer-Y/cs-video-courses#systems-programming)
- [Deep Learning](https://github.com/Developer-Y/cs-video-courses#deep-learning)

## Testing

### Test Suite

Each example includes comprehensive tests:

```bash
# Unit tests for individual kernels
tests/test_vector_addition.cu
tests/test_matrix_operations.cu

# Integration tests
tests/test_neural_network_forward.cu
tests/test_neural_network_backward.cu

# End-to-end tests
tests/test_mnist_training.cu
```

### Verification Strategies

**Correctness**:
- Compare with CPU implementations
- Numerical gradient checking
- Known test cases with verified outputs

**Performance**:
- Profile with nvprof/Nsight Compute
- Compare with optimized libraries (cuBLAS, cuDNN)
- Measure memory bandwidth utilization

### Automated Testing

```bash
make test              # Run all tests
make test-verbose      # Run with detailed output
make benchmark         # Run performance benchmarks
```

## Performance Tips

### Memory Optimization

1. **Coalesced Access**: Access consecutive memory locations in warps
2. **Shared Memory**: Reduce global memory accesses
3. **Constant Memory**: Use for read-only data accessed uniformly
4. **Pinned Memory**: Use for faster host-device transfers

### Execution Optimization

1. **Occupancy**: Maximize active warps per SM
2. **Divergence**: Minimize branch divergence within warps
3. **Bank Conflicts**: Avoid shared memory bank conflicts
4. **Register Pressure**: Balance register usage and occupancy

### Profiling

```bash
# Profile with nvprof (legacy)
nvprof ./program

# Profile with Nsight Compute (modern)
ncu --set full ./program

# Profile with Nsight Systems
nsys profile ./program
```

## Debugging

### Common Issues

**Kernel Launch Failures**:
```bash
# Check errors after kernel
cudaError_t err = cudaGetLastError();
if (err != cudaSuccess) {
    printf("Error: %s\n", cudaGetErrorString(err));
}
```

**Memory Errors**:
```bash
# Use cuda-memcheck
cuda-memcheck ./program

# Enable address sanitizer
nvcc -Xcompiler -fsanitize=address -g program.cu
```

**Performance Issues**:
```bash
# Check occupancy
ncu --metrics sm__warps_active.avg.pct_of_peak ./program

# Check memory throughput
ncu --metrics dram__throughput.avg.pct_of_peak ./program
```

## Architecture

### Data Flow

```
┌──────────────────┐
│  Host (CPU)      │
│  - Input data    │
│  - Model weights │
└────────┬─────────┘
         │ cudaMemcpy
         ▼
┌──────────────────┐
│  Device (GPU)    │
│  Global Memory   │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  CUDA Kernels    │
│  - Forward pass  │
│  - Backward pass │
│  - Weight update │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Shared Memory   │
│  (Per-block)     │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Registers       │
│  (Per-thread)    │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Computation     │
│  (GPU cores)     │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Results back    │
│  to Host         │
└──────────────────┘
```

## Advanced Topics

After completing the basic examples, explore:

### CUDA Compiler Internals
- **[cuda-compiler/](cuda-compiler/)** – Tiny CUDA→PTX compiler built from scratch
  - Lexer: tokenises CUDA-specific syntax (`__global__`, `threadIdx`, etc.)
  - Parser: recursive-descent parser producing an AST
  - PTX code generator: walks the AST and emits valid PTX assembly
  - Build: `cd cuda-compiler && make && ./cuda_compiler tests/vector_add.cu`

### Advanced Optimizations
- Streams and concurrent execution
- Multi-GPU programming
- Unified Memory
- Tensor Cores (for modern GPUs)
- Mixed precision training

### Advanced Architectures
- Convolutional Neural Networks (CNN)
- Recurrent Neural Networks (RNN/LSTM)
- Transformer attention mechanisms
- Custom layer implementations

### Integration
- PyTorch/TensorFlow custom operators
- CUDA Python (CuPy, Numba)
- OpenACC directives
- CUDA libraries (cuBLAS, cuDNN, cuFFT)

## Troubleshooting

### Common Errors

**"No CUDA-capable device"**:
- Check: `nvidia-smi`
- Ensure GPU drivers installed
- Verify CUDA toolkit compatibility

**Compilation errors**:
```bash
# Check CUDA version
nvcc --version

# Specify compute capability
nvcc -arch=sm_75 program.cu  # RTX 2080
nvcc -arch=sm_86 program.cu  # RTX 3090
```

**Out of memory**:
- Reduce batch size
- Free unused memory
- Use unified memory for large datasets

**Slow execution**:
- Profile with nsys/ncu
- Check occupancy
- Optimize memory access patterns

## Contributing

This is a learning project. Contributions welcome:
- Add more examples
- Improve documentation
- Optimize implementations
- Add benchmarks
- Fix bugs

## License

Educational purposes. Use freely for learning.

## Acknowledgments

Inspired by:
- NVIDIA CUDA samples
- cuDNN and cuBLAS implementations
- Stanford CS231n and CS149 courses
- "Programming Massively Parallel Processors" book
- PyTorch and TensorFlow CUDA kernels
