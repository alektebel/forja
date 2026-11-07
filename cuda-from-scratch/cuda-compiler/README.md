# Tiny CUDA Compiler

A from-scratch compiler that translates CUDA kernel source code into
**PTX (Parallel Thread eXecution)** assembly – NVIDIA's virtual ISA that
is JIT-compiled to native GPU machine code by the driver at load time.

## What is PTX?

PTX is NVIDIA's portable intermediate representation for GPU code.
When you write a CUDA kernel, the real `nvcc` compiler does two things:

```
CUDA source  →  [nvcc]  →  PTX  →  [GPU driver JIT]  →  SASS (native GPU code)
```

This tiny compiler replicates the **first step** from scratch, helping
you understand exactly what happens inside a CUDA compiler.

## Project Structure

```
cuda-compiler/
├── README.md           # This file
├── Makefile            # Build system
├── lexer.h             # Token type definitions
├── lexer.c             # CUDA tokenizer (lexical analysis)
├── ast.h               # Abstract Syntax Tree node definitions
├── parser.c            # Recursive-descent CUDA parser
├── codegen.c           # PTX code generator
├── main.c              # Compiler entry point
└── tests/
    ├── vector_add.cu   # Classic vector-add kernel
    ├── matrix_add.cu   # 2-D matrix addition kernel
    └── multi_kernel.cu # Two kernels in one file
```

## Compiler Phases

```
┌──────────────────────┐
│   CUDA source (.cu)  │
│   e.g. vector_add.cu │
└──────────┬───────────┘
           │
           ▼  Phase 1 – Lexical Analysis
┌──────────────────────┐
│   Token stream       │  __global__, void, vectorAdd, (, float, *, A, ...
│   (lexer.c)          │
└──────────┬───────────┘
           │
           ▼  Phase 2 – Parsing
┌──────────────────────┐
│   Abstract Syntax    │  KernelFunc("vectorAdd")
│   Tree  (parser.c)   │    ├─ Param(float*, "A")
│                      │    ├─ Param(float*, "B")
│                      │    └─ Body: Block
│                      │         ├─ VarDecl(int, "idx", ...)
│                      │         └─ If(idx < N)
│                      │              └─ C[idx] = A[idx] + B[idx]
└──────────┬───────────┘
           │
           ▼  Phase 3 – PTX Code Generation
┌──────────────────────┐
│   PTX assembly       │  .visible .entry vectorAdd(...)
│   (codegen.c)        │  { ld.param.u64, mov.u32 %r, %tid.x,
│                      │    mul.wide.s32, ld.global.f32, add.f32,
│                      │    st.global.f32, ret }
└──────────────────────┘
```

## Supported CUDA Subset

### Kernel Declaration
```cuda
__global__ void myKernel(float* A, float* B, int N) { ... }
```

### Types
| CUDA type | PTX register | PTX param |
|-----------|-------------|-----------|
| `int`     | `%r` (.b32) | `.u32`    |
| `float`   | `%f` (.f32) | `.f32`    |
| `float*`  | `%rd` (.b64)| `.u64`    |
| `int*`    | `%rd` (.b64)| `.u64`    |

### CUDA Built-ins
- `threadIdx.x / .y / .z` → `%tid.x / .y / .z`
- `blockIdx.x / .y / .z`  → `%ctaid.x / .y / .z`
- `blockDim.x / .y / .z`  → `%ntid.x / .y / .z`
- `gridDim.x / .y / .z`   → `%nctaid.x / .y / .z`

### Statements
- Variable declarations: `int idx = expr;`
- Assignments: `C[idx] = A[idx] + B[idx];`
- `if` / `else` blocks
- `while` loops
- `return`

### Expressions
- Arithmetic: `+`, `-`, `*`, `/`, `%`
- Comparisons: `<`, `>`, `<=`, `>=`, `==`, `!=`
- Logical: `&&`, `||`
- Array access: `arr[idx]`

## Quick Start

### Build

```bash
make
```

### Run

```bash
# Compile a CUDA kernel to PTX (stdout)
./cuda_compiler tests/vector_add.cu

# Write PTX to a file
./cuda_compiler tests/vector_add.cu -o vector_add.ptx

# Target a specific GPU architecture
./cuda_compiler tests/vector_add.cu -o out.ptx -arch sm_86

# Debug: print the token stream
./cuda_compiler tests/vector_add.cu -tokens
```

### Run all tests

```bash
make test
```

### Validate PTX (requires CUDA toolkit)

```bash
make validate        # runs ptxas on the generated PTX
```

## Example: Vector Addition

**Input** (`tests/vector_add.cu`):
```cuda
__global__ void vectorAdd(float* A, float* B, float* C, int N)
{
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < N) {
        C[idx] = A[idx] + B[idx];
    }
}
```

**Output PTX**:
```ptx
.version 7.5
.target sm_60
.address_size 64

.visible .entry vectorAdd(
    .param .u64    vectorAdd_param_0,   // float* A
    .param .u64    vectorAdd_param_1,   // float* B
    .param .u64    vectorAdd_param_2,   // float* C
    .param .u32    vectorAdd_param_3    // int N
)
{
    .reg .pred  %p<32>;
    .reg .f32   %f<64>;
    .reg .b32   %r<64>;
    .reg .b64   %rd<64>;

    // Load parameters
    ld.param.u64    %rd0, [vectorAdd_param_0];  // A
    ld.param.u64    %rd1, [vectorAdd_param_1];  // B
    ld.param.u64    %rd2, [vectorAdd_param_2];  // C
    ld.param.u32    %r0,  [vectorAdd_param_3];  // N

    // int idx = blockIdx.x * blockDim.x + threadIdx.x
    mov.u32         %r2, %ctaid.x;
    mov.u32         %r3, %ntid.x;
    mul.lo.s32      %r4, %r2, %r3;
    mov.u32         %r5, %tid.x;
    add.s32         %r6, %r4, %r5;
    mov.b32         %r1, %r6;          // idx

    // if (idx < N)
    setp.lt.s32     %p0, %r1, %r0;
    @!%p0 bra       BB_end_0;

    // C[idx] = A[idx] + B[idx]
    mul.wide.s32    %rd5, %r1, 4;
    add.s64         %rd6, %rd0, %rd5;
    ld.global.f32   %f0, [%rd6];       // A[idx]
    mul.wide.s32    %rd7, %r1, 4;
    add.s64         %rd8, %rd1, %rd7;
    ld.global.f32   %f1, [%rd8];       // B[idx]
    add.f32         %f2, %f0, %f1;
    st.global.f32   [%rd4], %f2;       // C[idx] = result

BB_end_0:
    ret;
}
```

## PTX Concepts Illustrated

| CUDA concept      | Generated PTX instruction          |
|-------------------|------------------------------------|
| `threadIdx.x`     | `mov.u32 %r, %tid.x`               |
| `blockIdx.x`      | `mov.u32 %r, %ctaid.x`             |
| `blockDim.x`      | `mov.u32 %r, %ntid.x`              |
| `a * b` (int)     | `mul.lo.s32 %r, %ra, %rb`          |
| `a * b` (float)   | `mul.f32 %f, %fa, %fb`             |
| `arr[i]` (read)   | `mul.wide.s32` + `add.s64` + `ld.global.f32` |
| `arr[i] = v`      | `mul.wide.s32` + `add.s64` + `st.global.f32` |
| `if (cond)`       | `setp.lt.s32` + `@!%p bra label`   |

## Learning Resources

- [PTX ISA Reference](https://docs.nvidia.com/cuda/parallel-thread-execution/)
- [CUDA Programming Guide](https://docs.nvidia.com/cuda/cuda-c-programming-guide/)
- [Godbolt Compiler Explorer](https://godbolt.org/) – see real nvcc PTX output
- [Modal's GPU Glossary](https://modal.com/gpu-glossary/readme/) — SASS, PTX, compute
  capability, and the nvcc/NVRTC pages sit directly under this compiler's output; the
  same glossary's device-hardware layer explains the machine the PTX runs on

## Implementation Notes

- **Single-pass codegen**: registers are allocated linearly; a production
  compiler would use SSA form and a register allocator.
- **No optimisation**: expressions are evaluated naively; `nvcc -O2` would
  CSE/fold many of the redundant address calculations.
- **Register budget**: we pre-declare `%r<64>`, `%f<64>`, etc.  A
  production pass would count exact register usage.
- **No `__syncthreads__`**: barrier instructions are not yet implemented.
