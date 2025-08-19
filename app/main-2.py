import os
import zipfile
import tempfile
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
import pandas as pd
from sqlalchemy import create_engine
from pandasai import PandasAI
from pandasai.llm import LangChainLLM
from langchain_google_genai import ChatGoogleGenerativeAI

# Carregar variáveis de ambiente
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_PRO_MODEL = os.getenv(
    "GEMINI_PRO_MODEL", "models/gemini-1.5-flash-latest")

app = FastAPI(
    title="API Automação de compra de VR/VA",
    description="I2A2-Desafio 4",
    version="1.0.0"  # Updated version
)

DB_PATH = "vales.db"

# Função auxiliar: normaliza planilha


def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [col.strip().upper() for col in df.columns]
    if "CADASTRO" in df.columns:
        df.rename(columns={"CADASTRO": "MATRICULA"}, inplace=True)
    return df


@app.post("/batch_of_xsl_to_sqlite_with_chainlang_agent")
async def batch_of_xsl_to_sqlite_with_chainlang_agent(zip_file: UploadFile = File(...)):
    # Pasta temporária
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "input.zip")
        with open(zip_path, "wb") as f:
            f.write(await zip_file.read())

        # Extrair ZIP
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(tmpdir)

        # Criar engine SQLite
        engine = create_engine(f"sqlite:///{DB_PATH}", echo=True)

        # Ler todas planilhas e criar tabelas
        for fname in os.listdir(tmpdir):
            if fname.endswith((".xls", ".xlsx")):
                df = pd.read_excel(os.path.join(tmpdir, fname))
                df = normalize_df(df)
                table_name = os.path.splitext(fname)[0].replace(
                    "-", "_").replace(" ", "_")

                # Salvar no SQLite
                if "MATRICULA" in df.columns:
                    df.to_sql(table_name, con=engine,
                              if_exists="replace", index=False)
                else:
                    df.to_sql(table_name, con=engine,
                              if_exists="replace", index=False)

        # Agregar todas as tabelas em um único DataFrame
        with engine.connect() as conn:
            table_names = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table';").fetchall()
            df_list = []
            for t in table_names:
                df_list.append(pd.read_sql(f"SELECT * FROM {t[0]}", conn))
            if df_list:
                merged_df = pd.concat(df_list, ignore_index=True)
            else:
                merged_df = pd.DataFrame()

        # Criar agente PandasAI usando Gemini
        llm = ChatGoogleGenerativeAI(
            model=GEMINI_PRO_MODEL,
            temperature=0,
            google_api_key=GOOGLE_API_KEY
        )
        langchain_llm = LangChainLLM(llm=llm)
        pandas_ai = PandasAI(langchain_llm, verbose=True)

        # Pergunta exemplo NL
        query_nl = """
        Gere a folha consolidada de VR/VA com as colunas: 
        MATRICULA, ADMISSÃO, SINDICATO, COMPETÊNCIA, DIAS, VALOR DIÁRIO VR, TOTAL, 
        CUSTO EMPRESA, DESCONTO PROFISSIONAL e OBS GERAL
        """
        result = pandas_ai.run(merged_df, prompt=query_nl)

        # Salvar resultado em XLSX
        result_path = os.path.join(tmpdir, "resultado.xlsx")
        if isinstance(result, pd.DataFrame):
            result.to_excel(result_path, index=False)
        else:
            # fallback se agente retornar texto
            pd.DataFrame([result]).to_excel(result_path, index=False)

        return FileResponse(
            result_path,
            filename="resultado.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
