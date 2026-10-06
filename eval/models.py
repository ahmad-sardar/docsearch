"""Models under test, on Apple's GPU (Metal) through MLX, quantized.

Rerankers read a question together with one documentation entry and give a relevance
score; they never write text, so every answer stays an official docs entry.

    QwenReranker   Qwen3-Reranker (trained for exactly this): P("yes") of its fixed prompt
    ChatJudge      a small chat model asked "does this entry answer the question?":
                   log P("yes") - log P("no") for the next word
    QwenEmbedder   Qwen3-Embedding: question and entries as vectors (last-token pooling)

Batches are padded on the right: a causal model never looks ahead, so the padding does
not change what each sequence's last real token sees. Only the hidden state of that last
token goes through the output layer, which keeps memory small even for 262k-word
vocabularies.
"""
from __future__ import annotations

import mlx.core as mx
import numpy as np
from mlx_lm import load

MAX_DOC_TOKENS = 320


def _head(model, h):
    """Output-layer logits for hidden states h (handles tied embeddings)."""
    if hasattr(model, "lm_head"):
        return model.lm_head(h)
    lm = getattr(model, "language_model", None)
    if lm is not None and hasattr(lm, "lm_head"):
        return lm.lm_head(h)
    inner = model.model if hasattr(model, "model") else model.language_model.model
    return inner.embed_tokens.as_linear(h)


def _inner(model):
    if hasattr(model, "model"):
        return model.model
    return model.language_model.model


def _last_hidden(model, seqs: list[list[int]], pad: int):
    n = max(len(s) for s in seqs)
    x = mx.array([s + [pad] * (n - len(s)) for s in seqs])
    h = _inner(model)(x)                                     # [B, L, H], after the final norm
    last = mx.array([len(s) - 1 for s in seqs])
    return h[mx.arange(len(seqs)), last]                     # [B, H]


class QwenReranker:
    PREFIX = ('<|im_start|>system\nJudge whether the Document meets the requirements based on the '
              'Query and the Instruct provided. Note that the answer can only be "yes" or "no".'
              '<|im_end|>\n<|im_start|>user\n')
    SUFFIX = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
    INSTRUCT = ("Given a programmer's question, judge whether this official documentation entry "
                "(an API reference, guide or tutorial section) answers it")

    def __init__(self, path: str, batch: int = 8):
        self.model, self.tok = load(path)
        self.batch = batch
        self.yes = self.tok.convert_tokens_to_ids("yes")
        self.no = self.tok.convert_tokens_to_ids("no")
        self.pad = self.tok.pad_token_id or 0

    def score(self, q: str, docs: list[str]) -> list[float]:
        head = self.tok.encode(f"{self.PREFIX}<Instruct>: {self.INSTRUCT}\n<Query>: {q}\n<Document>: ",
                               add_special_tokens=False)
        tail = self.tok.encode(self.SUFFIX, add_special_tokens=False)
        seqs = [head + self.tok.encode(d, add_special_tokens=False)[:MAX_DOC_TOKENS] + tail for d in docs]
        out = []
        for k in range(0, len(seqs), self.batch):
            h = _last_hidden(self.model, seqs[k:k + self.batch], self.pad)
            logits = _head(self.model, h)
            two = mx.stack([logits[:, self.no], logits[:, self.yes]], axis=1).astype(mx.float32)
            out += np.array(mx.softmax(two, axis=1)[:, 1]).tolist()
        return out


class ChatJudge:
    SYSTEM = ("You judge search results for a programmer. Answer only 'yes' or 'no': does the "
              "documentation entry answer the question?")

    def __init__(self, path: str, batch: int = 8):
        self.model, self.tok = load(path)
        self.batch = batch
        vocab = self.tok.get_vocab() if hasattr(self.tok, "get_vocab") else self.tok._tokenizer.get_vocab()

        def ids(words):
            return [vocab[w] for w in words if w in vocab]
        self.yes = ids(["yes", "Yes", "▁yes", "▁Yes", "Ġyes", "ĠYes"])
        self.no = ids(["no", "No", "▁no", "▁No", "Ġno", "ĠNo"])
        self.pad = self.tok.pad_token_id if self.tok.pad_token_id is not None else 0

    def prompt(self, q: str, doc: str) -> list[int]:
        doc_ids = self.tok.encode(doc, add_special_tokens=False)[:MAX_DOC_TOKENS]
        doc = self.tok.decode(doc_ids)
        msgs = [{"role": "system", "content": self.SYSTEM},
                {"role": "user", "content": f"Question: {q}\n\nDocumentation entry:\n{doc}\n\n"
                                            "Does this documentation entry answer the question? yes or no"}]
        try:
            text = self.tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True,
                                                enable_thinking=False)
        except Exception:  # noqa: BLE001 - templates without a system role
            msgs = [{"role": "user", "content": self.SYSTEM + "\n\n" + msgs[1]["content"]}]
            text = self.tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        return self.tok.encode(text, add_special_tokens=False)

    def score(self, q: str, docs: list[str]) -> list[float]:
        seqs = [self.prompt(q, d) for d in docs]
        out = []
        for k in range(0, len(seqs), self.batch):
            h = _last_hidden(self.model, seqs[k:k + self.batch], self.pad)
            z = _head(self.model, h).astype(mx.float32)
            logp = z - mx.logsumexp(z, axis=-1, keepdims=True)
            yes = mx.logsumexp(logp[:, self.yes], axis=1)
            no = mx.logsumexp(logp[:, self.no], axis=1)
            out += np.array(yes - no).tolist()
        return out


class QwenEmbedder:
    TASK = "Given a programmer's question, retrieve official documentation that answers it"

    def __init__(self, path: str, batch: int = 32):
        self.model, self.tok = load(path)
        self.batch = batch
        self.eos = self.tok.eos_token_id
        self.pad = self.tok.pad_token_id or self.eos

    def _embed(self, texts: list[str], max_tokens: int) -> np.ndarray:
        seqs = [self.tok.encode(t, add_special_tokens=False)[:max_tokens] + [self.eos] for t in texts]
        order = np.argsort([len(s) for s in seqs])                # similar lengths batch together
        out = np.zeros((len(texts), 0), dtype=np.float32)
        vecs = [None] * len(texts)
        for k in range(0, len(seqs), self.batch):
            idx = order[k:k + self.batch]
            h = _last_hidden(self.model, [seqs[i] for i in idx], self.pad).astype(mx.float32)
            h = h / mx.linalg.norm(h, axis=1, keepdims=True)
            for j, v in zip(idx, np.array(h)):
                vecs[j] = v
        out = np.stack(vecs)
        return out

    def docs(self, texts: list[str]) -> np.ndarray:
        return self._embed(texts, 128)

    def query(self, q: str) -> np.ndarray:
        return self._embed([f"Instruct: {self.TASK}\nQuery:{q}"], 128)[0]
