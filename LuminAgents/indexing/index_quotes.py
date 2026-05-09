import libzim
import lancedb
import pandas as pd
from sentence_transformers import SentenceTransformer
import torch
from tqdm import tqdm
import re
import gc

import os as _os
_BASE = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
ZIM_PATH = _os.path.join(_BASE, "wikiquote_ur_all_maxi_2026-04.zim")
DB_PATH = _os.path.join(_BASE, "db", "LuminAgents_Vectors")
MODEL_NAME = 'all-MiniLM-L6-v2' 

device = "cuda" if torch.cuda.is_available() else "cpu"
model = SentenceTransformer(MODEL_NAME, device=device)
db = lancedb.connect(DB_PATH)

def index_quotes():
    archive = libzim.Archive(ZIM_PATH)
    table_name = "wikiquote_knowledge"
    articles_batch = []
    table = None
    print(f"🚀 طحن الاقتباسات بدأ...")
    for i in tqdm(range(archive.all_entry_count)):
        try:
            entry = archive._get_entry_by_id(i)
            if entry.is_redirect: continue
            item = entry.get_item()
            if not item.mimetype.startswith("text/html"): continue
            content = bytes(item.content).decode('utf-8', errors='ignore')
            clean_text = " ".join(re.sub(r'<[^>]+>', ' ', content).split())
            if len(clean_text) > 100:
                articles_batch.append({"title": entry.title, "text": clean_text[:1000], "source": "wikiquote"})
            if len(articles_batch) >= 5000:
                vectors = model.encode([a['text'] for a in articles_batch], batch_size=512, show_progress_bar=False)
                for idx, v in enumerate(vectors): articles_batch[idx]['vector'] = v.tolist()
                df = pd.DataFrame(articles_batch)
                if table is None: table = db.create_table(table_name, data=df, mode="overwrite")
                else: table.add(data=df)
                articles_batch = []; torch.cuda.empty_cache()
        except: continue
    print("✅ انتهى الاقتباس!")

if __name__ == "__main__": index_quotes()
