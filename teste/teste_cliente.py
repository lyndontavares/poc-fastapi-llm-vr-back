import requests
url = "http://localhost:8000//upload_zip_xlsx_with_prompt"

prompts = [
    '''
        ## Descrição do Problema
         ### Agente 
            Você é um especialista em processamento e análise de dados de recursos humanos, 
            com o objetivo de gerar uma base de dados precisa para o envio de benefícios de Vale-Refeição
            (VR) a uma operadora. 
         ### Objetivo
            Sua tarefa é integrar e validar dados de várias fontes para produzir uma
            lista final de colaboradores elegíveis com os valores de VR calculados corretamente para a 
            competência de Maio de 2025.
    '''

    '''
        ## Entradas 
         -	ATIVOS.xlsx: Lista de colaboradores ativos com matrícula, sindicato e situação.
         -	ADMISSÃO ABRIL.xlsx: Lista de admitidos em abril de 2025 com matrícula e data de admissão.
         -	AFASTAMENTOS.xlsx: Lista de colaboradores afastados com matrícula e tipo de afastamento.
         -	DESLIGADOS.xlsx: Lista de colaboradores desligados com matrícula, data de demissão e status de comunicado.
         -	FÉRIAS.xlsx: Lista de colaboradores em férias com matrícula e dias de férias.
         -	EXTERIOR.xlsx: Lista de colaboradores que atuam no exterior.
         -	Base dias uteis.xlsx: Tabela de dias úteis por sindicato.
         -	Base sindicato x valor.xlsx: Tabela de valores diários de VR por sindicato.
         -	VR MENSAL 05.2025.xlsx: Modelo de planilha de saída.
    '''

    '''
        ## Requisitos e Lógica de Negócio 
        1.	Padronização de Dados: 
           - Unificar as colunas de identificação de colaboradores para 'MATRICULA' em todos os arquivos.
           - Renomear a coluna 'Cadastro' para 'MATRICULA' no arquivo 'EXTERIOR.xlsx'.
           - Substituir os nomes de estados por nomes completos de sindicatos no arquivo 'Base sindicato x valor.xlsx' conforme a especificação fornecida:"
          - 'Paraná' -> 'SITEPD PR - SIND DOS TRAB EM EMPR PRIVADAS DE PROC DE DADOS DE CURITIBA E REGIAO METROPOLITANA'
          - 'Rio de Janeiro' -> 'SINDPD RJ - SINDICATO PROFISSIONAIS DE PROC DADOS DO RIO DE JANEIRO'
          - 'Rio Grande do Sul' -> 'SINDPPD RS - SINDICATO DOS TRAB. EM PROC. DE DADOS RIO GRANDE DO SUL'
          - 'São Paulo' -> 'SINDPD SP - SIND.TRAB.EM PROC DADOS E EMPR.EMPRESAS PROC DADOS ESTADO DE SP.'
    '''

    '''
        2.Tratamento de Exclusões:
          -	Identificar e remover da base final os colaboradores que são: 
          -	Diretores (cargo não especificado, assumir que não há na base para este momento). 
          -	Estagiários e Aprendizes (buscar por 'ESTAGIARIO' e 'APRENDIZ' no TITULO DO CARGO e remover). 
          -	Afastados ou em Licença (matrículas presentes em AFASTAMENTOS.xlsx). 
          -	Profissionais no exterior (matrículas presentes em EXTERIOR.xlsx). 
          -	Empregados desligados: 
            - Excluir da compra aqueles com DATA DEMISSÃO até 15/05/2025 e com COMUNICADO DE DESLIGAMENTO como 'OK'.
            - Para desligamentos após 15/05/2025, manter na base para cálculo proporcional.
    '''
    '''
        ## RETORNO
        - Retorne uma planilha com conteúdo da tabela VR MENSAL 05.2025.xls.
        - Não retorn SQL, Python, Use somente formato .csv para formar a planilha.
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
