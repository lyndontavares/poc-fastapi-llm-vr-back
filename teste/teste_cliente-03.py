import requests
url = "http://localhost:8000//upload_zip_xlsx_with_prompt"

prompts = [

    '''
    AGENTE: 
        Gere os comandos SQL necessários para resolver o pedido a seguir.
        Forneça apenas os comandos SQL em ordem de execução, cada um separado por ponto e vírgula.
        Não adicione comentários, explicações ou texto adicional.

    TAREFA: 
        Remover na tabela 'ATIVOS' os colaboradores de férias.
        Renomear a coluna 'CADASTRO' para 'MATRICULA' na tabela 'EXTERIOR'.
    ''',

    ''' 
    Retorne somente valores separados por vírgula,
    Inclua cabeçalhos da tabela,
    Evite qualquer explicação ou prefixo,
    Lista a tabela de EXTERIOR (Não use LIMIT)
    ''',

]

# Preparndo request
with open("./Dados.zip", "rb") as f:
    files = {'file': ("Dados.zip", f, "application/zip")}
    # junta todos os prompts com "||"
    data = {"prompt": "||".join(prompts)}
    response = requests.post(url, files=files, data=data)
# Salvando resposta em arquivo Excel
if response.status_code == 200:
    with open("result.csv", "wb") as out:
        out.write(response.content)
    print("Planilha salva em result.csv")
else:
    print("Erro:", response.status_code, response.text)
