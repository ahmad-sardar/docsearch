"""The two models on the processor, with numpy only: for computers without MLX (Windows,
Linux, Intel Macs). The same model files and the same computations as the MLX versions in
embedding.py and rerank.py, in 32-bit floats; numpy's matrix products use every core.

Reading the weights needs no extra library: a safetensors file is an 8-byte length, a JSON
header (name, type, shape, where), then the plain numbers. Nothing in it can run code.
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

import numpy as np

TYPES = {"F32": np.float32, "F16": np.float16, "I64": np.int64, "I32": np.int32, "U32": np.uint32,
         "U8": np.uint8}


def load(path: Path) -> dict[str, np.ndarray]:
    """Every tensor of a .safetensors file. bfloat16 becomes float32 (numpy has no bfloat16;
    it is the top half of a float32, so this is exact)."""
    with open(path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        head = json.loads(f.read(n))
        raw = f.read()
    out = {}
    for name, t in head.items():
        if name == "__metadata__":
            continue
        a, b = t["data_offsets"]
        buf = raw[a:b]
        if t["dtype"] == "BF16":
            arr = (np.frombuffer(buf, "<u2").astype(np.uint32) << 16).view(np.float32)
        elif t["dtype"] in TYPES:
            arr = np.frombuffer(buf, np.dtype(TYPES[t["dtype"]]).newbyteorder("<"))
        else:
            raise ValueError(f"{path.name}: {name} has an unsupported type {t['dtype']}")
        out[name] = arr.reshape(t["shape"])
    return out


def dequantize(w: np.ndarray, scales: np.ndarray, biases: np.ndarray, group: int, bits: int) -> np.ndarray:
    """MLX's affine quantization back to floats: each 32-bit word packs 32/bits numbers,
    lowest bits first; each group of `group` numbers in a row shares a scale and a bias."""
    if bits != 4:
        raise ValueError(f"{bits}-bit weights are not supported (only 4-bit)")
    b = np.ascontiguousarray(w).view(np.uint8)                # little-endian bytes
    q = np.stack([b & 0x0F, b >> 4], axis=-1).reshape(w.shape[0], -1).astype(np.float32)
    q = q.reshape(w.shape[0], -1, group)
    return (q * scales[..., None] + biases[..., None]).reshape(w.shape[0], -1)


def layer_norm(x, w, b, eps):
    mu = x.mean(-1, keepdims=True)
    var = ((x - mu) ** 2).mean(-1, keepdims=True)
    return (x - mu) / np.sqrt(var + eps) * w + b


def rms_norm(x, w, eps):
    return x / np.sqrt((x * x).mean(-1, keepdims=True) + eps) * w


def erf(x):
    """erf to within 1.5e-7 (Abramowitz and Stegun 7.1.26): numpy has no erf."""
    s = np.sign(x)
    a = np.abs(x)
    t = 1.0 / (1.0 + 0.3275911 * a)
    y = 1.0 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t
               + 0.254829592) * t * np.exp(-a * a)
    return s * y


def gelu(x):
    return 0.5 * x * (1.0 + erf(x / np.sqrt(2.0)).astype(x.dtype))     # exact (erf) GELU, as BERT uses


def softmax(z):
    z = z - z.max(-1, keepdims=True)
    np.exp(z, out=z)
    return z / z.sum(-1, keepdims=True)


class Bert:
    """The sentence encoder's BERT: final hidden states of a padded batch."""

    def __init__(self, folder: Path, cfg: dict) -> None:
        self.w = {k: v for k, v in load(folder / "model.safetensors").items() if k != "embeddings.position_ids"}
        self.cfg = cfg
        self.heads = cfg["num_attention_heads"]
        self.eps = cfg.get("layer_norm_eps", 1e-12)

    def lin(self, x, name):
        return x @ self.w[f"{name}.weight"].T + self.w[f"{name}.bias"]

    def ln(self, x, name):
        return layer_norm(x, self.w[f"{name}.weight"], self.w[f"{name}.bias"], self.eps)

    def forward(self, ids: np.ndarray, mask: np.ndarray) -> np.ndarray:
        w = self.w
        B, L = ids.shape
        h = (w["embeddings.word_embeddings.weight"][ids] + w["embeddings.position_embeddings.weight"][:L]
             + w["embeddings.token_type_embeddings.weight"][0])
        h = self.ln(h, "embeddings.LayerNorm")
        H = h.shape[-1]
        dh = H // self.heads
        bias = ((1.0 - mask.astype(np.float32)) * -1e9)[:, None, None, :]

        def heads(x):
            return x.reshape(B, L, self.heads, dh).transpose(0, 2, 1, 3)
        for n in range(self.cfg["num_hidden_layers"]):
            p = f"encoder.layer.{n}"
            q = heads(self.lin(h, f"{p}.attention.self.query"))
            k = heads(self.lin(h, f"{p}.attention.self.key"))
            v = heads(self.lin(h, f"{p}.attention.self.value"))
            a = softmax(q @ k.transpose(0, 1, 3, 2) * dh ** -0.5 + bias) @ v
            ctx = a.transpose(0, 2, 1, 3).reshape(B, L, H)
            h = self.ln(h + self.lin(ctx, f"{p}.attention.output.dense"), f"{p}.attention.output.LayerNorm")
            h = self.ln(h + self.lin(gelu(self.lin(h, f"{p}.intermediate.dense")), f"{p}.output.dense"),
                        f"{p}.output.LayerNorm")
        return h


class Qwen3:
    """The reranker's Qwen3 decoder. The 4-bit weights are unpacked once at load (about 2 GB
    as floats; the word table stays packed and only the rows needed are unpacked)."""

    def __init__(self, folder: Path, cfg: dict) -> None:
        raw = load(folder / "model.safetensors")
        q = cfg.get("quantization") or {}
        self.group, self.bits = q.get("group_size", 64), q.get("bits", 4)
        self.packed = {}                             # the word table: rows on demand
        self.w = {}
        for name in raw:
            if not name.endswith(".weight"):
                continue
            base = name[:-len(".weight")]
            if f"{base}.scales" not in raw:
                self.w[name] = raw[name].astype(np.float32)
            elif base == "model.embed_tokens" or base == "lm_head":
                self.packed[base] = (raw[name], raw[f"{base}.scales"], raw[f"{base}.biases"])
            else:
                self.w[name] = np.ascontiguousarray(dequantize(raw[name], raw[f"{base}.scales"],
                                                               raw[f"{base}.biases"], self.group, self.bits).T)
        del raw
        self.layers = cfg["num_hidden_layers"]
        self.heads, self.kv_heads = cfg["num_attention_heads"], cfg["num_key_value_heads"]
        self.dh = cfg.get("head_dim") or cfg["hidden_size"] // self.heads
        self.eps = cfg["rms_norm_eps"]
        self.theta = cfg.get("rope_theta", 1_000_000)

    def rows(self, name: str, ids) -> np.ndarray:
        if name in self.packed:
            w, s, b = self.packed[name]
            return dequantize(w[ids], s[ids], b[ids], self.group, self.bits)
        return self.w[f"{name}.weight"][ids]

    def lin(self, x, name):
        return x @ self.w[f"{name}.weight"]          # stored transposed: [in, out]

    def norm(self, x, name):
        return rms_norm(x, self.w[f"{name}.weight"], self.eps)

    def rope(self, x, start: int):
        """Rotary positions, the "split halves" form (MLX traditional=False)."""
        half = self.dh // 2
        inv = self.theta ** (-np.arange(half, dtype=np.float64) * 2 / self.dh)
        ang = np.arange(start, start + x.shape[1])[:, None] * inv[None]
        cos, sin = np.cos(ang).astype(np.float32), np.sin(ang).astype(np.float32)
        a, b = x[..., :half], x[..., half:]
        return np.concatenate([a * cos - b * sin, b * cos + a * sin], axis=-1)

    def run(self, ids: list[int], past: list | None = None) -> tuple[np.ndarray, list]:
        """Read `ids` after the tokens already read into `past` (each layer's keys and values;
        the same prompt start is then read once for all documents). Returns the final hidden
        state of the last token, and the keys and values including these tokens."""
        L, P = len(ids), (0 if past is None else past[0][0].shape[1])
        h = self.rows("model.embed_tokens", np.array(ids))
        mask = np.concatenate([np.zeros((L, P), np.float32),
                               np.triu(np.full((L, L), -np.inf, np.float32), 1)], axis=1)   # causal
        rep = self.heads // self.kv_heads
        kv = []
        for n in range(self.layers):
            p = f"model.layers.{n}"
            x = self.norm(h, f"{p}.input_layernorm")
            q = self.norm(self.lin(x, f"{p}.self_attn.q_proj").reshape(L, self.heads, self.dh),
                          f"{p}.self_attn.q_norm").transpose(1, 0, 2)
            k = self.norm(self.lin(x, f"{p}.self_attn.k_proj").reshape(L, self.kv_heads, self.dh),
                          f"{p}.self_attn.k_norm").transpose(1, 0, 2)
            v = self.lin(x, f"{p}.self_attn.v_proj").reshape(L, self.kv_heads, self.dh).transpose(1, 0, 2)
            q, k = self.rope(q, P), self.rope(k, P)
            if past is not None:
                k, v = np.concatenate([past[n][0], k], axis=1), np.concatenate([past[n][1], v], axis=1)
            kv.append((k, v))
            k, v = np.repeat(k, rep, axis=0), np.repeat(v, rep, axis=0)  # grouped-query attention
            a = softmax(q @ k.transpose(0, 2, 1) * self.dh ** -0.5 + mask) @ v
            h = h + self.lin(a.transpose(1, 0, 2).reshape(L, -1), f"{p}.self_attn.o_proj")
            x = self.norm(h, f"{p}.post_attention_layernorm")
            g = self.lin(x, f"{p}.mlp.gate_proj")
            silu = g * (0.5 + 0.5 * np.tanh(0.5 * g))                     # g * sigmoid(g), no overflow
            h = h + self.lin(silu * self.lin(x, f"{p}.mlp.up_proj"), f"{p}.mlp.down_proj")
        return self.norm(h[-1], "model.norm"), kv

    def word_scores(self, h: np.ndarray, words: list[int]) -> np.ndarray:
        return h @ self.rows("lm_head" if "lm_head" in self.packed or "lm_head.weight" in self.w
                             else "model.embed_tokens", np.array(words)).T
