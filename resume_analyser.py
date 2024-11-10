#!/usr/bin/env python3.12
import streamlit as st
import requests
import os
from groq import Groq
from collections import defaultdict

def start_secure_resume_api():
    api_process = subprocess.Popen(['python', 'secure_resume_api.py'])
    return api_process

def health_check(url):
    try:
        response = requests.get(url)
        if response.status_code == 200 and response.text.strip() == "OK":
            return True
        else:
            return False
    except requests.exceptions.RequestException:
        return False

# Start the API process
api_process = start_secure_resume_api()

# Give the server some time to start
time.sleep(60)

# Perform health check
api_url = "http://flask_container:5000"
health_url = f"{api_url}/health"
if health_check(health_url):
    st.success("Health check passed: Server is running!")
else:
    st.error("Health check failed: Server is not running!")
    st.stop()

st.title("Análise de currículos")
api_url = "http://flask_container:5000"
model = os.environ.get("MODEL")


def query_groq(sys, user):
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    chat_completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": sys},
            {"role": "user", "content": user},
        ],
        model=model,
    )
    return chat_completion.choices[0].message.content


# Initialize session state
# Initialize session state
if "search" not in st.session_state:
    st.session_state.search = None
# Initialize session_state for files_to_be_uploaded
if "files_to_be_uploaded" not in st.session_state:
    st.session_state.files_to_be_uploaded = True
if "sumarizer" not in st.session_state:
    st.session_state.sumarizer = """
Follow the intructions within the xml tags below:
        <role>
            You are a resume analyzer machine. You'll receive a query and
            a context. Look for the candidates that have the skill
            specified by the query and sumarize their skills.
        </role>
        <rules>
        - Always start your answers with: "Resumo das habilidades em
        <query> de cada candidato:" and finish it with "Sinta-se livre para
        pesquisar mais informações sobre os candidatos", unless the query is
        not related to the main topic.
        - The query should be related to the context of professional skills,
        if it's not, then politely decline the request and guide them back to
        the main topic: professional skills.
        - Do not ask follow up questions.
        - Your answer will ALWAYS be in Brazilian Portuguese.
        - You'll receive context in the following format:
        <candidate_name><chunk1>information from a separate chunk of his resume
        </chunk1><chunk2>information from a different chunk of his resume
        </chunk2></candidate_name>
        - You should follow the examples.
        </rules>
        <examples>
            <correct_query_example>
            <query>
               Java
            </query>
            <your_answer>
            Resumo das habilidades em Java de cada candidato:

                Bruno Souza: (short summary of a the candidate skills here)

                Pedro Lima: (short summary of a the candidate skills here)

                (...)

            Sinta-se livre para pesquisar mais informações sobre os candidatos
            </your_answer>
            </correct_query_example>
            <unrelated_query_example>
            <query>
                Quem foi Thomas Jefferson?
            </query>
            <your_answer>
                Por favor, apenas faça perguntas sobre as
                habilidades dos candidatos.
            </your_answer>
            </unrelated_query_example>
        </examples>
"""


if st.session_state.files_to_be_uploaded:
    files = st.file_uploader(
        "Envie os currículos dos candidatos", accept_multiple_files=True
    )
    if files and st.session_state.files_to_be_uploaded:
        for file in files:
            upload_response = requests.post(
                f"{api_url}/upload_pdf",
                files={"file": file},
            )
            if upload_response.status_code == 201:
                st.success(f"{file.name} enviado com sucesso")
            else:
                st.error(f"Erro ao enviar {file.name}")
        st.session_state.files_to_be_uploaded = False


def create_xml_context(data):
    result = ""
    for name, content_list in data.items():
        content = "".join(
            [
                f"<chunk{i+1}>{chunk}</chunk{i+1}>"
                for i, chunk in enumerate(content_list)
            ]
        )
        content = content.strip()
        result += f"<{name}>{content}</{name}>"
    return result


# SEMANTIC SEARCH:
search_query = st.text_input("Pesquisar por habilidades:")
if st.button("Pesquisar"):
    response = requests.get(
        f"{api_url}/search?query={search_query}",
        params={"query": search_query},
    )
    if response.status_code == 200:
        st.session_state.search = response.json()
    if not st.session_state.search:
        st.error("Erro ao realizar a pesquisa, faça upload dos currículos.")
    else:

        grouped = defaultdict(list)
        for chnk in st.session_state.search:
            grouped[chnk["name"]].append(chnk["content"])

        context = create_xml_context(grouped)

        user_prompt = f"""
            <context>
                {context}
            </context>
            <query>
                {search_query}
            </query>"""

        llm_response = query_groq(st.session_state.sumarizer, user_prompt)

        st.write(llm_response)
