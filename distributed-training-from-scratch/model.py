"""model.py — the provided deterministic shape calculus for H1.

This is the *world* the whole course is measured against: one model, many
devices, the same math. Every plan a student writes must reproduce the
arithmetic below — the same parameters, the same optimizer state, the same
gradients, the same attention — while moving as few bytes as it can.

**Nothing here is measured and nothing here is random.** Two calls return
`==` values. Every number is an `int`; there are no floats anywhere, and where
a fraction is unavoidable it is an exact `(numerator, denominator)` pair of
ints, kept exact and never turned into `1.0 / x`.

Byte conventions
----------------
`ELEMENT_BYTES` (4) is `fabric.ELEMENT_BYTES` — a length in elements becomes a
size in bytes in exactly one place. Training state is priced per parameter:
`PARAM_BYTES` (2) for the bf16 parameter and again for its gradient,
`MASTER_BYTES` (4) for the fp32 master copy and `OPTIMIZER_BYTES` (8) for the
two fp32 Adam moments — 16 bytes per parameter held whole. Stage 3 shards
exactly that 16: ZeRO-1 keeps `12/N + 4` bytes per parameter per rank and
ZeRO-2 `12/N + 2/N + 4`. The constants are frozen here so every stage prices
it the same way.

The parameter calculus
----------------------
`ModelShape.params()` counts every parameter once: the embedding, each layer's
attention projections (fused qkv plus the output projection), the FFN (or the
expert bank), and the two per-layer norms, plus the final norm. When
`experts > 0` the FFN is replaced by `experts` banks and a token only touches
`top_k` of them, so `flops_per_token()` — not the parameter count — carries the
routing; when `tied_embeddings` the head re-uses the embedding matrix and is
counted once. `params()` is definitionally
`sum(t.elements for t in shape.tensors() if t.trainable)`.

The three fixtures in `SHAPES` are frozen:

* ``"tiny"`` — 2 layers, hidden 4, 2 heads, ffn 8, vocab 12: 388 parameters.
  Small enough that `reference_gradients` is cheap and hand-checkable.
* ``"1b"`` — 20 layers, hidden 2048, 16 heads, ffn 5632, vocab 32000:
  1_093_224_448 parameters ~ 1.09e9. The bytes/ledger fixture.
* ``"7b"`` — 34 layers, hidden 4096, 32 heads, ffn 11008, vocab 32000:
  7_012_110_336 parameters ~ 7.01e9. The memory fixture.

The attention convention (frozen here, reproduced by stage 9)
------------------------------------------------------------
Attention runs on **integer scores**: `s_ij = sum_d q_i[d] * k_j[d]`. The
weight of a score is the exact rational `2 ** s` — *not* `exp(s)` of a float
library; the base is 2 and the score is the exponent, so the whole computation
stays in the integers. A weight is carried as the pair

    (1 << s, 1)   if s >= 0        (the integer 2 ** s)
    (1, 1 << -s)  if s <  0        (the exact reciprocal, still a pair of ints)

and an accumulator is a pair `(num, den)` meaning `num / den`, holding the
running `(sum of weight * value, sum of weight)` — never a normalized softmax.
The max-rescale is an exact **shift**: when the running maximum score grows
from `m` to `m'`, both parts of every accumulator are shifted left by
`m' - m`

    num <<= m' - m  and  den <<= m' - m

because that multiplies `num / den` by `2 ** (m' - m)`, which the weight
`2 ** (s - m')` cancels exactly. Shifting the numerator and *not* the
denominator is stage 9's planted mistake: the value silently changes.
`reference_attention` returns the pair reduced to lowest terms with a positive
denominator, so **every split of the same sequence — one block, two, four —
returns the identical pair**; a ring-attention plan that accumulates blocks in
any order must land on the same ints.

The gradient convention (frozen here, reproduced by stages 2 and 3)
------------------------------------------------------------------
`reference_gradients` is the *exact* gradient, by the chain rule, of one
deterministic integer network over an integer batch, summed over the batch and
keyed by tensor name; its docstring states the network. There is no `random`
and no wall clock in it: the batch, the layer index and the position are the
only inputs. It is what a data-parallel plan must still produce after its
all-reduce, and what a ZeRO plan must still produce after reassembling its
shards.
"""

from dataclasses import dataclass
from math import gcd
import types

#: Bytes per element of a buffer. Mirrors `fabric.ELEMENT_BYTES`; the cost
#: model charges bytes, and this is the only place elements become bytes.
ELEMENT_BYTES = 4

#: bf16 parameters and gradients: 2 bytes each.
PARAM_BYTES = 2

#: fp32 master weights: 4 bytes per parameter.
MASTER_BYTES = 4

#: Two fp32 Adam moments: 8 bytes per parameter.
OPTIMIZER_BYTES = 8

#: The modulus of the reference gradient network's feature map (see
#: `reference_gradients`). Documented, not magic: the feature has period 7 in
#: the element index and the parameter init has period 5, so their product has
#: period 35 — which is why the per-tensor feature sum is cheap.
FEATURE_MODULUS = 7

#: The period in the element index of the product of the feature map and the
#: parameter init: `lcm(5, 7)`.
FEATURE_PERIOD = 35


class ModelError(ValueError):
    """A shape, a dimension or a plan the model refuses, naming the offender."""


def _require_int(value, what, *, minimum=None):
    """The house guard: a `bool` is not an int, and neither is a string.

    `minimum` is inclusive when given; a value below it is refused with the
    offending field's name interpolated.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise ModelError("%s=%r is not an int" % (what, value))
    if minimum is not None and value < minimum:
        raise ModelError("%s=%d is below %d" % (what, value, minimum))
    return value


def _require_shape(shape):
    """The shape argument of a cost or a reference call, or the refusal."""
    if not isinstance(shape, ModelShape):
        raise ModelError("shape=%r is not a ModelShape" % (shape,))
    return shape


def ceil_div(total, n):
    """`ceil(total / n)` in integers: the only rounding rule in the course."""
    _require_int(total, "total", minimum=0)
    _require_int(n, "n", minimum=1)
    return -(-total // n)


@dataclass(frozen=True)
class Tensor:
    """One parameter tensor of the model: a name, a size, and a trainability.

    `elements` is the number of parameters; bytes are `elements *
    ELEMENT_BYTES`, or `elements * PARAM_BYTES` for the bf16 copy a step moves.
    """

    name: str
    elements: int
    trainable: bool = True

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name:
            raise ModelError("name=%r is not a non-empty str" % (self.name,))
        _require_int(self.elements, "elements", minimum=1)
        if not isinstance(self.trainable, bool):
            raise ModelError("trainable=%r is not a bool" % (self.trainable,))


@dataclass(frozen=True)
class ModelShape:
    """The model's dimensions, and the calculus that hangs off them.

    Every field is frozen and validated on construction, so an impossible
    shape cannot exist to be priced. `experts=0` is a dense FFN; `top_k` is
    only meaningful when there are experts, and `tied_embeddings` says whether
    the head re-uses the embedding matrix (counted once) or owns its own.
    """

    layers: int
    hidden: int
    heads: int
    ffn_hidden: int
    vocab: int
    experts: int = 0
    top_k: int = 0
    tied_embeddings: bool = True

    def __post_init__(self):
        for field in ("layers", "hidden", "heads", "ffn_hidden", "vocab"):
            _require_int(getattr(self, field), field, minimum=1)
        _require_int(self.experts, "experts", minimum=0)
        _require_int(self.top_k, "top_k", minimum=0)
        if self.hidden % self.heads:
            raise ModelError(
                "heads=%d does not divide hidden=%d" % (self.heads, self.hidden))
        if not isinstance(self.tied_embeddings, bool):
            raise ModelError(
                "tied_embeddings=%r is not a bool" % (self.tied_embeddings,))
        if self.experts == 0:
            if self.top_k != 0:
                raise ModelError(
                    "top_k=%d is meaningless with experts=0" % (self.top_k,))
        elif not 1 <= self.top_k <= self.experts:
            raise ModelError(
                "top_k=%d must be between 1 and experts=%d"
                % (self.top_k, self.experts))

    def head_dim(self):
        """Elements per head: `hidden // heads`, which divides by validation."""
        return self.hidden // self.heads

    def _ffn_bank(self):
        """`(unit, copies)`: how many FFN banks a token multiplies at once,
        and how many exist."""
        if self.experts:
            return self.top_k, self.experts
        return 1, 1

    def _layer_tensors(self, layer):
        """The tensors of one layer, in the frozen tie order."""
        hidden = self.hidden
        prefix = "layer.%d" % layer
        rows = [
            Tensor("%s.attn.qkv" % prefix, 3 * hidden * hidden),
            Tensor("%s.attn.proj" % prefix, hidden * hidden),
            Tensor("%s.attn.norm" % prefix, hidden),
        ]
        if self.experts:
            for expert in range(self.experts):
                bank = "%s.expert.%d" % (prefix, expert)
                rows.append(Tensor("%s.w1" % bank, self.ffn_hidden * hidden))
                rows.append(Tensor("%s.w2" % bank, hidden * self.ffn_hidden))
                rows.append(Tensor("%s.w3" % bank, self.ffn_hidden * hidden))
        else:
            rows.append(Tensor("%s.ffn.w1" % prefix, self.ffn_hidden * hidden))
            rows.append(Tensor("%s.ffn.w2" % prefix, hidden * self.ffn_hidden))
            rows.append(Tensor("%s.ffn.w3" % prefix, self.ffn_hidden * hidden))
        rows.append(Tensor("%s.ffn.norm" % prefix, hidden))
        return rows

    def tensors(self, *, tied=None):
        """Every parameter tensor, **in the frozen order** (the gradient is
        aligned to it), as a `tuple[Tensor, ...]`.

        `tied` may restate the shape's own tying; asking a tied shape to be
        untied (or an untied shape to be tied) is refused, naming
        `tied_embeddings`, because a tie is a property of the model and not of
        the call.
        """
        if tied is None:
            tied = self.tied_embeddings
        elif not isinstance(tied, bool):
            raise ModelError("tied=%r is not a bool" % (tied,))
        elif tied != self.tied_embeddings:
            if self.tied_embeddings:
                raise ModelError(
                    "tied_embeddings=True on %r cannot be asked to be untied"
                    % (self,))
            raise ModelError(
                "tied_embeddings=False on %r cannot be asked to be tied"
                % (self,))
        rows = [Tensor("embed", self.vocab * self.hidden)]
        for layer in range(self.layers):
            rows.extend(self._layer_tensors(layer))
        rows.append(Tensor("norm", self.hidden))
        if not tied:
            rows.append(Tensor("unembed", self.vocab * self.hidden))
        return tuple(rows)

    def params(self):
        """Every parameter, counted once: embedding, attention, FFN/experts,
        norms — exactly as `tensors()` reports them."""
        return sum(t.elements for t in self.tensors() if t.trainable)

    def flops_per_token(self):
        """Forward multiply-adds for one token: two per matmul parameter, per
        layer.

        The embedding is a lookup and costs nothing; a tied head re-uses the
        embedding matrix; a routed FFN charges `top_k` banks and not all
        `experts`. The score and weight products of attention need the
        sequence length and live in `ComputeModel.compute_ticks`, not here.
        """
        unit, _ = self._ffn_bank()
        per_layer = 4 * self.hidden * self.hidden
        per_layer += unit * 3 * self.hidden * self.ffn_hidden
        return 2 * self.layers * per_layer

    def activation_bytes(self, batch, seq):
        """Activation bytes held at the peak: the residual stream and the MLP
        intermediate for every layer, plus the `heads x seq x seq` scores.

        Grows with both `batch` and `seq` (the score term is quadratic in
        `seq`), which is what the memory ledgers of stages 4 and 7 read.
        """
        batch = _require_int(batch, "batch", minimum=1)
        seq = _require_int(seq, "seq", minimum=1)
        unit, _ = self._ffn_bank()
        per_token = 2 * self.hidden + unit * self.ffn_hidden
        per_layer = batch * seq * per_token
        per_layer += batch * self.heads * seq * seq
        return ELEMENT_BYTES * self.layers * per_layer

    def params_per_world(self, ranks):
        """The parameter set split evenly over a world of `ranks` ranks.

        This is the **model's** rule: the reference puts whole equal parts on
        every rank, so a world the parameter set does not divide is refused
        here, naming `ranks` and the actual remainder. Stage 1's
        `params_by_rank` is the *plan's* rule and may shard the remainder on
        purpose; the two disagree exactly where a ledger bug hides.
        """
        ranks = _require_int(ranks, "ranks", minimum=1)
        total = self.params()
        if total % ranks:
            raise ModelError(
                "ranks=%d does not divide the %d parameters of %r "
                "(remainder %d)" % (ranks, total, self, total % ranks))
        return (total // ranks,) * ranks


@dataclass(frozen=True)
class ComputeModel:
    """What one device's compute is worth: flops per tick, and optionally a
    token rate.

    `compute_ticks` is the **max** of the two bounds, so both knobs bind: a
    device that issues `flops_per_tick` flops per tick and swallows
    `tokens_per_tick` tokens per tick takes the slower of the two. The result
    is an int and monotone in both `batch` and `seq`.
    """

    flops_per_tick: int
    tokens_per_tick: int = None

    def __post_init__(self):
        _require_int(self.flops_per_tick, "flops_per_tick", minimum=1)
        if self.tokens_per_tick is not None:
            _require_int(self.tokens_per_tick, "tokens_per_tick", minimum=1)

    def flops_for(self, shape, *, batch, seq):
        """The whole step's flops: `flops_per_token` over the batch, plus the
        two attention products (`q.k` and `weight.v`) per head."""
        shape = _require_shape(shape)
        batch = _require_int(batch, "batch", minimum=1)
        seq = _require_int(seq, "seq", minimum=1)
        flops = shape.flops_per_token() * batch * seq
        flops += 4 * shape.layers * batch * shape.heads * seq * seq * shape.head_dim()
        return flops

    def compute_ticks(self, shape, *, batch, seq):
        """The step's compute, in ticks, from the flops and (if given) the
        token rate."""
        batch = _require_int(batch, "batch", minimum=1)
        seq = _require_int(seq, "seq", minimum=1)
        ticks = ceil_div(self.flops_for(shape, batch=batch, seq=seq),
                         self.flops_per_tick)
        if self.tokens_per_tick is not None:
            ticks = max(ticks, ceil_div(batch * seq, self.tokens_per_tick))
        return ticks


def _require_matrix(value, what):
    """A tuple of equal-length tuples of ints, or the refusal naming `what`."""
    if not isinstance(value, tuple) or not value:
        raise ModelError("%s=%r is not a non-empty tuple of rows" % (what, value))
    width = None
    for row in value:
        if not isinstance(row, tuple) or not row:
            raise ModelError("%s=%r has a row that is not a tuple" % (what, value))
        if width is None:
            width = len(row)
        elif len(row) != width:
            raise ModelError("%s=%r has rows of different lengths" % (what, value))
        for item in row:
            if isinstance(item, bool) or not isinstance(item, int):
                raise ModelError("%s=%r holds a non-int element" % (what, value))
    return value, width


def reference_layer(x, w, b):
    """The integer matmul plus bias the tensor-parallel stage must reproduce
    through `f`/`g`, exactly.

    `x` is `rows x inner`, `w` is `out x inner` (one row per output neuron)
    and `b` is `out` numbers; the result is `rows x out` with

        y[i][j] = b[j] + sum_k x[i][k] * w[j][k]

    Every entry is an int, so `column_parallel`, `row_parallel` and their
    `f`/`g` composition can split `w` and recompose this product to the same
    ints, not to something close.
    """
    x, inner = _require_matrix(x, "x")
    w, w_inner = _require_matrix(w, "w")
    if w_inner != inner:
        raise ModelError("w inner=%d does not match x inner=%d" % (w_inner, inner))
    if not isinstance(b, tuple) or len(b) != len(w):
        raise ModelError("b=%r must have one entry per w row (%d)" % (b, len(w)))
    for item in b:
        if isinstance(item, bool) or not isinstance(item, int):
            raise ModelError("b=%r holds a non-int element" % (b,))
    out = []
    for row in x:
        out.append(tuple(b[j] + sum(row[k] * w[j][k] for k in range(inner))
                         for j in range(len(w))))
    return tuple(out)


def gradient_names(shape):
    """The names `reference_gradients` is aligned with: the trainable tensors,
    in `tensors()` order."""
    shape = _require_shape(shape)
    return tuple(t.name for t in shape.tensors() if t.trainable)


def _feature(p, j):
    """The reference network's feature of element `j` at token `p`."""
    return ((3 * p + 5 * j + 1) % FEATURE_MODULUS) - 3


def _theta(index, j):
    """The reference network's deterministic init of element `j` of the
    `index`-th tensor: an int in `(-2, 2)`, no `random` anywhere."""
    return ((j + index) % 5) - 2


def _feature_sum(index, p, elements):
    """`sum(_theta(index, j) * _feature(p, j) for j in range(elements))`.

    The product has period `FEATURE_PERIOD` in `j`, so the whole turns of 35
    are counted once and only the remainder is walked: `O(35)` per (tensor,
    token), which keeps the reference cheap even on `SHAPES["7b"]`.
    """
    whole, rest = divmod(elements, FEATURE_PERIOD)
    total = 0
    for j in range(FEATURE_PERIOD):
        total += _theta(index, j) * _feature(p, j)
    total *= whole
    for j in range(FEATURE_PERIOD, FEATURE_PERIOD + rest):
        total += _theta(index, j) * _feature(p, j)
    return total


def reference_gradients(shape, *, batch, seq):
    """The exact gradient of the reference network, per tensor, by name.

    The network is one integer layer, activated, with a squared-error loss:

        z(p)   = sum_t sum_{j < n_t} theta_t[j] * f(p, j)
        loss   = sum_{p < batch*seq} (relu(z(p)) - y(p)) ** 2
        f(p, j)= ((3*p + 5*j + 1) mod 7) - 3
        y(p)   = (2*p + 1) mod 5
        theta_t[j] = ((j + t) mod 5) - 2      # t = the tensor's index

    with `relu(a) = a if a > 0 else 0`. `batch`, `seq`, the tensor's index and
    the element's index are the only inputs: there is no `random`, no clock and
    no state, so two calls return equal ints. The returned tuple is aligned
    with `gradient_names(shape)` — the *exact* chain-rule value

        sum_j d loss / d theta_t[j]
        = sum_p 2 * (relu(z(p)) - y(p)) * relu'(z(p)) * sum_{j<n_t} f(p, j)

    so a data-parallel plan's all-reduce, or a ZeRO plan's reassembled shards,
    must land on these ints exactly. `tiny` (388 parameters) is the fixture it
    is meant to be called on and the one `/tmp/h1-checks/verify_model.py`
    recomputes by hand.
    """
    shape = _require_shape(shape)
    batch = _require_int(batch, "batch", minimum=1)
    seq = _require_int(seq, "seq", minimum=1)
    tensors = tuple(t for t in shape.tensors() if t.trainable)
    tokens = batch * seq
    sums = [[_feature_sum(index, p, tensor.elements) for p in range(tokens)]
            for index, tensor in enumerate(tensors)]
    z = [sum(row[p] for row in sums) for p in range(tokens)]
    out = []
    for index in range(len(tensors)):
        total = 0
        for p in range(tokens):
            gate = 1 if z[p] > 0 else 0
            total += 2 * (max(z[p], 0) - ((2 * p + 1) % 5)) * gate * sums[index][p]
        out.append(total)
    return tuple(out)


def _positions(blocks, what):
    """Flatten `blocks` — a non-empty tuple of ints and/or tuples of ints —
    into the sequence of per-position ints, or refuse naming `what`."""
    if not isinstance(blocks, tuple) or not blocks:
        raise ModelError("%s=%r is not a non-empty tuple" % (what, blocks))
    out = []
    for item in blocks:
        if isinstance(item, bool):
            raise ModelError("%s=%r holds a bool" % (what, blocks))
        if isinstance(item, int):
            out.append(item)
            continue
        if not isinstance(item, tuple) or not item:
            raise ModelError(
                "%s=%r holds an item that is not an int or a non-empty tuple"
                % (what, blocks))
        for inner in item:
            if isinstance(inner, bool) or not isinstance(inner, int):
                raise ModelError("%s=%r holds a non-int element" % (what, blocks))
            out.append(inner)
    if not out:
        raise ModelError("%s=%r is empty" % (what, blocks))
    return tuple(out)


def reference_attention(q, k, v):
    """The exact `(numerator, denominator)` pair an integer attention over
    blocks accumulates, whatever the sequence is split into.

    `q`, `k` and `v` are blocks — a tuple of ints, or of tuples of ints, or
    any mixture; the blocks are flattened into the sequence in order, so
    `((1, 2), (3,))` and `(1, 2, 3)` are the same sequence and must give the
    same pair. Position `i` attends every key position `j` with the integer
    score `s_ij = q_i * k_j` and the exact rational weight `2 ** s_ij`, held
    as the pair the module docstring freezes; the result is

        (sum_ij 2 ** s_ij * v_j, sum_ij 2 ** s_ij)

    reduced by `gcd` to lowest terms with a positive denominator — which is
    why every split of one sequence returns the *identical* ints. The
    streaming form of this accumulator (stage 9) keeps a running maximum and
    rescales both parts by `<< (m' - m)`, so it lands on the same reduced pair.
    """
    qs = _positions(q, "q")
    ks = _positions(k, "k")
    vs = _positions(v, "v")
    if len(ks) != len(qs):
        raise ModelError(
            "k has %d positions, q has %d" % (len(ks), len(qs)))
    if len(vs) != len(ks):
        raise ModelError(
            "v has %d positions, k has %d" % (len(vs), len(ks)))
    low = None
    for left in qs:
        for right in ks:
            score = left * right
            if low is None or score < low:
                low = score
    num = 0
    den = 0
    for left in qs:
        for j, right in enumerate(ks):
            weight = 1 << (left * right - low)
            num += vs[j] * weight
            den += weight
    common = gcd(abs(num), den)
    if common > 1:
        num //= common
        den //= common
    if den < 0:
        num, den = -num, -den
    return (num, den)


#: The three named fixtures: the hand-checkable `tiny`, and the two
#: bytes/memory fixtures whose `params()` land at ~1.09e9 and ~7.01e9.
SHAPES = types.MappingProxyType({
    "tiny": ModelShape(layers=2, hidden=4, heads=2, ffn_hidden=8, vocab=12),
    "1b": ModelShape(layers=20, hidden=2048, heads=16, ffn_hidden=5632,
                     vocab=32000),
    "7b": ModelShape(layers=34, hidden=4096, heads=32, ffn_hidden=11008,
                     vocab=32000),
})

