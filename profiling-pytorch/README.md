# Profiling in PyTorch

Study notes for **Profiling in PyTorch**, a three-part series on the Hugging Face blog
that teaches you to read `torch.profiler` output and let the trace drive an
optimization. The series' own one-line summary: *"a series where we slowly build the
skill of reading profiler traces and use it to drive optimization."*

| # | Post | You profile | The mismatch the trace reveals |
|---|------|-------------|-------------------------------|
| 1 | [A Beginner's Guide to `torch.profiler`](https://huggingface.co/blog/torch-profiler) | `torch.add(torch.matmul(x, w), b)`, eager and `torch.compile`d, at 64×64 and 4096×4096 bf16 | CPU-dispatches ≫ GPU-work on small shapes: 2.314 ms of CPU against 23.104 µs of CUDA, and a ~228 µs dead window between the annotation and the first `aten::matmul` |
| 2 | [From `nn.Linear` to a Fused MLP](https://huggingface.co/blog/torch-mlp-fusion) | one `nn.Linear`, then a three-layer GeGLU MLP, eager / compiled / hand-tuned kernel | the bias add is *already* inside the GEMM epilogue (`addmm`), so `torch.compile` has nothing left to fuse; and where the real win is (5 kernels → 1 fused Triton kernel for GeLU+mul) |
| 3 | [Attention is all you profile](https://huggingface.co/blog/torch-attention-profile) | naive attention, in-place masking, then `F.scaled_dot_product_attention` pinned to its four backends | the one-liner is **3.7× slower** on the math backend (20 kernels/forward instead of 5), and the fastest backend reports a "wrong-looking" 13% occupancy |

Authors: Aritra Roy Gosthipaty, Sayak Paul, Sergio Paniego, Rémi Ouazan Reboul,
Pedro Cuenca. Traces captured on an `NVIDIA A100-SXM4-80GB` with PyTorch 2.13.

## How to run it yourself

The series ships its scripts in a HF dataset, [`ariG23498/profiling-pytorch`](https://huggingface.co/datasets/ariG23498/profiling-pytorch):
`01_matmul_add.py`, `02_linear.py`, `03_simple_mlp.py`, `03_kernels_mlp.py`,
`04_a_naive_attention.py`, `04_b_inplace_ops_attention.py`, `04_c_sdpa_attention.py`,
`04_d_kernels_attention.py`.

You need a GPU (everything in the posts is CUDA-side), `uv` to run the scripts, and
[Perfetto](https://ui.perfetto.dev) to open the traces the scripts write into
`traces/`. `uvx trace-util -f traces -b <hf_uname>/traces` uploads them and prints the
Perfetto links; in Perfetto, `W A S D` navigates. The bare minimum, with no upload:

```py
with torch.profiler.profile(
    activities=[torch.profiler.ProfilerActivity.CPU, torch.profiler.ProfilerActivity.CUDA],
    schedule=torch.profiler.schedule(wait=1, warmup=1, active=3, repeat=1),
) as prof:
    with torch.profiler.record_function("matmul_add"):
        for _ in range(5):
            step()
            prof.step()

print(prof.key_averages().table(sort_by="cuda_time_total", row_limit=15))
prof.export_chrome_trace("trace.json")
```

Two artifacts, two questions: the **table** answers *what takes the most time* (hotspots,
`# of Calls`, `Self` vs `total`), the **trace** answers *when and why* (the CPU dispatch
chain, the GPU kernels, the gaps and the overlap). `Self` time excludes children,
`total` includes them.

## Part 1 — what the trace is made of

The whole first post is one question-led walk through a 64×64 `matmul + add`:

- **Overhead-bound vs compute-bound.** At 64×64 the CPU spends 2.314 ms to feed 23.104 µs
  of GPU work; at 4096×4096 the two are 4.908 ms and 4.495 ms. The transition is what a
  profiler makes visible, and the fix is trivial: bigger work per launch.
- **The ~228 µs cold-start gap.** On the first profiled step, `record_function("matmul_add")`
  opens 227.757 µs before `aten::matmul` starts; the next steps take 5.521 and 4.488 µs.
  Workspace allocation, cuBLAS heuristics and lazy module loading are one-time costs you
  should warm up past, not profile.
- **The CPU/GPU lane offset (~2.5 ms)** comes from the profiler's own
  `Activity Buffer Request` on the GPU lane; with `wait=0, warmup=0` you can watch a
  second buffer request open a gap between the matmul and the add kernels of one step.
  Run more iterations: a gap that appears once is the profiler, not your code.
- **The dispatch chain** is `ProfileStep#N` → your annotation → `aten::matmul` → `aten::mm`
  (2D) or `aten::bmm` (3D+). Add a batch dimension and cuBLAS does visibly more heuristic
  work before launching.
- **A GEMM plans its launch; an elementwise op does not.** `aten::mm` is preceded by
  `cudaOccupancyMaxActiveBlocksPerMultiprocessor`, `aten::add` is not. That occupancy
  query is the cheapest signal in a trace for "this is a heavyweight, adaptively launched
  kernel".
- **Kernel times are not constants.** Across 20 identical iterations the same GEMM takes
  ~580 µs most of the time and more when the GPU misbehaves; the mean says ~1 ms. Clocks,
  thermals, power management and driver housekeeping all show up. Read the trace, not the
  average.
- **What `torch.compile` did here:** the graph was rewritten to one `aten::addmm`, but the
  GPU kernel is byte-for-byte the same cuBLAS GEMM eager used — the fusion is *at the
  dispatcher level*. And the compiled run is ~2× more expensive per step on the CPU,
  because every call walks `TorchDynamo Cache Lookup` → `AOTDispatcher Runtime Wrapper
  Prologue` → `## Call CompiledFxGraph <hash>`. That tax only amortizes over many ops.
- **A `Memcpy DtoD` before the GEMM** is the bias being seeded into the destination buffer
  (`addmm` computes `α·A·B + β·C`, and cuBLAS's epilogue adds the bias on writeback). No
  `cudaLaunchKernel` for it — it arrives as `cudaMemcpyAsync`.

Diagnostics worth memorizing, in the words of the trace:

| You see | It means |
|---------|----------|
| `Self CPU` ≫ `Self CUDA` (CPU in ms, GPU in µs) | overhead-bound — the launch path is the bottleneck |
| `Self CPU` ≈ `Self CUDA`, both ms | compute-bound — the GPU is the bottleneck |
| one event dominating `CUDA total`, or a huge `# of Calls` | the hotspot, even if each call is cheap |
| `CPU total` ≫ `Self CPU` on a row | the cost is in the children — drill in |
| occupancy query before a launch | heavyweight kernel, cuBLAS sizing a grid |
| no occupancy query | elementwise/reduction, resource-light, launched mechanically |
| a long `cudaDeviceSynchronize` over tiny GPU work | the profiler flushing; 98% idle is the real diagnosis |

## Part 2 — a real building block, and where fusion actually pays

`nn.Linear` is the part-1 expression with parameters attached. Profiling it answers
questions the eager code raises and the trace settles:

- **What is `aten::t` doing in a linear layer?** `nn.Linear` transposes the weight — but
  `aten::t` only rewrites shape and stride metadata on the CPU (`transpose` returns a
  *view*: same buffer, swapped strides). It launches no kernel: check its `CUDA time`,
  `0.000us`.
- **Why is there no separate `aten::add`?** `aten::linear` sees a bias and dispatches
  `aten::addmm(bias, x, weight)`, whose cuBLAS kernel folds the bias addition into its
  writeback. That trailing computation is an **epilogue** — a GEMM doing a little extra
  work right before writing its result back to HBM, so the intermediate never makes a
  second round trip through memory. Adding a bias, an activation or a scale is the classic
  epilogue.
- **So `torch.compile` has nothing to fuse for one `nn.Linear`:** same GEMM, same
  `aten::addmm`; what compile removes is the *CPU* work of dispatching the `aten::t` view
  chain, because Inductor computes the strides once and bakes them in.
- **Read the kernel name like a fingerprint.** `..._tn_align8`, `bf16` vs `fp16`,
  `s16816gemm` vs `s161616gemm` — the suffix encodes the input layouts and the instruction
  shape. Same name ⇒ same work; different name ⇒ the dispatcher took a different branch.

Then the MLP (`gate_proj`, `up_proj`, GeLU, mul, `down_proj`, the GeGLU FFN shape) and the
payoff, measured:

| Setup | Kernels per forward | What changed |
|-------|--------------------|--------------|
| eager MLP | 5 (3 GEMMs + GeLU + mul) | the `[8192, 3072]` bf16 intermediate (~50 MB) round-trips through HBM between GeLU and mul |
| compiled MLP | 4 (3 GEMMs + 1 fused Triton kernel) | GeLU + mul + reshape collapse into `triton_poi_fused__unsafe_view_gelu_mul_0`; the intermediate stays in registers. The 3 GEMMs are untouched, identical cuBLAS kernel names |
| hand-tuned (Liger via `kernels`) | 4 | same fusion, baked into a hand-written Triton kernel with launch parameters chosen for the hardware, **no** Dynamo/guard/compile pre-ops, and no recompilation when shapes change |

- Two GEMM kernels for three same-FLOP matmuls: `128x128` for `gate`/`up`, `128x256` with
  a deeper pipeline for `down_proj` (`N=768` instead of `3072`) — same work, better tile
  for the shape, ~10% faster.
- The honest trade-off: Liger's fused kernel ran in **92.8 µs** vs Inductor's **89.4 µs**.
  The compiled kernel wins *because it was specialized for this exact `[8192, 3072]`*
  input; change the shape and Dynamo re-traces and pays again. A fast generic kernel vs a
  kernel specialized for one shape.
- Deploying a kernel is its own problem: the [`kernels`](https://github.com/huggingface/kernels)
  library pulls a pre-built, version-pinned binary from the Hub
  (`get_kernel("kernels-community/liger-kernels", version=1).layers`) and caches it, so the
  GPU-arch/CUDA/PyTorch build matrix stops being your problem.

The habit the post keeps repeating, and the one to keep: **guess first, then look.** Say
what you expect the trace to contain, then treat every mismatch as the most interesting
thing on the screen.

## Part 3 — attention: four ways to do the same math

Attention from primitives (`matmul(q, k.T)` → scale → mask → softmax → `matmul(attn, v)`)
launches 6 kernels per forward, and the trace has one surprise in it:

1. **A `Memcpy` you did not write.** It sits right before the masking kernel: the
   out-of-place `masked_fill` copies the tensor, masks the copy, and returns it. `masked_fill_`
   (in-place) deletes the kernel — 6 kernels → 5 for a one-character change. Safe here only
   because the script runs under `torch.no_grad`: in-place overwrites the values autograd
   needs for the backward pass. It also saves the memory of the copy, which matters for
   `[seq, seq]` logits.

2. **The one-liner is not automatically faster.** `F.scaled_dot_product_attention(q, k, v,
   is_causal=True)` on the **math** backend is 3.7× *slower* than the naive in-place version
   (7.239 ms vs 1.955 ms average CUDA, 20 kernels per forward instead of 5), for three
   concrete reasons visible in the trace:
   - `sgemm` instead of `s16816gemm`: it upcasts to FP32 and runs on the ordinary CUDA cores,
     never touching the Tensor Cores.
   - `is_causal=True` materializes the causal mask on *every* call (`aten::ones` →
     `aten::tril`, `aten::scalar_tensor` → `aten::fill_`, `aten::where`, then
     `triu_tril_kernel`/`where`/`add_` kernels) instead of reusing one mask.
   - `aten::_safe_softmax` adds kernels to keep a fully masked row from producing `0/0 =
     NaN` — correctness the naive version quietly lacks.
   The math backend is the reference implementation: always works, always slow.

3. **The fused backends are all "one kernel per forward" but not the same kernel.**
   - `efficient` (xformers, upstreamed): `fmha_cutlassF_bf16_aligned_64x64_rf_sm80` — bf16
     on Tensor Cores, working set in registers, tile 64×64, Ampere.
   - `flash`: `void pytorch_flash` — FlashAttention-2, vendored into PyTorch.
   - `cudnn`: `cudnn_generated_fort_native_sdpa_sm80_flash_fprop_wmma_f16_knob_6_...` —
     *generated and tuned per problem*, not a fixed binary.

4. **Why FlashAttention exists at all:** the math backend's real problem is not the kernel
   count, it is that step 1 writes a `[seq, seq]` matrix **per head** to HBM (4096² ≈ 16M
   numbers for one head) and every following kernel reads and writes it again. Attention is
   dominated by HBM traffic, not FLOPs. FlashAttention walks `k` and `v` in tiles, keeps a
   running softmax (online softmax) and accumulates the output tile by tile, so the full
   score matrix never reaches HBM.

5. **Why flash "looks wrong": 13% occupancy.** Each 128-thread block uses up to 255
   registers per thread: 128×255 = 32,640 of an SM's 65,536 registers ⇒ two blocks ⇒ 8
   resident warps of a possible 64 ≈ 13%. Low occupancy is the *design*: the registers and
   shared memory buy on-chip tiles and data reuse. High occupancy hides latency; it does not
   make work efficient.

6. **Clean traces can hide moved work.** cuDNN consumes `[B, H, S, D]` natively, so it needs
   zero `aten::transpose` where flash and efficient each insert four, and it launches through
   the driver-level `cuLaunchKernelEx` — which CUPTI cannot attribute occupancy to, so the
   trace reports `0% achieved` (the footprint says 240 registers × 256 threads = 61,440, one
   block per SM ≈ 12.5%, right in line with flash). Worse, cuDNN spends **214 µs** per
   forward on the CPU against flash's 138 and efficient's 117, almost all of it opaque inside
   `_cudnn_attention_forward` (the per-call knob/plan search). GPU time: efficient 277.9 µs,
   flash 146.8 µs, cudnn 186.3 µs.
   Fewer visible ATen ops ≠ less CPU work; it can mean the work moved into a library where
   the profiler can only show one fat bar.

7. **One keystroke, 2.7e-3 of relevance to everything you profile:** in Perfetto, clicking a
   GPU kernel shows the arrow to the CPU op that launched it. That is how you prove a
   `Memcpy` came from *that* `masked_fill` and not from somewhere else.

## Where this stops, and how it joins the rest of this repo

These posts are about **one device**: what the CPU dispatches, what the GPU runs, and where
the memory traffic goes. They stop at single-GPU span. Everything multi-device —
collectives, their cost model, what a training step's communication actually costs — is the
subject of `interconnects-from-scratch` and `distributed-training-from-scratch` in this
repo, whose stage 1 is literally the cost model (`latency + ceil(bytes / bandwidth)` per
hop, the max over a step's transfers, the sum over steps) that a profiler reports in ticks.

The reflexes to carry over:

1. **Cost is arithmetic before it is a measurement.** Predict the ticks/flops/bytes, then
   profile and compare. A unit you cannot predict is a unit you cannot debug.
2. **Self vs total, and what is inside vs outside the measured region.** The task said
   "read the profiler table", and the table's own footnote is that `Self` excludes children.
3. **A clean trace is a hypothesis, not a proof.** Check where the cost moved to.

## The posts themselves

The full texts are third-party material with no explicit license, so they are **not**
re-hosted here — they are downloaded into this directory for offline reading and ignored by
git (`torch-profiler.md`, `torch-mlp-fusion.md`, `torch-attention-profile.md`, fetched from
[`huggingface/blog`](https://github.com/huggingface/blog)). Read them at the links in the
table at the top; the notes above are this repo's summary of their mechanisms and numbers.
