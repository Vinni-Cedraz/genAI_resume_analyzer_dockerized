from flask import Flask, request, jsonify
import os
from werkzeug.utils import secure_filename
from werkzeug.exceptions import TooManyRequests
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import LLMChainExtractor
from langchain_huggingface import HuggingFaceEndpoint
import logging
import spacy

UPLOAD_FOLDER = "./pdfs_posted/"
ALLOWED_EXTENSIONS = {"pdf"}
MAX_FILE_SIZE = 15 * 1024 * 1024  # 15MB

app = Flask(__name__)
app.json.ensure_ascii = False
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# LangChain setup
embeddings = HuggingFaceEmbeddings(model_name="neuralmind/bert-base-portuguese-cased")
vector_store = Chroma(persist_directory="./chroma_data", embedding_function=embeddings)

# print huggingface token to debug:
import os
HUGGINGFACEHUB_API_TOKEN = os.getenv("HUGGINGFACEHUB_API_TOKEN")
if HUGGINGFACEHUB_API_TOKEN:
    print(f"Huggingface token: {HUGGINGFACEHUB_API_TOKEN}")
else:
    print("No Huggingface token found")

# Setup LLM for contextual compression
llm = HuggingFaceEndpoint(
    repo_id="pierreguillou/bert-base-cased-squad-v1.1-portuguese", temperature=0.5
)
compressor = LLMChainExtractor.from_llm(llm)

# Setup retriever with contextual compression
retriever = ContextualCompressionRetriever(
    base_compressor=compressor,
    base_retriever=vector_store.as_retriever(search_kwargs={"k": 4}),
)

# Load spaCy Portuguese NER model
spacy.cli.download("pt_core_news_sm")
nlp = spacy.load("pt_core_news_sm")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


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
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(file_path)

        # Check file size
        if os.path.getsize(file_path) > MAX_FILE_SIZE:
            os.remove(file_path)
            return jsonify({"error": "File size exceeds limit"}), 400

        # Process the PDF
        loader = PyPDFLoader(file_path)
        documents = loader.load()

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200
        )
        splits = text_splitter.split_documents(documents)

        # Add to vector store
        vector_store.add_documents(splits)

        return (
            jsonify(
                {
                    "message": f"PDF processed successfully, chunks created:\
                    {len(splits)}"
                }
            ),
            201,
        )
    return jsonify({"error": "Invalid file type"}), 400


@app.route("/curriculum/<string:filename>", methods=["DELETE"])
def delete_curriculum(filename):
    try:
        vector_store.delete(where={"source": filename})
        return jsonify({"message": "Curriculum deleted successfully"}), 200
    except Exception as e:
        return jsonify({"message": f"Error deleting document: {str(e)}"}), 500


@app.route("/search", methods=["GET"])
def search():
    query = request.args.get("query")
    if not query:
        return jsonify({"error": "No query provided"}), 400

    try:
        results = retriever.invoke(query)
    except requests.exceptions.HTTPError as e:
        app.logger.error(f"HTTP error occurred: {e}")
        return jsonify({"error": "Failed to retrieve documents"}), 500
    except Exception as e:
        app.logger.error(f"An error occurred: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

    response_data = []
    for i, doc in enumerate(results):
        response_data.append(
            {
                "document": os.path.basename(doc.metadata["source"]),
                "content": doc.page_content,
                "page": doc.metadata.get("page", 0),
                "name": extract_name(doc.page_content) if i == 0 else "",
            }
        )

    return jsonify(response_data), 200


def extract_name(content):
    doc = nlp(content)
    for ent in doc.ents:
        if ent.label_ == "PER":
            return ent.text
    return ""  # Return empty string if no name is found


@app.errorhandler(TooManyRequests)
def handle_too_many_requests(e):
    return jsonify({"error": "Limit of requests exceeded. Try again later."}), 429


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
