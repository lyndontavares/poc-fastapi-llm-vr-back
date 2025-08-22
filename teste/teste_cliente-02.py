import requests
url = "http://localhost:8000//upload_zip_xlsx_with_prompt"

prompts = [

    '''
       Retorne comando para renomear coluna 'Cadastro' para 'MATRICULA' na tabela 'EXTERIOR'.
       buscar por 'ESTAGIARIO' e 'APRENDIZ' no TITULO DO CARGO e deletar registros encontrados. 
       buscar por Afastados ou em Licença (matrículas presentes em AFASTAMENTOS
    '''

]

# Preparndo request
with open("./Dados.zip", "rb") as f:
    files = {'file': ("Dados.zip", f, "application/zip")}
    # junta todos os prompts com "||"
    data = {"prompt": "||".join(prompts)}
    response = requests.post(url, files=files, data=data)
# Salvando resposta em arquivo Excel
if response.status_code == 200:
    with open("resultado.xlsx", "wb") as out:
        out.write(response.content)
    print("Planilha salva em resultado.xlsx")
else:
    print("Erro:", response.status_code, response.text)
