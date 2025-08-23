import requests
import json


steps = [


    {"agent": "sql_generator", "prompt":
     '''
 
       Remover na tabela Ativos os colaboradores com situacao diferente de Trabalhando.

     '''},

    {"agent": "executor", "prompt": ""},   # usa o último SQL gerado

]


############################################################
url = "http://127.0.0.1:8000/multi_agent_zip"
files = {"file": open("Dados.zip", "rb")}
data = {"steps": json.dumps(steps)}
result = requests.post(url, files=files, data=data)
print(f">>> Results: {result.json()}")
