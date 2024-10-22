from transformers import AutoModelForTokenClassification, AutoTokenizer
import spacy
from PyPDF2 import PdfReader

# Load the NER model and tokenizer
model_name = "Davlan/bert-base-multilingual-cased-ner-hrl"
model = AutoModelForTokenClassification.from_pretrained(model_name)
tokenizer = AutoTokenizer.from_pretrained(model_name)

# Load spaCy's Portuguese model for NER
nlp = spacy.load("pt_core_news_sm")

def extract_text_from_pdf(pdf_path):
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

pdf_path = "curriculo_32.pdf"  # Replace with your actual file path
resume_text = extract_text_from_pdf(pdf_path)

def extract_name(text, tokenizer, model):
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
    outputs = model(**inputs)
    predictions = outputs.logits.argmax(dim=-1).squeeze().tolist()

    # Convert token IDs to words
    tokens = tokenizer.convert_ids_to_tokens(inputs["input_ids"].squeeze())

    # Extract and join words tagged as names
    name = []
    for i in range(len(predictions)):
        if predictions[i] in [1, 2]:  # Assuming '1' and '2' denote person tags
            name.append(tokens[i])
    name = " ".join(name)
    return name.replace(" ##", "")

name = extract_name(resume_text, tokenizer, model)
print(f"Extracted Name: {name}")

def extract_name_with_spacy(text):
    doc = nlp(text)
    for ent in doc.ents:
        if ent.label_ == "PER":
            return ent.text
    return ""

name_spacy = extract_name_with_spacy(resume_text)
print(f"Extracted Name with spaCy: {name_spacy}")
