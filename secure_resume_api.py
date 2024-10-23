from flask import Flask, request, jsonify
import os
import PyPDF2
import chromadb
from chromadb.utils import embedding_functions
from langchain.text_splitter import RecursiveCharacterTextSplitter
import logging
from werkzeug.exceptions import TooManyRequests
from groq import Groq

UPLOAD_FOLDER = "./pdfs_posted/"
ALLOWED_EXTENSIONS = {"pdf"}
MAX_FILE_SIZE = 15 * 1024 * 1024  # 15MB

app = Flask(__name__)
app.json.ensure_ascii = False
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# chromadb setup:
persist_directory = "./chroma_data"
chroma_client = chromadb.PersistentClient(path=persist_directory)
func = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="paraphrase-multilingual-MiniLM-L12-v2"
)
collection = chroma_client.get_or_create_collection(
    name="curriculos", embedding_function=func
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def allowed_file(filename):
    return (
        "." in filename and
        filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


@app.route("/health")
def health():
    app.logger.info("Health check endpoint called")
    return "OK", 200


@app.route("/upload_pdf", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400
    if file and allowed_file(file.filename):
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
        file.save(file_path)

        # Check file size
        if os.path.getsize(file_path) > MAX_FILE_SIZE:
            os.remove(file_path)
            return jsonify({"error": "File size exceeds limit"}), 400

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

            # Store chunks in ChromaDB
            for i, chunk in enumerate(chunks, start=1):
                collection.add(
                    documents=[chunk],
                    ids=[f"{file.filename}_chunk_{i}"],
                    metadatas=[{"source": file.filename}],
                )

        return (
            jsonify(
                {
                    "message":
                    f"PDF processed successfully, chunks created:\
                    {len(chunks)}"
                }
            ),
            201,
        )
    return jsonify({"error": "Invalid file type"}), 400


@app.route("/curriculum/<string:filename>", methods=["DELETE"])
def delete_curriculum(filename):
    collection = chroma_client.get_or_create_collection("curriculos")
    ids = collection.get(include=[])["ids"]
    if not any(filename in doc_id.split("_chunk_")[0] for doc_id in ids):
        return jsonify(
                {
                    "message": "Curriculum Not Found Within Database"
                }), 200
    try:
        for doc_id in ids:
            if filename in doc_id:
                collection.delete(ids=[doc_id])
        return jsonify({"message": "Curriculum deleted successfully"}), 200
    except Exception:
        return jsonify({"message": "Error deleting document"}), 500


@app.route("/search", methods=["GET"])
def search():
    query = request.args.get("query")
    meta = collection.get(include=["metadatas"])["metadatas"]
    meta = set(d["source"] for d in meta)
    response_data = []
    labeled = create_labeled_chunks()
    doc_name_dict = {d["document"]: d["name"] for d in labeled}
    for source in meta:
        results = collection.query(
            query_texts=[query], where={"source": source}, n_results=2
        )
        for i, result in enumerate(results["ids"][0]):
            document = result.split("_chunk_")[0]
            content = (
                    results["documents"][0][i]
                    .replace("\n", " ").replace("•", " ")
            )
            response_data.append(
                {
                    "document": document,
                    "content": content,
                    "distance": results["distances"][0][i],
                    "name": doc_name_dict[document],
                    "chunk": int(result.split("_chunk_")[1]),
                }
            )

    response_data = sorted(response_data, key=lambda x: x["distance"])
    return jsonify(response_data), 200


def query_groq(prompt):
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.2-11b-text-preview"
    )
    return chat_completion.choices[0].message.content


def create_labeled_chunks():
    results = collection.get(include=["documents"])
    response_data = []
    for i, result in enumerate(results["ids"]):
        content = results["documents"][i].replace("\n", " ").replace("•", " ")
        response_data.append(
            {
                "document": result.split("_chunk_")[0],
                "chunk": int(result.split("_chunk_")[1]),
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


@app.route("/labeled", methods=["GET"])
def get_labeled_chunks():
    return jsonify(create_labeled_chunks()), 200


@app.errorhandler(TooManyRequests)
def handle_too_many_requests(e):
    return (
        jsonify({"error": "Limit of requestes exceeded. Try again later."}),
        429,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
