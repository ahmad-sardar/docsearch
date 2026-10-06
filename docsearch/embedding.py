"""The meaning model (a small BERT sentence encoder) on Apple's GPU, through MLX.

This replaces PyTorch + sentence-transformers (about 700 MB installed): the same model
files, the same vectors (checked against sentence-transformers to a cosine of 0.9999+),
but only MLX (Metal) and the `tokenizers` library are needed.

The model: sentence-transformers/multi-qa-MiniLM-L6-cos-v1 (BERT, 6 layers, 384 dims),
mean pooling over the tokens, then unit length.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np


class SentenceEncoder:
    def __init__(self, folder: str | Path) -> None:
        import mlx.core as mx
        from tokenizers import Tokenizer
        folder = Path(folder)
        self.mx = mx
        self.cfg = json.loads((folder / "config.json").read_text())
        st = folder / "sentence_bert_config.json"
        max_len = json.loads(st.read_text()).get("max_seq_length", 512) if st.exists() else 512
        self.tok = Tokenizer.from_file(str(folder / "tokenizer.json"))
        self.tok.enable_truncation(max_length=max_len)
        self.tok.no_padding()
        self.w = {k: v for k, v in mx.load(str(folder / "model.safetensors")).items() if k != "embeddings.position_ids"}
        self.heads = self.cfg["num_attention_heads"]
        self.eps = self.cfg.get("layer_norm_eps", 1e-12)

    def _ln(self, x, name):
        return self.mx.fast.layer_norm(x, self.w[f"{name}.weight"], self.w[f"{name}.bias"], self.eps)

    def _lin(self, x, name):
        return x @ self.w[f"{name}.weight"].T + self.w[f"{name}.bias"]

    def _forward(self, ids, mask):
        mx, w = self.mx, self.w
        B, L = ids.shape
        h = (w["embeddings.word_embeddings.weight"][ids]
             + w["embeddings.position_embeddings.weight"][mx.arange(L)]
             + w["embeddings.token_type_embeddings.weight"][0])
        h = self._ln(h, "embeddings.LayerNorm")
        H = h.shape[-1]
        dh = H // self.heads
        bias = ((1.0 - mask.astype(mx.float32)) * -1e9)[:, None, None, :]   # padding is never attended
        for n in range(self.cfg["num_hidden_layers"]):
            p = f"encoder.layer.{n}"

            def heads(x):
                return x.reshape(B, L, self.heads, dh).transpose(0, 2, 1, 3)
            q = heads(self._lin(h, f"{p}.attention.self.query"))
            k = heads(self._lin(h, f"{p}.attention.self.key"))
            v = heads(self._lin(h, f"{p}.attention.self.value"))
            ctx = mx.fast.scaled_dot_product_attention(q, k, v, scale=dh ** -0.5, mask=bias)
            ctx = ctx.transpose(0, 2, 1, 3).reshape(B, L, H)
            h = self._ln(h + self._lin(ctx, f"{p}.attention.output.dense"), f"{p}.attention.output.LayerNorm")
            inner = self._gelu(self._lin(h, f"{p}.intermediate.dense"))
            h = self._ln(h + self._lin(inner, f"{p}.output.dense"), f"{p}.output.LayerNorm")
        return h

    def _gelu(self, x):
        import mlx.nn as nn
        return nn.gelu(x)                                   # exact (erf) GELU, as BERT uses

    def encode(self, texts: list[str], batch: int = 64) -> np.ndarray:
        """Unit-length vectors, one row per text."""
        mx = self.mx
        encs = self.tok.encode_batch(texts)
        order = np.argsort([len(e.ids) for e in encs])         # similar lengths batch together
        out = np.zeros((len(texts), self.cfg["hidden_size"]), dtype=np.float32)
        for k in range(0, len(texts), batch):
            idx = order[k:k + batch]
            L = max(len(encs[i].ids) for i in idx)
            ids = mx.array([encs[i].ids + [0] * (L - len(encs[i].ids)) for i in idx])
            mask = mx.array([[1] * len(encs[i].ids) + [0] * (L - len(encs[i].ids)) for i in idx])
            h = self._forward(ids, mask)
            m = mask[:, :, None].astype(h.dtype)
            pooled = (h * m).sum(axis=1) / mx.maximum(m.sum(axis=1), 1e-9)
            pooled = pooled / mx.maximum(mx.linalg.norm(pooled, axis=1, keepdims=True), 1e-12)
            out[idx] = np.array(pooled.astype(mx.float32))
        return out
