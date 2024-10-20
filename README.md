# genAI_resume_analyzer_dockerized

RAG conteinerizado para usar de qualquer máquina. Ele carrega informações de PDFs para facilitar sua consulta das habilidades de um grupo de até 50 candidatos por vez.

## Como usar:

### 1. Obtenha a chave de API e instale o Docker
Antes de tudo, você precisa ter uma chave de API da Groq Cloud e o Docker instalado. Se você não tem a chave, gere uma gratuitamente [aqui](https://console.groq.com/).

### 2. Configure a variável de ambiente
Crie uma variável de ambiente com o nome `GROQ_API_KEY` e salve nela a sua chave de API da Groq Cloud. O próximo passo só funcionará se isso for feito corretamente.

### 3. Execute o script
Execute o `run.sh` e responda às duas perguntas iniciais sobre o tamanho do modelo e o limite de requisições.

### 4. Aguarde a inicialização
Aguarde até ver a mensagem: "resume analyzer está pronto, clique aqui para acessar".

### 5. Faça o upload dos currículos
Faça o upload dos currículos e aguarde.

### 6. Realize a consulta
Escreva a informação que quer descobrir sobre os candidatos, por exemplo, "Experiência liderando equipes", clique no botão "Pesquisar" e aguarde. Sim, tem que clicar, apertar a tecla enter não basta.

### 7. Analise os resultados
O Analyzer irá utilizar busca semântica e inteligência artificial generativa para te dizer o nome dos candidatos que possuem a habilidade desejada e um resumo da experiência de cada um nesse quesito. Isso deve servir como um filtro inicial e facilitar a sua busca e leitura manuais.

### 8. Refaça a pesquisa se necessário
Caso a resposta esteja com uma formatação estranha ou resultado abaixo do esperado, simplesmente clique no botão de "Pesquisar" novamente e aguarde. Se isso não resolver o problema, siga a instrução abaixo.

### 9. Tente um modelo maior
É possível que o programa funcione melhor com alguns tipos de buscas e não tão bem com outros. Se isso acontecer, simplesmente rode o `run.sh` novamente e escolha um modelo LLM maior (70b).
