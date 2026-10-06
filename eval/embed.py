"""Embed every index entry with one model, in its own process, and save the vectors.

    .venv/bin/python eval/embed.py bge-small OUT.npy
    .venv/bin/python eval/embed.py qwen3-emb OUT.npy

Run separately so the GPU memory the model needs is freed when it exits (the benchmark
process then only holds the saved vectors). Offline: models come from the test-model folder.
"""
import sys
import time

import numpy as np

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from docsearch import cli  # noqa: E402


def texts() -> list[str]:
    sids = sorted(d.name for d in cli.HOME.iterdir() if (d / "meta.json").exists())
    out = []
    for sid in sids:
        _, entries = cli.load(sid)
        out += [f"{cli.api_name(e.title)}\n{cli.plain(e.text)[:cli.EMBED_CHARS]}" for e in entries]
    return out


def main(model: str, out: str) -> None:
    from run import hf_path
    t, docs = time.time(), texts()
    if model == "bge-small":
        from sentence_transformers import SentenceTransformer
        m = SentenceTransformer(hf_path("BAAI/bge-small-en-v1.5"), device="mps", local_files_only=True)
        V = m.encode(docs, batch_size=128, normalize_embeddings=True, show_progress_bar=False)
    elif model == "qwen3-emb":
        import mlx.core as mx
        mx.set_cache_limit(1 << 30)
        from models import QwenEmbedder
        V = QwenEmbedder(hf_path("mlx-community/Qwen3-Embedding-0.6B-4bit-DWQ"), batch=64)._embed(docs, 64)
    else:
        raise SystemExit(f"unknown model {model}")
    np.save(out, np.asarray(V, dtype=np.float32))
    print(f"embedded {len(docs)} entries with {model} in {time.time() - t:.0f} s", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
