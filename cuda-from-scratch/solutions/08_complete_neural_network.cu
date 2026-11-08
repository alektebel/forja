/*
 * Example 8: Complete Neural Network from Scratch
 *
 * Full implementation of a trainable neural network in CUDA
 * Trains on MNIST dataset to classify handwritten digits
 *
 * Learning Goals:
 * - End-to-end training pipeline
 * - Loss functions (Cross-entropy)
 * - Mini-batch training
 * - Model evaluation
 * - Real dataset handling
 *
 * Architecture:
 * Input (784) -> FC(128) -> ReLU -> FC(64) -> ReLU -> FC(10) -> Softmax
 *
 * Target: >95% accuracy on MNIST test set
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
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

#define IN 784
#define H1 128
#define H2 64
#define NC 10
#define THREADS 256
#define BLOCKS_FOR(n) (((n) + THREADS - 1) / THREADS)

/* ---------------------------------------------------------------- kernels */

/*
 * Fully connected layer forward: out = in @ W + b
 * Input [batchSize, inputSize], Weights [inputSize, outputSize],
 * Bias [outputSize], Output [batchSize, outputSize]. Grid-stride loop.
 */
__global__ void fullyConnectedForward(const float* input, const float* weights,
                                       const float* bias, float* output,
                                       int batchSize, int inputSize, int outputSize) {
    int total = batchSize * outputSize;
    for (int idx = blockIdx.x * blockDim.x + threadIdx.x;
         idx < total;
         idx += blockDim.x * gridDim.x) {
        int b = idx / outputSize;
        int o = idx % outputSize;
        float sum = 0.0f;
        for (int i = 0; i < inputSize; i++)
            sum += input[b * inputSize + i] * weights[i * outputSize + o];
        output[b * outputSize + o] = sum + bias[o];
    }
}

/* ReLU (in place): f(x) = max(0, x) */
__global__ void relu(float* data, int size) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < size) data[idx] = fmaxf(data[idx], 0.0f);
}

/*
 * ReLU backward: route the gradient only where the forward output > 0.
 * `output` here holds the post-ReLU activations (0 at dead units).
 */
__global__ void reluBackward(const float* output, const float* gradOutput,
                              float* gradInput, int size) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < size)
        gradInput[idx] = (output[idx] > 0.0f) ? gradOutput[idx] : 0.0f;
}

/*
 * Fully connected layer backward:
 * gradInput = gradOutput @ W^T, gradWeights = in^T @ gradOutput,
 * gradBias = column sums of gradOutput (atomicAdd into a zeroed buffer).
 */
__global__ void fullyConnectedBackward(
    const float* input, const float* weights, const float* gradOutput,
    float* gradInput, float* gradWeights, float* gradBias,
    int batchSize, int inputSize, int outputSize) {

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

    for (int idx = blockIdx.x * blockDim.x + threadIdx.x;
         idx < batchSize * outputSize;
         idx += blockDim.x * gridDim.x) {
        int o = idx % outputSize;
        atomicAdd(&gradBias[o], gradOutput[idx]);
    }

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

/* SGD update: w -= lr * g */
__global__ void sgdUpdate(float* weights, const float* gradients,
                           int size, float learningRate) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < size) weights[idx] -= learningRate * gradients[idx];
}

/*
 * Softmax, row-wise. One block per sample; blockDim.x must be a power of 2
 * >= numClasses. Block tree reduction for max (stability) then sum.
 */
__global__ void softmax(float* data, int batchSize, int numClasses) {
    int row = blockIdx.x;
    if (row >= batchSize) return;
    float* x = data + (size_t)row * numClasses;
    int tid = threadIdx.x;
    int nthr = blockDim.x;

    extern __shared__ float s[];              // nthr floats
    float v = (tid < numClasses) ? x[tid] : -INFINITY;

    // Reduce max across the block
    s[tid] = v;
    __syncthreads();
    for (int stride = nthr / 2; stride > 0; stride >>= 1) {
        if (tid < stride)
            s[tid] = fmaxf(s[tid], s[tid + stride]);
        __syncthreads();
    }
    float m = s[0];

    // Exponentiate, then reduce sum across the block
    float e = (tid < numClasses) ? expf(v - m) : 0.0f;
    s[tid] = e;
    __syncthreads();
    for (int stride = nthr / 2; stride > 0; stride >>= 1) {
        if (tid < stride)
            s[tid] += s[tid + stride];
        __syncthreads();
    }
    float sum = s[0];

    if (tid < numClasses) x[tid] = e / sum;
}

/*
 * Cross-entropy loss: loss += -log(predictions[label]) per sample.
 * `loss` (and, for the softmax path, nothing else) must be zeroed first;
 * the result is the SUM over the batch, mean is taken by the caller.
 */
__global__ void crossEntropyLoss(const float* predictions, const int* labels,
                                   float* loss, int batchSize, int numClasses) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < batchSize) {
        float p = predictions[(size_t)idx * numClasses + labels[idx]];
        if (p < 1e-12f) p = 1e-12f;
        atomicAdd(loss, -logf(p));
    }
}

/*
 * Gradient of the MEAN cross-entropy w.r.t. softmax predictions:
 * grad = (predictions - one_hot(labels)) / batchSize
 */
__global__ void crossEntropyGradient(const float* predictions, const int* labels,
                                       float* gradPredictions,
                                       int batchSize, int numClasses) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < batchSize * numClasses) {
        int row = idx / numClasses;
        int c = idx % numClasses;
        float onehot = (c == labels[row]) ? 1.0f : 0.0f;
        gradPredictions[idx] = (predictions[idx] - onehot) / (float)batchSize;
    }
}

/* Gather shuffled rows from the full dataset into a contiguous batch. */
__global__ void gatherBatch(const float* data, const int* rows,
                             float* out, int batch, int rowLen) {
    int total = batch * rowLen;
    for (int idx = blockIdx.x * blockDim.x + threadIdx.x;
         idx < total;
         idx += blockDim.x * gridDim.x) {
        int r = idx / rowLen;
        out[idx] = data[(size_t)rows[r] * rowLen + (idx % rowLen)];
    }
}

__global__ void gatherInts(const int* data, const int* rows, int* out, int batch) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < batch) out[idx] = data[rows[idx]];
}

/* Argmax accuracy: one thread per sample, atomic count of correct. */
__global__ void argmaxAccuracy(const float* predictions, const int* labels,
                                int* correct, int batchSize, int numClasses) {
    int row = blockIdx.x * blockDim.x + threadIdx.x;
    if (row < batchSize) {
        const float* p = predictions + (size_t)row * numClasses;
        int best = 0;
        for (int c = 1; c < numClasses; c++)
            if (p[c] > p[best]) best = c;
        if (best == labels[row]) atomicAdd(correct, 1);
    }
}

/* ------------------------------------------------------------ host model */

typedef struct {
    // device weights
    float *W1, *B1, *W2, *B2, *W3, *B3;
    // device gradients
    float *gW1, *gB1, *gW2, *gB2, *gW3, *gB3;
    // batch-sized scratch
    int maxBatch;
    float *in, *a1, *a2, *probs, *logits;
    float *gi1, *ga1, *gi2, *ga2, *gLogits;
    int *dRows, *dBatchLabels;
    float* dLoss;      // accumulated on-device loss (per epoch)
    int* dCorrect;     // eval counter
} Net;

static void netAlloc(Net* n, int maxBatch) {
    n->maxBatch = maxBatch;
    size_t f = sizeof(float);
    CUDA_CHECK(cudaMalloc(&n->W1, IN * H1 * f)); CUDA_CHECK(cudaMalloc(&n->B1, H1 * f));
    CUDA_CHECK(cudaMalloc(&n->W2, H1 * H2 * f)); CUDA_CHECK(cudaMalloc(&n->B2, H2 * f));
    CUDA_CHECK(cudaMalloc(&n->W3, H2 * NC * f)); CUDA_CHECK(cudaMalloc(&n->B3, NC * f));
    CUDA_CHECK(cudaMalloc(&n->gW1, IN * H1 * f)); CUDA_CHECK(cudaMalloc(&n->gB1, H1 * f));
    CUDA_CHECK(cudaMalloc(&n->gW2, H1 * H2 * f)); CUDA_CHECK(cudaMalloc(&n->gB2, H2 * f));
    CUDA_CHECK(cudaMalloc(&n->gW3, H2 * NC * f)); CUDA_CHECK(cudaMalloc(&n->gB3, NC * f));
    CUDA_CHECK(cudaMalloc(&n->in,     (size_t)maxBatch * IN * f));
    CUDA_CHECK(cudaMalloc(&n->a1,     (size_t)maxBatch * H1 * f));
    CUDA_CHECK(cudaMalloc(&n->a2,     (size_t)maxBatch * H2 * f));
    CUDA_CHECK(cudaMalloc(&n->logits, (size_t)maxBatch * NC * f));
    CUDA_CHECK(cudaMalloc(&n->probs,  (size_t)maxBatch * NC * f));
    CUDA_CHECK(cudaMalloc(&n->gi1,    (size_t)maxBatch * IN * f));
    CUDA_CHECK(cudaMalloc(&n->ga1,    (size_t)maxBatch * H1 * f));
    CUDA_CHECK(cudaMalloc(&n->gi2,    (size_t)maxBatch * H2 * f));
    CUDA_CHECK(cudaMalloc(&n->ga2,    (size_t)maxBatch * H2 * f));
    CUDA_CHECK(cudaMalloc(&n->gLogits, (size_t)maxBatch * NC * f));
    CUDA_CHECK(cudaMalloc(&n->dRows,  maxBatch * sizeof(int)));
    CUDA_CHECK(cudaMalloc(&n->dBatchLabels, maxBatch * sizeof(int)));
    CUDA_CHECK(cudaMalloc(&n->dLoss, sizeof(float)));
    CUDA_CHECK(cudaMalloc(&n->dCorrect, sizeof(int)));
}

/* Init: He-style U(-a, a) with a = sqrt(6/(fanIn+fanOut)); zero biases. */
static void netInit(Net* n) {
    float* h = (float*)malloc((size_t)IN * H1 * sizeof(float));
    int sizes[3][2] = {{IN, H1}, {H1, H2}, {H2, NC}};
    float* dsts[3] = {n->W1, n->W2, n->W3};
    for (int l = 0; l < 3; l++) {
        int is = sizes[l][0], os = sizes[l][1];
        float a = sqrtf(6.0f / (is + os));
        for (int i = 0; i < is * os; i++)
            h[i] = (2.0f * ((float)rand() / RAND_MAX) - 1.0f) * a;
        CUDA_CHECK(cudaMemcpy(dsts[l], h, (size_t)is * os * sizeof(float),
                              cudaMemcpyHostToDevice));
    }
    CUDA_CHECK(cudaMemset(n->B1, 0, H1 * sizeof(float)));
    CUDA_CHECK(cudaMemset(n->B2, 0, H2 * sizeof(float)));
    CUDA_CHECK(cudaMemset(n->B3, 0, NC * sizeof(float)));
    free(h);
}

/* Forward one batch already resident in n->in; fills n->probs (softmax). */
static void forwardBatch(Net* n, int batch, int withSoftmax) {
    fullyConnectedForward<<<BLOCKS_FOR(batch * H1), THREADS>>>(
        n->in, n->W1, n->B1, n->a1, batch, IN, H1);
    relu<<<BLOCKS_FOR(batch * H1), THREADS>>>(n->a1, batch * H1);
    fullyConnectedForward<<<BLOCKS_FOR(batch * H2), THREADS>>>(
        n->a1, n->W2, n->B2, n->a2, batch, H1, H2);
    relu<<<BLOCKS_FOR(batch * H2), THREADS>>>(n->a2, batch * H2);
    fullyConnectedForward<<<BLOCKS_FOR(batch * NC), THREADS>>>(
        n->a2, n->W3, n->B3, n->logits, batch, H2, NC);
    if (withSoftmax) {
        CUDA_CHECK(cudaMemcpyAsync(n->probs, n->logits,
                                   (size_t)batch * NC * sizeof(float),
                                   cudaMemcpyDeviceToDevice));
        softmax<<<batch, 16, 16 * sizeof(float)>>>(n->probs, batch, NC);
    }
    CUDA_CHECK(cudaGetLastError());
}

/*
 * Evaluation: forward the whole dataset in chunks of maxBatch (contiguous,
 * identity row mapping) and argmax against the labels. Accuracy in percent.
 */
float evaluate(Net* n, const float* d_images, const int* d_labels, int numImages) {
    // identity row map for chunked streaming
    int* hRows = (int*)malloc(n->maxBatch * sizeof(int));
    for (int r = 0; r < n->maxBatch; r++) hRows[r] = r;
    CUDA_CHECK(cudaMemcpy(n->dRows, hRows, n->maxBatch * sizeof(int),
                          cudaMemcpyHostToDevice));
    free(hRows);

    int correct = 0, done = 0;
    while (done < numImages) {
        int batch = numImages - done;
        if (batch > n->maxBatch) batch = n->maxBatch;

        gatherBatch<<<BLOCKS_FOR(batch * IN), THREADS>>>(
            d_images + (size_t)done * IN, n->dRows, n->in, batch, IN);
        forwardBatch(n, batch, 1);
        CUDA_CHECK(cudaMemsetAsync(n->dCorrect, 0, sizeof(int)));
        argmaxAccuracy<<<BLOCKS_FOR(batch), THREADS>>>(
            n->probs, d_labels + done, n->dCorrect, batch, NC);
        CUDA_CHECK(cudaGetLastError());
        CUDA_CHECK(cudaDeviceSynchronize());
        int c;
        CUDA_CHECK(cudaMemcpy(&c, n->dCorrect, sizeof(int), cudaMemcpyDeviceToHost));
        correct += c;
        done += batch;
    }
    return 100.0f * (float)correct / (float)numImages;
}

/*
 * Training loop: numEpochs passes over the mini-batches (Fisher-Yates
 * shuffle each epoch). Per batch: gather -> forward -> loss -> backward
 * (chain rule through all 3 layers) -> SGD. Loss is accumulated on device
 * to avoid a host sync per batch. Prints per-epoch stats incl. test acc.
 */
void train(Net* n, const float* d_trainImages, const int* d_trainLabels,
           int numTrain, const float* d_testImages, const int* d_testLabels,
           int numTest, int batch, int numEpochs, float learningRate) {
    int* perm = (int*)malloc((size_t)numTrain * sizeof(int));
    for (int i = 0; i < numTrain; i++) perm[i] = i;

    cudaEvent_t evStart, evStop;
    cudaEventCreate(&evStart);
    cudaEventCreate(&evStop);

    for (int epoch = 0; epoch < numEpochs; epoch++) {
        for (int i = numTrain - 1; i > 0; i--) {
            int j = rand() % (i + 1);
            int t = perm[i]; perm[i] = perm[j]; perm[j] = t;
        }

        cudaEventRecord(evStart);
        CUDA_CHECK(cudaMemsetAsync(n->dLoss, 0, sizeof(float)));
        int nb = (numTrain + batch - 1) / batch;
        for (int b = 0; b < nb; b++) {
            int thisBatch = numTrain - b * batch;
            if (thisBatch > batch) thisBatch = batch;

            // batch's shuffled row indices + gathered data
            CUDA_CHECK(cudaMemcpy(n->dRows, perm + (size_t)b * batch,
                                  thisBatch * sizeof(int), cudaMemcpyHostToDevice));
            gatherBatch<<<BLOCKS_FOR(thisBatch * IN), THREADS>>>(
                d_trainImages, n->dRows, n->in, thisBatch, IN);
            gatherInts<<<BLOCKS_FOR(thisBatch), THREADS>>>(
                d_trainLabels, n->dRows, n->dBatchLabels, thisBatch);

            // forward + loss
            forwardBatch(n, thisBatch, 1);
            crossEntropyLoss<<<BLOCKS_FOR(thisBatch), THREADS>>>(
                n->probs, n->dBatchLabels, n->dLoss, thisBatch, NC);

            // backward: loss gradient -> layer 3 -> relu -> layer 2 -> relu -> layer 1
            crossEntropyGradient<<<BLOCKS_FOR(thisBatch * NC), THREADS>>>(
                n->probs, n->dBatchLabels, n->gLogits, thisBatch, NC);
            CUDA_CHECK(cudaMemsetAsync(n->gB1, 0, H1 * sizeof(float)));
            CUDA_CHECK(cudaMemsetAsync(n->gB2, 0, H2 * sizeof(float)));
            CUDA_CHECK(cudaMemsetAsync(n->gB3, 0, NC * sizeof(float)));
            fullyConnectedBackward<<<BLOCKS_FOR(thisBatch * IN), THREADS>>>(
                n->a2, n->W3, n->gLogits, n->gi2, n->gW3, n->gB3,
                thisBatch, H2, NC);
            reluBackward<<<BLOCKS_FOR(thisBatch * H2), THREADS>>>(
                n->a2, n->gi2, n->ga2, thisBatch * H2);
            fullyConnectedBackward<<<BLOCKS_FOR(thisBatch * H1), THREADS>>>(
                n->a1, n->W2, n->ga2, n->gi1, n->gW2, n->gB2,
                thisBatch, H1, H2);
            reluBackward<<<BLOCKS_FOR(thisBatch * H1), THREADS>>>(
                n->a1, n->gi1, n->ga1, thisBatch * H1);
            // gradInput of layer 1 is unused: safe to overwrite gi1 (its
            // values were already consumed into ga1 by the kernel above)
            fullyConnectedBackward<<<BLOCKS_FOR(thisBatch * IN), THREADS>>>(
                n->in, n->W1, n->ga1, n->gi1, n->gW1, n->gB1,
                thisBatch, IN, H1);

            // SGD step on all weights and biases
            sgdUpdate<<<BLOCKS_FOR(IN * H1), THREADS>>>(n->W1, n->gW1, IN * H1, learningRate);
            sgdUpdate<<<BLOCKS_FOR(H1), THREADS>>>(n->B1, n->gB1, H1, learningRate);
            sgdUpdate<<<BLOCKS_FOR(H1 * H2), THREADS>>>(n->W2, n->gW2, H1 * H2, learningRate);
            sgdUpdate<<<BLOCKS_FOR(H2), THREADS>>>(n->B2, n->gB2, H2, learningRate);
            sgdUpdate<<<BLOCKS_FOR(H2 * NC), THREADS>>>(n->W3, n->gW3, H2 * NC, learningRate);
            sgdUpdate<<<BLOCKS_FOR(NC), THREADS>>>(n->B3, n->gB3, NC, learningRate);
        }
        cudaEventRecord(evStop);
        CUDA_CHECK(cudaGetLastError());
        CUDA_CHECK(cudaDeviceSynchronize());
        float ms = 0;
        cudaEventElapsedTime(&ms, evStart, evStop);

        float lossSum = 0.0f;
        CUDA_CHECK(cudaMemcpy(&lossSum, n->dLoss, sizeof(float), cudaMemcpyDeviceToHost));
        float avgLoss = lossSum / (float)numTrain;
        float acc = evaluate(n, d_testImages, d_testLabels, numTest);
        printf("Epoch %2d:  Loss=%.4f, Accuracy=%.2f%%  (%.1f s)\n",
               epoch + 1, avgLoss, acc, ms / 1000.0f);
    }

    cudaEventDestroy(evStart);
    cudaEventDestroy(evStop);
    free(perm);
}

/* Read a big-endian 32-bit integer (MNIST IDX header fields). */
static unsigned be32(FILE* f) {
    unsigned char b[4];
    if (fread(b, 1, 4, f) != 4) { fprintf(stderr, "Short header read\n"); exit(1); }
    return ((unsigned)b[0] << 24) | ((unsigned)b[1] << 16) |
           ((unsigned)b[2] << 8) | (unsigned)b[3];
}

/*
 * MNIST IDX loader.
 * Images: magic 0x00000803, count, rows(28), cols(28), big-endian header,
 * then one unsigned byte per pixel. Labels: magic 0x00000801, count, bytes.
 * Pixels normalized to [0, 1].
 */
void loadMNIST(const char* imageFile, const char* labelFile,
               float** images, int** labels, int* numImages) {

    FILE* f = fopen(imageFile, "rb");
    if (!f) { fprintf(stderr, "Cannot open %s\n", imageFile); exit(1); }
    unsigned magic = be32(f), count = be32(f), rows = be32(f), cols = be32(f);
    if (magic != 0x00000803 || rows != 28 || cols != 28) {
        fprintf(stderr, "Unexpected image file format in %s\n", imageFile);
        exit(1);
    }
    size_t npix = (size_t)rows * cols;
    float* img = (float*)malloc((size_t)count * npix * sizeof(float));
    unsigned char* row = (unsigned char*)malloc(npix);
    if (!img || !row) { fprintf(stderr, "Host allocation failed\n"); exit(1); }
    for (unsigned i = 0; i < count; i++) {
        if (fread(row, 1, npix, f) != npix) {
            fprintf(stderr, "Short read in %s\n", imageFile); exit(1);
        }
        for (size_t p = 0; p < npix; p++) img[i * npix + p] = row[p] / 255.0f;
    }
    fclose(f);
    free(row);

    f = fopen(labelFile, "rb");
    if (!f) { fprintf(stderr, "Cannot open %s\n", labelFile); exit(1); }
    magic = be32(f); count = be32(f);
    if (magic != 0x00000801) {
        fprintf(stderr, "Unexpected label file format in %s\n", labelFile);
        exit(1);
    }
    int* lab = (int*)malloc((size_t)count * sizeof(int));
    if (!lab) { fprintf(stderr, "Host allocation failed\n"); exit(1); }
    for (unsigned i = 0; i < count; i++) {
        int c = fgetc(f);
        if (c == EOF) { fprintf(stderr, "Short read in %s\n", labelFile); exit(1); }
        lab[i] = c;
    }
    fclose(f);

    *images = img;
    *labels = lab;
    *numImages = (int)count;
}

int main(int argc, char** argv) {
    printf("Complete Neural Network Training on MNIST\n");
    printf("Architecture: 784 -> 128 -> 64 -> 10\n\n");

    const char* dataDir = (argc > 1) ? argv[1] : "data";
    int numEpochs = (argc > 2) ? atoi(argv[2]) : 20;
    int batch = (argc > 3) ? atoi(argv[3]) : 100;
    float lr = (argc > 4) ? (float)atof(argv[4]) : 0.1f;
    if (numEpochs <= 0 || batch <= 0 || batch > 4096 || lr <= 0) {
        fprintf(stderr, "Invalid arguments\n");
        return 1;
    }

    char path[512];
    float *hTrainImg, *hTestImg;
    int *hTrainLab, *hTestLab;
    int numTrain, numTest;

    snprintf(path, sizeof(path), "%s/train-images-idx3-ubyte", dataDir);
    char imgTrain[512]; strcpy(imgTrain, path);
    snprintf(path, sizeof(path), "%s/train-labels-idx1-ubyte", dataDir);
    loadMNIST(imgTrain, path, &hTrainImg, &hTrainLab, &numTrain);

    snprintf(path, sizeof(path), "%s/t10k-images-idx3-ubyte", dataDir);
    char imgTest[512]; strcpy(imgTest, path);
    snprintf(path, sizeof(path), "%s/t10k-labels-idx1-ubyte", dataDir);
    loadMNIST(imgTest, path, &hTestImg, &hTestLab, &numTest);
    printf("Loaded %d training images, %d test images from %s\n",
           numTrain, numTest, dataDir);

    float *dTrainImg, *dTestImg;
    int *dTrainLab, *dTestLab;
    CUDA_CHECK(cudaMalloc(&dTrainImg, (size_t)numTrain * IN * sizeof(float)));
    CUDA_CHECK(cudaMalloc(&dTrainLab, numTrain * sizeof(int)));
    CUDA_CHECK(cudaMalloc(&dTestImg, (size_t)numTest * IN * sizeof(float)));
    CUDA_CHECK(cudaMalloc(&dTestLab, numTest * sizeof(int)));
    CUDA_CHECK(cudaMemcpy(dTrainImg, hTrainImg, (size_t)numTrain * IN * sizeof(float),
                          cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(dTrainLab, hTrainLab, numTrain * sizeof(int),
                          cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(dTestImg, hTestImg, (size_t)numTest * IN * sizeof(float),
                          cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(dTestLab, hTestLab, numTest * sizeof(int),
                          cudaMemcpyHostToDevice));
    free(hTrainImg); free(hTrainLab); free(hTestImg); free(hTestLab);

    // Initialize network parameters
    srand(42);
    Net net = {0};
    netAlloc(&net, batch);
    netInit(&net);
    printf("Batch size: %d, epochs: %d, learning rate: %.3f\n\n", batch, numEpochs, lr);

    // Train
    cudaEvent_t t0, t1;
    cudaEventCreate(&t0);
    cudaEventCreate(&t1);
    cudaEventRecord(t0);
    train(&net, dTrainImg, dTrainLab, numTrain, dTestImg, dTestLab, numTest,
          batch, numEpochs, lr);
    cudaEventRecord(t1);
    cudaEventSynchronize(t1);
    float totalMs = 0;
    cudaEventElapsedTime(&totalMs, t0, t1);

    // Final evaluation
    float acc = evaluate(&net, dTestImg, dTestLab, numTest);
    printf("\nFinal Test Accuracy: %.2f%%  (total training wall time %.1f s)\n",
           acc, totalMs / 1000.0f);
    printf("Target: >95%% accuracy\n");

    int passed = (acc > 95.0f);
    if (passed)
        printf("\xe2\x9c\x93 Verification PASSED\n");
    else
        printf("\xe2\x9c\x97 Verification FAILED\n");

    return passed ? 0 : 1;
}
