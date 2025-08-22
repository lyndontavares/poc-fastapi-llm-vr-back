import requests

# URL do endpoint FastAPI
url = "http://localhost:8000//upload_zip_xlsx_with_prompt"

# Caminho relativo do arquivo zip com várias planilhas
zip_path = "./Dados.zip"

# Supondo que o zip contenha as planilhas:
# "VR_MENSAL.xlsx", "ATIVOS.xlsx", "ADMISSAO_ABRIL.xlsx"
# Criamos prompts encadeados explicitando a tabela alvos
prompts = [
    "Na tabela 'VR_MENSAL', crie uma nova coluna chamada 'TOTAL_BRUTO' que é a soma de 'TOTAL' e 'CUSTO EMPRESA'.",
    "Na tabela 'VR_MENSAL', filtre apenas as linhas onde 'TOTAL_BRUTO' > 200.",
    " retorne a média da coluna 'TOTAL_BRUTO' em um novo DataFrame com uma única linha."
]

# Concatena múltiplos prompts usando '||' para envio
prompt_str = "||".join(prompts)

# Abrir arquivo zip local
with open(zip_path, "rb") as f:
    files = {"file": ("Dados.zip", f, "application/zip")}
    data = {"prompt": prompt_str}

    # Enviar POST request
    response = requests.post(url, files=files, data=data)

# Salvar planilha de resultado
if response.status_code == 200:
    with open("resultado.xlsx", "wb") as out:
        out.write(response.content)
    print("✅ Planilha salva em resultado.xlsx")
else:
    print("❌ Erro:", response.status_code, response.text)
