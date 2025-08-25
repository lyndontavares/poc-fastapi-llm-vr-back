import base64
import requests
import json

steps = [

    #############################
    # Ajustar Estrutura de Dados
    #############################
    {"agent": "sql_generator", "prompt":
     '''
        ### Passo 1: Importante ajustar a estrutura de dados primeiro
        ### A cada chamada ao agente SQL_GENERATOR o schema é atualizado
        ### Into garante que o agente estará sempre atualizado sobre o contexto

        Renomear a coluna UNNAMED_2 para SITUACAO na tabela EXTERIOR.
        Renomear a coluna CADASTRO para MATRICULA na tabela EXTERIOR.
        Remover na tabela BASE_DIAS_UTEIS primeiro registro. 

        Renomear a primeira coluna da tabela BASE_DIAS_UTEIS para 'SINDICATO'.  
        Renomear a segunda coluna da tabela BASE_DIAS_UTEIS para 'DIAS_UTEIS'.
        Renomear a coluna UNNAMED_3 para SITUACAO na tabela ADMISSAO_ABRIL.
        Renomear a coluna UNNAMED_3 para SITUACAO na tabela 'AFASTAMENTOS'.

        ### Passo 2: Neste etapa, procuramos manter a integridade dos dados
        adicione VALOR inteiro na tabela BASE_DIAS_UTEIS.
        atualize VALOR= 37.5 em BASE_DIAS_UTEIS quando SINDICATO contém ' SP '.
        atualize VALOR= 35 em BASE_DIAS_UTEIS quando SINDICATO contém ' SP ' ou ' RS ' ou ' PR '.
        
        ### Passo 4: Criar tabela temporária para retorno da planilha de VR/VA mensal
        Crie uma tabela chamada VR_MENSAL. Somente se ela não existir. Com os seguintes campos:
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

        ### PASSO 5: Limpar a tabela. Garantir que tabela estará vazia.
        Remova todos os registros da tabela VR_MENSAL.
 
     '''},
    {"agent": "executor", "prompt": ""},

    #############################
    # Regras de Exclusão
    #############################
    {"agent": "sql_generator", "prompt":
     ''' 

        ### Passo 5: Criaremos uma tabela para manter a lista de colaboradores elegíveis.
        ### Inicialmente igual a lista de colaboradores. 
        ### Nos passos seguintes, iremos refinar e deixar somentes aqueles que receberam VR/VA.

        - Remova a tabela ELEGIVEIS, se ele existir.
        - Crie a tabela ELEGIVEIS a partir de ATIVOS. (Garantir que a tabela vai estar criada e limpa)

        ### Passo 6: Etapa de exclusões. 
        ### Já preparando para extração da query principal

        - Deletar todos os registro de ELEGIVEIS com comunicado de desligamento igual a 'OK' e 
          data de desligamento menor ou igual 15/05/2025 na consuta por matricula em DESLIGADOS.
        - Iterar sobre as bases de ESTAGIO, APRENDIZ, AFASTAMENTOS, EXTERIOR e remover todos 
          os registros correspondentes em ELEGIVEIS.
        - Remover de ELEGIVEIS todos os colaboradores com situacao diferente de Trabalhando.
        - Remover de ELEGIVEIS todos os colaboradores sem SINDICATO
               
     '''},
    {"agent": "executor", "prompt": ""},

    #############################
    # Preparação dos Dados Finais
    #############################
    {"agent": "sql_generator", "prompt":
     '''

        ### Passo 7: Montar SQL principal com regras de cálculo do VR/VA
        ### Revisar as fórmulas de cálculo:

        Iterar sobre o relacinamento a seguir:
            - ELEGIVEIS relaciona com tabela ADMISSAO_ABRIL pela coluna MATRICULA.
            - ELEGIVEIS relaciona com tabela BASE_DIAS_UTEIS pela coluna SINDICATO.

            Inserir na tabela VR_MENSAL os seguintes campos:
                MATRICULA vindo de ELEGIVEIS,
                ADMISSAO vindo da coluna ADMISSAO da ADMISSAO_ABRIL,
                SINDICATO vindo de SINDICATO da ELEGIVEIS, 
                COMPETENCIA com valor fixo '01/05/2025',
                DIAS com DIAS da BASE_DIAS_UTEIS - subtraido o total de dias de férias,
                VALOR_DIARIO_VR com VALOR de BASE_DIAS_UTEIS (2 decimais),
                TOTAL_VR calculado como DIAS * VALOR_DIARIO_VR (2 decimais), 
                CUSTO_EMPRESA calculado como TOTAL_VR * 0.8 (2 decimais),
                DESCONTO_PROFISSIONAL calculado como TOTAL_VR * 0.2 (2 decimais),
                OBS_GERAL com valor fixo 'VR MENSAL MAIO/2025';
         
        ### Passo 8: Após gerar o SQL, o agente faz a excução e atuliza base.

     '''},
    {"agent": "executor", "prompt": ""},


    #############################
    # SQL Formação da Planilha
    #############################
    {"agent": "sql_generator", "prompt":
     '''

        ### Passo 10: Listar Retorno
        ### Com a consulta montada acima, conseguimos formatar o retorno para CSV.

        Retorne todo o conteúdo da tabela VR_MENSAL. 
        
        ## Adicione alias para colunas coluna que contiver (_) trocando (_) por espaço.
        ## Apenas escreva a SQL, nada mais.      

     '''},
    {"agent": "executor", "prompt": ""},


    ############################################
    # Formatação Final
    #  {"agent": "formatter", "prompt": "csv"}
    #  {"agent": "formatter", "prompt": "xlsx"}
    #  {"agent": "formatter", "prompt": "table"}
    #  {"agent": "formatter", "prompt": "json"}
    ############################################
    {"agent": "formatter", "prompt": "xlsx"}
]

############################################################
# Preparar e enviar os dados para o servidor
############################################################

url = "http://127.0.0.1:8000/multi_agent_zip"
files = {"file": open("dados.zip", "rb")}
data = {"steps": json.dumps(steps)}
result = requests.post(url, files=files, data=data)


############################################################
# Salvar o resultado completo em um arquivo JSON
############################################################

with open("resultado.json", "w", encoding="utf-8") as f:
    json.dump(result.json(), f, ensure_ascii=False, indent=2)

############################################################
# Salvar o resultado final em um arquivo CSV/XLSX
# RESPOSTA DO DESAFIO
############################################################

last_output = result.json()["results"][-1]

# Garante que seja dict com "type" e "content"
output_type = last_output["prompt"]
content = last_output.get("output", "")

# Definir nome base do arquivo
basename = "VR_MENSAL_05_2025"

if output_type == "csv":  # tabelas textuais
    filename = f"{basename}.csv"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)

elif output_type == "markdown" or output_type == "md":
    filename = f"{basename}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)

elif output_type == "json":
    filename = f"{basename}.json"
    # Se já for string → parse e reformatar
    try:
        parsed = json.loads(content)
    except Exception:
        parsed = content
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)

elif output_type == "xlsx":
    filename = f"{basename}.xlsx"
    # Conteúdo esperado em base64
    xlsx_bytes = base64.b64decode(content)
    with open(filename, "wb") as f:
        f.write(xlsx_bytes)

else:  # fallback → texto simples
    filename = f"{basename}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(str(content))

print(f"Arquivo salvo: {filename}")
