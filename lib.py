import os
import PyPDF2
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from langchain.text_splitter import RecursiveCharacterTextSplitter
import logging
from werkzeug.exceptions import TooManyRequests
from groq import Groq

UPLOAD_FOLDER = "./pdfs_posted/"
ALLOWED_EXTENSIONS = {"pdf"}
MAX_FILE_SIZE = 15 * 1024 * 1024  # 15MB

# FAISS setup
embedding_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
dimension = embedding_model.get_sentence_embedding_dimension()
index = faiss.IndexFlatL2(dimension)
documents = []
metadata = []

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def allowed_file(filename):
    return (
        "." in filename and
        filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def health():
    logger.info("Health check function called")
    return "OK", 200


def upload_file(file):
    if file.filename == "":
        return {"error": "No selected file"}, 400
    if file and allowed_file(file.filename):
        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(file_path)

        # Check file size
        if os.path.getsize(file_path) > MAX_FILE_SIZE:
            os.remove(file_path)
            return {"error": "File size exceeds limit"}, 400

        # Process the PDF
        with open(file_path, "rb") as f:
            pdf_reader = PyPDF2.PdfReader(f)
            text = ""
            for page_num in range(len(pdf_reader.pages)):
                text += pdf_reader.pages[page_num].extract_text()

            splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000, chunk_overlap=500, separators=[" ", "\n", "."]
            )
            chunks = splitter.split_text(text)

            # Store chunks in FAISS
            for i, chunk in enumerate(chunks, start=1):
                embedding = embedding_model.encode(chunk)
                index.add(np.array([embedding]))
                documents.append(chunk)
                metadata.append({"source": file.filename, "chunk_id": i})

        return {
            "message": f"PDF processed successfully, chunks created: {len(chunks)}"
        }, 201
    return {"error": "Invalid file type"}, 400


def delete_curriculum(filename):
    global index, documents, metadata
    indices_to_delete = [i for i, meta in enumerate(metadata) if meta["source"] == filename]
    if not indices_to_delete:
        return {"message": "Curriculum Not Found Within Database"}, 200

    try:
        index.remove_ids(np.array(indices_to_delete))
        documents = [doc for i, doc in enumerate(documents) if i not in indices_to_delete]
        metadata = [meta for i, meta in enumerate(metadata) if i not in indices_to_delete]
        return {"message": "Curriculum deleted successfully"}, 200
    except Exception:
        return {"message": "Error deleting document"}, 500


def search(query):
    query_embedding = embedding_model.encode(query)
    D, I = index.search(np.array([query_embedding]), k=2)
    response_data = []
    labeled = create_labeled_chunks()
    doc_name_dict = {d["document"]: d["name"] for d in labeled}
    for i in I[0]:
        if i == -1:
            continue
        document = metadata[i]["source"]
        content = documents[i].replace("\n", " ").replace("•", " ")
        response_data.append(
            {
                "document": document,
                "content": content,
                "distance": D[0][i],
                "name": doc_name_dict[document],
                "chunk": metadata[i]["chunk_id"],
            }
        )

    response_data = sorted(response_data, key=lambda x: x["distance"])
    return response_data, 200


def query_groq(prompt):
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.2-11b-text-preview"
    )
    return chat_completion.choices[0].message.content


def create_labeled_chunks():
    response_data = []
    for i, doc in enumerate(documents):
        content = doc.replace("\n", " ").replace("•", " ")
        response_data.append(
            {
                "document": metadata[i]["source"],
                "chunk": metadata[i]["chunk_id"],
                "content": content,
                "name": "",
            }
        )

    for chunk in response_data:
        if chunk["chunk"] == 1:
            name = query_groq(
                f"""In the given chunk of text, Identify the name of the
                candidate, filtering out any extra information and return
                only their name and nothing else. Follow the example and
                answer with a name and absolutely no other words, be extremely
                concise.
                <examples>
                    <example1>
                        <chunk>
                            Diego Martins São Paulo, SP | (11) 9XXXX-XXXX |
                            diego.martins@42sp.org.br Resumo Profissional Como
                            Senior Cybersecurity
                        </chunk>
                        <your-answer>
                            Diego Martins
                        </your-answer>
                    </example1>
                    <example2>
                        <chunk>
                            Rafael Almeida São Paulo, SP | (11) 9XXXX-XXXX |
                            rafael.almeida@42sp.org.br
                        </chunk>
                        <your-answer>
                            Rafael Almeida
                        </your-answer>
                    </example2>
                </examples>
                <chunk>
                {chunk["content"][:150]}
                </chunk>
                """
            )
            chunk["name"] = name

    for chunk in response_data:
        if chunk["name"] != "":
            name = chunk["name"]
            doc_id = chunk["document"]
            for chunk in response_data:
                if chunk["document"] == doc_id:
                    chunk["name"] = name
    return response_data


def get_labeled_chunks():
    return create_labeled_chunks(), 200


def handle_too_many_requests(e):
    return (
        {"error": "Limit of requestes exceeded. Try again later."},
        429,
    )
