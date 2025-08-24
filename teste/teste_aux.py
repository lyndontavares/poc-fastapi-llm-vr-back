import requests
import json

# - Selecione a matricula de desligados que  desligamento igual a 'OK' e
#   data de desligamento menor ou igual 15/05/2025, então remova de ativos os registros correspondentes.

# Regras:
# 1. Use apenas colunas existentes no schema informado.
# 2. Nunca invente nomes de colunas ou tabelas.
# 3. Responda apenas com o SQL puro, sem explicações, sem comentários, sem markdown.
# 4. Garanta compatibilidade com SQLite.

# Tabela: DESLIGADOS
# Colunas: MATRICULA, COMUNICADO_DE_DESLIGAMENTO, DATA_DEMISSAO

steps = [

    {"agent": "sql_generator", "prompt":
     '''
    
        Deletar todos os registros de ATIVOS cujas matrículas existem na tabela DESLIGADOS 
        onde COMUNICADO_DE_DESLIGAMENTO = 'OK' e DATA_DEMISSAO <= '2025-05-15'.

 
        '''},


    {"agent": "executor", "prompt": ""},   # usa o último SQL gerado

]


############################################################
url = "http://127.0.0.1:8000/multi_agent_zip"
files = {"file": open("Dados.zip", "rb")}
data = {"steps": json.dumps(steps)}
result = requests.post(url, files=files, data=data)
print(f">>> Results: {result.json()}")
