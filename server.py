"""
Servidor Backend em Python para a Landing Page do Instituto / ONG.
Funcionalidades:
- Servir arquivos estáticos (HTML, CSS, JS, PDFs)
- API REST para carregar configurações do site (/api/config)
- API REST para atualizar dados da página pelo painel administrativo (/api/config)
- API para receber mensagens de contato (/api/contato) com banco SQLite
- API para receber inscrições de voluntários (/api/voluntario) com banco SQLite
- API de visualização e métricas para a gestão da ONG (/api/mensagens, /api/voluntarios, /api/stats)
"""

import os
import sys
import re
import json
import base64
import sqlite3
import mimetypes
import hashlib
import secrets
import uuid
import ssl
import urllib.request
from datetime import datetime, timedelta
import socket
from http.cookies import SimpleCookie
import threading
from contextlib import contextmanager
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, urlencode

# Caminhos base
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
DB_FILE = os.path.join(DATA_DIR, "ong.db")

# Garante diretórios
DOCS_DIR = os.path.join(PUBLIC_DIR, "docs")
IMG_DIR = os.path.join(PUBLIC_DIR, "assets", "img")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(PUBLIC_DIR, exist_ok=True)
os.makedirs(DOCS_DIR, exist_ok=True)
os.makedirs(IMG_DIR, exist_ok=True)

def load_env():
    """Carrega variáveis de ambiente a partir do arquivo local .env (sem dependências externas)."""
    env_file = os.path.join(BASE_DIR, ".env")
    if os.path.exists(env_file):
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, val = line.split("=", 1)
                        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))
        except Exception as e:
            print(f"[AVISO] Não foi possível ler o arquivo .env: {e}")

load_env()

# Persistência Permanente na Nuvem (sobrevive a reinicializações e discos efêmeros do Render)
KVDB_BUCKET_URL = os.environ.get("KVDB_BUCKET_URL", "https://kvdb.io/CRiiwUrgTkUsVqFprcTA67/site_config")
KVDB_DB_BACKUP_URL = os.environ.get("KVDB_DB_BACKUP_URL", "https://kvdb.io/CRiiwUrgTkUsVqFprcTA67/site_db_backup")
KVDB_HISTORICO_URL = os.environ.get("KVDB_HISTORICO_URL", "https://kvdb.io/CRiiwUrgTkUsVqFprcTA67/site_db_historico")
KVDB_CONFIG_HISTORICO_URL = os.environ.get("KVDB_CONFIG_HISTORICO_URL", "https://kvdb.io/CRiiwUrgTkUsVqFprcTA67/site_config_historico")

def sincronizar_config_nuvem():
    """
    Sincroniza o arquivo local config.json com o banco de dados em nuvem permanente (KVDB).
    Garante que:
    1. Se houver alterações na nuvem mais recentes (ex: feitas no painel admin no Render), elas são restauradas localmente.
    2. Se o arquivo local tiver alterações mais recentes (ex: deploy novo de código, git pull ou edição local), ele atualiza a nuvem automaticamente.
    3. Gravação atômica em disco com flush e fsync para evitar qualquer risco de arquivo corrompido em reinicializações forçadas.
    """
    local_cfg = None
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                local_cfg = json.load(f)
        except Exception as e:
            print(f"[AVISO] Falha ao ler config.json local: {e}")

    cloud_cfg = None
    try:
        req = urllib.request.Request(
            KVDB_BUCKET_URL,
            headers={"User-Agent": "Spa-Glow-Party/1.0"}
        )
        ctx = ssl.create_default_context()
        try:
            res = urllib.request.urlopen(req, timeout=10, context=ctx)
        except Exception:
            ctx = ssl._create_unverified_context()
            res = urllib.request.urlopen(req, timeout=10, context=ctx)

        with res:
            if res.status == 200:
                raw_data = res.read().decode('utf-8').strip()
                if raw_data:
                    cloud_cfg = json.loads(raw_data)
    except Exception as e:
        print(f"[AVISO] Não foi possível contatar nuvem KVDB (mantendo arquivo local): {e}")

    # Decisão inteligente de sincronização bidirecional
    if cloud_cfg and isinstance(cloud_cfg, dict) and "instituicao" in cloud_cfg:
        cloud_time_str = cloud_cfg.get("_atualizado_em")
        local_time_str = local_cfg.get("_atualizado_em") if local_cfg else None

        deve_usar_nuvem = True
        if local_cfg and local_time_str and cloud_time_str:
            try:
                t_local = datetime.fromisoformat(local_time_str)
                t_cloud = datetime.fromisoformat(cloud_time_str)
                if t_local > t_cloud:
                    deve_usar_nuvem = False
            except Exception:
                pass
        elif local_cfg and not cloud_time_str and local_time_str:
            deve_usar_nuvem = False

        if deve_usar_nuvem:
            tmp_file = CONFIG_FILE + ".tmp"
            with open(tmp_file, 'w', encoding='utf-8') as f:
                json.dump(cloud_cfg, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_file, CONFIG_FILE)
            print("[PERSISTÊNCIA] Configurações sincronizadas da nuvem permanente com sucesso!")
            return cloud_cfg
        else:
            salvar_config_nuvem(local_cfg)
            print("[PERSISTÊNCIA] Configurações locais mais recentes sincronizadas para a nuvem com sucesso!")
            return local_cfg
    elif local_cfg:
        salvar_config_nuvem(local_cfg)
        return local_cfg

    return None

def salvar_config_nuvem(dados_dict):
    """
    Salva imediatamente as novas configurações no banco de dados persistente em nuvem (KVDB).
    Também salva uma cópia histórica em 'site_config_historico' para backup perpétuo.
    """
    try:
        if not dados_dict.get("_atualizado_em"):
            dados_dict["_atualizado_em"] = datetime.now().isoformat()

        body_bytes = json.dumps(dados_dict, ensure_ascii=False, indent=2).encode('utf-8')
        req = urllib.request.Request(
            KVDB_BUCKET_URL,
            data=body_bytes,
            method="POST",
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "Spa-Glow-Party/1.0"
            }
        )
        ctx = ssl.create_default_context()
        try:
            res = urllib.request.urlopen(req, timeout=10, context=ctx)
        except Exception:
            ctx = ssl._create_unverified_context()
            res = urllib.request.urlopen(req, timeout=10, context=ctx)

        with res:
            if res.status in (200, 201):
                print("[PERSISTÊNCIA] Configurações salvas permanentemente na nuvem!")

        # Envia também para histórico perpétuo de configurações
        try:
            req_h = urllib.request.Request(
                KVDB_CONFIG_HISTORICO_URL,
                data=body_bytes,
                method="POST",
                headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "Spa-Glow-Party/1.0"}
            )
            try:
                res_h = urllib.request.urlopen(req_h, timeout=8, context=ctx)
            except Exception:
                res_h = urllib.request.urlopen(req_h, timeout=8, context=ssl._create_unverified_context())
            with res_h:
                pass
        except Exception:
            pass

        return True
    except Exception as e:
        print(f"[AVISO] Falha ao enviar configurações para a nuvem permanente: {e}")
    return False

# Restaura as configurações da nuvem na inicialização do servidor
sincronizar_config_nuvem()

DB_LOCK = threading.RLock()

def get_db_connection():
    """
    Cria uma conexão com o banco SQLite com configurações avançadas de concorrência:
    - timeout de 30 segundos
    - WAL mode (Write-Ahead Logging) ativo
    - busy_timeout de 30.000 ms (espera até 30s antes de dar locked)
    - synchronous = NORMAL (melhor performance sem travamentos)
    """
    conn = sqlite3.connect(DB_FILE, timeout=30.0, check_same_thread=False)
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 30000;")
        conn.execute("PRAGMA synchronous = NORMAL;")
    except Exception:
        pass
    return conn

@contextmanager
def get_db():
    """
    Context manager thread-safe com liberação e fechamento garantido (finally: close).
    Garante que conexões nunca fiquem abertas e previne travamentos de 'database is locked'.
    """
    with DB_LOCK:
        conn = get_db_connection()
        try:
            yield conn
        finally:
            try:
                conn.close()
            except Exception:
                pass

def hash_password(password, salt=None):
    if not salt:
        salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return key.hex(), salt

def verify_password(password, stored_hash, salt):
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return secrets.compare_digest(key.hex(), stored_hash)

def create_admin_session(username):
    token = secrets.token_hex(32)
    criado_em = datetime.now()
    expira_em = criado_em + timedelta(days=1)  # Token expira em exatamente 1 dia (24 horas)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO sessoes_admin (token, username, criado_em, expira_em)
            VALUES (?, ?, ?, ?)
        """, (token, username, criado_em.isoformat(), expira_em.isoformat()))
        conn.commit()
    return token

def verify_session_token(token):
    if not token:
        return None
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT username, expira_em FROM sessoes_admin WHERE token = ?", (token,))
            row = cursor.fetchone()
            if not row:
                return None
            username, expira_em_str = row[0], row[1]
            expira_em = datetime.fromisoformat(expira_em_str)
            if datetime.now() > expira_em:
                conn.execute("DELETE FROM sessoes_admin WHERE token = ?", (token,))
                conn.commit()
                return None
            return username
    except Exception:
        return None

def delete_admin_session(token):
    if not token:
        return
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM sessoes_admin WHERE token = ?", (token,))
            conn.commit()
    except Exception:
        pass

# Inicializa banco de dados SQLite com suporte otimizado a concorrencia
def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA busy_timeout = 30000;")
        cursor.execute("PRAGMA synchronous = NORMAL;")
        try:
            cursor.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        except Exception:
            pass
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contatos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                email TEXT NOT NULL,
                telefone TEXT,
                assunto TEXT,
                mensagem TEXT NOT NULL,
                data_envio TEXT NOT NULL,
                lido INTEGER DEFAULT 0
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS voluntarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                email TEXT NOT NULL,
                whatsapp TEXT NOT NULL,
                area_interesse TEXT NOT NULL,
                disponibilidade TEXT,
                experiencia TEXT,
                data_envio TEXT NOT NULL,
                status TEXT DEFAULT 'Pendente'
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios_admin (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                data_criacao TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessoes_admin (
                token TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                criado_em TEXT NOT NULL,
                expira_em TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historico_contatos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_id INTEGER,
                nome TEXT NOT NULL,
                email TEXT NOT NULL,
                telefone TEXT,
                assunto TEXT,
                mensagem TEXT NOT NULL,
                data_envio TEXT NOT NULL,
                status_admin TEXT DEFAULT 'Ativo',
                apagado_em TEXT,
                UNIQUE(nome, email, data_envio, mensagem)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historico_voluntarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_id INTEGER,
                nome TEXT NOT NULL,
                email TEXT NOT NULL,
                whatsapp TEXT NOT NULL,
                area_interesse TEXT NOT NULL,
                disponibilidade TEXT,
                experiencia TEXT,
                data_envio TEXT NOT NULL,
                status TEXT DEFAULT 'Pendente',
                status_admin TEXT DEFAULT 'Ativo',
                apagado_em TEXT,
                UNIQUE(nome, email, data_envio, area_interesse)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historico_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_salvamento TEXT NOT NULL,
                config_json TEXT NOT NULL
            )
        """)
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO historico_contatos (original_id, nome, email, telefone, assunto, mensagem, data_envio, status_admin)
                SELECT id, nome, email, telefone, assunto, mensagem, data_envio, 'Ativo' FROM contatos
            """)
            cursor.execute("""
                INSERT OR IGNORE INTO historico_voluntarios (original_id, nome, email, whatsapp, area_interesse, disponibilidade, experiencia, data_envio, status, status_admin)
                SELECT id, nome, email, whatsapp, area_interesse, disponibilidade, experiencia, data_envio, status, 'Ativo' FROM voluntarios
            """)
        except Exception:
            pass

        # Gerenciamento de credenciais do administrador via variáveis de ambiente (.env)
        admin_user = os.environ.get("ADMIN_USER", "admin").strip()
        admin_pass = os.environ.get("ADMIN_PASSWORD", "").strip()

        cursor.execute("SELECT id, username, password_hash, salt FROM usuarios_admin WHERE username = ?", (admin_user,))
        row = cursor.fetchone()

        if admin_pass:
            # Se uma senha foi definida no .env/ambiente, sincroniza com o banco de dados
            p_hash, salt = hash_password(admin_pass)
            if row:
                cursor.execute("UPDATE usuarios_admin SET password_hash = ?, salt = ? WHERE username = ?", (p_hash, salt, admin_user))
            else:
                data_criacao = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                cursor.execute("""
                    INSERT INTO usuarios_admin (username, password_hash, salt, data_criacao)
                    VALUES (?, ?, ?, ?)
                """, (admin_user, p_hash, salt, data_criacao))
        elif not row:
            cursor.execute("SELECT COUNT(*) FROM usuarios_admin")
            if cursor.fetchone()[0] == 0:
                temp_pass = secrets.token_urlsafe(10)
                p_hash, salt = hash_password(temp_pass)
                data_criacao = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                cursor.execute("""
                    INSERT INTO usuarios_admin (username, password_hash, salt, data_criacao)
                    VALUES (?, ?, ?, ?)
                """, (admin_user, p_hash, salt, data_criacao))
                print("\n" + "=" * 65)
                print("  [SEGURANÇA] Nenhum ADMIN_PASSWORD foi definido no .env!")
                print(f"  -> Usuário inicial: {admin_user}")
                print(f"  -> Senha gerada temporária: {temp_pass}")
                print("  -> Dica: Crie o arquivo .env com ADMIN_PASSWORD=sua_senha")
                print("=" * 65 + "\n")

        conn.commit()
init_db()

def salvar_banco_nuvem():
    """
    1. Salva mensagens e voluntários ativos em 'site_db_backup'.
    2. Salva o HISTÓRICO COMPLETO E PERMANENTE na nuvem em 'site_db_historico',
       garantindo que mesmo se o usuário apagar algo no painel admin,
       o histórico completo permaneça guardado para sempre na nuvem.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            # 1. Contatos e Voluntários ativos da caixa
            cursor.execute("SELECT id, nome, email, telefone, assunto, mensagem, data_envio, lido FROM contatos ORDER BY id ASC")
            contatos = [
                {"id": row[0], "nome": row[1], "email": row[2], "telefone": row[3],
                 "assunto": row[4], "mensagem": row[5], "data_envio": row[6], "lido": row[7]}
                for row in cursor.fetchall()
            ]
            cursor.execute("SELECT id, nome, email, whatsapp, area_interesse, disponibilidade, experiencia, data_envio, status FROM voluntarios ORDER BY id ASC")
            voluntarios = [
                {"id": row[0], "nome": row[1], "email": row[2], "whatsapp": row[3],
                 "area_interesse": row[4], "disponibilidade": row[5], "experiencia": row[6],
                 "data_envio": row[7], "status": row[8]}
                for row in cursor.fetchall()
            ]
            
            # 2. Histórico permanente perpétuo (nunca perde dados de exclusões)
            cursor.execute("SELECT id, original_id, nome, email, telefone, assunto, mensagem, data_envio, status_admin, apagado_em FROM historico_contatos ORDER BY id ASC")
            hist_contatos = [
                {"id": row[0], "original_id": row[1], "nome": row[2], "email": row[3], "telefone": row[4],
                 "assunto": row[5], "mensagem": row[6], "data_envio": row[7], "status_admin": row[8], "apagado_em": row[9]}
                for row in cursor.fetchall()
            ]
            cursor.execute("SELECT id, original_id, nome, email, whatsapp, area_interesse, disponibilidade, experiencia, data_envio, status, status_admin, apagado_em FROM historico_voluntarios ORDER BY id ASC")
            hist_voluntarios = [
                {"id": row[0], "original_id": row[1], "nome": row[2], "email": row[3], "whatsapp": row[4],
                 "area_interesse": row[5], "disponibilidade": row[6], "experiencia": row[7],
                 "data_envio": row[8], "status": row[9], "status_admin": row[10], "apagado_em": row[11]}
                for row in cursor.fetchall()
            ]

        ctx = ssl.create_default_context()

        # Envia backup dos ativos
        payload_ativos = {
            "contatos": contatos,
            "voluntarios": voluntarios,
            "atualizado_em": datetime.now().isoformat()
        }
        body_ativos = json.dumps(payload_ativos, ensure_ascii=False).encode('utf-8')
        req1 = urllib.request.Request(
            KVDB_DB_BACKUP_URL,
            data=body_ativos,
            method="POST",
            headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "Instituto-Sementes-Amanha/1.0"}
        )
        try:
            res1 = urllib.request.urlopen(req1, timeout=10, context=ctx)
        except Exception:
            res1 = urllib.request.urlopen(req1, timeout=10, context=ssl._create_unverified_context())
        with res1:
            pass

        # Envia HISTÓRICO PERMANENTE para a nuvem
        payload_historico = {
            "historico_contatos": hist_contatos,
            "historico_voluntarios": hist_voluntarios,
            "total_contatos": len(hist_contatos),
            "total_voluntarios": len(hist_voluntarios),
            "atualizado_em": datetime.now().isoformat()
        }
        body_hist = json.dumps(payload_historico, ensure_ascii=False).encode('utf-8')
        req2 = urllib.request.Request(
            KVDB_HISTORICO_URL,
            data=body_hist,
            method="POST",
            headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "Instituto-Sementes-Amanha/1.0"}
        )
        try:
            res2 = urllib.request.urlopen(req2, timeout=10, context=ctx)
        except Exception:
            res2 = urllib.request.urlopen(req2, timeout=10, context=ssl._create_unverified_context())
        with res2:
            pass
        print(f"[PERSISTÊNCIA] Histórico permanente salvo na nuvem com sucesso! ({len(hist_contatos)} contatos, {len(hist_voluntarios)} voluntários)")
    except Exception as e:
        print(f"[AVISO] Falha ao fazer backup do histórico na nuvem: {e}")

def disparar_salvar_banco_nuvem_async():
    """Dispara a sincronização de nuvem em thread de fundo para não travar respostas HTTP."""
    t = threading.Thread(target=salvar_banco_nuvem, daemon=True)
    t.start()

def sincronizar_banco_nuvem():
    """
    1. Restaura contatos e voluntários ativos da nuvem.
    2. Restaura o HISTÓRICO PERMANENTE completo da nuvem, garantindo
       que mesmo com reinício do Render ou exclusões no painel, nada seja perdido.
    """
    ctx = ssl.create_default_context()
    # 1. Restaura ativos
    try:
        req = urllib.request.Request(KVDB_DB_BACKUP_URL, headers={"User-Agent": "Instituto-Sementes-Amanha/1.0"})
        try:
            res = urllib.request.urlopen(req, timeout=10, context=ctx)
        except Exception:
            res = urllib.request.urlopen(req, timeout=10, context=ssl._create_unverified_context())
        with res:
            if res.status == 200:
                raw = res.read().decode('utf-8').strip()
                if raw:
                    data = json.loads(raw)
                    with get_db() as conn:
                        cursor = conn.cursor()
                        if "contatos" in data:
                            cursor.execute("DELETE FROM contatos")
                            for c in data.get("contatos", []):
                                cursor.execute("""
                                    INSERT INTO contatos (id, nome, email, telefone, assunto, mensagem, data_envio, lido)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                """, (c["id"], c["nome"], c["email"], c.get("telefone", ""), c.get("assunto", ""), c["mensagem"], c["data_envio"], c.get("lido", 0)))
                        if "voluntarios" in data:
                            cursor.execute("DELETE FROM voluntarios")
                            for v in data.get("voluntarios", []):
                                cursor.execute("""
                                    INSERT INTO voluntarios (id, nome, email, whatsapp, area_interesse, disponibilidade, experiencia, data_envio, status)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, (v["id"], v["nome"], v["email"], v["whatsapp"], v["area_interesse"], v.get("disponibilidade", ""), v.get("experiencia", ""), v["data_envio"], v.get("status", "Pendente")))
                        conn.commit()
    except Exception as e:
        print(f"[AVISO] Falha ao sincronizar ativos da nuvem: {e}")

    # 2. Restaura HISTÓRICO PERMANENTE da nuvem
    try:
        req_h = urllib.request.Request(KVDB_HISTORICO_URL, headers={"User-Agent": "Instituto-Sementes-Amanha/1.0"})
        try:
            res_h = urllib.request.urlopen(req_h, timeout=10, context=ctx)
        except Exception:
            res_h = urllib.request.urlopen(req_h, timeout=10, context=ssl._create_unverified_context())
        with res_h:
            if res_h.status == 200:
                raw_h = res_h.read().decode('utf-8').strip()
                if raw_h:
                    data_h = json.loads(raw_h)
                    with get_db() as conn:
                        cursor = conn.cursor()
                        if "historico_contatos" in data_h:
                            for c in data_h.get("historico_contatos", []):
                                cursor.execute("""
                                    INSERT OR REPLACE INTO historico_contatos (id, original_id, nome, email, telefone, assunto, mensagem, data_envio, status_admin, apagado_em)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, (c.get("id"), c.get("original_id"), c["nome"], c["email"], c.get("telefone", ""), c.get("assunto", ""), c["mensagem"], c["data_envio"], c.get("status_admin", "Ativo"), c.get("apagado_em")))
                        if "historico_voluntarios" in data_h:
                            for v in data_h.get("historico_voluntarios", []):
                                cursor.execute("""
                                    INSERT OR REPLACE INTO historico_voluntarios (id, original_id, nome, email, whatsapp, area_interesse, disponibilidade, experiencia, data_envio, status, status_admin, apagado_em)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, (v.get("id"), v.get("original_id"), v["nome"], v["email"], v["whatsapp"], v["area_interesse"], v.get("disponibilidade", ""), v.get("experiencia", ""), v["data_envio"], v.get("status", "Pendente"), v.get("status_admin", "Ativo"), v.get("apagado_em")))
                        conn.commit()
                    print("[PERSISTÊNCIA] Histórico permanente completo restaurado da nuvem com sucesso!")
                    # Sincroniza qualquer dado residual local de volta para a nuvem
                    disparar_salvar_banco_nuvem_async()
    except Exception as e:
        print(f"[AVISO] Falha ao sincronizar histórico da nuvem: {e}")

# Restaura mensagens de contato e voluntários da nuvem na inicialização
sincronizar_banco_nuvem()

def enviar_para_nuvem_permanente(dados_binarios, nome_arquivo, content_type="application/octet-stream"):
    """
    Tenta enviar o arquivo para armazenamento em nuvem permanente (Cloudinary ou Catbox).
    Retorna a URL HTTPS pública definitiva ou None em caso de falha.
    """
    # 1. Cloudinary (se configurado nas variáveis de ambiente ou .env)
    cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME")
    api_key = os.environ.get("CLOUDINARY_API_KEY")
    api_secret = os.environ.get("CLOUDINARY_API_SECRET")

    if cloud_name and api_key and api_secret:
        try:
            import time
            timestamp = str(int(time.time()))
            sig_str = f"timestamp={timestamp}{api_secret}"
            signature = hashlib.sha1(sig_str.encode("utf-8")).hexdigest()
            boundary = uuid.uuid4().hex
            resource_type = "raw" if nome_arquivo.lower().endswith(('.pdf', '.doc', '.docx', '.xls', '.xlsx')) else "image"
            url_endpoint = f"https://api.cloudinary.com/v1_1/{cloud_name}/{resource_type}/upload"

            body = (
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"api_key\"\r\n\r\n{api_key}\r\n"
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"timestamp\"\r\n\r\n{timestamp}\r\n"
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"signature\"\r\n\r\n{signature}\r\n"
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{nome_arquivo}\"\r\nContent-Type: {content_type}\r\n\r\n"
            ).encode("utf-8") + dados_binarios + f"\r\n--{boundary}--\r\n".encode("utf-8")

            req = urllib.request.Request(
                url_endpoint,
                data=body,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
            )
            ctx = ssl.create_default_context()
            try:
                res = urllib.request.urlopen(req, timeout=25, context=ctx)
            except Exception:
                ctx = ssl._create_unverified_context()
                res = urllib.request.urlopen(req, timeout=25, context=ctx)

            with res:
                ret = json.loads(res.read().decode("utf-8"))
                if "secure_url" in ret:
                    print(f"[STORAGE] Arquivo salvo no Cloudinary: {ret['secure_url']}")
                    return ret["secure_url"]
        except Exception as e:
            print(f"[AVISO] Upload Cloudinary falhou, tentando fallback: {e}")

    # 2. Nuvem Pública Permanente (Catbox) - Grátis, sem necessidade de credenciais
    try:
        boundary = uuid.uuid4().hex
        catbox_userhash = os.environ.get("CATBOX_USERHASH", "").strip()
        userhash_part = b""
        if catbox_userhash:
            userhash_part = f"--{boundary}\r\nContent-Disposition: form-data; name=\"userhash\"\r\n\r\n{catbox_userhash}\r\n".encode("utf-8")

        body = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"reqtype\"\r\n\r\nfileupload\r\n"
        ).encode("utf-8") + userhash_part + (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"fileToUpload\"; filename=\"{nome_arquivo}\"\r\nContent-Type: {content_type}\r\n\r\n"
        ).encode("utf-8") + dados_binarios + f"\r\n--{boundary}--\r\n".encode("utf-8")

        req = urllib.request.Request(
            "https://catbox.moe/user/api.php",
            data=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "User-Agent": "Instituto-Sementes-Amanha/1.0"
            }
        )
        ctx = ssl.create_default_context()
        try:
            res = urllib.request.urlopen(req, timeout=25, context=ctx)
        except Exception:
            ctx = ssl._create_unverified_context()
            res = urllib.request.urlopen(req, timeout=25, context=ctx)

        with res:
            url_gerada = res.read().decode("utf-8").strip()
            if url_gerada.startswith("http://") or url_gerada.startswith("https://"):
                print(f"[STORAGE] Arquivo salvo na nuvem permanente: {url_gerada}")
                return url_gerada
    except Exception as e:
        print(f"[AVISO] Upload em nuvem permanente falhou: {e}")

    return None

def excluir_catbox_asset(url):
    """
    Exclui arquivo do Catbox caso CATBOX_USERHASH esteja configurado.
    """
    catbox_userhash = os.environ.get("CATBOX_USERHASH", "").strip()
    if not catbox_userhash or not url or "catbox.moe" not in url:
        return False
    try:
        nome_arq = os.path.basename(urlparse(url).path)
        if not nome_arq:
            return False
        params = urlencode({
            "reqtype": "deletefiles",
            "userhash": catbox_userhash,
            "files": nome_arq
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://catbox.moe/user/api.php",
            data=params,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Instituto-Sementes-Amanha/1.0"
            }
        )
        ctx = ssl.create_default_context()
        try:
            res = urllib.request.urlopen(req, timeout=10, context=ctx)
        except Exception:
            ctx = ssl._create_unverified_context()
            res = urllib.request.urlopen(req, timeout=10, context=ctx)
        with res:
            res_txt = res.read().decode("utf-8")
            print(f"[STORAGE] Exclusão no Catbox ({nome_arq}): {res_txt}")
            return True
    except Exception as e:
        print(f"[AVISO] Falha ao excluir arquivo do Catbox: {e}")
        return False

def excluir_cloudinary_asset(url):
    """
    Exclui arquivo da nuvem Cloudinary caso credenciais estejam configuradas.
    """
    cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME", "").strip()
    api_key = os.environ.get("CLOUDINARY_API_KEY", "").strip()
    api_secret = os.environ.get("CLOUDINARY_API_SECRET", "").strip()
    if not (cloud_name and api_key and api_secret and url and "cloudinary.com" in url):
        return False
    try:
        match = re.search(r'cloudinary\.com/[^/]+/(image|raw|video)/upload/(?:v\d+/)?(.+)', url)
        if not match:
            return False
        resource_type = match.group(1)
        public_id_com_ext = match.group(2)

        # Imagens no Cloudinary usam public_id sem extensão; arquivos raw (PDFs) mantêm extensão
        if resource_type == 'image':
            public_id = os.path.splitext(public_id_com_ext)[0]
        else:
            public_id = public_id_com_ext

        import time
        timestamp = str(int(time.time()))
        sig_str = f"public_id={public_id}&timestamp={timestamp}{api_secret}"
        signature = hashlib.sha1(sig_str.encode("utf-8")).hexdigest()

        params = urlencode({
            "public_id": public_id,
            "timestamp": timestamp,
            "api_key": api_key,
            "signature": signature
        }).encode("utf-8")

        req = urllib.request.Request(
            f"https://api.cloudinary.com/v1_1/{cloud_name}/{resource_type}/destroy",
            data=params,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        ctx = ssl.create_default_context()
        try:
            res = urllib.request.urlopen(req, timeout=15, context=ctx)
        except Exception:
            ctx = ssl._create_unverified_context()
            res = urllib.request.urlopen(req, timeout=15, context=ctx)

        with res:
            res_data = json.loads(res.read().decode("utf-8"))
            print(f"[STORAGE] Exclusão no Cloudinary ({public_id}): {res_data}")
            return res_data.get("result") in ("ok", "not found")
    except Exception as e:
        print(f"[AVISO] Falha ao excluir arquivo do Cloudinary ({url}): {e}")
        return False

def excluir_midia_nuvem(url):
    """
    Exclui arquivo do provedor de nuvem correspondente (Cloudinary ou Catbox com token).
    """
    if not url:
        return False
    if "cloudinary.com" in url:
        return excluir_cloudinary_asset(url)
    elif "catbox.moe" in url:
        return excluir_catbox_asset(url)
    return False

ARQUIVOS_LOCAIS_PROTEGIDOS = {
    "cartao_cnpj_exemplo.pdf",
    "certificado_osc_exemplo.pdf",
    "cnd_federal_exemplo.pdf",
    "estatuto_social_exemplo.pdf",
    "relatorio_anual_2023.pdf",
    "relatorio_anual_2024.pdf",
    "relatorio_anual_2025.pdf",
}

def extrair_todas_referencias_midia(config_data):
    """
    Extrai recursivamente todos os caminhos locais, nomes de arquivos e URLs
    referenciados na configuração atual do site.
    """
    referencias = set()
    def _coletar(item):
        if isinstance(item, str):
            s = item.strip()
            if s:
                referencias.add(s)
                if s.startswith('/'):
                    referencias.add(s[1:])
                nome_base = os.path.basename(s.replace('\\', '/'))
                if nome_base:
                    referencias.add(nome_base)
        elif isinstance(item, dict):
            for v in item.values():
                _coletar(v)
        elif isinstance(item, list):
            for v in item:
                _coletar(v)
    _coletar(config_data)
    return referencias

def executar_faxina_midia(novo_config=None, config_anterior=None):
    """
    Realiza a faxina de mídias:
    1. Se config_anterior for fornecido, detecta URLs em nuvem que foram substituídas e apaga da nuvem.
    2. Compara todos os arquivos locais em public/assets/img e public/docs com as referências ativas
       e remove arquivos órfãos/antigos que não são mais utilizados no site.
    Retorna a lista de itens removidos e bytes liberados.
    """
    removidos = []
    bytes_liberados = 0

    # 1. Carrega configuração ativa
    config_atual = novo_config
    if config_atual is None:
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config_atual = json.load(f)
            except Exception:
                config_atual = {}
        else:
            config_atual = {}

    refs_ativas = extrair_todas_referencias_midia(config_atual)

    # 2. Se houver configuração anterior, identifica arquivos e URLs que foram desvinculados
    if config_anterior:
        refs_antigas = extrair_todas_referencias_midia(config_anterior)
        desvinculados = refs_antigas - refs_ativas
        for item in desvinculados:
            if item.startswith("http://") or item.startswith("https://"):
                if excluir_midia_nuvem(item):
                    removidos.append({"tipo": "nuvem", "alvo": item})

    # 3. Faxina de arquivos locais em public/assets/img
    if os.path.exists(IMG_DIR):
        for f in os.listdir(IMG_DIR):
            caminho = os.path.join(IMG_DIR, f)
            if not os.path.isfile(caminho):
                continue
            if f in ARQUIVOS_LOCAIS_PROTEGIDOS or f in refs_ativas:
                continue
            rel_path1 = f"/assets/img/{f}"
            rel_path2 = f"assets/img/{f}"
            if rel_path1 in refs_ativas or rel_path2 in refs_ativas:
                continue
            try:
                tam = os.path.getsize(caminho)
                os.remove(caminho)
                bytes_liberados += tam
                removidos.append({"tipo": "local_imagem", "arquivo": f, "tamanho": tam})
                print(f"[FAXINA] Imagem não utilizada removida do disco: {f}")
            except Exception as e:
                print(f"[AVISO] Não foi possível remover imagem órfã {f}: {e}")

    # 4. Faxina de arquivos locais em public/docs
    if os.path.exists(DOCS_DIR):
        for f in os.listdir(DOCS_DIR):
            caminho = os.path.join(DOCS_DIR, f)
            if not os.path.isfile(caminho):
                continue
            if f in ARQUIVOS_LOCAIS_PROTEGIDOS or f.endswith('_exemplo.pdf') or f in refs_ativas:
                continue
            rel_path1 = f"/docs/{f}"
            rel_path2 = f"/public/docs/{f}"
            rel_path3 = f"docs/{f}"
            if rel_path1 in refs_ativas or rel_path2 in refs_ativas or rel_path3 in refs_ativas:
                continue
            try:
                tam = os.path.getsize(caminho)
                os.remove(caminho)
                bytes_liberados += tam
                removidos.append({"tipo": "local_documento", "arquivo": f, "tamanho": tam})
                print(f"[FAXINA] Documento não utilizado removido do disco: {f}")
            except Exception as e:
                print(f"[AVISO] Não foi possível remover documento órfão {f}: {e}")

    return {
        "removidos": removidos,
        "total_removidos": len(removidos),
        "bytes_liberados": bytes_liberados
    }


class ONGRequestHandler(BaseHTTPRequestHandler):
    def end_headers(self):
        # Habilita CORS e desativa cache agressivo para desenvolvimento
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def send_json(self, data, status_code=200):
        response_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(response_bytes)))
        self.end_headers()
        self.wfile.write(response_bytes)

    def send_file(self, file_path):
        if not os.path.isfile(file_path):
            self.send_response(404)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(b"<h1>404 - Arquivo n\xc3\xa3o encontrado</h1>")
            return

        content_type, _ = mimetypes.guess_type(file_path)
        if not content_type:
            content_type = 'application/octet-stream'

        file_size = os.path.getsize(file_path)
        range_header = self.headers.get('Range')

        try:
            if range_header and range_header.startswith('bytes='):
                # Suporte a HTTP Range Requests (streaming de video e audio para navegadores)
                ranges = range_header[6:].split('-')
                start = int(ranges[0]) if ranges[0] else 0
                end = int(ranges[1]) if len(ranges) > 1 and ranges[1] else file_size - 1
                if start >= file_size:
                    self.send_response(416)
                    self.send_header('Content-Range', f'bytes */{file_size}')
                    self.end_headers()
                    return
                end = min(end, file_size - 1)
                chunk_len = end - start + 1

                self.send_response(206)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
                self.send_header('Content-Length', str(chunk_len))
                self.send_header('Accept-Ranges', 'bytes')
                self.end_headers()

                with open(file_path, 'rb') as f:
                    f.seek(start)
                    bytes_remaining = chunk_len
                    buffer_size = 64 * 1024
                    while bytes_remaining > 0:
                        to_read = min(bytes_remaining, buffer_size)
                        buf = f.read(to_read)
                        if not buf:
                            break
                        self.wfile.write(buf)
                        bytes_remaining -= len(buf)
            else:
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(file_size))
                self.send_header('Accept-Ranges', 'bytes')
                self.end_headers()

                with open(file_path, 'rb') as f:
                    buffer_size = 64 * 1024
                    while True:
                        buf = f.read(buffer_size)
                        if not buf:
                            break
                        self.wfile.write(buf)
        except (ConnectionResetError, BrokenPipeError):
            pass
        except Exception as e:
            try:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(f"Erro ao carregar arquivo: {str(e)}".encode('utf-8'))
            except Exception:
                pass

    def get_session_token(self):
        # 1. Verifica Cookie HTTP
        cookie_header = self.headers.get('Cookie')
        if cookie_header:
            cookie = SimpleCookie()
            try:
                cookie.load(cookie_header)
                if 'admin_token' in cookie:
                    return cookie['admin_token'].value
            except Exception:
                pass

        # 2. Verifica Authorization Header (Bearer)
        auth_header = self.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            return auth_header[7:].strip()

        # 3. Verifica Header Customizado
        token_hdr = self.headers.get('X-Admin-Token')
        if token_hdr:
            return token_hdr.strip()

        # 4. Fallback de compatibilidade via query param (essencial para mobile/Safari/iOS)
        try:
            parsed = urlparse(self.path)
            q_params = parse_qs(parsed.query)
            if 'token' in q_params and q_params['token']:
                return q_params['token'][0].strip()
            if 'admin_token' in q_params and q_params['admin_token']:
                return q_params['admin_token'][0].strip()
        except Exception:
            pass

        return None

    def get_authenticated_user(self):
        token = self.get_session_token()
        if not token:
            return None
        return verify_session_token(token)

    def is_authenticated(self):
        return self.get_authenticated_user() is not None

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # Rotas da Landing Page, Login e Painel Admin
        if path == '/' or path == '/index.html':
            self.send_file(os.path.join(PUBLIC_DIR, 'index.html'))
            return
        elif path == '/login' or path == '/login.html':
            self.send_file(os.path.join(PUBLIC_DIR, 'login.html'))
            return
        elif path == '/admin' or path == '/admin.html':
            token = self.get_session_token()
            user = verify_session_token(token) if token else None
            if not user:
                self.send_response(302)
                self.send_header('Location', '/login')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return

            # Renova ou garante o cookie seguro caso tenha vindo via parâmetro no celular
            is_https = (
                self.headers.get('X-Forwarded-Proto', '').lower() == 'https' or
                self.headers.get('X-Forwarded-Ssl', '').lower() == 'on'
            )
            secure_flag = "; Secure" if is_https else ""
            cookie_val = f"admin_token={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=86400{secure_flag}"

            file_path = os.path.join(PUBLIC_DIR, 'admin.html')
            if not os.path.isfile(file_path):
                self.send_response(404)
                self.end_headers()
                return
            try:
                with open(file_path, 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Set-Cookie', cookie_val)
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(f"Erro ao carregar admin.html: {str(e)}".encode('utf-8'))
            return

        # Rotas de API
        if path == '/api/config':
            try:
                if not os.path.exists(CONFIG_FILE):
                    sincronizar_config_nuvem()
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                self.send_json(config_data)
            except Exception as e:
                self.send_json({"erro": f"Falha ao carregar configuracoes: {str(e)}"}, 500)
            return

        elif path == '/api/admin/me':
            user = self.get_authenticated_user()
            if not user:
                self.send_json({"sucesso": False, "erro": "Não autenticado."}, 401)
                return
            self.send_json({"sucesso": True, "username": user})
            return

        elif path == '/api/stats':
            if not self.is_authenticated():
                self.send_json({"sucesso": False, "erro": "Acesso não autorizado. Faça login como administrador."}, 401)
                return
            try:
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM contatos")
                    total_contatos = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM voluntarios")
                    total_voluntarios = cursor.fetchone()[0]
                self.send_json({
                    "sucesso": True,
                    "total_contatos": total_contatos,
                    "total_voluntarios": total_voluntarios
                })
            except Exception as e:
                self.send_json({"erro": str(e)}, 500)
            return

        elif path == '/api/mensagens':
            if not self.is_authenticated():
                self.send_json({"sucesso": False, "erro": "Acesso não autorizado. Faça login como administrador."}, 401)
                return
            try:
                with get_db() as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM contatos ORDER BY id DESC LIMIT 100")
                    rows = [dict(r) for r in cursor.fetchall()]
                self.send_json(rows)
            except Exception as e:
                self.send_json({"erro": str(e)}, 500)
            return

        elif path == '/api/voluntarios':
            if not self.is_authenticated():
                self.send_json({"sucesso": False, "erro": "Acesso não autorizado. Faça login como administrador."}, 401)
                return
            try:
                with get_db() as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM voluntarios ORDER BY id DESC LIMIT 100")
                    rows = [dict(r) for r in cursor.fetchall()]
                self.send_json(rows)
            except Exception as e:
                self.send_json({"erro": str(e)}, 500)
            return

        elif path == '/api/admin/banco/status':
            if not self.is_authenticated():
                self.send_json({"sucesso": False, "erro": "Acesso não autorizado."}, 401)
                return
            try:
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM contatos")
                    n_contatos = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM voluntarios")
                    n_voluntarios = cursor.fetchone()[0]
                tamanho_kb = round(os.path.getsize(DB_FILE) / 1024, 1) if os.path.exists(DB_FILE) else 0
                self.send_json({
                    "sucesso": True,
                    "nuvem_conectada": True,
                    "provedor": "KVDB Cloud Backup",
                    "total_contatos": n_contatos,
                    "total_voluntarios": n_voluntarios,
                    "tamanho_banco_kb": tamanho_kb,
                    "modo": "SQLite com Backup Automático na Nuvem"
                })
            except Exception as e:
                self.send_json({"sucesso": False, "erro": str(e)}, 500)
            return

        elif path == '/api/admin/historico':
            if not self.is_authenticated():
                self.send_json({"sucesso": False, "erro": "Acesso não autorizado."}, 401)
                return
            try:
                with get_db() as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM historico_contatos ORDER BY id DESC")
                    h_contatos = [dict(r) for r in cursor.fetchall()]
                    cursor.execute("SELECT * FROM historico_voluntarios ORDER BY id DESC")
                    h_voluntarios = [dict(r) for r in cursor.fetchall()]
                self.send_json({
                    "sucesso": True,
                    "total_contatos": len(h_contatos),
                    "total_voluntarios": len(h_voluntarios),
                    "contatos": h_contatos,
                    "voluntarios": h_voluntarios
                })
            except Exception as e:
                self.send_json({"sucesso": False, "erro": str(e)}, 500)
            return

        elif path == '/api/admin/historico/restaurar':
            if not self.is_authenticated():
                self.send_json({"sucesso": False, "erro": "Acesso não autorizado."}, 401)
                return
            try:
                tipo = body_json.get('tipo', 'contato')
                item_id = int(body_json.get('id', 0))
                if not item_id:
                    self.send_json({"sucesso": False, "erro": "ID inválido."}, 400)
                    return

                with get_db() as conn:
                    cursor = conn.cursor()

                    if tipo == 'contato':
                        cursor.execute("SELECT original_id, nome, email, telefone, assunto, mensagem, data_envio FROM historico_contatos WHERE id = ?", (item_id,))
                        row = cursor.fetchone()
                        if row:
                            cursor.execute("""
                                INSERT INTO contatos (nome, email, telefone, assunto, mensagem, data_envio, lido)
                                VALUES (?, ?, ?, ?, ?, ?, 0)
                            """, (row[1], row[2], row[3], row[4], row[5], row[6]))
                            cursor.execute("UPDATE historico_contatos SET status_admin = 'Ativo', apagado_em = NULL WHERE id = ?", (item_id,))
                    else:
                        cursor.execute("SELECT original_id, nome, email, whatsapp, area_interesse, disponibilidade, experiencia, data_envio, status FROM historico_voluntarios WHERE id = ?", (item_id,))
                        row = cursor.fetchone()
                        if row:
                            cursor.execute("""
                                INSERT INTO voluntarios (nome, email, whatsapp, area_interesse, disponibilidade, experiencia, data_envio, status)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8]))
                            cursor.execute("UPDATE historico_voluntarios SET status_admin = 'Ativo', apagado_em = NULL WHERE id = ?", (item_id,))

                    conn.commit()
                disparar_salvar_banco_nuvem_async()
                self.send_json({"sucesso": True, "mensagem": "Item restaurado com sucesso para a caixa de entrada ativa!"})
            except Exception as e:
                self.send_json({"sucesso": False, "erro": str(e)}, 500)
            return

        elif path == '/api/admin/banco/exportar':
            if not self.is_authenticated():
                self.send_json({"sucesso": False, "erro": "Acesso não autorizado."}, 401)
                return
            try:
                with get_db() as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM contatos ORDER BY id ASC")
                    contatos = [dict(r) for r in cursor.fetchall()]
                    cursor.execute("SELECT * FROM voluntarios ORDER BY id ASC")
                    voluntarios = [dict(r) for r in cursor.fetchall()]
                    cursor.execute("SELECT * FROM historico_contatos ORDER BY id ASC")
                    h_contatos = [dict(r) for r in cursor.fetchall()]
                    cursor.execute("SELECT * FROM historico_voluntarios ORDER BY id ASC")
                    h_voluntarios = [dict(r) for r in cursor.fetchall()]

                export_data = {
                    "sistema": "Spa Glow Party - Exportação Oficial do Banco de Dados",
                    "data_exportacao": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                    "resumo": {
                        "mensagens_ativas": len(contatos),
                        "voluntarios_ativos": len(voluntarios),
                        "total_historico_mensagens": len(h_contatos),
                        "total_historico_voluntarios": len(h_voluntarios)
                    },
                    "mensagens_contato": contatos,
                    "inscricoes_voluntarios": voluntarios,
                    "historico_completo_mensagens": h_contatos,
                    "historico_completo_voluntarios": h_voluntarios
                }
                export_bytes = json.dumps(export_data, ensure_ascii=False, indent=2).encode('utf-8')
                data_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                nome_arq = f"backup_ong_{data_str}.json"

                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Disposition', f'attachment; filename="{nome_arq}"')
                self.send_header('Content-Length', str(len(export_bytes)))
                self.end_headers()
                self.wfile.write(export_bytes)
            except Exception as e:
                self.send_json({"sucesso": False, "erro": str(e)}, 500)
            return

        elif path == '/api/admin/relatorio':
            if not self.is_authenticated():
                self.send_json({"sucesso": False, "erro": "Acesso não autorizado. Faça login como administrador."}, 401)
                return
            try:
                query_params = parse_qs(parsed.query)
                periodo_solicitado = query_params.get('periodo', [''])[0].strip()

                with get_db() as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    # Lê dados do HISTÓRICO PERMANENTE PERPÉTUO (mesmo que tenham sido apagados do painel)
                    cursor.execute("SELECT * FROM historico_contatos ORDER BY id DESC")
                    todos_contatos = [dict(r) for r in cursor.fetchall()]
                    cursor.execute("SELECT * FROM historico_voluntarios ORDER BY id DESC")
                    todos_voluntarios = [dict(r) for r in cursor.fetchall()]

                    # Fallback de segurança se historico estiver vazio
                    if not todos_contatos:
                        cursor.execute("SELECT * FROM contatos ORDER BY id DESC")
                        todos_contatos = [dict(r) for r in cursor.fetchall()]
                    if not todos_voluntarios:
                        cursor.execute("SELECT * FROM voluntarios ORDER BY id DESC")
                        todos_voluntarios = [dict(r) for r in cursor.fetchall()]

                def extrair_ano_mes(d_str):
                    if not d_str:
                        return None
                    d_str = d_str.strip()
                    if len(d_str) >= 10 and d_str[2] == '/' and d_str[5] == '/':
                        dia, mes, ano = d_str[:10].split('/')
                        return f"{ano}-{mes}"
                    if len(d_str) >= 7 and d_str[4] == '-':
                        return d_str[:7]
                    return None

                mes_atual_iso = datetime.now().strftime("%Y-%m")
                nomes_meses = {
                    "01": "Janeiro", "02": "Fevereiro", "03": "Março", "04": "Abril",
                    "05": "Maio", "06": "Junho", "07": "Julho", "08": "Agosto",
                    "09": "Setembro", "10": "Outubro", "11": "Novembro", "12": "Dezembro"
                }

                periodos_encontrados = set()
                periodos_encontrados.add(mes_atual_iso)
                for c in todos_contatos:
                    ym = extrair_ano_mes(c.get("data_envio", ""))
                    if ym:
                        periodos_encontrados.add(ym)
                for v in todos_voluntarios:
                    ym = extrair_ano_mes(v.get("data_envio", ""))
                    if ym:
                        periodos_encontrados.add(ym)

                periodos_ordenados = sorted(list(periodos_encontrados), reverse=True)
                periodos_opcoes = []
                for p in periodos_ordenados:
                    partes = p.split("-")
                    if len(partes) == 2:
                        ano_p, mes_p = partes
                        label = f"{nomes_meses.get(mes_p, mes_p)} de {ano_p}"
                        periodos_opcoes.append({"valor": p, "label": label})
                periodos_opcoes.append({"valor": "todos", "label": "Todo o Histórico (Geral)"})

                if not periodo_solicitado:
                    periodo_ativo = mes_atual_iso
                else:
                    periodo_ativo = periodo_solicitado

                if periodo_ativo == "todos":
                    periodo_label = "Todo o Histórico (Consolidado)"
                    contatos_filtrados = todos_contatos
                    voluntarios_filtrados = todos_voluntarios
                else:
                    if "-" in periodo_ativo:
                        ano_sel, mes_sel = periodo_ativo.split("-")
                    else:
                        ano_sel = str(datetime.now().year)
                        mes_sel = str(datetime.now().month).zfill(2)
                    periodo_label = f"{nomes_meses.get(mes_sel, mes_sel)} de {ano_sel}"
                    contatos_filtrados = [c for c in todos_contatos if extrair_ano_mes(c.get("data_envio", "")) == periodo_ativo]
                    voluntarios_filtrados = [v for v in todos_voluntarios if extrair_ano_mes(v.get("data_envio", "")) == periodo_ativo]

                areas_contagem = {}
                for v in voluntarios_filtrados:
                    area = v.get("area_interesse", "Não informada").strip()
                    if area:
                        areas_contagem[area] = areas_contagem.get(area, 0) + 1

                total_vol_periodo = len(voluntarios_filtrados)
                areas_distribuicao = [
                    {
                        "area": area,
                        "quantidade": qtd,
                        "percentual": round((qtd / total_vol_periodo * 100), 1) if total_vol_periodo > 0 else 0
                    }
                    for area, qtd in sorted(areas_contagem.items(), key=lambda x: x[1], reverse=True)
                ]

                assuntos_contagem = {}
                for c in contatos_filtrados:
                    ass = c.get("assunto", "Geral").strip() or "Geral"
                    assuntos_contagem[ass] = assuntos_contagem.get(ass, 0) + 1

                total_msg_periodo = len(contatos_filtrados)
                assuntos_distribuicao = [
                    {
                        "assunto": ass,
                        "quantidade": qtd,
                        "percentual": round((qtd / total_msg_periodo * 100), 1) if total_msg_periodo > 0 else 0
                    }
                    for ass, qtd in sorted(assuntos_contagem.items(), key=lambda x: x[1], reverse=True)
                ]

                tamanho_kb = round(os.path.getsize(DB_FILE) / 1024, 1) if os.path.exists(DB_FILE) else 0
                total_imagens = len([f for f in os.listdir(IMG_DIR) if os.path.isfile(os.path.join(IMG_DIR, f))]) if os.path.exists(IMG_DIR) else 0
                total_docs = len([f for f in os.listdir(DOCS_DIR) if os.path.isfile(os.path.join(DOCS_DIR, f))]) if os.path.exists(DOCS_DIR) else 0

                nome_instituicao = "Spa Glow Party"
                if os.path.exists(CONFIG_FILE):
                    try:
                        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                            cfg = json.load(f)
                            nome_instituicao = cfg.get("instituicao", {}).get("nome", nome_instituicao)
                    except Exception:
                        pass

                linhas_whatsapp = [
                    f"📊 *Relatório de Resultados & Acompanhamento Web*",
                    f"🏢 *{nome_instituicao}*",
                    f"🗓️ *Período:* {periodo_label}",
                    f"────────────────────────",
                    f"📩 *Mensagens Recebidas:* {total_msg_periodo} (Total histórico: {len(todos_contatos)})",
                    f"🤝 *Voluntários Cadastrados:* {total_vol_periodo} (Total histórico: {len(todos_voluntarios)})",
                ]

                if areas_distribuicao:
                    linhas_whatsapp.append(f"\n🎯 *Áreas mais procuradas pelos voluntários:*")
                    for a in areas_distribuicao[:3]:
                        linhas_whatsapp.append(f"• {a['area']}: {a['quantidade']} ({a['percentual']}%)")

                linhas_whatsapp.extend([
                    f"\n🛡️ *Saúde do Sistema & Manutenção:*",
                    f"• Status do Site: 🟢 100% Operacional e Ativo",
                    f"• Banco de Dados: Sincronizado e Seguro na Nuvem",
                    f"• Armazenamento: {total_imagens + total_docs} arquivos ativos com faxina automática",
                    f"────────────────────────",
                    f"✅ *Acompanhamento e suporte técnico em dia!*"
                ])
                texto_whatsapp = "\n".join(linhas_whatsapp)

                self.send_json({
                    "sucesso": True,
                    "periodo_ativo": periodo_ativo,
                    "periodo_label": periodo_label,
                    "periodos_disponiveis": periodos_opcoes,
                    "nome_instituicao": nome_instituicao,
                    "data_geracao": datetime.now().strftime("%d/%m/%Y às %H:%M"),
                    "metricas": {
                        "total_mensagens_periodo": total_msg_periodo,
                        "total_mensagens_geral": len(todos_contatos),
                        "total_voluntarios_periodo": total_vol_periodo,
                        "total_voluntarios_geral": len(todos_voluntarios),
                        "banco_tamanho_kb": tamanho_kb,
                        "arquivos_imagens": total_imagens,
                        "arquivos_documentos": total_docs,
                        "status_servidor": "Operacional 100%"
                    },
                    "areas_voluntariado": areas_distribuicao,
                    "assuntos_contato": assuntos_distribuicao,
                    "ultimas_mensagens": [
                        {
                            "id": c["id"],
                            "nome": c["nome"],
                            "email": c["email"],
                            "telefone": c.get("telefone", ""),
                            "assunto": c.get("assunto", "Sem assunto"),
                            "data_envio": c["data_envio"],
                            "mensagem_resumo": (c["mensagem"][:100] + "...") if len(c.get("mensagem", "")) > 100 else c.get("mensagem", "")
                        }
                        for c in contatos_filtrados[:10]
                    ],
                    "ultimos_voluntarios": [
                        {
                            "id": v["id"],
                            "nome": v["nome"],
                            "email": v["email"],
                            "whatsapp": v.get("whatsapp", ""),
                            "area_interesse": v.get("area_interesse", ""),
                            "disponibilidade": v.get("disponibilidade", ""),
                            "data_envio": v["data_envio"],
                            "status": v.get("status", "Pendente")
                        }
                        for v in voluntarios_filtrados[:10]
                    ],
                    "texto_whatsapp": texto_whatsapp
                })
            except Exception as e:
                self.send_json({"sucesso": False, "erro": f"Erro ao gerar relatório: {str(e)}"}, 500)
            return

        # Servir arquivos estáticos dentro de /public
        clean_path = path.lstrip('/')
        if clean_path.startswith('public/'):
            clean_path = clean_path[len('public/'):]
        
        file_candidate = os.path.join(PUBLIC_DIR, clean_path)
        if os.path.isfile(file_candidate):
            self.send_file(file_candidate)
            return

        # Fallback 404
        self.send_response(404)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(b"<h1>404 - Nao encontrado</h1>")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get('Content-Length', 0))
        post_body = self.rfile.read(content_length)

        try:
            body_json = json.loads(post_body.decode('utf-8')) if post_body else {}
        except Exception:
            body_json = {}

        if path == '/api/admin/login':
            username = body_json.get('username', '').strip()
            password = body_json.get('password', '')
            if not username or not password:
                self.send_json({"sucesso": False, "erro": "Informe o usuário e a senha."}, 400)
                return

            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT username, password_hash, salt FROM usuarios_admin WHERE LOWER(username) = LOWER(?)", (username,))
                row = cursor.fetchone()

            if not row or not verify_password(password, row[1], row[2]):
                self.send_json({"sucesso": False, "erro": "Usuário ou senha incorretos."}, 401)
                return

            db_username = row[0]
            token = create_admin_session(db_username)

            is_https = (
                self.headers.get('X-Forwarded-Proto', '').lower() == 'https' or
                self.headers.get('X-Forwarded-Ssl', '').lower() == 'on'
            )
            secure_flag = "; Secure" if is_https else ""
            cookie_val = f"admin_token={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=86400{secure_flag}"

            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Set-Cookie', cookie_val)
            self.end_headers()
            self.wfile.write(json.dumps({
                "sucesso": True,
                "token": token,
                "username": db_username,
                "mensagem": "Login realizado com sucesso!"
            }, ensure_ascii=False).encode('utf-8'))
            return

        elif path == '/api/admin/logout':
            token = self.get_session_token()
            if token:
                delete_admin_session(token)
            is_https = (
                self.headers.get('X-Forwarded-Proto', '').lower() == 'https' or
                self.headers.get('X-Forwarded-Ssl', '').lower() == 'on'
            )
            secure_flag = "; Secure" if is_https else ""
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Set-Cookie', f'admin_token=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=0{secure_flag}')
            self.end_headers()
            self.wfile.write(json.dumps({"sucesso": True, "mensagem": "Logout efetuado com sucesso."}).encode('utf-8'))
            return

        elif path == '/api/admin/alterar-senha':
            self.send_json({"sucesso": False, "erro": "A alteração de senha via painel foi desativada por segurança. As credenciais são definidas exclusivamente através das Variáveis de Ambiente da Host."}, 403)
            return

        elif path == '/api/contato':
            nome = body_json.get('nome', '').strip()
            email = body_json.get('email', '').strip()
            telefone = body_json.get('telefone', '').strip()
            assunto = body_json.get('assunto', '').strip()
            mensagem = body_json.get('mensagem', '').strip()

            # 1. Validação do Nome (sem exigir sobrenome)
            if not nome or len(nome) < 2:
                self.send_json({"sucesso": False, "erro": "Por favor, informe seu nome (mínimo de 2 letras)."}, 400)
                return
            if re.search(r'\d', nome):
                self.send_json({"sucesso": False, "erro": "O nome não pode conter números."}, 400)
                return

            # 2. Validação do E-mail
            email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
            if not email or not re.match(email_regex, email) or '.' not in email.split('@')[-1]:
                self.send_json({"sucesso": False, "erro": "Por favor, informe um e-mail válido (exemplo: seu.nome@email.com)."}, 400)
                return

            # 3. Validação do Telefone / WhatsApp com DDD brasileiro
            nums = re.sub(r'\D', '', telefone)
            if nums.startswith('55') and len(nums) in (12, 13):
                nums = nums[2:]
            ddds_validos = {
                11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 24, 27, 28,
                31, 32, 33, 34, 35, 37, 38, 41, 42, 43, 44, 45, 46, 47, 48, 49,
                51, 53, 54, 55, 61, 62, 63, 64, 65, 66, 67, 68, 69, 71, 73, 74, 75, 77, 79,
                81, 82, 83, 84, 85, 86, 87, 88, 89, 91, 92, 93, 94, 95, 96, 97, 98, 99
            }
            if len(nums) not in (10, 11):
                self.send_json({"sucesso": False, "erro": "Informe um telefone/WhatsApp válido com DDD (10 ou 11 dígitos)."}, 400)
                return
            ddd = int(nums[:2])
            if ddd not in ddds_validos:
                self.send_json({"sucesso": False, "erro": f"O DDD ({ddd}) informado não é um DDD válido no Brasil."}, 400)
                return
            if len(nums) == 11 and nums[2] != '9':
                self.send_json({"sucesso": False, "erro": "Celulares com DDD no Brasil devem conter o 9 como primeiro dígito após o DDD."}, 400)
                return
            if len(set(nums[2:])) <= 1:
                self.send_json({"sucesso": False, "erro": "Por favor, informe um número de telefone real."}, 400)
                return

            # Formata o número antes de gravar
            if len(nums) == 11:
                telefone_formatado = f"({nums[:2]}) {nums[2:7]}-{nums[7:]}"
            else:
                telefone_formatado = f"({nums[:2]}) {nums[2:6]}-{nums[6:]}"

            # 4. Validação do Assunto
            if not assunto or len(assunto) < 3:
                self.send_json({"sucesso": False, "erro": "Por favor, informe o assunto da mensagem (mínimo de 3 caracteres)."}, 400)
                return

            # 5. Validação da Mensagem
            if not mensagem or len(mensagem) < 8:
                self.send_json({"sucesso": False, "erro": "Por favor, escreva sua mensagem (mínimo de 8 caracteres)."}, 400)
                return

            try:
                data_envio = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO contatos (nome, email, telefone, assunto, mensagem, data_envio)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (nome, email, telefone_formatado, assunto, mensagem, data_envio))
                    novo_id = cursor.lastrowid

                    # Salva também no HISTÓRICO PERMANENTE PERPÉTUO (nunca se perde)
                    cursor.execute("""
                        INSERT OR IGNORE INTO historico_contatos (original_id, nome, email, telefone, assunto, mensagem, data_envio, status_admin)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 'Ativo')
                    """, (novo_id, nome, email, telefone_formatado, assunto, mensagem, data_envio))
                    conn.commit()

                # Sincroniza em background sem prender a conexão ou bloquear a resposta do formulário
                disparar_salvar_banco_nuvem_async()

                self.send_json({
                    "sucesso": True,
                    "mensagem": "Sua mensagem foi recebida com sucesso! Nossa equipe entrará em contato em breve."
                })
            except Exception as e:
                self.send_json({"sucesso": False, "erro": f"Erro ao salvar: {str(e)}"}, 500)
            return

        elif path == '/api/voluntario':
            nome = body_json.get('nome', '').strip()
            email = body_json.get('email', '').strip()
            whatsapp = body_json.get('whatsapp', '').strip()
            area_interesse = body_json.get('area_interesse', '').strip()
            disponibilidade = body_json.get('disponibilidade', '').strip()
            experiencia = body_json.get('experiencia', '').strip()

            # 1. Validação do Nome (sem exigir sobrenome)
            if not nome or len(nome) < 2:
                self.send_json({"sucesso": False, "erro": "Por favor, informe seu nome (mínimo de 2 letras)."}, 400)
                return
            if re.search(r'\d', nome):
                self.send_json({"sucesso": False, "erro": "O nome não pode conter números."}, 400)
                return

            # 2. Validação do E-mail
            email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
            if not email or not re.match(email_regex, email) or '.' not in email.split('@')[-1]:
                self.send_json({"sucesso": False, "erro": "Por favor, informe um e-mail válido (exemplo: seu.nome@email.com)."}, 400)
                return

            # 3. Validação do WhatsApp / Celular com DDD brasileiro
            nums = re.sub(r'\D', '', whatsapp)
            if nums.startswith('55') and len(nums) in (12, 13):
                nums = nums[2:]
            ddds_validos = {
                11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 24, 27, 28,
                31, 32, 33, 34, 35, 37, 38, 41, 42, 43, 44, 45, 46, 47, 48, 49,
                51, 53, 54, 55, 61, 62, 63, 64, 65, 66, 67, 68, 69, 71, 73, 74, 75, 77, 79,
                81, 82, 83, 84, 85, 86, 87, 88, 89, 91, 92, 93, 94, 95, 96, 97, 98, 99
            }
            if len(nums) not in (10, 11):
                self.send_json({"sucesso": False, "erro": "Informe um telefone/WhatsApp válido com DDD (10 ou 11 dígitos)."}, 400)
                return
            ddd = int(nums[:2])
            if ddd not in ddds_validos:
                self.send_json({"sucesso": False, "erro": f"O DDD ({ddd}) informado não é um DDD válido no Brasil."}, 400)
                return
            if len(nums) == 11 and nums[2] != '9':
                self.send_json({"sucesso": False, "erro": "Celulares com DDD no Brasil devem conter o 9 como primeiro dígito após o DDD."}, 400)
                return
            if len(set(nums[2:])) <= 1:
                self.send_json({"sucesso": False, "erro": "Por favor, informe um número de WhatsApp real."}, 400)
                return

            # Formata o número antes de gravar
            if len(nums) == 11:
                whatsapp_formatado = f"({nums[:2]}) {nums[2:7]}-{nums[7:]}"
            else:
                whatsapp_formatado = f"({nums[:2]}) {nums[2:6]}-{nums[6:]}"

            # 4. Validação da Área de Atuação
            if not area_interesse or len(area_interesse) < 3:
                self.send_json({"sucesso": False, "erro": "Por favor, selecione uma área de atuação de interesse."}, 400)
                return

            # 5. Validação da Disponibilidade
            if not disponibilidade or len(disponibilidade) < 3:
                self.send_json({"sucesso": False, "erro": "Por favor, informe seus dias ou períodos de disponibilidade."}, 400)
                return

            # 6. Validação da Mensagem de Motivação/Experiência
            if not experiencia or len(experiencia) < 8:
                self.send_json({"sucesso": False, "erro": "Por favor, conte um pouco sobre sua motivação ou profissão (mínimo de 8 caracteres)."}, 400)
                return

            try:
                data_envio = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO voluntarios (nome, email, whatsapp, area_interesse, disponibilidade, experiencia, data_envio)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (nome, email, whatsapp_formatado, area_interesse, disponibilidade, experiencia, data_envio))
                    novo_v_id = cursor.lastrowid

                    # Salva também no HISTÓRICO PERMANENTE PERPÉTUO (nunca se perde)
                    cursor.execute("""
                        INSERT OR IGNORE INTO historico_voluntarios (original_id, nome, email, whatsapp, area_interesse, disponibilidade, experiencia, data_envio, status, status_admin)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Pendente', 'Ativo')
                    """, (novo_v_id, nome, email, whatsapp_formatado, area_interesse, disponibilidade, experiencia, data_envio))
                    conn.commit()

                # Sincroniza em background sem prender a conexão ou bloquear a resposta do formulário
                disparar_salvar_banco_nuvem_async()

                self.send_json({
                    "sucesso": True,
                    "mensagem": "Inscrição de voluntariado recebida com alegria! Entraremos em contato via WhatsApp/E-mail."
                })
            except Exception as e:
                self.send_json({"sucesso": False, "erro": f"Erro ao salvar: {str(e)}"}, 500)
            return

        elif path == '/api/voluntario/excluir':
            if not self.is_authenticated():
                self.send_json({"sucesso": False, "erro": "Acesso não autorizado. Faça login como administrador."}, 401)
                return
            vol_id = body_json.get('id')
            if vol_id is None or vol_id == '':
                self.send_json({"sucesso": False, "erro": "ID do voluntário não informado."}, 400)
                return
            try:
                vol_id = int(vol_id)
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT id, nome, email, data_envio FROM voluntarios WHERE id = ?", (vol_id,))
                    v_row = cursor.fetchone()
                    
                    # Remove da lista ativa da caixa de entrada
                    cursor.execute("DELETE FROM voluntarios WHERE id = ?", (vol_id,))

                    # NO HISTÓRICO PERMANENTE NA NUVEM: NUNCA APAGA! Marca como arquivado
                    data_exclusao = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    if v_row:
                        cursor.execute("""
                            UPDATE historico_voluntarios 
                            SET status_admin = 'Arquivado do Painel', apagado_em = ?
                            WHERE original_id = ? OR (nome = ? AND email = ? AND data_envio = ?)
                        """, (data_exclusao, vol_id, v_row[1], v_row[2], v_row[3]))
                    else:
                        cursor.execute("""
                            UPDATE historico_voluntarios 
                            SET status_admin = 'Arquivado do Painel', apagado_em = ?
                            WHERE original_id = ?
                        """, (data_exclusao, vol_id))

                    conn.commit()
                disparar_salvar_banco_nuvem_async()
                self.send_json({
                    "sucesso": True, 
                    "mensagem": "Inscrição removida da caixa de entrada. O registro histórico permanece salvo com segurança na nuvem!"
                })
            except Exception as e:
                self.send_json({"sucesso": False, "erro": f"Erro ao excluir: {str(e)}"}, 500)
            return

        elif path == '/api/contato/excluir':
            if not self.is_authenticated():
                self.send_json({"sucesso": False, "erro": "Acesso não autorizado. Faça login como administrador."}, 401)
                return
            contato_id = body_json.get('id')
            if contato_id is None or contato_id == '':
                self.send_json({"sucesso": False, "erro": "ID da mensagem não informado."}, 400)
                return
            try:
                contato_id = int(contato_id)
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT id, nome, email, data_envio FROM contatos WHERE id = ?", (contato_id,))
                    c_row = cursor.fetchone()

                    # Remove da lista ativa da caixa de entrada
                    cursor.execute("DELETE FROM contatos WHERE id = ?", (contato_id,))

                    # NO HISTÓRICO PERMANENTE NA NUVEM: NUNCA APAGA! Marca como arquivado
                    data_exclusao = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    if c_row:
                        cursor.execute("""
                            UPDATE historico_contatos 
                            SET status_admin = 'Arquivado do Painel', apagado_em = ?
                            WHERE original_id = ? OR (nome = ? AND email = ? AND data_envio = ?)
                        """, (data_exclusao, contato_id, c_row[1], c_row[2], c_row[3]))
                    else:
                        cursor.execute("""
                            UPDATE historico_contatos 
                            SET status_admin = 'Arquivado do Painel', apagado_em = ?
                            WHERE original_id = ?
                        """, (data_exclusao, contato_id))

                    conn.commit()
                disparar_salvar_banco_nuvem_async()
                self.send_json({
                    "sucesso": True, 
                    "mensagem": "Mensagem removida da caixa de entrada. O registro histórico permanece salvo com segurança na nuvem!"
                })
            except Exception as e:
                self.send_json({"sucesso": False, "erro": f"Erro ao excluir: {str(e)}"}, 500)
            return

        elif path == '/api/config':
            if not self.is_authenticated():
                self.send_json({"sucesso": False, "erro": "Acesso não autorizado. Faça login como administrador."}, 401)
                return
            # Atualiza o config.json com novas informações passadas pelo painel administrativo
            try:
                if not body_json or not isinstance(body_json, dict):
                    self.send_json({"sucesso": False, "erro": "Dados inválidos."}, 400)
                    return

                # Lê a configuração anterior para identificar mídias substituídas ou deletadas
                config_anterior = None
                if os.path.exists(CONFIG_FILE):
                    try:
                        with open(CONFIG_FILE, 'r', encoding='utf-8') as f_orig:
                            config_anterior = json.load(f_orig)
                    except Exception:
                        config_anterior = None

                # Salva backup antes de sobrescrever
                backup_file = os.path.join(DATA_DIR, "config.backup.json")
                if config_anterior:
                    with open(backup_file, 'w', encoding='utf-8') as f_bkp:
                        json.dump(config_anterior, f_bkp, ensure_ascii=False, indent=2)

                body_json['_atualizado_em'] = datetime.now().isoformat()

                # Gravação atômica em disco para proteção contra reinicialização abrupta
                tmp_cfg = CONFIG_FILE + ".tmp"
                with open(tmp_cfg, 'w', encoding='utf-8') as f:
                    json.dump(body_json, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_cfg, CONFIG_FILE)

                # Salva snapshot na tabela SQLite historico_config
                try:
                    with get_db() as conn:
                        conn.execute(
                            "INSERT INTO historico_config (data_salvamento, config_json) VALUES (?, ?)",
                            (datetime.now().strftime("%d/%m/%Y %H:%M:%S"), json.dumps(body_json, ensure_ascii=False))
                        )
                        conn.commit()
                except Exception as e_hist:
                    print(f"[AVISO] Falha ao registrar historico_config no SQLite: {e_hist}")

                # Salva na nuvem permanente para nunca perder alterações em reinicializações do Render
                nuvem_salva = salvar_config_nuvem(body_json)

                # Executa faxina automática de mídias desvinculadas ou órfãs
                resultado_faxina = executar_faxina_midia(novo_config=body_json, config_anterior=config_anterior)

                self.send_json({
                    "sucesso": True,
                    "nuvem_sincronizada": nuvem_salva,
                    "faxina": resultado_faxina,
                    "mensagem": "Configurações do site salvas com sucesso! Mídias não utilizadas foram limpas automaticamente."
                })
            except Exception as e:
                self.send_json({"sucesso": False, "erro": f"Erro ao salvar configurações: {str(e)}"}, 500)
            return

        elif path == '/api/admin/limpar-midia':
            if not self.is_authenticated():
                self.send_json({"sucesso": False, "erro": "Acesso não autorizado. Faça login como administrador."}, 401)
                return
            try:
                resultado_faxina = executar_faxina_midia()
                total = resultado_faxina["total_removidos"]
                kb = round(resultado_faxina["bytes_liberados"] / 1024, 1)
                if total > 0:
                    msg = f"Faxina concluída com sucesso! {total} arquivo(s) não utilizado(s) foram apagados ({kb} KB liberados)."
                else:
                    msg = "Nenhum arquivo órfão encontrado. Todas as fotos e documentos estão em uso no site!"

                self.send_json({
                    "sucesso": True,
                    "mensagem": msg,
                    "total_removidos": total,
                    "bytes_liberados": resultado_faxina["bytes_liberados"],
                    "arquivos_removidos": resultado_faxina["removidos"]
                })
            except Exception as e:
                self.send_json({"sucesso": False, "erro": f"Erro ao executar faxina: {str(e)}"}, 500)
            return

        elif path == '/api/upload':
            if not self.is_authenticated():
                self.send_json({"sucesso": False, "erro": "Acesso não autorizado. Faça login como administrador."}, 401)
                return

            nome_arquivo = body_json.get('nome_arquivo', '').strip()
            conteudo_b64 = body_json.get('conteudo_b64', '').strip()
            tipo = body_json.get('tipo', 'documento').strip().lower()

            if not nome_arquivo or not conteudo_b64:
                self.send_json({"sucesso": False, "erro": "Arquivo ou conteúdo não fornecido."}, 400)
                return

            # Remove prefixo data URI se presente (ex.: data:application/pdf;base64,....)
            if ',' in conteudo_b64 and 'base64' in conteudo_b64.split(',', 1)[0]:
                conteudo_b64 = conteudo_b64.split(',', 1)[1]

            # Sanitização e validação da extensão
            _, ext = os.path.splitext(nome_arquivo.lower())
            extensoes_permitidas_docs = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.odt', '.ods', '.txt', '.csv'}
            extensoes_permitidas_imgs = {'.png', '.jpg', '.jpeg', '.webp', '.svg', '.gif'}
            todas_extensoes_permitidas = extensoes_permitidas_docs | extensoes_permitidas_imgs

            if ext not in todas_extensoes_permitidas:
                self.send_json({
                    "sucesso": False,
                    "erro": f"Extensão '{ext}' não permitida. Envie arquivos PDF, documentos ou imagens."
                }, 400)
                return

            # Sanitiza nome do arquivo
            base_nome = os.path.splitext(os.path.basename(nome_arquivo))[0]
            base_nome = re.sub(r'[^a-zA-Z0-9_\-]', '_', base_nome)
            if not base_nome:
                base_nome = "arquivo"

            # Gera sufixo único com timestamp para não sobrescrever arquivos antigos
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nome_limpo = f"{base_nome}_{timestamp}{ext}"

            # Determina pasta de destino e URL pública
            if ext in extensoes_permitidas_imgs or tipo == 'imagem':
                destino_dir = IMG_DIR
                url_publica = f"/assets/img/{nome_limpo}"
            else:
                destino_dir = DOCS_DIR
                url_publica = f"/docs/{nome_limpo}"

            try:
                dados_binarios = base64.b64decode(conteudo_b64)
            except Exception as e:
                self.send_json({"sucesso": False, "erro": f"Falha ao decodificar arquivo base64: {str(e)}"}, 400)
                return

            # Limite de tamanho (25 MB)
            if len(dados_binarios) > 25 * 1024 * 1024:
                self.send_json({"sucesso": False, "erro": "Arquivo muito grande. O limite máximo é de 25MB."}, 400)
                return

            caminho_final = os.path.join(destino_dir, nome_limpo)
            try:
                # 1. Salva cópia local no disco como garantia e backup
                with open(caminho_final, 'wb') as f:
                    f.write(dados_binarios)

                # 2. Tenta enviar para a nuvem permanente (para nunca sumir quando o Render reiniciar)
                mime_tipo = mimetypes.guess_type(nome_limpo)[0] or 'application/octet-stream'
                url_nuvem = enviar_para_nuvem_permanente(dados_binarios, nome_limpo, mime_tipo)

                if url_nuvem:
                    url_retorno = url_nuvem
                    armazenamento = "cloud_permanente"
                    msg_sucesso = "Arquivo enviado e hospedado na nuvem permanente com sucesso!"
                else:
                    url_retorno = url_publica
                    armazenamento = "local"
                    msg_sucesso = "Arquivo salvo no servidor local com sucesso!"

                self.send_json({
                    "sucesso": True,
                    "mensagem": msg_sucesso,
                    "url": url_retorno,
                    "nome_arquivo": nome_limpo,
                    "armazenamento": armazenamento,
                    "tamanho_bytes": len(dados_binarios)
                })
            except Exception as e:
                self.send_json({"sucesso": False, "erro": f"Erro ao processar arquivo: {str(e)}"}, 500)
            return

        self.send_json({"sucesso": False, "erro": "Rota POST não encontrada"}, 404)

def run_server(port=8000):
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

    server_address = ('', port)
    httpd = ThreadingHTTPServer(server_address, ONGRequestHandler)

    local_ip = "localhost"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    print("=" * 65)
    print(f"  [OK] Servidor da ONG / Projeto Social iniciado com sucesso!")
    print(f"  -> Landing Page no Computador: http://localhost:{port}")
    print(f"  -> Painel de Edição no Computador: http://localhost:{port}/admin")
    if local_ip != "localhost":
        print(f"  -> Acesso no Celular (mesmo Wi-Fi): http://{local_ip}:{port}/login")
    print(f"  -> Arquivo de dados: {CONFIG_FILE}")
    print("=" * 65)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado pelo usuario.")
        httpd.server_close()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    run_server(port)