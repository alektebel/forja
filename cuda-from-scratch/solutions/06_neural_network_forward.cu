/*
 * Example 6: Neural Network Forward Pass
 *
 * Implements forward propagation for a simple neural network
 *
 * Learning Goals:
 * - Matrix-vector operations for neural networks
 * - Activation functions (ReLU, Sigmoid, Tanh)
 * - Batch processing
 * - Layer composition
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

/*
 * Fully connected layer forward pass.
 *
 * Input: [batchSize, inputSize]
 * Weights: [inputSize, outputSize]
 * Bias: [outputSize]
 * Output: [batchSize, outputSize]
 *
 * Computation: output = input @ weights + bias
 *
 * One thread computes one output[b][o] = sum_i input[b][i]*W[i][o] + bias[o].
 * A grid-stride loop handles batch*outputSize of any size (ragged grids safe).
 */
__global__ void fullyConnectedForward(const float* input, const float* weights,
                                       const float* bias, float* output,
                                       int batchSize, int inputSize, int outputSize) {
    int total = batchSize * outputSize;
    for (int idx = blockIdx.x * blockDim.x + threadIdx.x;
         idx < total;
         idx += blockDim.x * gridDim.x) {
        // Output position: (batch index, neuron index)
        int b = idx / outputSize;
        int o = idx % outputSize;

        // Weighted sum over the inputSize dimension
        float sum = 0.0f;
        for (int i = 0; i < inputSize; i++) {
            sum += input[b * inputSize + i] * weights[i * outputSize + o];
        }

        // Add bias, write output
        output[b * outputSize + o] = sum + bias[o];
    }
}

/*
 * Activation functions (element-wise, in place).
 */
__global__ void relu(float* data, int size) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < size) {
        // ReLU: f(x) = max(0, x)
        data[idx] = fmaxf(data[idx], 0.0f);
    }
}

__global__ void sigmoid(float* data, int size) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < size) {
        // Sigmoid: f(x) = 1 / (1 + exp(-x))
        data[idx] = 1.0f / (1.0f + expf(-data[idx]));
    }
}

__global__ void tanhAct(float* data, int size) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < size) {
        // Tanh: f(x) = tanh(x)
        data[idx] = tanhf(data[idx]);
    }
}

/*
 * Host-side pipeline: input (batch x 784) -> FC(128) -> ReLU
 * -> FC(64) -> ReLU -> FC(10). Weights live on device for the duration.
 */
typedef struct {
    float *d_w1, *d_b1, *d_w2, *d_b2, *d_w3, *d_b3;
    float *d_in, *d_a1, *d_a2, *d_out;
} Network;

#define IN 784
#define H1 128
#define H2 64
#define OUT 10

void netCreate(Network* net) {
    CUDA_CHECK(cudaMalloc(&net->d_w1, IN * H1 * sizeof(float)));
    CUDA_CHECK(cudaMalloc(&net->d_b1, H1 * sizeof(float)));
    CUDA_CHECK(cudaMalloc(&net->d_w2, H1 * H2 * sizeof(float)));
    CUDA_CHECK(cudaMalloc(&net->d_b2, H2 * sizeof(float)));
    CUDA_CHECK(cudaMalloc(&net->d_w3, H2 * OUT * sizeof(float)));
    CUDA_CHECK(cudaMalloc(&net->d_b3, OUT * sizeof(float)));
}

void netForward(Network* net, const float* h_input, float* h_output, int batchSize) {
    // Stage activations in device scratch sized for this batch
    CUDA_CHECK(cudaMalloc(&net->d_in,  batchSize * IN  * sizeof(float)));
    CUDA_CHECK(cudaMalloc(&net->d_a1,  batchSize * H1  * sizeof(float)));
    CUDA_CHECK(cudaMalloc(&net->d_a2,  batchSize * H2  * sizeof(float)));
    CUDA_CHECK(cudaMalloc(&net->d_out, batchSize * OUT * sizeof(float)));
    CUDA_CHECK(cudaMemcpy(net->d_in, h_input, batchSize * IN * sizeof(float),
                          cudaMemcpyHostToDevice));

    const int threads = 256;
    int n;

    // Layer 1: FC(784 -> 128) + ReLU
    n = batchSize * H1;
    fullyConnectedForward<<<(n + threads - 1) / threads, threads>>>(
        net->d_in, net->d_w1, net->d_b1, net->d_a1, batchSize, IN, H1);
    relu<<<(n + threads - 1) / threads, threads>>>(net->d_a1, n);

    // Layer 2: FC(128 -> 64) + ReLU
    n = batchSize * H2;
    fullyConnectedForward<<<(n + threads - 1) / threads, threads>>>(
        net->d_a1, net->d_w2, net->d_b2, net->d_a2, batchSize, H1, H2);
    relu<<<(n + threads - 1) / threads, threads>>>(net->d_a2, n);

    // Layer 3: FC(64 -> 10) (logits)
    n = batchSize * OUT;
    fullyConnectedForward<<<(n + threads - 1) / threads, threads>>>(
        net->d_a2, net->d_w3, net->d_b3, net->d_out, batchSize, H2, OUT);

    CUDA_CHECK(cudaGetLastError());
    CUDA_CHECK(cudaDeviceSynchronize());
    CUDA_CHECK(cudaMemcpy(h_output, net->d_out, n * sizeof(float),
                          cudaMemcpyDeviceToHost));

    cudaFree(net->d_in); cudaFree(net->d_a1);
    cudaFree(net->d_a2); cudaFree(net->d_out);
}

/* CPU reference forward pass (same math, sequential order). */
static void cpuLinear(const float* in, const float* w, const float* b,
                      float* out, int bs, int is, int os, int reluAfter) {
    for (int bb = 0; bb < bs; bb++)
        for (int o = 0; o < os; o++) {
            float s = 0.0f;
            for (int i = 0; i < is; i++) s += in[bb * is + i] * w[i * os + o];
            s += b[o];
            if (reluAfter) s = s > 0.0f ? s : 0.0f;
            out[bb * os + o] = s;
        }
}

int main(int argc, char** argv) {
    printf("Neural Network Forward Pass\n");
    printf("Architecture: Input(784) -> FC(128) -> ReLU -> FC(64) -> ReLU -> FC(10)\n");

    int batchSize = 32;
    if (argc > 1) batchSize = atoi(argv[1]);
    if (batchSize <= 0) { fprintf(stderr, "Invalid batch size\n"); return 1; }
    printf("Batch size: %d %s\n", batchSize,
           (batchSize % 16) ? "(ragged)" : "");

    // Host weights: small pseudo-random values
    float *w1 = (float*)malloc(IN * H1 * sizeof(float));
    float *b1 = (float*)malloc(H1 * sizeof(float));
    float *w2 = (float*)malloc(H1 * H2 * sizeof(float));
    float *b2 = (float*)malloc(H2 * sizeof(float));
    float *w3 = (float*)malloc(H2 * OUT * sizeof(float));
    float *b3 = (float*)malloc(OUT * sizeof(float));
    for (int i = 0; i < IN * H1; i++) w1[i] = (float)(rand() % 2000 - 1000) / 100000.0f;
    for (int i = 0; i < H1; i++) b1[i] = (float)(rand() % 2000 - 1000) / 100000.0f;
    for (int i = 0; i < H1 * H2; i++) w2[i] = (float)(rand() % 2000 - 1000) / 100000.0f;
    for (int i = 0; i < H2; i++) b2[i] = (float)(rand() % 2000 - 1000) / 100000.0f;
    for (int i = 0; i < H2 * OUT; i++) w3[i] = (float)(rand() % 2000 - 1000) / 100000.0f;
    for (int i = 0; i < OUT; i++) b3[i] = (float)(rand() % 2000 - 1000) / 100000.0f;

    // Upload weights
    Network net = {0};
    netCreate(&net);
    CUDA_CHECK(cudaMemcpy(net.d_w1, w1, IN * H1 * sizeof(float), cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(net.d_b1, b1, H1 * sizeof(float), cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(net.d_w2, w2, H1 * H2 * sizeof(float), cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(net.d_b2, b2, H2 * sizeof(float), cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(net.d_w3, w3, H2 * OUT * sizeof(float), cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(net.d_b3, b3, OUT * sizeof(float), cudaMemcpyHostToDevice));

    // Input batch in [0,1)
    float* h_in = (float*)malloc(batchSize * IN * sizeof(float));
    float* h_out = (float*)malloc(batchSize * OUT * sizeof(float));
    for (int i = 0; i < batchSize * IN; i++) h_in[i] = (float)rand() / RAND_MAX;

    // GPU forward, timed
    cudaEvent_t start, stop;
    cudaEventCreate(&start);
    cudaEventCreate(&stop);
    cudaEventRecord(start);
    netForward(&net, h_in, h_out, batchSize);
    cudaEventRecord(stop);
    cudaEventSynchronize(stop);
    float ms = 0;
    cudaEventElapsedTime(&ms, start, stop);
    printf("Forward pass (batch %d): %.3f ms\n", batchSize, ms);

    // CPU reference
    float* a1 = (float*)malloc(batchSize * H1 * sizeof(float));
    float* a2 = (float*)malloc(batchSize * H2 * sizeof(float));
    float* c_out = (float*)malloc(batchSize * OUT * sizeof(float));
    cpuLinear(h_in, w1, b1, a1, batchSize, IN, H1, 1);
    cpuLinear(a1, w2, b2, a2, batchSize, H1, H2, 1);
    cpuLinear(a2, w3, b3, c_out, batchSize, H2, OUT, 0);

    int errors = 0;
    float maxDiff = 0.0f;
    for (int i = 0; i < batchSize * OUT; i++) {
        float d = fabsf(h_out[i] - c_out[i]);
        if (d > maxDiff) maxDiff = d;
        if (d > 1e-3f) {
            if (errors < 5)
                fprintf(stderr, "mismatch at %d: cpu %.6f gpu %.6f\n", i, c_out[i], h_out[i]);
            errors++;
        }
    }
    printf("Max abs diff vs CPU: %.3e\n", maxDiff);

    // Also verify the elementwise activation kernels themselves
    float act[4] = {-2.0f, -0.5f, 0.3f, 4.0f};
    float* d_act;
    CUDA_CHECK(cudaMalloc(&d_act, sizeof(act)));
    CUDA_CHECK(cudaMemcpy(d_act, act, sizeof(act), cudaMemcpyHostToDevice));
    relu<<<1, 4>>>(d_act, 4);
    CUDA_CHECK(cudaMemcpy(act, d_act, sizeof(act), cudaMemcpyDeviceToHost));
    float reluExpect[4] = {0.0f, 0.0f, 0.3f, 4.0f};
    for (int i = 0; i < 4; i++)
        if (fabsf(act[i] - reluExpect[i]) > 1e-6f) {
            fprintf(stderr, "relu mismatch at %d: %.6f vs %.6f\n", i, act[i], reluExpect[i]);
            errors++;
        }
    CUDA_CHECK(cudaMemcpy(d_act, act, sizeof(act), cudaMemcpyHostToDevice));
    sigmoid<<<1, 4>>>(d_act, 4);
    CUDA_CHECK(cudaMemcpy(act, d_act, sizeof(act), cudaMemcpyDeviceToHost));
    for (int i = 0; i < 4; i++) {
        float e = 1.0f / (1.0f + expf(-reluExpect[i]));
        if (fabsf(act[i] - e) > 1e-5f) {
            fprintf(stderr, "sigmoid mismatch at %d: %.6f vs %.6f\n", i, act[i], e);
            errors++;
        }
    }
    CUDA_CHECK(cudaFree(d_act));

    if (errors == 0)
        printf("\xe2\x9c\x93 Verification PASSED\n");
    else
        printf("\xe2\x9c\x97 Verification FAILED (%d mismatches)\n", errors);

    free(w1); free(b1); free(w2); free(b2); free(w3); free(b3);
    free(h_in); free(h_out); free(a1); free(a2); free(c_out);
    cudaEventDestroy(start); cudaEventDestroy(stop);
    CUDA_CHECK(cudaFree(net.d_w1)); CUDA_CHECK(cudaFree(net.d_b1));
    CUDA_CHECK(cudaFree(net.d_w2)); CUDA_CHECK(cudaFree(net.d_b2));
    CUDA_CHECK(cudaFree(net.d_w3)); CUDA_CHECK(cudaFree(net.d_b3));

    return errors ? 1 : 0;
}
