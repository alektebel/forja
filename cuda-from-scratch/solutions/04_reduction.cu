/*
 * Example 4: Parallel Reduction in CUDA
 *
 * Demonstrates parallel reduction pattern for computing sum, min, max, etc.
 * This is a fundamental pattern used in many GPU algorithms.
 *
 * Learning Goals:
 * - Tree-based parallel reduction
 * - Avoiding warp divergence
 * - Shared memory optimization
 * - Multi-pass reduction for large arrays
 */

#include <stdio.h>
#include <stdlib.h>
#include <cuda_runtime.h>
#include <math.h>

#define CUDA_CHECK(call) \
do { \
    cudaError_t err = call; \
    if (err != cudaSuccess) { \
        fprintf(stderr, "CUDA Error: %s (err_num=%d) at %s:%d\n", \
                cudaGetErrorString(err), err, __FILE__, __LINE__); \
        exit(EXIT_FAILURE); \
    } \
} while(0)

/*
 * Basic parallel reduction (sum), tree-based:
 * 1. Each thread loads data into shared memory
 * 2. Threads reduce in a tree pattern; active threads halve each iteration
 * 3. Thread 0 writes the final block result
 *
 * Example for 8 elements:
 * Initial: [1, 2, 3, 4, 5, 6, 7, 8]
 * Step 1:  [3, 7, 11, 15, -, -, -, -]  (stride=1)
 * Step 2:  [10, 26, -, -, -, -, -, -]  (stride=2)
 * Step 3:  [36, -, -, -, -, -, -, -]   (stride=4)
 * Result: 36
 */
__global__ void reduceSumKernel(const float* input, float* output, int N) {
    // Shared memory sized to blockDim.x (dynamic, passed at launch)
    extern __shared__ float sdata[];

    // Load data into shared memory (zero for out-of-bounds tail threads)
    int tid = threadIdx.x;
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    sdata[tid] = (idx < N) ? input[idx] : 0.0f;
    __syncthreads();

    // Tree-based reduction. __syncthreads() at the end of EVERY iteration:
    // the next stride reads elements written by other threads in this one.
    for (int stride = blockDim.x / 2; stride > 0; stride >>= 1) {
        if (tid < stride) {
            sdata[tid] += sdata[tid + stride];
        }
        __syncthreads();
    }

    // Thread 0 writes this block's partial sum
    if (tid == 0) {
        output[blockIdx.x] = sdata[0];
    }
}

/*
 * Host function for multi-pass reduction: keeps re-reducing the array of
 * partial block sums until a single value remains, ping-ponging between
 * two device buffers (the kernel writes output[blockIdx.x], so each pass
 * compacts its partials at the start of the destination buffer).
 */
float reduceSum(const float* h_input, int N) {
    const int threadsPerBlock = 256;
    int blocksPerGrid = (N + threadsPerBlock - 1) / threadsPerBlock;

    // Allocate device memory
    float *d_input, *d_a, *d_b;
    CUDA_CHECK(cudaMalloc(&d_input, N * sizeof(float)));
    CUDA_CHECK(cudaMalloc(&d_a, blocksPerGrid * sizeof(float)));
    CUDA_CHECK(cudaMalloc(&d_b, blocksPerGrid * sizeof(float)));

    // Copy input to device
    CUDA_CHECK(cudaMemcpy(d_input, h_input, N * sizeof(float), cudaMemcpyHostToDevice));

    // First pass: reduce the input down to one partial per block
    size_t sharedMemSize = threadsPerBlock * sizeof(float);
    reduceSumKernel<<<blocksPerGrid, threadsPerBlock, sharedMemSize>>>(
        d_input, d_a, N);
    CUDA_CHECK(cudaGetLastError());

    // Follow-up passes: each reduces `current` partials into
    // ceil(current / threadsPerBlock) partials in the other buffer,
    // until one value remains. Threads past `current` contribute 0.
    float* src = d_a;
    float* dst = d_b;
    int current = blocksPerGrid;
    while (current > 1) {
        int next = (current + threadsPerBlock - 1) / threadsPerBlock;
        reduceSumKernel<<<next, threadsPerBlock, sharedMemSize>>>(src, dst, current);
        CUDA_CHECK(cudaGetLastError());
        float* tmp = src; src = dst; dst = tmp;
        current = next;
    }
    CUDA_CHECK(cudaDeviceSynchronize());

    float result = 0.0f;
    CUDA_CHECK(cudaMemcpy(&result, src, sizeof(float), cudaMemcpyDeviceToHost));

    CUDA_CHECK(cudaFree(d_input));
    CUDA_CHECK(cudaFree(d_a));
    CUDA_CHECK(cudaFree(d_b));

    return result;
}

int main(int argc, char** argv) {
    int N = 1000000;
    if (argc > 1) N = atoi(argv[1]);

    printf("Parallel Reduction: N = %d elements\n", N);

    // Allocate and initialize input
    float* h_input = (float*)malloc(N * sizeof(float));
    for (int i = 0; i < N; i++) {
        h_input[i] = 1.0f;  // Simple test: sum should equal N
    }

    // Compute on GPU
    float gpuSum = reduceSum(h_input, N);

    // Verify
    float cpuSum = 0.0f;
    for (int i = 0; i < N; i++) cpuSum += h_input[i];

    printf("GPU sum: %.2f\n", gpuSum);
    printf("CPU sum: %.2f\n", cpuSum);
    bool passed = (fabs(gpuSum - cpuSum) < 1e-2);
    printf("Match: %s\n", passed ? "YES" : "NO");
    if (passed) {
        printf("✓ Verification PASSED\n");
    } else {
        printf("✗ Verification FAILED\n");
    }

    free(h_input);
    return passed ? 0 : 1;
}

/*
 * OPTIMIZATION OPPORTUNITIES:
 * - Use sequential addressing to avoid divergence
 * - Unroll last warp (no sync needed)
 * - Use warp shuffle instructions
 * - Process multiple elements per thread
 */
