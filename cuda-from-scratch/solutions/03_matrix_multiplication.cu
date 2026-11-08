/*
 * Example 3: Matrix Multiplication in CUDA
 *
 * This example demonstrates optimization with shared memory:
 * - Tiled matrix multiplication
 * - Shared memory usage
 * - Thread synchronization (__syncthreads)
 * - Performance comparison (naive vs optimized)
 *
 * Learning Goals:
 * - Understand shared memory benefits
 * - Implement tiling for data reuse
 * - Master __syncthreads() usage
 * - Analyze memory access patterns
 *
 * Matrix multiplication: C = A * B
 * where A is MxK, B is KxN, and C is MxN
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

#define TILE_SIZE 16

/*
 * Naive matrix multiplication kernel (global memory only).
 *
 * For C = A * B (A is MxK, B is KxN, C is MxN), each thread computes
 * one element: C[row][col] = sum(A[row][k] * B[k][col]) for k = 0..K-1
 */
__global__ void matrixMulNaive(const float* A, const float* B, float* C,
                                int M, int N, int K) {
    // Calculate output position
    int row = blockIdx.y * blockDim.y + threadIdx.y;
    int col = blockIdx.x * blockDim.x + threadIdx.x;

    // Check bounds (grid rounded up to cover M x N)
    if (row < M && col < N) {
        // Compute dot product over the K dimension
        float sum = 0.0f;
        for (int k = 0; k < K; k++) {
            // A is row-major: A[row][k] = A[row * K + k]
            // B is row-major: B[k][col] = B[k * N + col]
            sum += A[row * K + k] * B[k * N + col];
        }

        // Write result
        C[row * N + col] = sum;
    }
}

/*
 * Tiled matrix multiplication with shared memory.
 *
 * Each block loads tiles of A and B into shared memory so all threads in
 * the block reuse them, cutting global memory traffic:
 * - Naive: Each element loaded K times from global memory
 * - Tiled: Each element loaded once per tile from global memory
 */
__global__ void matrixMulTiled(const float* A, const float* B, float* C,
                                int M, int N, int K) {
    // Step 1 - Shared memory for tiles
    __shared__ float tileA[TILE_SIZE][TILE_SIZE];
    __shared__ float tileB[TILE_SIZE][TILE_SIZE];

    // Step 2 - Calculate indices
    int row = blockIdx.y * TILE_SIZE + threadIdx.y;
    int col = blockIdx.x * TILE_SIZE + threadIdx.x;
    int tx = threadIdx.x;
    int ty = threadIdx.y;

    // Step 3 - Initialize accumulator
    float sum = 0.0f;

    // Step 4 - Loop over tiles of the K dimension
    int numTiles = (K + TILE_SIZE - 1) / TILE_SIZE;
    for (int t = 0; t < numTiles; t++) {

        // Step 4a - Load tile from A (zero-pad out-of-bounds)
        int aCol = t * TILE_SIZE + tx;
        if (row < M && aCol < K) {
            tileA[ty][tx] = A[row * K + aCol];
        } else {
            tileA[ty][tx] = 0.0f;
        }

        // Step 4b - Load tile from B (zero-pad out-of-bounds)
        int bRow = t * TILE_SIZE + ty;
        if (bRow < K && col < N) {
            tileB[ty][tx] = B[bRow * N + col];
        } else {
            tileB[ty][tx] = 0.0f;
        }

        // Step 4c - Wait until the whole tile is loaded
        __syncthreads();

        // Step 4d - Compute partial dot product using shared memory
        for (int k = 0; k < TILE_SIZE; k++) {
            sum += tileA[ty][k] * tileB[k][tx];
        }

        // Step 4e - Wait before overwriting tiles with next chunk
        __syncthreads();
    }

    // Step 5 - Write result
    if (row < M && col < N) {
        C[row * N + col] = sum;
    }
}

void matrixMul(const float* h_A, const float* h_B, float* h_C,
               int M, int N, int K, bool useTiled) {
    size_t bytesA = M * K * sizeof(float);
    size_t bytesB = K * N * sizeof(float);
    size_t bytesC = M * N * sizeof(float);

    // Allocate device memory
    float *d_A, *d_B, *d_C;
    CUDA_CHECK(cudaMalloc(&d_A, bytesA));
    CUDA_CHECK(cudaMalloc(&d_B, bytesB));
    CUDA_CHECK(cudaMalloc(&d_C, bytesC));

    // Copy inputs to device
    CUDA_CHECK(cudaMemcpy(d_A, h_A, bytesA, cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(d_B, h_B, bytesB, cudaMemcpyHostToDevice));

    // Configure grid and block dimensions
    dim3 threadsPerBlock(TILE_SIZE, TILE_SIZE);
    dim3 blocksPerGrid(
        (N + TILE_SIZE - 1) / TILE_SIZE,
        (M + TILE_SIZE - 1) / TILE_SIZE
    );

    // Launch appropriate kernel
    if (useTiled) {
        matrixMulTiled<<<blocksPerGrid, threadsPerBlock>>>(d_A, d_B, d_C, M, N, K);
    } else {
        matrixMulNaive<<<blocksPerGrid, threadsPerBlock>>>(d_A, d_B, d_C, M, N, K);
    }

    CUDA_CHECK(cudaGetLastError());
    CUDA_CHECK(cudaDeviceSynchronize());

    // Copy result back
    CUDA_CHECK(cudaMemcpy(h_C, d_C, bytesC, cudaMemcpyDeviceToHost));

    // Free device memory
    CUDA_CHECK(cudaFree(d_A));
    CUDA_CHECK(cudaFree(d_B));
    CUDA_CHECK(cudaFree(d_C));
}

int main(int argc, char** argv) {
    int M = 1024, N = 1024, K = 1024;

    if (argc > 1) M = atoi(argv[1]);
    if (argc > 2) N = atoi(argv[2]);
    if (argc > 3) K = atoi(argv[3]);

    printf("Matrix Multiplication: C(%dx%d) = A(%dx%d) * B(%dx%d)\n",
           M, N, M, K, K, N);

    // Allocate host memory
    float* h_A = (float*)malloc(M * K * sizeof(float));
    float* h_B = (float*)malloc(K * N * sizeof(float));
    float* h_C_naive = (float*)malloc(M * N * sizeof(float));
    float* h_C_tiled = (float*)malloc(M * N * sizeof(float));

    // Initialize matrices
    for (int i = 0; i < M * K; i++) h_A[i] = (float)rand() / RAND_MAX;
    for (int i = 0; i < K * N; i++) h_B[i] = (float)rand() / RAND_MAX;

    // Test naive version
    printf("\nTesting naive version...\n");
    cudaEvent_t start, stop;
    cudaEventCreate(&start);
    cudaEventCreate(&stop);

    cudaEventRecord(start);
    matrixMul(h_A, h_B, h_C_naive, M, N, K, false);
    cudaEventRecord(stop);
    cudaEventSynchronize(stop);

    float naiveTime = 0;
    cudaEventElapsedTime(&naiveTime, start, stop);
    printf("Naive kernel time: %.3f ms\n", naiveTime);

    // Test tiled version
    printf("\nTesting tiled version...\n");
    cudaEventRecord(start);
    matrixMul(h_A, h_B, h_C_tiled, M, N, K, true);
    cudaEventRecord(stop);
    cudaEventSynchronize(stop);

    float tiledTime = 0;
    cudaEventElapsedTime(&tiledTime, start, stop);
    printf("Tiled kernel time: %.3f ms\n", tiledTime);
    printf("Speedup: %.2fx\n", naiveTime / tiledTime);

    // Verify results match
    bool match = true;
    for (int i = 0; i < M * N && match; i++) {
        if (fabs(h_C_naive[i] - h_C_tiled[i]) > 1e-3) {
            match = false;
        }
    }

    printf("\nResults match: %s\n", match ? "YES" : "NO");

    // Cleanup
    free(h_A);
    free(h_B);
    free(h_C_naive);
    free(h_C_tiled);
    cudaEventDestroy(start);
    cudaEventDestroy(stop);

    return 0;
}

/*
 * EXPECTED OUTPUT:
 * Matrix Multiplication: C(1024x1024) = A(1024x1024) * B(1024x1024)
 * Testing naive version...
 * Naive kernel time: ~50-100 ms
 * Testing tiled version...
 * Tiled kernel time: ~5-15 ms
 * Speedup: 5-10x
 * Results match: YES
 */
