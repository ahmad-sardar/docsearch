"""Search with AI: a small language model reorders the top results (MLX on the Apple GPU,
or numpy on the processor elsewhere: cpu.py).

The model reads the question with each of the top results and scores how well that
documentation entry answers it. It never writes text, so every answer is still an
official docs entry; it only changes the order. Results whose API name is exactly the
query (np.sum, Vec::push) stay first: the benchmark showed the model would otherwise
move them down.

Which model: the one the benchmark in eval/ picked (see eval/results-test.md), within a
memory budget of 4 GB for the whole search page. Its files live on this computer in
data/models: `search setup` fetches them once, from a fixed commit of the Hugging Face
repository, and checks them; searching never downloads anything.

The model (Qwen3, 28 layers, 4-bit weights) runs here directly with MLX or numpy, like
the meaning model in embedding.py: no PyTorch, no transformers. Only two of its outputs
are needed, the scores of the words "yes" and "no". On the processor, the start of the
prompt (instructions and question) is read once and shared by all the results.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

import numpy as np

from docsearch import cli

# The chosen model, and the exact files (a commit of the model repository).
MODEL = "mlx-community/Qwen3-Reranker-0.6B-4bit"
REVISION = "5f324548f1d20c2b5a450f126fc6ef2fb1126524"
# Exactly these files, each checked against the SHA-256 Hugging Face publishes for this
# commit. Weights in safetensors only (plain numbers; pickle files can run code).
FILES = {
    "config.json": "09adff58b65e9305009c9caa4923b3365b18dd2f84135b44168aaf869278bea4",
    "tokenizer.json": "be75606093db2094d7cd20f3c2f385c212750648bd6ea4fb2bf507a6a4c55506",
    "tokenizer_config.json": "1689852cc9c45010de040c8302a8acdc0d2c4c6c740dd7e9dd0a8c704e16eada",
    "model.safetensors": "1d212560a5b1c36186787fdae19f11f20fecfc29bef91522e12a8e0d118f4545",
}
TOP = 20                       # results it reads (more = slower, rarely better)
MAX_DOC_TOKENS = 320           # of each result
PIN = True                     # exact API-name matches stay first (chosen on the dev split)
FUSE: float | None = None      # also keep this much of the normal order (rank fusion weight)


def model_dir() -> Path | None:
    folder = cli.pinned_dir(MODEL, REVISION)
    return folder if all((folder / f).exists() for f in FILES) else None


def download() -> Path:
    """Fetch the model files (only `search setup` does this, once), each checked."""
    return cli.fetch_pinned(MODEL, REVISION, FILES)


def reorder(ids: list[int], scores: list[float], exact: set[int],
            pin: bool = PIN, fuse: float | None = FUSE) -> list[int]:
    """The final order: the model's scores for the first len(scores) results, combined with
    the normal order as chosen on the benchmark (eval/run.py measures this function)."""
    head = ids[:len(scores)]
    order = [head[j] for j in sorted(range(len(head)), key=lambda j: -scores[j])]
    if fuse:
        order = [i for i, _, _ in cli.rrf([("first", head, fuse), ("model", order, 1.0)])]
    if pin:
        top = [i for i in head if i in exact]
        order = top + [i for i in order if i not in exact]
    return order + ids[len(head):]


class Qwen3:
    """The Qwen3 decoder (quantized), enough to read a prompt and score its next word."""

    def __init__(self, folder: Path) -> None:
        import mlx.core as mx
        self.mx = mx
        cfg = json.loads((folder / "config.json").read_text(encoding="utf-8"))
        if cfg.get("model_type") != "qwen3":
            raise ValueError(f"{folder}: not a Qwen3 model")
        self.cfg = cfg
        q = cfg.get("quantization") or {}
        self.group, self.bits = q.get("group_size", 64), q.get("bits", 4)
        self.w = mx.load(str(folder / "model.safetensors"))
        self.layers = cfg["num_hidden_layers"]
        self.heads, self.kv_heads = cfg["num_attention_heads"], cfg["num_key_value_heads"]
        self.dh = cfg.get("head_dim") or cfg["hidden_size"] // self.heads
        self.eps = cfg["rms_norm_eps"]
        self.theta = cfg.get("rope_theta", 1_000_000)

    def rows(self, name: str, ids):
        """Rows of a (quantized) matrix, e.g. the embeddings of these tokens."""
        mx, w = self.mx, self.w
        if f"{name}.scales" not in w:
            return w[f"{name}.weight"][ids]
        return mx.dequantize(w[f"{name}.weight"][ids], w[f"{name}.scales"][ids], w[f"{name}.biases"][ids],
                             group_size=self.group, bits=self.bits)

    def lin(self, x, name: str):
        mx, w = self.mx, self.w
        if f"{name}.scales" not in w:
            return x @ w[f"{name}.weight"].T
        return mx.quantized_matmul(x, w[f"{name}.weight"], w[f"{name}.scales"], w[f"{name}.biases"],
                                   transpose=True, group_size=self.group, bits=self.bits)

    def norm(self, x, name: str):
        return self.mx.fast.rms_norm(x, self.w[f"{name}.weight"], self.eps)

    def hidden(self, ids):
        """The final hidden state of every token: [batch, length, hidden]."""
        mx = self.mx
        B, L = ids.shape
        h = self.rows("model.embed_tokens", ids)
        for n in range(self.layers):
            p = f"model.layers.{n}"
            x = self.norm(h, f"{p}.input_layernorm")

            def heads(t, count, name):
                t = self.norm(t.reshape(B, L, count, self.dh), name) if name else t.reshape(B, L, count, self.dh)
                return t.transpose(0, 2, 1, 3)
            q = heads(self.lin(x, f"{p}.self_attn.q_proj"), self.heads, f"{p}.self_attn.q_norm")
            k = heads(self.lin(x, f"{p}.self_attn.k_proj"), self.kv_heads, f"{p}.self_attn.k_norm")
            v = heads(self.lin(x, f"{p}.self_attn.v_proj"), self.kv_heads, None)
            q = mx.fast.rope(q, self.dh, traditional=False, base=self.theta, scale=1.0, offset=0)
            k = mx.fast.rope(k, self.dh, traditional=False, base=self.theta, scale=1.0, offset=0)
            a = mx.fast.scaled_dot_product_attention(q, k, v, scale=self.dh ** -0.5, mask="causal")
            h = h + self.lin(a.transpose(0, 2, 1, 3).reshape(B, L, -1), f"{p}.self_attn.o_proj")
            x = self.norm(h, f"{p}.post_attention_layernorm")
            g = self.lin(x, f"{p}.mlp.gate_proj")
            h = h + self.lin(g * mx.sigmoid(g) * self.lin(x, f"{p}.mlp.up_proj"), f"{p}.mlp.down_proj")  # SwiGLU
        return self.norm(h, "model.norm")

    def word_scores(self, h, words: list[int]):
        """Scores (logits) of some next words: the output layer, for those rows only."""
        mx = self.mx
        out = self.rows("lm_head" if "lm_head.weight" in self.w else "model.embed_tokens", mx.array(words))
        return h @ out.T


class Reranker:
    PREFIX = ('<|im_start|>system\nJudge whether the Document meets the requirements based on the '
              'Query and the Instruct provided. Note that the answer can only be "yes" or "no".'
              '<|im_end|>\n<|im_start|>user\n')
    SUFFIX = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
    INSTRUCT = ("Given a programmer's question, judge whether this official documentation entry "
                "(an API reference, guide or tutorial section) answers it")

    def __init__(self, folder: Path) -> None:
        from tokenizers import Tokenizer
        if cli.use_mlx():
            import mlx.core as mx
            mx.set_cache_limit(512 << 20)            # keep at most 512 MB of freed GPU memory
            self.mx, self.model = mx, Qwen3(folder)
        else:
            from docsearch import cpu
            self.mx = None
            self.model = cpu.Qwen3(folder, json.loads((folder / "config.json").read_text(encoding="utf-8")))
        self.tok = Tokenizer.from_file(str(folder / "tokenizer.json"))
        self.yes, self.no = self.tok.token_to_id("yes"), self.tok.token_to_id("no")
        self.lock = threading.Lock()

    def _enc(self, text: str) -> list[int]:
        return self.tok.encode(text, add_special_tokens=False).ids

    def _start(self, q: str) -> list[int]:
        return self._enc(f"{self.PREFIX}<Instruct>: {self.INSTRUCT}\n<Query>: {q}\n<Document>: ")

    def _rest(self, doc: str) -> list[int]:
        return self._enc(doc)[:MAX_DOC_TOKENS] + self._enc(self.SUFFIX)

    def _ids(self, q: str, doc: str) -> list[int]:
        return self._start(q) + self._rest(doc)

    def scores(self, q: str, docs: list[str], batch: int = 8) -> list[float]:
        """How strongly the model says "yes, this answers it" (yes minus no), per document."""
        mx = self.mx
        if mx is None:                               # numpy: the prompt start once, then each result
            with self.lock:
                _, past = self.model.run(self._start(q))
                return [float(z[0] - z[1]) for z in
                        (self.model.word_scores(self.model.run(self._rest(d), past)[0], [self.yes, self.no])
                         for d in docs)]
        seqs = [self._ids(q, d) for d in docs]
        out: list[float] = []
        with self.lock:                              # one question at a time on the GPU
            for k in range(0, len(seqs), batch):
                part = seqs[k:k + batch]
                n = max(len(s) for s in part)        # right padding: a causal model never looks ahead
                h = self.model.hidden(mx.array([s + [0] * (n - len(s)) for s in part]))
                last = h[mx.arange(len(part)), mx.array([len(s) - 1 for s in part])]
                z = self.model.word_scores(last, [self.yes, self.no]).astype(mx.float32)
                out += np.array(z[:, 0] - z[:, 1]).tolist()
        return out


_reranker: Reranker | None = None
_load_lock = threading.Lock()


def get() -> Reranker | None:
    """The reranker, loaded on first use (None if its files are not on this computer)."""
    global _reranker
    with _load_lock:
        if _reranker is None:
            folder = model_dir()
            if folder is None:
                return None
            _reranker = Reranker(folder)
        return _reranker
