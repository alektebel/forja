/*
 * Example 5: 2D Convolution in CUDA
 *
 * Implements 2D image convolution for filtering operations
 *
 * Learning Goals:
 * - Constant memory for filter kernel
 * - Handling boundary conditions
 * - Stencil computations
 * - Shared memory tiling with halos
 */

#include <stdio.h>
#include <stdlib.h>
#include <cuda_runtime.h>
#include <math.h>

#define CUDA_CHECK(call) \
do { \
    cudaError_t err = call; \
    if (err != cudaSuccess) { \
        fprintf(stderr, "CUDA Error at %s:%d - %s\n", __FILE__, __LINE__, \
                cudaGetErrorString(err)); \
        exit(EXIT_FAILURE); \
    } \
} while(0)

#define MAX_FILTER_SIZE 11

// Filter coefficients in constant memory: cached, broadcast when all threads
// in a warp read the same element (which stencil loops do each iteration).
__constant__ float c_filter[MAX_FILTER_SIZE * MAX_FILTER_SIZE];

// Tile of output pixels computed by one block; each block also loads a halo
// of radius r around the tile into shared memory.
#define TILE 16

/*
 * 2D convolution kernel: generic filter stored in constant memory.
 * Each thread computes one output pixel; boundary is handled by clamping
 * (edge pixel repetition). Tile + halo keeps global loads at one per pixel.
 */
__global__ void convolve2D(const float* input, float* output,
                            int width, int height, int filterSize) {
    int r = filterSize / 2;
    // Dynamic shared memory: (TILE + 2r) x (TILE + 2r) tile with halo
    extern __shared__ float tile[];
    int tilePitch = TILE + 2 * r;

    // Tile origin in the image
    int xBase = blockIdx.x * TILE - r;
    int yBase = blockIdx.y * TILE - r;

    // Load tile + halo: threads cover (TILE+2r)^2 positions
    for (int i = threadIdx.y * TILE + threadIdx.x;
         i < tilePitch * tilePitch;
         i += TILE * TILE) {
        int ty = i / tilePitch;
        int tx = i % tilePitch;
        // Clamp coordinates for halo pixels that fall off the image edge
        int gy = yBase + ty;
        int gx = xBase + tx;
        gy = (gy < 0) ? 0 : (gy >= height ? height - 1 : gy);
        gx = (gx < 0) ? 0 : (gx >= width ? width - 1 : gx);
        tile[ty * tilePitch + tx] = input[gy * width + gx];
    }
    __syncthreads();

    // One output pixel per thread
    int x = blockIdx.x * TILE + threadIdx.x;
    int y = blockIdx.y * TILE + threadIdx.y;
    if (x < width && y < height) {
        float sum = 0.0f;
        for (int fy = 0; fy < filterSize; fy++) {
            for (int fx = 0; fx < filterSize; fx++) {
                // tile is offset by -r, so image (y+fy-r, x+fx-r) is at
                // (fy, fx) inside the padded tile
                sum += tile[(fy + threadIdx.y) * tilePitch + (fx + threadIdx.x)]
                     * c_filter[fy * filterSize + fx];
            }
        }
        output[y * width + x] = sum;
    }
}

/*
 * Gaussian blur, 5x5 binomial kernel (outer product of [1 4 6 4 1], /256).
 * Direct 2D form: one mechanism, tiled with halo, clamped boundaries.
 */
__global__ void gaussianBlur5x5(const float* input, float* output,
                                 int width, int height) {
    const int r = 2;
    __shared__ float tile[(TILE + 2 * r) * (TILE + 2 * r)];
    const int tilePitch = TILE + 2 * r;

    int xBase = blockIdx.x * TILE - r;
    int yBase = blockIdx.y * TILE - r;

    // Cooperative load of tile + halo (clamped at image edges)
    for (int i = threadIdx.y * TILE + threadIdx.x;
         i < tilePitch * tilePitch;
         i += TILE * TILE) {
        int ty = i / tilePitch;
        int tx = i % tilePitch;
        int gy = yBase + ty, gx = xBase + tx;
        gy = (gy < 0) ? 0 : (gy >= height ? height - 1 : gy);
        gx = (gx < 0) ? 0 : (gx >= width ? width - 1 : gx);
        tile[ty * tilePitch + tx] = input[gy * width + gx];
    }
    __syncthreads();

    int x = blockIdx.x * TILE + threadIdx.x;
    int y = blockIdx.y * TILE + threadIdx.y;
    if (x < width && y < height) {
        // Integer weights sum to 256; divide once at the end
        const int w[5] = {1, 4, 6, 4, 1};
        int sum = 0;
        for (int fy = 0; fy < 5; fy++) {
            for (int fx = 0; fx < 5; fx++) {
                sum += (int)lroundf(tile[(fy + threadIdx.y) * tilePitch +
                                          (fx + threadIdx.x)])
                     * w[fy] * w[fx];
            }
        }
        output[y * width + x] = (float)sum / 256.0f;
    }
}

/*
 * Sobel edge magnitude. Integer-exact: image pixels are integers 0..255,
 * gradients gx, gy are computed in int (|g| <= 1020), magnitude uses
 * sqrt(gx*gx + gy*gy) whose argument fits exactly in a float.
 * No atomics: each thread writes only its own output pixel.
 */
__global__ void sobelEdge(const float* input, float* output,
                           int width, int height) {
    const int r = 1;
    __shared__ float tile[(TILE + 2 * r) * (TILE + 2 * r)];
    const int tilePitch = TILE + 2 * r;

    int xBase = blockIdx.x * TILE - r;
    int yBase = blockIdx.y * TILE - r;

    for (int i = threadIdx.y * TILE + threadIdx.x;
         i < tilePitch * tilePitch;
         i += TILE * TILE) {
        int ty = i / tilePitch;
        int tx = i % tilePitch;
        int gy = yBase + ty, gx = xBase + tx;
        gy = (gy < 0) ? 0 : (gy >= height ? height - 1 : gy);
        gx = (gx < 0) ? 0 : (gx >= width ? width - 1 : gx);
        tile[ty * tilePitch + tx] = input[gy * width + gx];
    }
    __syncthreads();

    int x = blockIdx.x * TILE + threadIdx.x;
    int y = blockIdx.y * TILE + threadIdx.y;
    if (x < width && y < height) {
        // Shared-memory neighborhood, integerized
        int p[3][3];
        for (int j = 0; j < 3; j++)
            for (int i = 0; i < 3; i++)
                p[j][i] = (int)lroundf(tile[(j + threadIdx.y) * tilePitch +
                                              (i + threadIdx.x)]);
        // gx: [-1 0 1; -2 0 2; -1 0 1], gy: transpose
        int gX = (p[0][2] - p[0][0]) + 2 * (p[1][2] - p[1][0]) + (p[2][2] - p[2][0]);
        int gY = (p[2][0] - p[0][0]) + 2 * (p[2][1] - p[0][1]) + (p[2][2] - p[0][2]);
        output[y * width + x] = sqrtf((float)(gX * gX + gY * gY));
    }
}

/*
 * Sharpening: 3x3 kernel [0 -1 0; -1 5 -1; 0 -1 0], tiled with halo,
 * clamped boundaries.
 */
__global__ void sharpen3x3(const float* input, float* output,
                            int width, int height) {
    const int r = 1;
    __shared__ float tile[(TILE + 2 * r) * (TILE + 2 * r)];
    const int tilePitch = TILE + 2 * r;

    int xBase = blockIdx.x * TILE - r;
    int yBase = blockIdx.y * TILE - r;

    for (int i = threadIdx.y * TILE + threadIdx.x;
         i < tilePitch * tilePitch;
         i += TILE * TILE) {
        int ty = i / tilePitch;
        int tx = i % tilePitch;
        int gy = yBase + ty, gx = xBase + tx;
        gy = (gy < 0) ? 0 : (gy >= height ? height - 1 : gy);
        gx = (gx < 0) ? 0 : (gx >= width ? width - 1 : gx);
        tile[ty * tilePitch + tx] = input[gy * width + gx];
    }
    __syncthreads();

    int x = blockIdx.x * TILE + threadIdx.x;
    int y = blockIdx.y * TILE + threadIdx.y;
    if (x < width && y < height) {
        int c = (int)lroundf(tile[(1 + threadIdx.y) * tilePitch + (1 + threadIdx.x)]);
        int n = (int)lroundf(tile[(threadIdx.y) * tilePitch + (1 + threadIdx.x)])
              + (int)lroundf(tile[(2 + threadIdx.y) * tilePitch + (1 + threadIdx.x)])
              + (int)lroundf(tile[(1 + threadIdx.y) * tilePitch + (threadIdx.x)])
              + (int)lroundf(tile[(1 + threadIdx.y) * tilePitch + (2 + threadIdx.x)]);
        output[y * width + x] = (float)(5 * c - n);
    }
}

/* CPU reference: generic odd-size convolution with clamped boundaries. */
void convolve2D_cpu(const float* input, float* output,
                    int width, int height, const float* filter, int filterSize) {
    int r = filterSize / 2;
    for (int y = 0; y < height; y++) {
        for (int x = 0; x < width; x++) {
            float sum = 0.0f;
            for (int fy = 0; fy < filterSize; fy++) {
                for (int fx = 0; fx < filterSize; fx++) {
                    int gy = y + fy - r, gx = x + fx - r;
                    if (gy < 0) gy = 0;
                    if (gy >= height) gy = height - 1;
                    if (gx < 0) gx = 0;
                    if (gx >= width) gx = width - 1;
                    sum += input[gy * width + gx] * filter[fy * filterSize + fx];
                }
            }
            output[y * width + x] = sum;
        }
    }
}

static int compare(const float* a, const float* b, int n, float tol, const char* name) {
    int errors = 0;
    for (int i = 0; i < n; i++) {
        if (fabsf(a[i] - b[i]) > tol) {
            if (errors < 5)
                fprintf(stderr, "%s mismatch at %d: cpu %.4f gpu %.4f\n",
                        name, i, b[i], a[i]);
            errors++;
        }
    }
    printf("%s: %s\n", name, errors ? "FAILED" : "OK");
    return errors;
}

int main(int argc, char** argv) {
    printf("2D Convolution Example\n");

    int width = 512, height = 512;   // image size
    int ragged = 0;                  // set to use a non-multiple-of-TILE size
    if (argc > 1) width = atoi(argv[1]);
    if (argc > 2) height = atoi(argv[2]);
    if (argc > 3) ragged = atoi(argv[3]);
    if (ragged) { width = 101; height = 37; }   // neither is a multiple of TILE
    if (width <= 0 || height <= 0) {
        fprintf(stderr, "Invalid image dimensions\n");
        return 1;
    }

    printf("Image: %d x %d (%s)\n", width, height,
           (width % TILE || height % TILE) ? "ragged" : "tiled");

    size_t bytes = width * height * sizeof(float);
    float* h_input = (float*)malloc(bytes);
    float *h_gauss = (float*)malloc(bytes), *h_sobel = (float*)malloc(bytes);
    float *h_sharp = (float*)malloc(bytes), *h_gen = (float*)malloc(bytes);
    float *c_gauss = (float*)malloc(bytes), *c_sobel = (float*)malloc(bytes);
    float *c_sharp = (float*)malloc(bytes), *c_gen = (float*)malloc(bytes);
    if (!h_input || !h_gauss || !h_sobel || !h_sharp || !h_gen ||
        !c_gauss || !c_sobel || !c_sharp || !c_gen) {
        fprintf(stderr, "Failed to allocate host memory\n");
        return 1;
    }

    // Integer gray levels keep Sobel/Gaussian/sharpen arithmetic exact
    for (int i = 0; i < width * height; i++)
        h_input[i] = (float)(rand() % 256);

    float* d_input; float* d_output;
    CUDA_CHECK(cudaMalloc(&d_input, bytes));
    CUDA_CHECK(cudaMalloc(&d_output, bytes));
    CUDA_CHECK(cudaMemcpy(d_input, h_input, bytes, cudaMemcpyHostToDevice));

    dim3 block(TILE, TILE);
    dim3 grid((width + TILE - 1) / TILE, (height + TILE - 1) / TILE);
    cudaEvent_t start, stop;
    cudaEventCreate(&start);
    cudaEventCreate(&stop);

    // 1) Gaussian blur 5x5
    float gaussMs = 0;
    cudaEventRecord(start);
    gaussianBlur5x5<<<grid, block>>>(d_input, d_output, width, height);
    cudaEventRecord(stop);
    cudaEventSynchronize(stop);
    CUDA_CHECK(cudaGetLastError());
    cudaEventElapsedTime(&gaussMs, start, stop);
    CUDA_CHECK(cudaMemcpy(h_gauss, d_output, bytes, cudaMemcpyDeviceToHost));

    // 2) Sobel edge magnitude
    float sobelMs = 0;
    cudaEventRecord(start);
    sobelEdge<<<grid, block>>>(d_input, d_output, width, height);
    cudaEventRecord(stop);
    cudaEventSynchronize(stop);
    CUDA_CHECK(cudaGetLastError());
    cudaEventElapsedTime(&sobelMs, start, stop);
    CUDA_CHECK(cudaMemcpy(h_sobel, d_output, bytes, cudaMemcpyDeviceToHost));

    // 3) Sharpening
    float sharpMs = 0;
    cudaEventRecord(start);
    sharpen3x3<<<grid, block>>>(d_input, d_output, width, height);
    cudaEventRecord(stop);
    cudaEventSynchronize(stop);
    CUDA_CHECK(cudaGetLastError());
    cudaEventElapsedTime(&sharpMs, start, stop);
    CUDA_CHECK(cudaMemcpy(h_sharp, d_output, bytes, cudaMemcpyDeviceToHost));

    // 4) Generic constant-memory convolution with a random 5x5 filter
    float genFilter[5 * 5];
    for (int i = 0; i < 25; i++) genFilter[i] = (float)(rand() % 9 - 4);
    CUDA_CHECK(cudaMemcpyToSymbol(c_filter, genFilter, sizeof(genFilter)));
    int r = 2, tilePitch = TILE + 2 * r;
    size_t sharedBytes = tilePitch * tilePitch * sizeof(float);
    float genMs = 0;
    cudaEventRecord(start);
    convolve2D<<<grid, block, sharedBytes>>>(d_input, d_output, width, height, 5);
    cudaEventRecord(stop);
    cudaEventSynchronize(stop);
    CUDA_CHECK(cudaGetLastError());
    cudaEventElapsedTime(&genMs, start, stop);
    CUDA_CHECK(cudaMemcpy(h_gen, d_output, bytes, cudaMemcpyDeviceToHost));

    printf("Kernel times: gaussian %.3f ms, sobel %.3f ms, sharpen %.3f ms, generic %.3f ms\n",
           gaussMs, sobelMs, sharpMs, genMs);

    // CPU references
    const float kw[5] = {1, 4, 6, 4, 1};
    float kf[5 * 5];
    for (int j = 0; j < 5; j++)
        for (int i = 0; i < 5; i++)
            kf[j * 5 + i] = kw[j] * kw[i] / 256.0f;
    convolve2D_cpu(h_input, c_gauss, width, height, kf, 5);

    int sf[3][3] = {{-1, 0, 1}, {-2, 0, 2}, {-1, 0, 1}};
    for (int y = 0; y < height; y++) {
        for (int x = 0; x < width; x++) {
            int gX = 0, gY = 0;
            for (int j = 0; j < 3; j++) {
                for (int i = 0; i < 3; i++) {
                    int gy = y + j - 1, gx = x + i - 1;
                    if (gy < 0) gy = 0;
                    if (gy >= height) gy = height - 1;
                    if (gx < 0) gx = 0;
                    if (gx >= width) gx = width - 1;
                    int p = (int)lroundf(h_input[gy * width + gx]);
                    gX += sf[j][i] * p;      // x-gradient
                    gY += sf[i][j] * p;      // y-gradient (transposed)
                }
            }
            c_sobel[y * width + x] = sqrtf((float)(gX * gX + gY * gY));
        }
    }

    const float sharpenF[3][3] = {{0, -1, 0}, {-1, 5, -1}, {0, -1, 0}};
    convolve2D_cpu(h_input, c_sharp, width, height, &sharpenF[0][0], 3);
    convolve2D_cpu(h_input, c_gen, width, height, genFilter, 5);

    // Verify GPU vs CPU
    int errors = 0;
    errors += compare(h_gauss, c_gauss, width * height, 1e-4f, "Gaussian blur");
    errors += compare(h_sobel, c_sobel, width * height, 1e-4f, "Sobel edges");
    errors += compare(h_sharp, c_sharp, width * height, 1e-4f, "Sharpening");
    errors += compare(h_gen, c_gen, width * height, 1e-4f, "Generic conv (constant filter)");

    if (errors == 0) {
        printf("\xe2\x9c\x93 Verification PASSED\n");
    } else {
        printf("\xe2\x9c\x97 Verification FAILED (%d mismatches)\n", errors);
    }

    free(h_input); free(h_gauss); free(h_sobel); free(h_sharp); free(h_gen);
    free(c_gauss); free(c_sobel); free(c_sharp); free(c_gen);
    CUDA_CHECK(cudaFree(d_input));
    CUDA_CHECK(cudaFree(d_output));
    cudaEventDestroy(start);
    cudaEventDestroy(stop);

    return errors ? 1 : 0;
}

/*
 * IMPLEMENTATION STEPS (done):
 * 1. Load filter into constant memory (cudaMemcpyToSymbol)
 * 2. Implement basic convolution kernel
 * 3. Add boundary handling (clamp/edge replication)
 * 4. Optimize with shared memory tiling + halo
 * 5. Test with different filter sizes and ragged image sizes
 */
