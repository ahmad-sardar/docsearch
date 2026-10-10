"""The meaning model (a small BERT sentence encoder) on Apple's GPU through MLX, or on the
processor with numpy where MLX is not available (cpu.py).

This replaces PyTorch + sentence-transformers (about 700 MB installed): the same model
files, the same vectors (checked against sentence-transformers to a cosine of 0.9999+;
MLX and numpy agree to 0.99999+), but only MLX or numpy and `tokenizers` are needed.

The model: sentence-transformers/multi-qa-MiniLM-L6-cos-v1 (BERT, 6 layers, 384 dims),
mean pooling over the tokens, then unit length.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np


class SentenceEncoder:
    def __init__(self, folder: str | Path) -> None:
        from tokenizers import Tokenizer

        from docsearch import cli, cpu
        folder = Path(folder)
        self.cfg = json.loads((folder / "config.json").read_text(encoding="utf-8"))
        st = folder / "sentence_bert_config.json"
        max_len = json.loads(st.read_text(encoding="utf-8")).get("max_seq_length", 512) if st.exists() else 512
        self.tok = Tokenizer.from_file(str(folder / "tokenizer.json"))
        self.tok.enable_truncation(max_length=max_len)
        self.tok.no_padding()
        if not cli.use_mlx():
            self.mx, self.cpu = None, cpu.Bert(folder, self.cfg)
            return
        import mlx.core as mx
        self.mx, self.cpu = mx, None
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

    def encode(self, texts: list[str], batch: int = 64, progress=None, part: int = 8192) -> np.ndarray:
        """Unit-length vectors, one row per text. progress(n) is called after each n texts.

        Similar lengths batch together. The texts are tokenized `part` at a time, twice: for
        their lengths, then each part of that order as it comes (all 300,000 of a big site's
        at once took 2 GB). The batches are the same as tokenizing them all at once."""
        mx = self.mx
        lengths: list[int] = []
        for k in range(0, len(texts), part):
            lengths += [len(e.ids) for e in self.tok.encode_batch(texts[k:k + part])]
        order = np.argsort(lengths)
        part = max(batch, part // batch * batch)                # (a batch never spans two parts)
        out = np.zeros((len(texts), self.cfg["hidden_size"]), dtype=np.float32)
        encs: dict = {}
        for k in range(0, len(texts), batch):
            if k % part == 0:
                these = order[k:k + part].tolist()
                encs = dict(zip(these, self.tok.encode_batch([texts[i] for i in these])))
            idx = order[k:k + batch]
            L = max(len(encs[i].ids) for i in idx)
            if mx is None:                                      # numpy, on the processor
                ids = np.array([encs[i].ids + [0] * (L - len(encs[i].ids)) for i in idx])
                mask = np.array([[1] * len(encs[i].ids) + [0] * (L - len(encs[i].ids)) for i in idx])
                h = self.cpu.forward(ids, mask)
                pooled = (h * mask[:, :, None]).sum(axis=1) / np.maximum(mask.sum(axis=1, keepdims=True), 1e-9)
                out[idx] = pooled / np.maximum(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12)
                if progress:
                    progress(len(idx))
                continue
            ids = mx.array([encs[i].ids + [0] * (L - len(encs[i].ids)) for i in idx])
            mask = mx.array([[1] * len(encs[i].ids) + [0] * (L - len(encs[i].ids)) for i in idx])
            h = self._forward(ids, mask)
            m = mask[:, :, None].astype(h.dtype)
            pooled = (h * m).sum(axis=1) / mx.maximum(m.sum(axis=1), 1e-9)
            pooled = pooled / mx.maximum(mx.linalg.norm(pooled, axis=1, keepdims=True), 1e-12)
            out[idx] = np.array(pooled.astype(mx.float32))
            if progress:
                progress(len(idx))
        return out
