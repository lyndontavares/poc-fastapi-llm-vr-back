import requests
import json

steps = [


    {"agent": "sql_generator", "prompt":
     '''
        Interar sobre desligados e remover os colaboradores correspondentes de ATIVOS se campo comunicado de desligamento for 'OK'
     '''},

    {"agent": "executor", "prompt": ""},   # usa o último SQL gerado
]

""" TESTES:
        Crie uma lista contento ESTÁGIO, ATIVOS, APRENDIZ e ATIVOS. Adicione as colunas MATRICULA e TITULO_DO_CARGO. 
        Adicione uma coluna para identicar a tabela de origem.
"""

############################################################
url = "http://127.0.0.1:8000/multi_agent_zip"
files = {"file": open("Dados.zip", "rb")}
data = {"steps": json.dumps(steps)}
result = requests.post(url, files=files, data=data)
last_output = result.json()["results"][-1]["output"]
# print(last_output.json())
with open("resultado.json", "w", encoding="utf-8") as f:
    json.dump(result.json(), f, ensure_ascii=False, indent=2)
# RESULTADO FINAL COM DADOS DE VR/VA
filename = "VR_MENSAL_05_2025.csv"
# Salvar em arquivo
with open(filename, "w", encoding="utf-8") as f:
    f.write(last_output)
############################################################
