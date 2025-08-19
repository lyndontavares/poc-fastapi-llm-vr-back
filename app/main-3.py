import os
import zipfile
import tempfile
import shutil
import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import create_engine, String
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents.agent_types import AgentType
from langchain_experimental.agents import create_pandas_dataframe_agent
import io

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Verifica se a API Key está configurada
if not GOOGLE_API_KEY:
    raise ValueError(
        "GOOGLE_API_KEY not found. Please set it in your .env file.")

# Configuração da aplicação FastAPI
app = FastAPI()

# Configuração do LLM Gemini
llm = ChatGoogleGenerativeAI(
    model="models/gemini-1.5-flash-latest",
    google_api_key=GOOGLE_API_KEY,
    convert_system_message_to_human=True
)


@app.post('/batch_of_xsl_to_sqlite_with_chainlang_agent')
async def process_batch(zip_file: UploadFile = File(...)):
    """
    Endpoint que aceita um arquivo ZIP, descompacta planilhas,
    cria um banco de dados SQLite, consulta com um agente Gemini
    e retorna uma planilha XLSX.
    """
    # 1. Validar o upload do arquivo
    if not zip_file.filename.endswith('.zip'):
        raise HTTPException(
            status_code=400, detail="O arquivo deve ser no formato .zip")

    # Criar diretórios temporários para descompactação e o banco de dados
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "vale_beneficios.sqlite")

    try:
        # 2. Descompactar o arquivo ZIP
        zip_path = os.path.join(temp_dir, zip_file.filename)
        # Salva o arquivo no diretório temporário
        with open(zip_path, "wb") as f:
            f.write(await zip_file.read())

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        # 3. Conectar ao banco de dados SQLite
        engine = create_engine(f'sqlite:///{db_path}')

        # Obter a lista de arquivos de planilha
        excel_files = [f for f in os.listdir(
            temp_dir) if f.endswith(('.xls', '.xlsx'))]
        if not excel_files:
            raise HTTPException(
                status_code=400, detail="Nenhum arquivo .xls ou .xlsx encontrado no arquivo ZIP.")

        print("--- Criando tabelas a partir das planilhas ---")

        # DataFrame que será usado pelo agente Pandas para demonstração
        df_for_agent = None

        # 4. Processar cada planilha e criar as tabelas
        for excel_file in excel_files:
            file_path = os.path.join(temp_dir, excel_file)
            df = pd.read_excel(file_path)

            # Remover colunas sem nome e renomear 'Cadastro'
            df = df.dropna(axis=1, how='all')
            df.columns = df.columns.astype(str).str.strip()
            df = df.rename(columns={'Cadastro': 'MATRICULA'})

            # Use a primeira planilha encontrada para o agente Pandas
            if df_for_agent is None:
                df_for_agent = df.copy()

            # Acessar nome da tabela e tratar caracteres especiais
            table_name = os.path.splitext(excel_file)[0]
            table_name = table_name.replace(" ", "_").replace("-", "_").lower()

            # Lógica para criar a tabela com chave primária se existir 'MATRICULA'
            if 'MATRICULA' in df.columns:
                print(
                    f"Criando tabela '{table_name}' com MATRICULA como chave primária.")
                df.to_sql(table_name, con=engine, index=False,
                          if_exists='replace', dtype={'MATRICULA': String(255)})
            else:
                print(f"Criando tabela '{table_name}' sem chave primária.")
                df.to_sql(table_name, con=engine,
                          index=False, if_exists='replace')

            print(
                f"Dados do arquivo '{excel_file}' inseridos na tabela '{table_name}'.")

        if df_for_agent is None:
            raise HTTPException(
                status_code=500, detail="Não foi possível criar o DataFrame para o agente.")

        # 5. Criar o agente LangChain (Pandas Agent)
        print("\n--- Agente Gemini (Pandas) criado. Executando consulta... ---")
        agent_executor = create_pandas_dataframe_agent(
            llm=llm,
            df=df_for_agent,
            agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            verbose=True,  # Mostra o raciocínio do agente
            return_intermediate_steps=True,
            allow_dangerous_code=True  # Opt-in para executar código Python
        )

        # 6. Exemplo de consulta em linguagem natural
        # Este prompt é mais robusto e não falha se as colunas não existirem
        prompt_query = (

            "Base única consolidada: Reunir e consolidar informações de 5 bases separadas em uma única base final para (Ativos, Férias, desligados, Base cadastral (admitidos do mês), Base sindicato x valor e Dias úteis por colaborador."
            "- Tratamento de exclusões: Remover da base final, todos os profissionais com cargo de diretores, estagiários e aprendizes, afastados em geral (ex.: licença maternidade),"
            " profissionais que atuam no exterior. Para isto, se guiar pela matrícula nas planilhas."
            "- Validar e corrigir: datas inconsistentes ou quebradas , campos faltantes, férias mal preenchidas, feriados estaduais e municipais corretamente aplicados"
            "- Cálculo automatizado do benefício: Com base na planilha calcular automaticamente:"
            "- Quantidade de dias úteis por colaborador (considerando os dias úteis de cada sindicato, férias, afastamentos e data de desligamento)"
            "- Regra de desligamento: Para desligamento se estiver como OK o comunicado de desligamento até dia 15, não considerar para pagamento. Se for informado depois do dia 15, a compra deve ser proporcional. "
            "- Verificar se pela matricula se é elegível ao benefício (vide base de tratamento de exclusões)"
            "- Valor total de Vale Refeição (VR) a ser concedido para cada"
            "- colaborador, de acordo com o valor de cada sindicato que o"
            "- profissional está vinculado, gerando o cálculo, correto e vigente."

            "Adicone uma coluna COMPETENCIA no DataFrame com o valor 'Junho de 2024' para todas as linhas."
            "Adicione uma coluna 'ADMISSÃO' com a data de admissão do colaborador."
            "Adicione uma coluna 'SINDICATO' com o nome do sindicato do colaborador."
            "Adicione uma coluna 'CUSTO EMPRESA' com o valor total do benefício para a empresa."
            "Adicione uma coluna 'DESCONTO PROFISSIONAL'"
            "Adicione uma coluna 'OBS GERAL' com observações gerais sobre o colaborador."
            "Adicione uma coluna 'DIAS' com a quantidade de dias úteis do mês de Junho de 2024."
            "Adicione uma coluna 'VALOR DIÁRIO VR' com o valor diário do VR."
            "Adicione uma coluna 'TOTAL' com o valor total do benefício."
            "Adicione uma coluna 'MATRICULA' com a matrícula do colaborador."
            # "(considering the rules for calculating days, VR values based on the syndicate, and proportional payments for late desligamento comunicados), and handle the data cleaning and filtering steps appropriately"

            "Na planilha de retorno:"
            " adicione as colunas: 'MATRICULA', 'ADMISSÃO', 'SIDICATO', 'COMPETÊNCIA', 'DIAS', 'VALOR DIÁRIO VR', 'TOTAL', 'CUSTO EMPRESA', 'DESCONTO PROFISSIONA' e 'OBS GERAL'. "
            "Responda apenas com o DataFrame final, sem explicações adicionais."
            "Retorne o resultado como uma planiha .XLSX. Não retorne strings ou blocos de código."
        )

        agent_result = agent_executor.invoke(prompt_query)

        # 7. Extrair o DataFrame de resultado do agente
        raw_output = agent_result.get('output', None)

        result_df = None

        # LÓGICA ATUALIZADA: Tenta extrair e executar o código
        if isinstance(raw_output, str):
            # Tenta encontrar um bloco de código Python com ou sem a formatação ```
            code_block = raw_output.replace(
                "```python", "").replace("```", "").strip()

            if code_block:
                print("Saída do agente contém código. Tentando executar...")
                local_scope = {'pd': pd, 'np': __import__(
                    'numpy'), 'df': df_for_agent}

                try:
                    # Executa o código e tenta capturar o DataFrame resultante
                    exec(code_block, {}, local_scope)
                    for name, var in local_scope.items():
                        if isinstance(var, pd.DataFrame):
                            result_df = var
                            break
                except Exception as e:
                    print(
                        f"Aviso: Erro ao executar o código do agente. Usando DataFrame original. Erro: {e}")
            else:
                print(
                    f"Aviso: Saída do agente não é um bloco de código. Usando DataFrame original. Resposta: '{raw_output}'")

        # Fallback: Se o agente não retornou um DataFrame válido, usa o DataFrame original
        if not isinstance(result_df, pd.DataFrame) or result_df.empty:
            print(
                "Nenhum DataFrame válido foi gerado. Usando o DataFrame da primeira planilha como fallback.")
            result_df = df_for_agent

        # 8. Renomear as colunas e gerar o XLSX
        # Utiliza as colunas do DataFrame resultante para evitar erros
        output_df = result_df

        # Usar um buffer de memória para o arquivo XLSX
        excel_buffer = io.BytesIO()
        output_df.to_excel(excel_buffer, index=False, engine='openpyxl')
        excel_buffer.seek(0)

        print("\n--- Análise concluída. Gerando planilha de retorno. ---")
        return StreamingResponse(
            excel_buffer,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={
                "Content-Disposition": "attachment; filename=relatorio_final.xlsx"}
        )

    except Exception as e:
        print(f"Ocorreu um erro: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Limpar diretórios temporários
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

""" if __name__ == '__main__':
    # Execute o servidor FastAPI usando Uvicorn
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) """
