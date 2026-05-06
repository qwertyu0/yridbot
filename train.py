from langchain.text_splitter import RecursiveCharacterTextSplitter

from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

import os

embedding = HuggingFaceEmbeddings(
    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200
)

# =========================
# ФУНКЦИЯ СОЗДАНИЯ БАЗЫ
# =========================
def build_db(folder, db_name):
    texts = []

    for file in os.listdir(folder):
        if file.endswith(".txt"):
            path = os.path.join(folder, file)

            with open(path, "r", encoding="utf-8") as f:
                texts.append(f.read())

    full_text = "\n\n".join(texts)

    chunks = splitter.split_text(full_text)

    print(f"{db_name}: чанков {len(chunks)}")

    db = Chroma.from_texts(
        chunks,
        embedding,
        persist_directory=db_name
    )

    db.persist()

    print(f"{db_name} готова")


build_db("laws/uk", "db_uk")
build_db("laws/koap", "db_koap")
build_db("laws/fz", "db_fz")
