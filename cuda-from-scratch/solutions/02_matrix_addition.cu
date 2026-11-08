/*
 * Example 2: Matrix Addition in CUDA
 *
 * This example extends vector addition to 2D data structures:
 * - 2D thread indexing
 * - 2D grid configuration
 * - Row-major memory layout
 * - Handling non-square matrices
 *
 * Learning Goals:
 * - Use dim3 for 2D grids and blocks
 * - Calculate 2D thread indices
 * - Understand row-major layout
 * - Handle matrix dimensions properly
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
 * 2D matrix addition kernel.
 *
 * Memory Layout (row-major):
 * For a 3x4 matrix:
 *   [ 0  1  2  3 ]    =>  [ 0 1 2 3 4 5 6 7 8 9 10 11 ]
 *   [ 4  5  6  7 ]
 *   [ 8  9 10 11 ]
 */
__global__ void matrixAddKernel(const float* A, const float* B, float* C,
                                 int rows, int cols) {
    // Step 1 - Calculate 2D indices
    int row = blockIdx.y * blockDim.y + threadIdx.y;
    int col = blockIdx.x * blockDim.x + threadIdx.x;

    // Step 2 - Check bounds (grid is rounded up in both dimensions)
    if (row < rows && col < cols) {
        // Step 3 - Convert to 1D index (row-major)
        int idx = row * cols + col;

        // Step 4 - Perform addition
        C[idx] = A[idx] + B[idx];
    }
}

/*
 * Host function for matrix addition: 2D grid configuration with dim3.
 */
void matrixAdd(const float* h_A, const float* h_B, float* h_C,
               int rows, int cols) {
    // Step 1 - Calculate memory size
    size_t bytes = rows * cols * sizeof(float);

    // Step 2 - Allocate device memory
    float* d_A = NULL;
    float* d_B = NULL;
    float* d_C = NULL;
    CUDA_CHECK(cudaMalloc(&d_A, bytes));
    CUDA_CHECK(cudaMalloc(&d_B, bytes));
    CUDA_CHECK(cudaMalloc(&d_C, bytes));

    // Step 3 - Copy input matrices to device
    CUDA_CHECK(cudaMemcpy(d_A, h_A, bytes, cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(d_B, h_B, bytes, cudaMemcpyHostToDevice));

    // Step 4 - Configure 2D grid (16x16 block is common)
    dim3 threadsPerBlock(16, 16);

    // Ceiling division in each dimension
    dim3 blocksPerGrid(
        (cols + threadsPerBlock.x - 1) / threadsPerBlock.x,
        (rows + threadsPerBlock.y - 1) / threadsPerBlock.y
    );

    printf("Grid: (%d, %d) blocks, Block: (%d, %d) threads\n",
           blocksPerGrid.x, blocksPerGrid.y,
           threadsPerBlock.x, threadsPerBlock.y);

    // Step 5 - Launch kernel
    matrixAddKernel<<<blocksPerGrid, threadsPerBlock>>>(d_A, d_B, d_C, rows, cols);

    // Step 6 - Check for errors
    CUDA_CHECK(cudaGetLastError());
    CUDA_CHECK(cudaDeviceSynchronize());

    // Step 7 - Copy result back
    CUDA_CHECK(cudaMemcpy(h_C, d_C, bytes, cudaMemcpyDeviceToHost));

    // Step 8 - Free device memory
    CUDA_CHECK(cudaFree(d_A));
    CUDA_CHECK(cudaFree(d_B));
    CUDA_CHECK(cudaFree(d_C));
}

/*
 * Helper function to print a small portion of matrix (for debugging)
 */
void printMatrix(const float* matrix, int rows, int cols, const char* name) {
    printf("%s (%dx%d) - first 4x4:\n", name, rows, cols);
    int printRows = (rows < 4) ? rows : 4;
    int printCols = (cols < 4) ? cols : 4;

    for (int i = 0; i < printRows; i++) {
        for (int j = 0; j < printCols; j++) {
            printf("%6.2f ", matrix[i * cols + j]);
        }
        printf("\n");
    }
    printf("\n");
}

/*
 * Main function with testing
 */
int main(int argc, char** argv) {
    // Parse command line arguments
    int rows = 1024;
    int cols = 1024;

    if (argc > 1) rows = atoi(argv[1]);
    if (argc > 2) cols = atoi(argv[2]);

    if (rows <= 0 || cols <= 0) {
        fprintf(stderr, "Invalid matrix dimensions\n");
        return 1;
    }

    printf("Matrix Addition: %d x %d\n", rows, cols);

    // Allocate host memory
    size_t bytes = rows * cols * sizeof(float);
    float* h_A = (float*)malloc(bytes);
    float* h_B = (float*)malloc(bytes);
    float* h_C = (float*)malloc(bytes);

    if (!h_A || !h_B || !h_C) {
        fprintf(stderr, "Failed to allocate host memory\n");
        return 1;
    }

    // Initialize matrices
    printf("Initializing matrices...\n");
    for (int i = 0; i < rows * cols; i++) {
        h_A[i] = (float)rand() / RAND_MAX;
        h_B[i] = (float)rand() / RAND_MAX;
    }

    // Optional: Print small sample for debugging
    // printMatrix(h_A, rows, cols, "Matrix A");
    // printMatrix(h_B, rows, cols, "Matrix B");

    // Perform matrix addition on GPU
    printf("Performing matrix addition on GPU...\n");

    // Timing
    cudaEvent_t start, stop;
    cudaEventCreate(&start);
    cudaEventCreate(&stop);
    cudaEventRecord(start);

    matrixAdd(h_A, h_B, h_C, rows, cols);

    cudaEventRecord(stop);
    cudaEventSynchronize(stop);
    float milliseconds = 0;
    cudaEventElapsedTime(&milliseconds, start, stop);
    printf("Kernel execution time: %.3f ms\n", milliseconds);

    // Calculate bandwidth
    float bandwidth = (3.0f * bytes) / (milliseconds * 1e6);  // GB/s
    printf("Effective bandwidth: %.2f GB/s\n", bandwidth);

    // Verify results
    printf("Verifying results...\n");
    bool success = true;
    int errors = 0;
    const int maxErrors = 10;

    for (int i = 0; i < rows * cols && errors < maxErrors; i++) {
        float expected = h_A[i] + h_B[i];
        float diff = fabs(h_C[i] - expected);
        if (diff > 1e-5) {
            int row = i / cols;
            int col = i % cols;
            fprintf(stderr, "Error at [%d][%d]: expected %.6f, got %.6f\n",
                   row, col, expected, h_C[i]);
            errors++;
            success = false;
        }
    }

    if (success) {
        printf("✓ Verification PASSED\n");
    } else {
        printf("✗ Verification FAILED (%d errors found)\n", errors);
    }

    // Optional: Print result sample
    // printMatrix(h_C, rows, cols, "Result C");

    // Cleanup
    free(h_A);
    free(h_B);
    free(h_C);
    cudaEventDestroy(start);
    cudaEventDestroy(stop);

    return success ? 0 : 1;
}

/*
 * EXPECTED OUTPUT:
 * Matrix Addition: 1024 x 1024
 * Initializing matrices...
 * Performing matrix addition on GPU...
 * Grid: (64, 64) blocks, Block: (16, 16) threads
 * Kernel execution time: ~0.2-1 ms
 * Effective bandwidth: ~200-400 GB/s
 * Verifying results...
 * ✓ Verification PASSED
 *
 * PERFORMANCE EXPERIMENTS:
 * 1. Try different block sizes: (8,8), (16,16), (32,32)
 * 2. Test with non-square matrices: 1024x512, 2048x1024
 * 3. Compare bandwidth with theoretical peak
 * 4. Profile with: nvprof ./02_matrix_addition 1024 1024
 */
