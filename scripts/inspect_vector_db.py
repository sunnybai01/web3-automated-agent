"""Inspect Chroma vector DB collections and sample metadata."""
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import chromadb
from config.settings import settings


def main():
    host = os.getenv("CHROMA_HOST", settings.CHROMA_HOST)
    port = int(os.getenv("CHROMA_PORT", settings.CHROMA_PORT))

    client = chromadb.HttpClient(host=host, port=port)
    collections = client.list_collections()

    print(f"chroma={host}:{port}")
    print(f"collections={len(collections)}")

    for col in collections:
        print(f"\n== {col.name} ==")
        try:
            count = col.count()
        except Exception as e:
            print(f"count_error={e}")
            continue

        print(f"count={count}")

        if count <= 0:
            continue

        limit = 5 if count >= 5 else count
        data = col.get(limit=limit, include=["metadatas", "documents"])
        ids = data.get("ids") or []
        metas = data.get("metadatas") or []
        docs = data.get("documents") or []

        for i, vec_id in enumerate(ids):
            meta = metas[i] if i < len(metas) else {}
            doc = docs[i] if i < len(docs) and docs[i] else ""
            preview = doc.replace("\n", " ")[:120]
            print(f"- id={vec_id}")
            print(f"  metadata={meta}")
            print(f"  doc_preview={preview}")


if __name__ == "__main__":
    main()
