import requests
import json


steps = [

    {"agent": "sql_generator", "prompt":
     '''
        ## 1
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
 
        ## 2
        Renomear a coluna 'UNNAMED_2' para 'SITUACAO' na tabela 'EXTERIOR'.
        Remover na tabela 'ATIVOS' os colaboradores de férias.
        Renomear a coluna 'CADASTRO' para 'MATRICULA' na tabela 'EXTERIOR'.
        Remover na tabela BASE_DIAS_UTEIS primeiro registro. 
        Renomear a primeira coluna da tabela 'BASE_DIAS_UTEIS' para 'SINDICATO'.  
        Renomear a segunda coluna da tabela 'BASE_DIAS_UTEIS' para 'DIAS_UTEIS'.
        Renomear a coluna 'UNNAMED_3' para 'SITUACAO' na tabela 'ADMISSÃO_ABRIL'.
        Renomear a coluna 'UNNAMED_3' para 'SITUACAO' na tabela 'AFASTAMENTOS'.
        Renomear a coluna 'MATRICULA_' para 'MATRICULA' na tabela 'DESLIGADOS'.

        ## 3

       adicione VALOR inteiro na tabela BASE_DIAS_UTEIS.
       atualize VALOR=22 em BASE_DIAS_UTEIS quando SINDICATO contém ' PR ' ou ' SP '.
       atualize VALOR=21 em BASE_DIAS_UTEIS quando SINDICATO contém ' RJ ' ou ' RS '.

        
        '''},


    {"agent": "sql_generator", "prompt":
     '''    

  Itere sobre a relação entre tabelas 
            ATIVOS, ADMISSÃO_ABRIL, BASE_DIAS_UTEIS:
            inserir na tabela VR_MENSAL_05_2025_FINAL os seguintes campos:
            MATRICULA de ATIVOS,
            ADMISSAO de ADMISSÃO_ABRIL,
            SINDICAO de ATIVOS, 
            COMPETENCIA com valor fixo '2025-05-01',
            DIAS de BASE_DIAS_UTEIS,
            VALOR_DIARIO_VR de BASE_DIAS_UTEIS,
            TOTAL_VR calculado como DIAS * VALOR_DIARIO_VR,
            CUSTO_EMPRESA calculado como TOTAL_VR * 1.12,
            DESCONTO_PROFISSIONAL calculado como TOTAL_VR * 0.02,
            OBS_GERAL com valor fixo 'VR MENSAL MAIO/2025',

            Observe as relações:
             - ATIVOS com ADMISSÃO_ABRIL por 'MATRICULA'
             - ATIVOS com BASE_DIAS_UTEIS por 'SINDICATO'
 
     '''},
    {"agent": "executor", "prompt": ""},   # usa o último SQL gerado

]


############################################################
url = "http://127.0.0.1:8000/multi_agent_zip"
files = {"file": open("Dados.zip", "rb")}
data = {"steps": json.dumps(steps)}
result = requests.post(url, files=files, data=data)
print(f">>> Results: {result.json()}")
