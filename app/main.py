import io
import zipfile
import tempfile
import pandas as pd
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import StreamingResponse
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.sql_database import SQLDatabase
import logging
import os
from dotenv import load_dotenv
import google.generativeai as genai
import json
import re

# --- Logging ---
logger = logging.getLogger("uvicorn")
logger.setLevel(logging.INFO)
logger.info(f"--- Iniciando FastAPI com Google Generative AI --")

# --- API Key ---
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError(
        "A variável de ambiente 'GOOGLE_API_KEY' não está definida.")
genai.configure(api_key=GOOGLE_API_KEY)

# --- FastAPI ---
app = FastAPI()

# --- SQLite ---
DATABASE_URL = "sqlite:///./uploaded_data4.db"
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ==========================================================
# AGENTES
# ==========================================================


def agent_extract_zip(zip_file: UploadFile):
    """Agente extractor - carrega planilhas XLSX para SQLite"""
    with tempfile.TemporaryDirectory() as tmpdirname:
        with zipfile.ZipFile(zip_file.file, "r") as zip_ref:
            zip_ref.extractall(tmpdirname)
        for file in zip_ref.namelist():
            if file.endswith(".xlsx"):
                df = pd.read_excel(f"{tmpdirname}/{file}")
                df.columns = [str(col).replace(
                    " ", "_").replace(".", "_").replace(":", "").upper() for col in df.columns]
                table_name = file.replace(".xlsx", "").replace(
                    " ", "_").replace(".", "_").upper()
                df.to_sql(table_name, con=engine,
                          if_exists="replace", index=False)
                logger.info(
                    f"Planilha '{file}' importada como tabela '{table_name}'.")


def agent_generate_sql(prompt: str, schema: str):
    """Agente sql_generator - gera SQL puro com Gemini"""
    llm = ChatGoogleGenerativeAI(
        model="models/gemini-1.5-flash-latest",
        temperature=0
    )
    full_prompt = f"""
    Você é um especialista em SQL (SQLite).
    Responda SOMENTE com SQL válido.
    Esquema de tabelas:
    {schema}

    Instrução:
    {prompt}
    """
    result = llm.invoke(full_prompt)
    sql = result.content.strip()
    # remove prefixos se aparecerem
    for prefix in ["Answer:", "SQLQuery:", "Resposta:"]:
        if sql.startswith(prefix):
            sql = sql[len(prefix):].strip()
    return sql


def agent_execute_sql(sql: str):
    """Agente executor - executa SQL"""
    sql = sql.replace("```sql", "").replace("```", "")
    logger.info(f"Executando SQL: {sql}")
    commands = [c.strip() for c in sql.split(";") if c.strip()]
    results = []
    with engine.begin() as conn:
        for cmd in commands:
            try:
                res = conn.execute(text(cmd))
                try:
                    rows = res.fetchall()
                    if rows:
                        df = pd.DataFrame(rows, columns=res.keys())
                        results.append(df)
                except Exception:
                    results.append(pd.DataFrame([{"Executado": cmd}]))
            except Exception as e:
                logger.error(f"Erro ao executar comando: {e}")
                results.append(pd.DataFrame(
                    [{"Erro": str(e), "Comando": cmd}]))
    return results


def agent_formatter(df: pd.DataFrame, fmt: str = "csv"):
    """Agente formatter - converte DataFrame para saída desejada"""
    logger.info(f"Formatando em {fmt}")
    if fmt == "json":
        result = df.to_json(orient="records", force_ascii=False)
        logger.info(f"retorno json: {result}")
        return result

    elif fmt == "table":
        result = df.to_string(index=False)
        logger.info(f"retorno table: {result}")
        return result

    elif fmt == "xlsx":
        # gera excel em memória
        buffer = io.BytesIO()
        df.to_excel(buffer, index=False, engine="openpyxl")
        buffer.seek(0)
        logger.info(f"retorno xlsx: {len(buffer.getvalue())} bytes")
        return buffer.getvalue()

    else:  # default csv
        result = df.to_csv(index=False)
        logger.info(f"retorno csv: {result}")
        return result
# ==========================================================
# ENDPOINT MULTI-AGENTE
# ==========================================================


@app.post("/multi_agent_zip")
async def multi_agent_zip(
    file: UploadFile = File(...),
    steps: str = Form(...)  # JSON: lista de {agent, prompt}
):
    # 1. Extrair planilhas
    agent_extract_zip(file)

    # Montar schema para o agente de SQL
    schema = ""
    with engine.begin() as conn:
        tables = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
        for (tname,) in tables:
            cols = conn.execute(text(f"PRAGMA table_info({tname})")).fetchall()
            colnames = [c[1] for c in cols]
            schema += f"Tabela: {tname} | Colunas: {colnames}\n"

    steps_list = json.loads(steps)
    results = []
    last_result = None

    for idx, step in enumerate(steps_list, start=1):
        agent = step.get("agent")
        prompt = step.get("prompt")

        logger.info(f"[{idx}] Executando agente={agent}, prompt={prompt}")

        if agent == "sql_generator":
            sql = agent_generate_sql(prompt, schema)
            last_result = sql
            results.append({"agent": agent, "prompt": prompt, "output": sql})

        elif agent == "executor":
            sql = prompt if prompt.strip().upper().startswith(
                ("SELECT", "INSERT", "UPDATE", "DELETE", "ALTER", "CREATE")) else last_result
            res_dfs = agent_execute_sql(sql)
            if res_dfs:
                last_result = res_dfs[-1]
                results.append({"agent": agent, "prompt": sql, "output": last_result.head(
                    5).to_dict(orient="records")})
            else:
                last_result = pd.DataFrame([{"Executado": "OK"}])
                results.append({"agent": agent, "prompt": sql, "output": "OK"})

        elif agent == "formatter":
            logger.info(f"formatter: last_result {last_result}")
            if isinstance(last_result, pd.DataFrame):
                formatted = agent_formatter(last_result, prompt)
                results.append(
                    {"agent": agent, "prompt": prompt, "output": formatted})
                last_result = formatted
            else:
                results.append({"agent": agent, "prompt": prompt,
                               "error": "Nada para formatar"})

        else:
            results.append({"agent": agent, "prompt": prompt,
                           "error": "Agente desconhecido"})

    # resposta final
    return {"results": results}
