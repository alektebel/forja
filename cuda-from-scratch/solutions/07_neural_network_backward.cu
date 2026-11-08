/*
 * Example 7: Neural Network Backward Pass
 *
 * Implements backpropagation for computing gradients
 *
 * Learning Goals:
 * - Gradient computation via chain rule
 * - Backpropagation algorithm
 * - Weight updates (SGD)
 * - Numerical gradient checking
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
 * Activation derivatives.
 * `output` is the layer's forward output (already passed through ReLU), so
 * the derivative is the forward mask: 1 where the activation was positive,
 * 0 elsewhere. gradOutput is routed through that mask.
 */
__global__ void reluBackward(const float* output, const float* gradOutput,
                              float* gradInput, int size) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < size) {
        // ReLU derivative: 1 if x > 0, else 0
        gradInput[idx] = (output[idx] > 0.0f) ? gradOutput[idx] : 0.0f;
    }
}

__global__ void sigmoidBackward(const float* output, const float* gradOutput,
                                 float* gradInput, int size) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < size) {
        // d/dx sigmoid(x) = sigmoid(x) * (1 - sigmoid(x))
        float s = output[idx];
        gradInput[idx] = gradOutput[idx] * s * (1.0f - s);
    }
}

/*
 * Fully connected layer backward pass.
 *
 * Computes three gradients:
 * 1. gradInput   = gradOutput @ weights^T   [batchSize, inputSize]
 * 2. gradWeights = input^T @ gradOutput     [inputSize, outputSize]
 * 3. gradBias    = rowsum(gradOutput)        [outputSize]
 *
 * One thread per gradInput element and one per gradWeights element; the
 * gradBias column sums use atomicAdd into a host-zeroed buffer. All three
 * loops are grid-stride so any (batch, input, output) size is covered.
 */
__global__ void fullyConnectedBackward(
    const float* input, const float* weights, const float* gradOutput,
    float* gradInput, float* gradWeights, float* gradBias,
    int batchSize, int inputSize, int outputSize) {

    // 1. gradInput = gradOutput @ weights^T
    for (int idx = blockIdx.x * blockDim.x + threadIdx.x;
         idx < batchSize * inputSize;
         idx += blockDim.x * gridDim.x) {
        int b = idx / inputSize;
        int i = idx % inputSize;
        float sum = 0.0f;
        for (int o = 0; o < outputSize; o++)
            sum += gradOutput[b * outputSize + o] * weights[i * outputSize + o];
        gradInput[idx] = sum;
    }

    // 3. gradBias = sum(gradOutput, axis=0)
    for (int idx = blockIdx.x * blockDim.x + threadIdx.x;
         idx < batchSize * outputSize;
         idx += blockDim.x * gridDim.x) {
        int o = idx % outputSize;
        atomicAdd(&gradBias[o], gradOutput[idx]);
    }

    // 2. gradWeights = input^T @ gradOutput
    for (int idx = blockIdx.x * blockDim.x + threadIdx.x;
         idx < inputSize * outputSize;
         idx += blockDim.x * gridDim.x) {
        int i = idx / outputSize;
        int o = idx % outputSize;
        float sum = 0.0f;
        for (int b = 0; b < batchSize; b++)
            sum += input[b * inputSize + i] * gradOutput[b * outputSize + o];
        gradWeights[idx] = sum;
    }
}

/*
 * SGD weight update: weights -= learningRate * gradients
 */
__global__ void sgdUpdate(float* weights, const float* gradients,
                           int size, float learningRate) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < size) {
        weights[idx] -= learningRate * gradients[idx];
    }
}

/* CPU forward: out = input @ weights (row-major, no bias in this test). */
static void cpuForward(const float* in, const float* w, float* out,
                       int bs, int is, int os) {
    for (int b = 0; b < bs; b++)
        for (int o = 0; o < os; o++) {
            float s = 0.0f;
            for (int i = 0; i < is; i++) s += in[b * is + i] * w[i * os + o];
            out[b * os + o] = s;
        }
}

/* CPU reference for all three backward gradients. */
static void cpuBackward(const float* in, const float* w, const float* go,
                        float* gi, float* gw, float* gb,
                        int bs, int is, int os) {
    for (int b = 0; b < bs; b++)
        for (int i = 0; i < is; i++) {
            float s = 0.0f;
            for (int o = 0; o < os; o++) s += go[b * os + o] * w[i * os + o];
            gi[b * is + i] = s;
        }
    for (int i = 0; i < is; i++)
        for (int o = 0; o < os; o++) {
            float s = 0.0f;
            for (int b = 0; b < bs; b++) s += in[b * is + i] * go[b * os + o];
            gw[i * os + o] = s;
        }
    for (int o = 0; o < os; o++) {
        float s = 0.0f;
        for (int b = 0; b < bs; b++) s += go[b * os + o];
        gb[o] = s;
    }
}

/* Mean squared error loss of the linear layer against target.
 * Accumulated in double: the finite-difference ratio (lp - lm) / 2eps
 * suffers catastrophic cancellation if the losses are only float. */
static double mseLoss(const float* in, const float* w, const float* target,
                      int bs, int is, int os) {
    double l = 0.0;
    for (int b = 0; b < bs; b++)
        for (int o = 0; o < os; o++) {
            double s = 0.0;
            for (int i = 0; i < is; i++) s += (double)in[b * is + i] * w[i * os + o];
            double d = s - target[b * os + o];
            l += d * d;
        }
    return l / (bs * os);
}

static float maxAbsDiff(const float* a, const float* b, int n) {
    float m = 0.0f;
    for (int i = 0; i < n; i++) {
        float d = fabsf(a[i] - b[i]);
        if (d > m) m = d;
    }
    return m;
}

int main(int argc, char** argv) {
    printf("Neural Network Backward Pass\n");

    // Small layer so the numerical gradient check is cheap. Batch 13 (odd)
    // exercises the grid-stride bounds handling.
    int bs = 13, is = 7, os = 5;
    if (argc > 1) bs = atoi(argv[1]);
    if (argc > 2) is = atoi(argv[2]);
    if (argc > 3) os = atoi(argv[3]);
    if (bs <= 0 || is <= 0 || os <= 0) {
        fprintf(stderr, "Invalid layer dimensions\n");
        return 1;
    }
    printf("Layer: input(%d) -> output(%d), batch %d\n", is, os, bs);

    int nIn = bs * is, nOut = bs * os, nW = is * os;

    float *in = (float*)malloc(nIn * sizeof(float));
    float *W  = (float*)malloc(nW * sizeof(float));
    float *out = (float*)malloc(nOut * sizeof(float));
    float *target = (float*)malloc(nOut * sizeof(float));
    float *go = (float*)malloc(nOut * sizeof(float));
    float *gi = (float*)malloc(nIn * sizeof(float));
    float *gw = (float*)malloc(nW * sizeof(float));
    float *gb = (float*)malloc(os * sizeof(float));
    float *cgi = (float*)malloc(nIn * sizeof(float));
    float *cgw = (float*)malloc(nW * sizeof(float));
    float *cgb = (float*)malloc(os * sizeof(float));

    for (int i = 0; i < nIn; i++) in[i] = (float)rand() / RAND_MAX;
    for (int i = 0; i < nW; i++)  W[i]  = (float)rand() / RAND_MAX - 0.5f;
    for (int i = 0; i < nOut; i++) target[i] = (float)rand() / RAND_MAX - 0.5f;

    // Forward + dL/dout on the CPU (the layer under test is tiny)
    cpuForward(in, W, out, bs, is, os);
    for (int i = 0; i < nOut; i++)
        go[i] = 2.0f * (out[i] - target[i]) / (float)nOut;

    float *d_in, *d_W, *d_go, *d_gi, *d_gw, *d_gb;
    CUDA_CHECK(cudaMalloc(&d_in, nIn * sizeof(float)));
    CUDA_CHECK(cudaMalloc(&d_W, nW * sizeof(float)));
    CUDA_CHECK(cudaMalloc(&d_go, nOut * sizeof(float)));
    CUDA_CHECK(cudaMalloc(&d_gi, nIn * sizeof(float)));
    CUDA_CHECK(cudaMalloc(&d_gw, nW * sizeof(float)));
    CUDA_CHECK(cudaMalloc(&d_gb, os * sizeof(float)));
    CUDA_CHECK(cudaMemcpy(d_in, in, nIn * sizeof(float), cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(d_W, W, nW * sizeof(float), cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(d_go, go, nOut * sizeof(float), cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemset(d_gb, 0, os * sizeof(float)));   // atomic accumulation

    const int threads = 128;
    int maxIdx = nIn > nW ? nIn : nW;
    if (nOut > maxIdx) maxIdx = nOut;
    int blocks = (maxIdx + threads - 1) / threads;

    cudaEvent_t start, stop;
    cudaEventCreate(&start);
    cudaEventCreate(&stop);
    cudaEventRecord(start);
    fullyConnectedBackward<<<blocks, threads>>>(d_in, d_W, d_go, d_gi, d_gw, d_gb,
                                                bs, is, os);
    CUDA_CHECK(cudaGetLastError());
    CUDA_CHECK(cudaDeviceSynchronize());
    cudaEventRecord(stop);
    cudaEventSynchronize(stop);
    float bwdMs = 0;
    cudaEventElapsedTime(&bwdMs, start, stop);

    CUDA_CHECK(cudaMemcpy(gi, d_gi, nIn * sizeof(float), cudaMemcpyDeviceToHost));
    CUDA_CHECK(cudaMemcpy(gw, d_gw, nW * sizeof(float), cudaMemcpyDeviceToHost));
    CUDA_CHECK(cudaMemcpy(gb, d_gb, os * sizeof(float), cudaMemcpyDeviceToHost));

    // Reference: CPU gradients from the same gradOutput
    cpuBackward(in, W, go, cgi, cgw, cgb, bs, is, os);

    int errors = 0;
    printf("Backward kernel time: %.3f ms\n", bwdMs);
    float d1 = maxAbsDiff(gi, cgi, nIn);
    float d2 = maxAbsDiff(gw, cgw, nW);
    float d3 = maxAbsDiff(gb, cgb, os);
    printf("gradInput   max diff vs CPU: %.3e\n", d1);
    printf("gradWeights max diff vs CPU: %.3e\n", d2);
    printf("gradBias    max diff vs CPU: %.3e\n", d3);
    if (d1 > 1e-4f || d2 > 1e-4f || d3 > 1e-4f) errors++;

    // Numerical gradient check on the weights: central differences on the
    // MSE loss vs the analytic gradWeights. MSE is quadratic in W, so the
    // truncation error of the centered quotient is O(eps^2); losses are
    // summed in double so cancellation in (lp - lm) stays negligible.
    const double eps = 1e-3;
    double worst = 0.0;
    for (int i = 0; i < nW; i++) {
        float saved = W[i];
        W[i] = (float)(saved + eps);
        double lp = mseLoss(in, W, target, bs, is, os);
        W[i] = (float)(saved - eps);
        double lm = mseLoss(in, W, target, bs, is, os);
        W[i] = saved;
        double num = (lp - lm) / (2.0 * eps);
        double scale = fmax(1e-6, fmax(fabs(num), fabs((double)cgw[i])));
        double rel = fabs(num - (double)cgw[i]) / scale;
        if (rel > worst) worst = rel;
    }
    printf("Numerical gradient check: worst relative error %.3e (expect < 1e-3)\n", worst);
    if (worst > 1e-3) errors++;

    // SGD update on device, compared against W - lr * gradWeights
    float lr = 0.1f;
    sgdUpdate<<<(nW + threads - 1) / threads, threads>>>(d_W, d_gw, nW, lr);
    CUDA_CHECK(cudaGetLastError());
    CUDA_CHECK(cudaDeviceSynchronize());
    CUDA_CHECK(cudaMemcpy(gi, d_W, nW * sizeof(float), cudaMemcpyDeviceToHost));
    float d4 = 0.0f;
    for (int i = 0; i < nW; i++) {
        float expect = W[i] - lr * cgw[i];
        float d = fabsf(gi[i] - expect);
        if (d > d4) d4 = d;
    }
    printf("SGD update max diff vs CPU: %.3e\n", d4);
    if (d4 > 1e-5f) errors++;

    // ReLU backward: gradient survives only where the forward output > 0
    float fwd[4]  = {0.0f, 2.0f, -1.0f, 0.5f};   // forward outputs
    float gfwd[4] = {1.0f, 1.0f,  1.0f, 1.0f};   // gradOutput
    float rif[4]  = {0.0f, 0.0f,  0.0f, 0.0f};
    float *d_fwd, *d_gfwd, *d_rif;
    CUDA_CHECK(cudaMalloc(&d_fwd, sizeof(fwd)));
    CUDA_CHECK(cudaMalloc(&d_gfwd, sizeof(gfwd)));
    CUDA_CHECK(cudaMalloc(&d_rif, sizeof(rif)));
    CUDA_CHECK(cudaMemcpy(d_fwd, fwd, sizeof(fwd), cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(d_gfwd, gfwd, sizeof(gfwd), cudaMemcpyHostToDevice));
    reluBackward<<<1, 4>>>(d_fwd, d_gfwd, d_rif, 4);
    CUDA_CHECK(cudaDeviceSynchronize());
    CUDA_CHECK(cudaMemcpy(rif, d_rif, sizeof(rif), cudaMemcpyDeviceToHost));
    float reluExp[4] = {0.0f, 1.0f, 0.0f, 1.0f};
    for (int i = 0; i < 4; i++)
        if (fabsf(rif[i] - reluExp[i]) > 1e-6f) {
            fprintf(stderr, "reluBackward mismatch at %d: %.3f vs %.3f\n",
                    i, rif[i], reluExp[i]);
            errors++;
        }
    CUDA_CHECK(cudaFree(d_fwd)); CUDA_CHECK(cudaFree(d_gfwd)); CUDA_CHECK(cudaFree(d_rif));

    if (errors == 0)
        printf("\xe2\x9c\x93 Verification PASSED\n");
    else
        printf("\xe2\x9c\x97 Verification FAILED\n");

    free(in); free(W); free(out); free(target); free(go);
    free(gi); free(gw); free(gb); free(cgi); free(cgw); free(cgb);
    cudaEventDestroy(start); cudaEventDestroy(stop);
    CUDA_CHECK(cudaFree(d_in)); CUDA_CHECK(cudaFree(d_W)); CUDA_CHECK(cudaFree(d_go));
    CUDA_CHECK(cudaFree(d_gi)); CUDA_CHECK(cudaFree(d_gw)); CUDA_CHECK(cudaFree(d_gb));

    return errors ? 1 : 0;
}
