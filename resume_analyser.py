#!/usr/bin/env python3.12
import streamlit as st
import requests
import os
from groq import Groq
from collections import defaultdict

st.title("Análise de currículos")
api_url = "http://flask_container:5000"

def query_groq(sys_content, user_content, model):
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    chat_completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": sys_content},
            {"role": "user", "content": user_content},
        ],
        model=model,
    )
    return chat_completion.choices[0].message.content

# Initialize session state
if "search" not in st.session_state:
    st.session_state.search = None
if "files_to_be_uploaded" not in st.session_state:
    st.session_state.files_to_be_uploaded = True
if "sumarizer" not in st.session_state:
    st.session_state.sumarizer = """
Follow the intructions within the xml tags below:
    <role>
        You are a resume analyzer machine. You'll receive a query and
        a context. Look for the candidates whose context fit the query the most
        and summarize their skills.
    </role>
    <rules>
    - Always start your answers with: "Resumo das habilidades em
    <query> de cada candidato:" and finish it with "Sinta-se livre para
    pesquisar mais informações sobre os candidatos".
    - Do not ask follow up questions.
    - Your answer will ALWAYS be in Brazilian Portuguese.
    - If the query has absolutely nothing to do with the context of
      professional skills, hard or soft, politely decline to answer.
    - Queries with a more conversational tone, like "Tell me about the
      candidate's experience with Java" or "Which of these candidates would be
      a good fit for a diverse team" are also valid.
    - You'll receive context in the following format:
    <candidate_name><chunk1>information from a separate chunk of his resume
    </chunk1><chunk2>information from a different chunk of his resume
    </chunk2></candidate_name>
    - You should follow the examples.
    </rules>
    <query_example>
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
    </query_example>
"""
if "queries_and_answers" not in st.session_state:
    st.session_state.queries_and_answers = []
if "candidate_names" not in st.session_state:
    st.session_state.candidate_names = []
if "session_closed" not in st.session_state:
    st.session_state.session_closed = False

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

if not st.session_state.session_closed:
    # File uploader
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
            st.session_state.candidate_names = list(grouped.keys())
            context = create_xml_context(grouped)
            user_prompt = f"""
                <context>
                    {context}
                </context>
                <query>
                    {search_query}
                </query>"""
            llm_response = query_groq(
                st.session_state.sumarizer, user_prompt, model=os.environ.get("MODEL")
            )
            st.write(llm_response)
            st.session_state.queries_and_answers.append(
                {"query": search_query, "response": llm_response}
            )

    if st.button("Finalizar seleção"):
        if st.session_state.queries_and_answers and st.session_state.candidate_names:
            first_candidate_name = st.session_state.candidate_names[0]
            system_prompt = "You are a helpful assistant who is generating feedback for a candidate based on previous queries and answers. You write the feedbacks in Brazilian Portuguese."
            user_prompt = f"""
The candidate's name is {first_candidate_name}.

You are to generate a feedback for this candidate that will contain all queries
from the recruiter, and for each query, provide feedback on how this candidate
compared to others regarding what was asked by the query. Be extremely careful not to
mention the names of the other candidates.

Proceed to give the feedback in the following format, talk directly to the candidate:

{first_candidate_name}, here is your personalized feedback:

[Query 1]: [Feedback]

[Query 2]: [Feedback]

...

Here are the queries and your previous responses:

"""
            for item in st.session_state.queries_and_answers:
                user_prompt += f"Query: {item['query']}\nResponse:\n{item['response']}\n\n"
            feedback = query_groq(
                system_prompt, user_prompt, model="llama-3.2-90b-text-preview"
            )

            # Process the feedback to remove names of other candidates
            system_prompt_cleaning = """You are a helpful assistant who edits
texts and doesn't answer with anything other than the edited text.
You will receive a feedback text, and you should fix only one thing:
if the names of OTHER candidates are mentioned they should be completely removed.
Only the name of the candidate who is receiving the feedback can be mentioned.
Let all the rest remain the same."""

            user_prompt_cleaning = f"""Feedback to edit:
{feedback}
"""

            cleaned_feedback = query_groq(
                system_prompt_cleaning, user_prompt_cleaning, model="llama-3.2-11b-text-preview"
            )

            st.write(cleaned_feedback)
            st.session_state.session_closed = True
        else:
            st.error("Não há dados suficientes para gerar o feedback.")
else:
    st.write("A sessão foi encerrada. Nenhuma nova entrada será aceita.")
