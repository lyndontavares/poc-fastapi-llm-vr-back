import os
import pandas as pd
import zipfile
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
from dotenv import load_dotenv
import logging
import uuid
import shutil

# --- LangChain specific imports ---
from langchain_google_genai import ChatGoogleGenerativeAI

from langchain.agents.agent_types import AgentType

from langchain_community.utilities import SQLDatabase # Para o agente SQL
 
from langchain_experimental.agents.agent_toolkits import create_pandas_dataframe_agent

from sqlalchemy import create_engine # Para o SQLite

from langchain_community.agent_toolkits import create_sql_agent

from langchain.agents.agent_types import AgentType

# --- Configuração de Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Carregar variáveis de ambiente ---
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("A variável de ambiente 'GOOGLE_API_KEY' não está definida. "
                     "Por favor, defina sua chave de API do Google Gemini no arquivo .env.")

# --- Configuração da API Gemini ---
genai.configure(api_key=GOOGLE_API_KEY)
GEMINI_PRO_MODEL = "models/gemini-1.5-flash-latest" #"models/gemini-2.0-flash" #"models/gemini-pro" #"gemini-2.0-flash"


# --- Inicialização do FastAPI ---
app = FastAPI(
    title="API de Perguntas sobre CSVs com Gemini (Completa e com Agentes)",
    description="Permite upload de arquivos CSV/ZIP e perguntas a agentes LangChain.",
    version="1.6.0" # Updated version
)

# --- Configuração CORS ---
origins = [
    "*"
    #"http://localhost",
    #"http://localhost:8000",
    #"http://localhost:4200", # Porta padrão do Angular CLI
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Variáveis Globais para o Estado dos DataFrames ---
UPLOAD_DIR = "uploads"
EXTRACTED_DIR = os.path.join(UPLOAD_DIR, "extracted_csvs") # Para extração persistente (do /upload_zip)
TEMP_PROCESSING_DIR = os.path.join(UPLOAD_DIR, "temp_processing") # Para processamento temporário de ZIPs/CSVs

# DataFrame atualmente carregado para consulta individual
current_loaded_df: pd.DataFrame = None
current_loaded_csv_name: str = None

# Garante que os diretórios existam na inicialização
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(EXTRACTED_DIR, exist_ok=True)
os.makedirs(TEMP_PROCESSING_DIR, exist_ok=True)

logger.info("API iniciadando...")

@app.on_event("startup")
async def startup_event():
    logger.info("API iniciada. Diretórios de upload e processamento garantidos.")
    # Limpar diretórios temporários na inicialização para evitar lixo de sessões anteriores
    for folder in os.listdir(TEMP_PROCESSING_DIR):
        shutil.rmtree(os.path.join(TEMP_PROCESSING_DIR, folder))
    # Limpar também o diretório de extração persistente (se desejado, para um estado limpo a cada restart)
    for f in os.listdir(EXTRACTED_DIR):
        os.remove(os.path.join(EXTRACTED_DIR, f))
    logger.info("Diretórios temporários e de extração limpos na inicialização.")


# --- Endpoint de Status ---
@app.get("/status")
async def get_status():
    """Retorna o status da API e o CSV atualmente carregado."""
    return {
        "status": "ok",
        "message": "API está funcionando!",
        "current_csv_loaded": current_loaded_csv_name
    }

class PromptRequest(BaseModel):
    prompt: str

@app.post("/chat/gemini") # ,tags=["Interação com LLM"]
async def chat_with_gemini(request: PromptRequest):
    """
    Recebe um prompt de texto, interage com o modelo Google Gemini e retorna a resposta.
    """
    try:
        model = genai.GenerativeModel(GEMINI_PRO_MODEL)
        
        # Gera o conteúdo usando o modelo
        response = model.generate_content(request.prompt)
        
        # Verifica se a resposta contém texto
        if response.parts:
            # Concatena todas as partes da resposta
            full_response_text = "".join([part.text for part in response.parts if hasattr(part, 'text')])
            return {"response": full_response_text}
        else:
            # Lida com casos onde a resposta pode ser vazia ou não ter texto
            return {"response": "Não foi possível gerar uma resposta para o prompt."}

    except Exception as e:
        # Captura erros da API ou outros problemas
        raise HTTPException(
            status_code=500, 
            detail=f"Erro ao interagir com o modelo Gemini: {str(e)}"
        )


# --- Endpoint: Upload de Arquivo ZIP (para extração persistente, mantém os arquivos) ---
@app.post("/upload_zip")
async def upload_zip_file(file: UploadFile = File(...)):
    """
    Recebe um arquivo ZIP, salva-o e extrai seus conteúdos CSV para
    um diretório de arquivos extraídos (limpa os anteriores).
    """
    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Por favor, envie um arquivo no formato .zip")

    # Limpar diretório de extração persistente antes de extrair novos arquivos
    for f_name in os.listdir(EXTRACTED_DIR):
        os.remove(os.path.join(EXTRACTED_DIR, f_name))
    logger.info(f"Diretório '{EXTRACTED_DIR}' limpo antes da nova extração.")

    zip_file_path = os.path.join(UPLOAD_DIR, file.filename) # Salva o ZIP na pasta 'uploads'
    try:
        # Salva o arquivo ZIP
        with open(zip_file_path, "wb") as f:
            f.write(await file.read())
        logger.info(f"Arquivo ZIP '{file.filename}' salvo em '{UPLOAD_DIR}'.")

        # Extrai os CSVs para o diretório de extraídos
        extracted_csvs = []
        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            for member in zip_ref.namelist():
                if member.lower().endswith('.csv') and not member.startswith('__MACOSX/'): # Ignora arquivos de metadados do Mac
                    source = zip_ref.open(member)
                    # Usamos os.path.basename para evitar caminhos internos do zip (subdiretórios)
                    target_path = os.path.join(EXTRACTED_DIR, os.path.basename(member))
                    with open(target_path, "wb") as target:
                        target.write(source.read())
                    extracted_csvs.append(os.path.basename(member))
        logger.info(f"CSVs extraídos de '{file.filename}': {extracted_csvs}")

        return {
            "message": f"Arquivo '{file.filename}' carregado e extraído com sucesso! Os CSVs anteriores foram removidos e novos extraídos para '{EXTRACTED_DIR}'.",
            "extracted_csvs": extracted_csvs
        }
    except Exception as e:
        logger.error(f"Erro ao processar o upload do ZIP '{file.filename}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro no processamento do arquivo ZIP: {e}")
    finally:
        # Opcional: Remover o arquivo ZIP original após a extração se não for mais necessário
        if os.path.exists(zip_file_path):
             os.remove(zip_file_path)
             logger.info(f"Arquivo ZIP '{zip_file_path}' removido após extração.")


# --- Endpoint para Listar CSVs Extraídos ---
@app.get("/list_extracted_csvs")
async def list_extracted_csvs():
    """Lista todos os arquivos CSV disponíveis no diretório de extraídos."""
    try:
        csv_files = [f for f in os.listdir(EXTRACTED_DIR) if f.lower().endswith('.csv')]
        return {"csv_files": csv_files}
    except Exception as e:
        logger.error(f"Erro ao listar CSVs extraídos: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao listar arquivos CSV: {e}")

# --- Endpoint para Carregar um CSV Específico ---
@app.post("/load_csv")
async def load_csv_file(csv_filename: str = Form(...)):
    """
    Carrega um arquivo CSV específico do diretório de extraídos para
    ser o DataFrame ativo para consultas individuais.
    """
    global current_loaded_df, current_loaded_csv_name
    csv_file_path = os.path.join(EXTRACTED_DIR, csv_filename)

    if not os.path.exists(csv_file_path):
        raise HTTPException(status_code=404, detail=f"Arquivo CSV '{csv_filename}' não encontrado.")

    try:
        current_loaded_df = pd.read_csv(csv_file_path)
        current_loaded_csv_name = csv_filename
        logger.info(f"Arquivo '{csv_filename}' carregado com sucesso e definido como ativo.")
        return {"message": f"Arquivo '{csv_filename}' carregado com sucesso."}
    except Exception as e:
        logger.error(f"Erro ao carregar o arquivo CSV '{csv_filename}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao carregar o arquivo CSV: {e}")

# --- Modelo Pydantic para a Requisição de Pergunta ---
class QuestionRequest(BaseModel):
    question: str

# --- Endpoint para Perguntar ao Gemini sobre o CSV Carregado (Individual) ---
@app.post("/ask_csv")
async def ask_csv_question(request: QuestionRequest):
    """
    Recebe uma pergunta em linguagem natural e a processa com o Gemini
    usando o contexto do arquivo CSV atualmente carregado.
    """
    if current_loaded_df is None:
        raise HTTPException(status_code=400, detail="Nenhum arquivo CSV está carregado. Por favor, carregue um arquivo primeiro.")

    user_question = request.question
    logger.info(f"Pergunta recebida para '{current_loaded_csv_name}': '{user_question}'")

    df_info = current_loaded_df.dtypes.to_string()
    df_head = current_loaded_df.head(5).to_string(index=False)

    prompt = f"""
    Você é um assistente de análise de dados especializado em responder perguntas sobre o arquivo CSV atualmente carregado, cujo nome é '{current_loaded_csv_name}'.
    Eu fornecerei o esquema (nomes das colunas e tipos de dados) e algumas linhas de amostra do CSV,
    junto com uma pergunta. Por favor, responda a pergunta de forma concisa e direta,
    baseando-se apenas nas informações que você pode inferir dos dados fornecidas e seu conhecimento geral.
    Se a pergunta exigir um cálculo ou agregação, explique brevemente como você chegou à resposta.
    Você NÃO tem acesso para executar código Python ou Pandas.

    ---
    **Esquema do CSV ('{current_loaded_csv_name}'):**
    ```
    {df_info}
    ```

    **Primeiras 5 linhas do CSV (amostra dos dados de '{current_loaded_csv_name}'):**
    ```
    {df_head}
    ```
    ---

    **Pergunta do Usuário:** "{user_question}"

    **Sua Resposta:**
    """

    try:
        model = genai.GenerativeModel(GEMINI_PRO_MODEL)
        response = model.generate_content(prompt)
        gemini_answer = response.text
        logger.info(f"Resposta do Gemini para '{current_loaded_csv_name}': '{gemini_answer}'")
        return {"answer": gemini_answer}
    except Exception as e:
        logger.error(f"Erro ao comunicar com o Gemini: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro interno ao processar a pergunta: {e}")


# --- Endpoint para Perguntar sobre TODOS os CSVs descompactados (separados) ---
@app.post("/ask_all_extracted_csvs")
async def ask_all_extracted_csvs(request: QuestionRequest):
    """
    Recebe uma pergunta em linguagem natural e a processa com o Gemini
    usando o contexto de *todos* os arquivos CSV atualmente no diretório de extração,
    enviando-os separadamente no prompt.
    """
    all_extracted_csv_files = [f for f in os.listdir(EXTRACTED_DIR) if f.lower().endswith('.csv')]

    if not all_extracted_csv_files:
        raise HTTPException(status_code=400, detail="Nenhum arquivo CSV foi extraído. Por favor, faça upload de um ZIP primeiro.")

    user_question = request.question
    logger.info(f"Pergunta recebida para TODOS os CSVs extraídos (separados): '{user_question}'")

    combined_csv_context = ""
    for csv_file_name in all_extracted_csv_files:
        csv_file_path = os.path.join(EXTRACTED_DIR, csv_file_name)
        try:
            df = pd.read_csv(csv_file_path)
            combined_csv_context += f"\n--- Contexto do CSV: '{csv_file_name}' ---\n"
            combined_csv_context += f"**Esquema:**\n```\n{df.dtypes.to_string()}\n```\n"
            combined_csv_context += f"**Primeiras 5 linhas (amostra):**\n```\n{df.head(5).to_string(index=False)}\n```\n"
        except Exception as e:
            logger.warning(f"Não foi possível ler o CSV '{csv_file_name}': {e}")
            combined_csv_context += f"\n--- Erro ao ler CSV: '{csv_file_name}' ({e}) ---\n"

    if not combined_csv_context:
        raise HTTPException(status_code=500, detail="Nenhum CSV extraído pôde ser lido para fornecer contexto.")

    prompt = f"""
    Você é um assistente de análise de dados especializado em responder perguntas sobre *vários* arquivos CSV.
    Abaixo, fornecerei o esquema (nomes das colunas e tipos de dados) e algumas linhas de amostra para CADA UM dos CSVs extraídos.
    Por favor, analise a 'Pergunta do Usuário' e tente respondê-la utilizando as informações disponíveis em todos os CSVs fornecidos.

    **Instruções Importantes:**
    1.  Se a pergunta puder ser respondida por um único CSV, identifique qual CSV foi usado.
    2.  Se a pergunta exigir informações de MÚLTIPLOS CSVs, indique isso. **Você NÃO pode realizar junções (joins) ou operações complexas entre DataFrames.** Apenas raciocine sobre os dados apresentados em cada CSV individualmente.
    3.  Se a pergunta envolver cálculos ou agregações, explique brevemente como chegou à resposta.
    4.  Se a pergunta não puder ser respondida com os dados fornecidos em nenhum dos CSVs, diga isso claramente.

    ---
    **Contexto de Todos os CSVs Extraídos:**
    {combined_csv_context}
    ---

    **Pergunta do Usuário:** "{user_question}"

    **Sua Resposta:**
    """

    try:
        model = genai.GenerativeModel(GEMINI_PRO_MODEL)
        response = model.generate_content(prompt)
        gemini_answer = response.text
        logger.info(f"Resposta do Gemini para todos os CSVs: '{gemini_answer}'")
        return {"answer": gemini_answer}
    except Exception as e:
        logger.error(f"Erro ao comunicar com o Gemini para múltiplos CSVs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro interno ao processar a pergunta para múltiplos CSVs: {e}")


# --- Endpoint: Upload de ZIP, Concatena CSVs em MEMÓRIA e Pergunta ao Gemini ---
@app.post("/upload_zip_and_ask_concatenated")
async def upload_zip_and_ask_concatenated(file: UploadFile = File(...), question: str = Form(...)):
    """
    Recebe um arquivo ZIP, extrai todos os CSVs, concatena-os em um único DataFrame (em memória)
    e faz uma pergunta ao Gemini sobre os dados concatenados.
    """
    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Por favor, envie um arquivo no formato .zip")

    temp_extract_path = os.path.join(TEMP_PROCESSING_DIR, str(uuid.uuid4()))
    os.makedirs(temp_extract_path, exist_ok=True)
    zip_file_path = os.path.join(temp_extract_path, file.filename)

    try:
        with open(zip_file_path, "wb") as f:
            f.write(await file.read())
        logger.info(f"Arquivo ZIP temporário '{file.filename}' salvo em '{temp_extract_path}'.")

        extracted_csv_paths = []
        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            for member in zip_ref.namelist():
                if member.lower().endswith('.csv') and not member.startswith('__MACOSX/'):
                    source = zip_ref.open(member)
                    target_path = os.path.join(temp_extract_path, os.path.basename(member))
                    with open(target_path, "wb") as target:
                        target.write(source.read())
                    extracted_csv_paths.append(target_path)
        logger.info(f"CSVs extraídos para '{temp_extract_path}': {extracted_csv_paths}")

        if not extracted_csv_paths:
            raise HTTPException(status_code=400, detail="O arquivo ZIP não contém nenhum arquivo CSV.")

        list_of_dfs = []
        for csv_path in extracted_csv_paths:
            try:
                df = pd.read_csv(csv_path)
                list_of_dfs.append(df)
            except Exception as e:
                logger.warning(f"Não foi possível ler o CSV '{os.path.basename(csv_path)}' para concatenação (em memória): {e}")
                continue

        if not list_of_dfs:
            raise HTTPException(status_code=500, detail="Nenhum arquivo CSV pôde ser lido para concatenação a partir do ZIP.")

        combined_df = pd.concat(list_of_dfs, ignore_index=True, sort=False)
        logger.info(f"CSVs concatenados em memória. DataFrame resultante tem {combined_df.shape[0]} linhas e {combined_df.shape[1]} colunas.")

        df_info = combined_df.dtypes.to_string()
        df_head = combined_df.head(10).to_string(index=False)

        prompt = f"""
        Você é um assistente de análise de dados especializado em responder perguntas sobre um arquivo CSV que foi
        formado pela concatenação de múltiplos arquivos CSV. O arquivo original era um ZIP.

        **Atenção:** Os dados que você está vendo foram combinados de vários CSVs. Isso significa que algumas colunas podem
        ter valores ausentes (NaN) se elas não existiam em todos os arquivos CSV originais.

        ---
        **Esquema do CSV Concatenado (em memória):**
        ```
        {df_info}
        ```

        **Primeiras 10 linhas do CSV Concatenado (amostra dos dados):**
        ```
        {df_head}
        ```
        ---

        **Pergunta do Usuário:** "{question}"

        **Sua Resposta:**
        """

        model = genai.GenerativeModel(GEMINI_PRO_MODEL)
        response = model.generate_content(prompt)
        gemini_answer = response.text
        logger.info(f"Resposta do Gemini (concatenado em memória): '{gemini_answer}'")

        return {"answer": gemini_answer}

    except Exception as e:
        logger.error(f"Erro no endpoint /upload_zip_and_ask_concatenated: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao processar a requisição: {e}")
    finally:
        if os.path.exists(temp_extract_path):
            shutil.rmtree(temp_extract_path) # Remove o diretório temporário e seu conteúdo
            logger.info(f"Diretório temporário '{temp_extract_path}' e seus conteúdos removidos.")


# --- Endpoint: Upload de ZIP, CRIA ARQUIVO CSV Concatenado e Pergunta ao Gemini ---
@app.post("/upload_zip_create_concatenated_csv_and_ask")
async def upload_zip_create_concatenated_csv_and_ask(file: UploadFile = File(...), question: str = Form(...)):
    """
    Recebe um arquivo ZIP, extrai todos os CSVs, CONCATENA-OS EM UM NOVO ARQUIVO CSV,
    e faz uma pergunta ao Gemini sobre os dados desse novo arquivo CSV concatenado.
    """
    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Por favor, envie um arquivo no formato .zip")

    # Criar um diretório temporário único para esta operação
    temp_session_dir = os.path.join(TEMP_PROCESSING_DIR, str(uuid.uuid4()))
    os.makedirs(temp_session_dir, exist_ok=True)
    zip_file_path = os.path.join(temp_session_dir, file.filename)
    concatenated_csv_filename = "concatenated_data.csv"
    concatenated_csv_path = os.path.join(temp_session_dir, concatenated_csv_filename)

    try:
        # 1. Salva o arquivo ZIP temporariamente
        with open(zip_file_path, "wb") as f:
            f.write(await file.read())
        logger.info(f"Arquivo ZIP temporário '{file.filename}' salvo em '{temp_session_dir}'.")

        # 2. Extrai CSVs para o diretório temporário
        extracted_csv_paths = []
        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            for member in zip_ref.namelist():
                if member.lower().endswith('.csv') and not member.startswith('__MACOSX/'):
                    source = zip_ref.open(member)
                    target_path = os.path.join(temp_session_dir, os.path.basename(member))
                    with open(target_path, "wb") as target:
                        target.write(source.read())
                    extracted_csv_paths.append(target_path)
        logger.info(f"CSVs extraídos para '{temp_session_dir}': {extracted_csv_paths}")

        if not extracted_csv_paths:
            raise HTTPException(status_code=400, detail="O arquivo ZIP não contém nenhum arquivo CSV.")

        # 3. Carregar e concatenar todos os CSVs em um DataFrame
        list_of_dfs = []
        for csv_path in extracted_csv_paths:
            try:
                df = pd.read_csv(csv_path)
                list_of_dfs.append(df)
            except Exception as e:
                logger.warning(f"Não foi possível ler o CSV '{os.path.basename(csv_path)}' para concatenação: {e}")
                continue

        if not list_of_dfs:
            raise HTTPException(status_code=500, detail="Nenhum arquivo CSV pôde ser lido para concatenação a partir do ZIP.")

        combined_df = pd.concat(list_of_dfs, ignore_index=True, sort=False)
        logger.info(f"CSVs concatenados em memória. DataFrame resultante tem {combined_df.shape[0]} linhas e {combined_df.shape[1]} colunas.")

        # 4. Salvar o DataFrame concatenado em um novo arquivo CSV (já é feito por este endpoint)
        combined_df.to_csv(concatenated_csv_path, index=False)
        logger.info(f"DataFrame concatenado salvo em '{concatenated_csv_path}'.")

        # 5. Preparar o prompt para o Gemini usando o novo arquivo CSV
        df_info = combined_df.dtypes.to_string()
        df_head = combined_df.head(10).to_string(index=False)

        prompt = f"""
        Você é um assistente de análise de dados especializado em responder perguntas sobre um arquivo CSV
        que foi criado pela concatenação de múltiplos arquivos CSV ( '{concatenated_csv_filename}' ).
        O arquivo original era um ZIP.

        **Atenção:** Os dados que você está vendo foram combinados de vários CSVs. Isso significa que algumas colunas podem
        ter valores ausentes (NaN) se elas não existiam em todos os arquivos CSV originais.

        ---
        **Esquema do CSV Concatenado ('{concatenated_csv_filename}'):**
        ```
        {df_info}
        ```

        **Primeiras 10 linhas do CSV Concatenado (amostra dos dados de '{concatenated_csv_filename}'):**
        ```
        {df_head}
        ```
        ---

        **Pergunta do Usuário:** "{question}"

        **Sua Resposta:**
        """

        # 6. Chamar o Gemini
        model = genai.GenerativeModel(GEMINI_PRO_MODEL)
        response = model.generate_content(prompt)
        gemini_answer = response.text
        logger.info(f"Resposta do Gemini (do arquivo concatenado): '{gemini_answer}'")

        return {"answer": gemini_answer}

    except Exception as e:
        logger.error(f"Erro no endpoint /upload_zip_create_concatenated_csv_and_ask: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao processar a requisição: {e}")
    finally:
        # 7. Limpar arquivos temporários e o diretório da sessão
        if os.path.exists(temp_session_dir):
            shutil.rmtree(temp_session_dir) # Remove o diretório temporário e seu conteúdo
            logger.info(f"Diretório temporário '{temp_session_dir}' e seus conteúdos removidos.")


# --- ENDPOINT: Upload de ZIP e Consulta com LangChain create_pandas_dataframe_agent ---
@app.post("/upload_zip_and_query_with_pandas_agent")
async def upload_zip_and_query_with_pandas_agent(file: UploadFile = File(...), question: str = Form(...)):
    """
    Recebe um arquivo ZIP, extrai e concatena todos os CSVs em um DataFrame,
    e usa o agente LangChain (create_pandas_dataframe_agent) para responder
    perguntas complexas que exigem manipulação de dados Pandas.
    """
    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Por favor, envie um arquivo no formato .zip")

    # Criar um diretório temporário único para esta operação
    temp_session_dir = os.path.join(TEMP_PROCESSING_DIR, str(uuid.uuid4()))
    os.makedirs(temp_session_dir, exist_ok=True)
    zip_file_path = os.path.join(temp_session_dir, file.filename)

    try:
        # 1. Salvar o arquivo ZIP temporariamente
        with open(zip_file_path, "wb") as f:
            f.write(await file.read())
        logger.info(f"Arquivo ZIP '{file.filename}' salvo temporariamente em '{temp_session_dir}'.")

        # 2. Extrair CSVs para o diretório temporário
        extracted_csv_paths = []
        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            for member in zip_ref.namelist():
                if member.lower().endswith('.csv') and not member.startswith('__MACOSX/'):
                    source = zip_ref.open(member)
                    target_path = os.path.join(temp_session_dir, os.path.basename(member))
                    with open(target_path, "wb") as target:
                        target.write(source.read())
                    extracted_csv_paths.append(target_path)
        logger.info(f"CSVs extraídos para '{temp_session_dir}': {extracted_csv_paths}")

        if not extracted_csv_paths:
            raise HTTPException(status_code=400, detail="O arquivo ZIP não contém nenhum arquivo CSV.")

        # 3. Carregar e concatenar todos os CSVs em um único DataFrame
        list_of_dfs = []
        for csv_path in extracted_csv_paths:
            try:
                df = pd.read_csv(csv_path)
                list_of_dfs.append(df)
            except Exception as e:
                logger.warning(f"Não foi possível ler o CSV '{os.path.basename(csv_path)}' para concatenação: {e}")
                continue

        if not list_of_dfs:
            raise HTTPException(status_code=500, detail="Nenhum arquivo CSV pôde ser lido para concatenação a partir do ZIP.")

        combined_df = pd.concat(list_of_dfs, ignore_index=True, sort=False)
        logger.info(f"CSVs concatenados em um único DataFrame para o agente Pandas. Shape: {combined_df.shape}")

        # 4. Inicializar o LLM para o LangChain
        # temperature=0.0 para respostas mais determinísticas, útil para agentes que geram código
        llm = ChatGoogleGenerativeAI(model=GEMINI_PRO_MODEL, temperature=0.0, google_api_key=GOOGLE_API_KEY)

        # 5. Criar o agente Pandas do LangChain
        # verbose=True para ver os passos de raciocínio do agente (qual código ele gera e executa)
        pandas_agent = create_pandas_dataframe_agent(
            llm,
            combined_df,
            verbose=True,
            agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION, #TOOL_CALLING, #CHAT_CONVERSATIONAL_REACT_DESCRIPTION, # Ou AgentType.OPENAI_FUNCTIONS
            # Permite que o agente execute o código Python gerado.
            # CUIDADO: Em produção, isso exigiria um ambiente sandboxed.
            allow_dangerous_code=True,
            handle_parsing_errors=True # Para lidar com erros de parsing do LLM
        )

        logger.info(f"Agente Pandas criado. Perguntando: '{question}'")

        # 6. Executar a pergunta com o agente
        # A chamada `agent.run` é síncrona, portanto, não é necessário `await` aqui.
        agent_response = pandas_agent.run(question)
        logger.info(f"Resposta do Agente Pandas: '{agent_response}'")

        return {"answer": agent_response}

    except Exception as e:
        logger.error(f"Erro no endpoint /upload_zip_and_query_with_pandas_agent: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao processar a requisição com agente Pandas: {e}")
    finally:
        # 7. Limpar arquivos temporários e o diretório da sessão
        if os.path.exists(temp_session_dir):
            shutil.rmtree(temp_session_dir)
            logger.info(f"Diretório temporário '{temp_session_dir}' e seus conteúdos removidos.")


# --- NOVO ENDPOINT: Upload de Lote de CSVs e Consulta com Agente SQL (LangChain) ---
@app.post("/upload_csv_batch_and_query_with_sql_agent")
async def upload_csv_batch_and_query_with_sql_agent(
    files: list[UploadFile] = File(...),
    question: str = Form(...)
):
    """
    Recebe um lote de arquivos CSV, carrega-os em um banco de dados SQLite em memória
    e usa um agente LangChain SQL para responder perguntas complexas sobre os dados,
    incluindo possíveis junções entre os "tabelas" (CSVs).
    """
    if not files:
        raise HTTPException(status_code=400, detail="Nenhum arquivo CSV foi enviado.")

    temp_session_dir = os.path.join(TEMP_PROCESSING_DIR, str(uuid.uuid4()))
    os.makedirs(temp_session_dir, exist_ok=True)

    db_path = ":memory:" # Usar banco de dados SQLite em memória
    engine = None # Inicializa engine como None para o finally block

    try:
        # 1. Carregar CSVs e criar tabelas no SQLite
        dfs = {}
        for file in files:
            if not file.filename.lower().endswith(".csv"):
                raise HTTPException(status_code=400, detail=f"Arquivo '{file.filename}' não é um CSV. Por favor, envie apenas arquivos CSV.")

            csv_file_path = os.path.join(temp_session_dir, file.filename)
            try:
                with open(csv_file_path, "wb") as f:
                    f.write(await file.read())
                df = pd.read_csv(csv_file_path)
                # Criar um nome de tabela válido a partir do nome do arquivo (remover extensão e caracteres especiais)
                table_name = os.path.splitext(os.path.basename(file.filename))[0]
                table_name = ''.join(c for c in table_name if c.isalnum() or c == '_').lower()
                if not table_name: # Handle case where filename results in empty table name
                    table_name = f"csv_data_{uuid.uuid4().hex[:8]}" # Generate unique name
                dfs[table_name] = df
                logger.info(f"CSV '{file.filename}' carregado e pronto para ser uma tabela '{table_name}'.")
            except Exception as e:
                logger.warning(f"Não foi possível ler o CSV '{file.filename}': {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"Erro ao ler o CSV '{file.filename}': {e}")

        if not dfs:
            raise HTTPException(status_code=400, detail="Nenhum arquivo CSV válido foi processado.")

        # 2. Criar o engine SQLite e carregar DataFrames como tabelas
        engine = create_engine(f"sqlite:///{db_path}") # Conexão com o banco de dados em memória
        for table_name, df in dfs.items():
            df.to_sql(table_name, engine, if_exists='replace', index=False)
            logger.info(f"DataFrame '{table_name}' carregado no SQLite.")

        # 3. Inicializar o LLM e o Agente SQL do LangChain
        llm = ChatGoogleGenerativeAI(model=GEMINI_PRO_MODEL, temperature=0.0, google_api_key=GOOGLE_API_KEY)
        db = SQLDatabase(engine)

        sql_agent = create_sql_agent(
            llm,
            db=db,
            agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION, # Ou AgentType.OPENAI_FUNCTIONS
            verbose=True, # Para ver os passos de raciocínio e o SQL gerado
            handle_parsing_errors=True,
            system_prompt=f"""### PAPEL: Especialista em SQLite3.
            ### CONTEXTO: Você tem acesso a um banco de dados SQLite3 em memória
            ### INSTRUÇÕES: Responda às perguntas do usuário usando os dados disponíveis nas tabelas carregadas.
            ### PONTOS DE ATENÇÃO
            - utiilize aiaas para todas as colunas de todas as tabelas m todos comandos DML (Data Manipulation Language).
            - Usar aspas duplas garante que o banco de dados interprete corretamente o nome inteiro, incluindo os espaços, como um único identificador de coluna.
            - As tabelas estão relaconadas pela coluna: chave_acesso TEXT, que é a chave primária de cada tabela.
            - Você pode realizar junções (joins) entre tabelas usando a coluna chave_acesso.
            - Se a pergunta exigir cálculos ou agregações, explique brevemente como chegou à resposta.
            - Se a pergunta não puder ser respondida com os dados disponíveis, diga isso claramente.
            - Caso seja solicitado algo fora do seu contexto retorne vazio ('').
            - Utilize alias para nomear a coluna retornada conforme o contexto dela.
            - Para procurar conteúdo de texto utilizar sempre a função UPPER para garantir que não tenha problemas decorrentes de consistência de dados.
            """
        )

        logger.info(f"Agente SQL criado. Perguntando: '{question}'")

        # 4. Executar a pergunta com o agente
        agent_response = sql_agent.run(question)
        logger.info(f"Resposta do Agente SQL: '{agent_response}'")

        return {"answer": agent_response}

    except HTTPException as e:
        # Re-raise HTTPException directly
        raise e
    except Exception as e:
        logger.error(f"Erro no endpoint /upload_csv_batch_and_query_with_sql_agent: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao processar a requisição com agente SQL: {e}")
    finally:
        # 5. Limpar arquivos temporários e o diretório da sessão
        if os.path.exists(temp_session_dir):
            shutil.rmtree(temp_session_dir)
            logger.info(f"Diretório temporário '{temp_session_dir}' e seus conteúdos removidos.")
        # Fechar a conexão com o banco de dados se não for em memória e for persistente.
        # Para ":memory:", a conexão é fechada quando o processo termina ou o objeto engine é descartado.
        if engine:
            engine.dispose()
            logger.info("Conexão com o banco de dados SQLite em memória descartada.")


# --- NOVO ENDPOINT: Perguntar sobre TODOS os CSVs descompactados (separados), com PROMPT CUSTOMIZADO ---
class CustomPromptQuestionRequest(BaseModel):
    user_question: str # A pergunta real do usuário
    prompt_template: str # O template de prompt fornecido pelo usuário, com placeholders

@app.post("/ask_all_extracted_csvs_custom_prompt")
async def ask_all_extracted_csvs_custom_prompt(request: CustomPromptQuestionRequest):
    """
    Recebe uma pergunta e um template de prompt customizado para o Gemini.
    O template deve conter '{csv_context}' e '{user_question}' como placeholders,
    que serão preenchidos com os dados de todos os CSVs extraídos e a pergunta do usuário.
    """
    all_extracted_csv_files = [f for f in os.listdir(EXTRACTED_DIR) if f.lower().endswith('.csv')]

    if not all_extracted_csv_files:
        raise HTTPException(status_code=400, detail="Nenhum arquivo CSV foi extraído. Por favor, faça upload de um ZIP primeiro usando /upload_zip.")

    user_question = request.user_question
    prompt_template = request.prompt_template
    logger.info(f"Pergunta recebida (custom prompt) para TODOS os CSVs extraídos: '{user_question}'")
    logger.info(f"Template de prompt recebido: '{prompt_template}'")

    # 1. Gerar o contexto combinado dos CSVs
    csv_context_string = ""
    for csv_file_name in all_extracted_csv_files:
        csv_file_path = os.path.join(EXTRACTED_DIR, csv_file_name)
        try:
            df = pd.read_csv(csv_file_path)
            csv_context_string += f"\n--- Contexto do CSV: '{csv_file_name}' ---\n"
            csv_context_string += f"**Esquema:**\n```\n{df.dtypes.to_string()}\n```\n"
            csv_context_string += f"**Primeiras 5 linhas (amostra):**\n```\n{df.head(5).to_string(index=False)}\n```\n"
        except Exception as e:
            logger.warning(f"Não foi possível ler o CSV '{csv_file_name}': {e}")
            csv_context_string += f"\n--- Erro ao ler CSV: '{csv_file_name}' ({e}) ---\n"

    if not csv_context_string:
        raise HTTPException(status_code=500, detail="Nenhum CSV extraído pôde ser lido para fornecer contexto.")

    # 2. Validar e preencher o template do prompt
    if "{csv_context}" not in prompt_template:
        raise HTTPException(status_code=400, detail="O template de prompt deve conter o placeholder '{csv_context}'.")
    if "{user_question}" not in prompt_template:
        raise HTTPException(status_code=400, detail="O template de prompt deve conter o placeholder '{user_question}'.")

    try:
        final_prompt = prompt_template.format(csv_context=csv_context_string, user_question=user_question)
        logger.info(f"Prompt final enviado ao Gemini: \n{final_prompt[:500]}...") # Log os primeiros 500 chars
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Erro ao preencher o template do prompt. Placeholder ausente ou incorreto: {e}")

    # 3. Chamar o Gemini
    try:
        model = genai.GenerativeModel(GEMINI_PRO_MODEL)
        response = model.generate_content(final_prompt)
        gemini_answer = response.text
        logger.info(f"Resposta do Gemini (custom prompt): '{gemini_answer}'")
        return {"answer": gemini_answer}
    except Exception as e:
        logger.error(f"Erro ao comunicar com o Gemini (custom prompt): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro interno ao processar a pergunta com prompt customizado: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)