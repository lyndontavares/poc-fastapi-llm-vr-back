import requests
import json

url = "http://127.0.0.1:8000/multi_agent_zip"

steps = [
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
      '''
     },

    {"agent": "executor", "prompt": ""},   # usa o último SQL gerado

    {"agent": "sql_generator", "prompt":
     '''

        Crie uma lista contento ESTÁGIO, ATIVOS, APRENDIZ e ATIVOS. Adicione as colunas MATRICULA e TITULO_DO_CARGO. 
        Adicione uma coluna para identicar a tabela de origem.
 

     '''},

    {"agent": "executor", "prompt": ""},   # usa o último SQL gerado

    {"agent": "formatter", "prompt": "csv"}
]

files = {"file": open("Dados.zip", "rb")}
data = {"steps": json.dumps(steps)}

result = requests.post(url, files=files, data=data)

# print(result.json())

last_output = result.json()["results"][-1]["output"]

# print(last_output.json())

with open("resultado.json", "w", encoding="utf-8") as f:
    json.dump(result.json(), f, ensure_ascii=False, indent=2)

# RESULTADO FINAL COM DADOS DE VR/VA
filename = "VR_MENSAL_05_2025.csv"

# Salvar em arquivo
with open(filename, "w", encoding="utf-8") as f:
    f.write(last_output)
