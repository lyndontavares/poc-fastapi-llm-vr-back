import requests
import json

steps = [

    #############################
    # Ajustar Estrutura de Dados
    #############################
    {"agent": "sql_generator", "prompt":
     '''
        Renomear a coluna 'UNNAMED_2' para 'SITUACAO' na tabela 'EXTERIOR'.
        Remover na tabela 'ATIVOS' os colaboradores de férias.
        Renomear a coluna 'CADASTRO' para 'MATRICULA' na tabela 'EXTERIOR'.
        Remover na tabela BASE_DIAS_UTEIS primeiro registro. 
        Renomear a primeira coluna da tabela 'BASE_DIAS_UTEIS' para 'SINDICATO'.  
        Renomear a segunda coluna da tabela 'BASE_DIAS_UTEIS' para 'DIAS_UTEIS'.
        Renomear a coluna 'UNNAMED_3' para 'SITUACAO' na tabela 'ADMINSSÂO_ABRIL'.
        Renomear a coluna 'UNNAMED_3' para 'SITUACAO' na tabela 'AFASTAMENTOS'.
        Renomear a coluna 'MATRICULA_' para 'MATRICULA' na tabela 'DESLIGADOS'.
     '''},
    {"agent": "executor", "prompt": ""},

    #############################
    # Regras de Exclusão
    #############################
    {"agent": "sql_generator", "prompt":
     '''
        - Interar sobre desligados e remover os colaboradores correspondentes de ATIVOS se campo comunicado de desligamento for 'OK'
        e com data de desligamento menor ou igual 15/05/2025.
        - Iterar sobre as bases de ESTÁGIO, APRENDIZ, AFASTAMENTOS, EXTERIOR e remover os colaboradores correspondentes em ATIVOS.
        - Remover na tabela Ativos os colaboradores com situacao diferente de Trabalhando.
     '''},
    {"agent": "executor", "prompt": ""},

    #############################
    # Preparação dos Dados Finais
    #############################
    {"agent": "sql_generator", "prompt":
     '''

     '''},
    {"agent": "executor", "prompt": ""},

    #############################
    # Formatação Final em CSV
    #############################
    {"agent": "formatter", "prompt": "csv"}
]

############################################################
# Preparar e enviar os dados para o servidor
############################################################

url = "http://127.0.0.1:8000/multi_agent_zip"
files = {"file": open("dados.zip", "rb")}
data = {"steps": json.dumps(steps)}
result = requests.post(url, files=files, data=data)
last_output = result.json()["results"][-1]["output"]

############################################################
# Salvar o resultado completo em um arquivo JSON
############################################################

with open("resultado.json", "w", encoding="utf-8") as f:
    json.dump(result.json(), f, ensure_ascii=False, indent=2)

############################################################
# Salvar o resultado final em um arquivo CSV
############################################################

filename = "VR_MENSAL_05_2025.csv"
# Salvar em arquivo
with open(filename, "w", encoding="utf-8") as f:
    f.write(last_output)
