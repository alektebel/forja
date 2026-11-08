/*
 * Example 1: Vector Addition in CUDA
 *
 * This is the "Hello World" of CUDA programming. It demonstrates:
 * - Basic CUDA kernel structure
 * - Thread indexing (1D)
 * - Memory allocation and transfers
 * - Error checking
 * - Performance measurement
 *
 * Learning Goals:
 * - Understand __global__ keyword
 * - Learn threadIdx, blockIdx, blockDim
 * - Master cudaMalloc/cudaMemcpy/cudaFree
 * - Implement proper error handling
 */

#include <stdio.h>
#include <stdlib.h>
#include <cuda_runtime.h>
#include <math.h>

// Error checking macro
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
 * Vector addition kernel: each thread adds ONE element.
 *
 * Key Concepts:
 * - __global__: This function runs on GPU, called from CPU
 * - blockIdx.x: Index of the current block in the grid
 * - threadIdx.x: Index of the current thread within its block
 * - blockDim.x: Number of threads per block
 */
__global__ void vectorAddKernel(const float* A, const float* B, float* C, int N) {
    // Step 1 - Calculate global thread index
    int idx = blockIdx.x * blockDim.x + threadIdx.x;

    // Step 2 - Check bounds (grid is rounded up, so some threads are extra)
    if (idx < N) {
        // Step 3 - Perform addition
        C[idx] = A[idx] + B[idx];
    }
}

/*
 * Host function that orchestrates the GPU computation:
 * 1. Allocate device memory for input and output arrays
 * 2. Copy input data from host to device
 * 3. Configure and launch the kernel
 * 4. Copy results back to host
 * 5. Free device memory
 */
void vectorAdd(const float* h_A, const float* h_B, float* h_C, int N) {
    // Step 1 - Calculate memory size in bytes
    size_t bytes = N * sizeof(float);

    // Step 2 - Allocate device memory (3 arrays)
    float* d_A = NULL;
    float* d_B = NULL;
    float* d_C = NULL;
    CUDA_CHECK(cudaMalloc(&d_A, bytes));
    CUDA_CHECK(cudaMalloc(&d_B, bytes));
    CUDA_CHECK(cudaMalloc(&d_C, bytes));

    // Step 3 - Copy input vectors from host to device
    CUDA_CHECK(cudaMemcpy(d_A, h_A, bytes, cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(d_B, h_B, bytes, cudaMemcpyHostToDevice));

    // Step 4 - Configure kernel launch parameters
    int threadsPerBlock = 256;
    // Ceiling division: last block is partial, bounds check handles it
    int blocksPerGrid = (N + threadsPerBlock - 1) / threadsPerBlock;

    // Step 5 - Launch kernel
    vectorAddKernel<<<blocksPerGrid, threadsPerBlock>>>(d_A, d_B, d_C, N);

    // Step 6 - Check for kernel launch errors
    CUDA_CHECK(cudaGetLastError());

    // Step 7 - Wait for GPU to finish
    CUDA_CHECK(cudaDeviceSynchronize());

    // Step 8 - Copy result back to host
    CUDA_CHECK(cudaMemcpy(h_C, d_C, bytes, cudaMemcpyDeviceToHost));

    // Step 9 - Free device memory
    CUDA_CHECK(cudaFree(d_A));
    CUDA_CHECK(cudaFree(d_B));
    CUDA_CHECK(cudaFree(d_C));
}

/*
 * Main function with testing and performance measurement
 */
int main(int argc, char** argv) {
    // Parse command line arguments
    int N = 1000000;  // Default: 1 million elements
    if (argc > 1) {
        N = atoi(argv[1]);
        if (N <= 0) {
            fprintf(stderr, "Invalid vector size\n");
            return 1;
        }
    }

    printf("Vector Addition: N = %d elements\n", N);

    // Allocate host memory
    size_t bytes = N * sizeof(float);
    float* h_A = (float*)malloc(bytes);
    float* h_B = (float*)malloc(bytes);
    float* h_C = (float*)malloc(bytes);

    if (!h_A || !h_B || !h_C) {
        fprintf(stderr, "Failed to allocate host memory\n");
        return 1;
    }

    // Initialize input vectors with random values
    printf("Initializing input vectors...\n");
    for (int i = 0; i < N; i++) {
        h_A[i] = (float)rand() / RAND_MAX;
        h_B[i] = (float)rand() / RAND_MAX;
    }

    // Perform vector addition on GPU
    printf("Performing vector addition on GPU...\n");

    // Performance measurement with CUDA events
    cudaEvent_t start, stop;
    cudaEventCreate(&start);
    cudaEventCreate(&stop);
    cudaEventRecord(start);

    vectorAdd(h_A, h_B, h_C, N);

    cudaEventRecord(stop);
    cudaEventSynchronize(stop);
    float milliseconds = 0;
    cudaEventElapsedTime(&milliseconds, start, stop);
    printf("Kernel execution time: %.3f ms\n", milliseconds);

    // Verify results
    printf("Verifying results...\n");
    bool success = true;
    for (int i = 0; i < N; i++) {
        float expected = h_A[i] + h_B[i];
        float diff = fabs(h_C[i] - expected);
        if (diff > 1e-5) {
            fprintf(stderr, "Verification failed at index %d: "
                           "expected %.6f, got %.6f\n", i, expected, h_C[i]);
            success = false;
            break;
        }
    }

    if (success) {
        printf("✓ Verification PASSED\n");
    } else {
        printf("✗ Verification FAILED\n");
    }

    // Free host memory
    free(h_A);
    free(h_B);
    free(h_C);

    // Clean up timing events
    cudaEventDestroy(start);
    cudaEventDestroy(stop);

    return success ? 0 : 1;
}

/*
 * EXPECTED OUTPUT:
 * Vector Addition: N = 1000000 elements
 * Initializing input vectors...
 * Performing vector addition on GPU...
 * Kernel execution time: ~0.5-2 ms
 * Verifying results...
 * ✓ Verification PASSED
 *
 * PERFORMANCE TIPS:
 * - Try different thread counts: 128, 256, 512, 1024
 * - Compare performance with different vector sizes
 * - Profile with: nvprof ./01_vector_addition
 * - Calculate bandwidth: (3 * N * 4 bytes) / time
 */
