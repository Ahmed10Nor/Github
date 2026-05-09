import lancedb
import pandas as pd
import xml.etree.ElementTree as ET
from sentence_transformers import SentenceTransformer
import torch
from tqdm import tqdm
import gc
import re
import os

import os as _os
_BASE = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
STACK_FOLDERS = [_os.path.join(_BASE, "academia.stackexchange.com"), _os.path.join(_BASE, "lifehacks.stackexchange.com")]
DB_PATH = _os.path.join(_BASE, "db", "LuminAgents_Vectors")
MODEL_NAME = 'all-MiniLM-L6-v2'

device = "cuda" if torch.cuda.is_available() else "cpu"
model = SentenceTransformer(MODEL_NAME, device=device)
db = lancedb.connect(DB_PATH)

def index_stack():
    table_name = "human_expertise"
    table = None
    for folder in STACK_FOLDERS:
        xml_path = os.path.join(folder, "Posts.xml")
        if not os.path.exists(xml_path): continue
        print(f"🚀 طحن {os.path.basename(folder)}...")
        posts_batch = []
        context = ET.iterparse(xml_path, events=('end',))
        for event, elem in tqdm(context):
            if elem.tag == 'row':
                body = elem.get('Body', ''); title = elem.get('Title', '')
                if len(body) > 150:
                    clean_text = re.sub(r'<[^>]+>', ' ', f"{title} {body}"[:1000])
                    posts_batch.append({"title": title if title else "Advice", "text": " ".join(clean_text.split()), "source": os.path.basename(folder)})
                elem.clear()
                if len(posts_batch) >= 5000:
                    vectors = model.encode([p['text'] for p in posts_batch], batch_size=512, show_progress_bar=False)
                    for idx, v in enumerate(vectors): posts_batch[idx]['vector'] = v.tolist()
                    df = pd.DataFrame(posts_batch)
                    if table is None: table = db.create_table(table_name, data=df, mode="overwrite")
                    else: table.add(data=df)
                    posts_batch = []; gc.collect(); torch.cuda.empty_cache()
    print("✅ انتهى Stack Exchange!")

if __name__ == "__main__": index_stack()
