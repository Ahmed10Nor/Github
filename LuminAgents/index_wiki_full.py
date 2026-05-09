import libzim
import lancedb
import pandas as pd
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
import os
import re
import json
import torch

import os as _os
_BASE     = _os.path.dirname(_os.path.abspath(__file__))
ZIM_PATH  = _os.path.join(_BASE, "wikipedia_en_all_nopic_2026-03.zim")
DB_PATH   = _os.path.join(_BASE, "db", "LuminAgents_Full_Wiki")
CKPT_PATH = _os.path.join(_BASE, "db", "index_checkpoint.json")
BATCH_SIZE = 40000

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Working on: {device.upper()}")

model = SentenceTransformer('all-MiniLM-L6-v2', device=device)
db    = lancedb.connect(DB_PATH)

# ── checkpoint helpers ────────────────────────────────────────────────────────
def load_checkpoint() -> int:
    """Return the last fully-processed entry index, or -1 if fresh start."""
    if os.path.exists(CKPT_PATH):
        with open(CKPT_PATH) as f:
            data = json.load(f)
        idx = data.get("last_entry_index", -1)
        print(f"Resuming from entry {idx + 1:,}")
        return idx
    return -1

def save_checkpoint(last_index: int):
    os.makedirs(os.path.dirname(CKPT_PATH), exist_ok=True)
    with open(CKPT_PATH, "w") as f:
        json.dump({"last_entry_index": last_index}, f)

# ── html cleaner ─────────────────────────────────────────────────────────────
def clean_html(raw_html):
    clean = re.sub(r'<[^>]+>', ' ', raw_html)
    return " ".join(clean.split())

# ── main indexer ─────────────────────────────────────────────────────────────
def process_full_zim():
    if not os.path.exists(ZIM_PATH):
        print(f"Error: ZIM file not found at {ZIM_PATH}")
        return

    start_i = load_checkpoint()          # -1 = fresh, N = resume after N

    # Decide table mode: append if table already exists (resume), else overwrite
    table_exists = "wiki_knowledge" in db.table_names()
    table = db.open_table("wiki_knowledge") if table_exists else None

    archive = libzim.Archive(ZIM_PATH)
    total   = archive.all_entry_count
    batch_articles = []

    print(f"Total entries: {total:,}  |  Starting at: {start_i + 1:,}")

    with tqdm(total=total, initial=start_i + 1) as pbar:
        for i in range(start_i + 1, total):
            try:
                entry = archive._get_entry_by_id(i)
                if entry.is_redirect:
                    pbar.update(1)
                    continue
                item = entry.get_item()
                if not item.mimetype.startswith("text/html"):
                    pbar.update(1)
                    continue

                text = clean_html(bytes(item.content).decode('utf-8', errors='ignore'))
                if len(text) > 500:
                    batch_articles.append({
                        "title":  entry.title,
                        "text":   text[:1000],
                        "source": "wikipedia",
                    })

                if len(batch_articles) >= BATCH_SIZE:
                    df      = pd.DataFrame(batch_articles)
                    vectors = model.encode(
                        df['text'].tolist(),
                        show_progress_bar=False,
                        batch_size=128,
                    )
                    df['vector'] = vectors.tolist()

                    if table is None:
                        table = db.create_table("wiki_knowledge", data=df, mode="overwrite")
                    else:
                        table.add(data=df)

                    batch_articles = []
                    save_checkpoint(i)          # ← checkpoint after every batch
                    print(f"\n[CKPT] Saved at entry {i:,}")

            except Exception:
                pass
            pbar.update(1)

    # flush remaining articles
    if batch_articles:
        df      = pd.DataFrame(batch_articles)
        vectors = model.encode(df['text'].tolist(), show_progress_bar=False, batch_size=128)
        df['vector'] = vectors.tolist()
        if table is None:
            db.create_table("wiki_knowledge", data=df, mode="overwrite")
        else:
            table.add(data=df)
        save_checkpoint(total - 1)

    print("Indexing complete.")

if __name__ == "__main__":
    process_full_zim()
