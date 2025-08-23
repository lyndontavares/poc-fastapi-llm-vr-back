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
        Renomear a coluna 'UNNAMED_3' para 'SITUACAO' na tabela 'ADMISSÃO_ABRIL'.
        Renomear a coluna 'UNNAMED_3' para 'SITUACAO' na tabela 'AFASTAMENTOS'.
        Renomear a coluna 'MATRICULA_' para 'MATRICULA' na tabela 'DESLIGADOS'.

        adicione VALOR inteiro na tabela BASE_DIAS_UTEIS.
        atualize VALOR=22 em BASE_DIAS_UTEIS quando SINDICATO contém ' PR ' ou ' SP '.
        atualize VALOR=21 em BASE_DIAS_UTEIS quando SINDICATO contém ' RJ ' ou ' RS '.
        

     '''},
    {"agent": "executor", "prompt": ""},

    #############################
    # Regras de Exclusão
    #############################
    {"agent": "sql_generator", "prompt":
     ''' 

        - Interar sobre desligados e deletar de ATIVOS se campo comunicado de desligamento for 'OK' e 
          data de desligamento menor ou igual 15/05/2025 e MATRICULA iguals.
        - Iterar sobre as bases de ESTÁGIO, APRENDIZ, AFASTAMENTOS, EXTERIOR e remover os colaboradores correspondentes em ATIVOS.
        - Remover na tabela Ativos os colaboradores com situacao diferente de Trabalhando.
        
     '''},
    {"agent": "executor", "prompt": ""},

    #############################
    # Preparação dos Dados Finais
    #############################
    {"agent": "sql_generator", "prompt":
     '''
        Crie uma tabela chamada 'VR_MENSAL_05_2025_FINAL', se ela não existe, com os seguintes campos:
            MATRICULA inteiro,
            ADMISSAO data,
            SINDICATO texto,
            COMPETENCIA data, 
            DIAS inteiro, 
            VALOR_DIARIO_VR real,
            TOTAL_VR real,
            CUSTO_EMPRESA real,
            DESCONTO_PROFISSIONAL real,
            OBS_GERAL texto.
        
        Delete todos os registros da tabela 'VR_MENSAL_05_2025_FINAL'.

        Itere sobre o relacinamento a seguir:
            ATIVOS relaciona com ADMISSÃO_ABRIL por MATRICULA,
            ATIVOS relaciona com BASE_DIAS_UTEIS por SINDICATO

            inserir na tabela VR_MENSAL_05_2025_FINAL os seguintes campos:
                MATRICULA vindo de ATIVOS,
                ADMISSAO vindo do campo ADMISSÂO da ADMISSÃO_ABRIL,
                SINDICATO vindo de SINDICATO da ATIVOS, 
                COMPETENCIA com valor fixo '2025-05-01',
                DIAS com DIAS da BASE_DIAS_UTEIS,
                VALOR_DIARIO_VR com com VALOR de ASE_DIAS_UTEIS,
                TOTAL_VR calculado como DIAS * VALOR_DIARIO_VR,
                CUSTO_EMPRESA calculado como TOTAL_VR * 1.12,
                DESCONTO_PROFISSIONAL calculado como TOTAL_VR * 0.02,
                OBS_GERAL com valor fixo 'VR MENSAL MAIO/2025'

     '''},
    {"agent": "executor", "prompt": ""},


    #############################
    # SQL Formação da PLanilha de Retorno
    #############################
    {"agent": "sql_generator", "prompt":
     '''

      Retorne VR_MENSAL_05_2025_FINAL sem LIMIT.
        
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
