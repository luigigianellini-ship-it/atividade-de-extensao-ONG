#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
import sqlite3
import mimetypes
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Caminhos base
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
DB_FILE = os.path.join(DATA_DIR, "ong.db")

# Garante diretórios
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(PUBLIC_DIR, exist_ok=True)

def get_db_connection():
    conn = sqlite3.connect(DB_FILE, timeout=10.0)
    return conn

# Inicializa banco de dados SQLite com suporte otimizado a concorrencia
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Modo WAL permite leituras e gravacoes simultaneas sem travamento
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA busy_timeout = 5000;")
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
    conn.commit()
    conn.close()

init_db()

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

        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Erro ao carregar arquivo: {str(e)}".encode('utf-8'))

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # Rotas da Landing Page e Painel Admin
        if path == '/' or path == '/index.html':
            self.send_file(os.path.join(PUBLIC_DIR, 'index.html'))
            return
        elif path == '/admin' or path == '/admin.html':
            self.send_file(os.path.join(PUBLIC_DIR, 'admin.html'))
            return

        # Rotas de API
        if path == '/api/config':
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                self.send_json(config_data)
            except Exception as e:
                self.send_json({"erro": f"Falha ao carregar configuracoes: {str(e)}"}, 500)
            return

        elif path == '/api/stats':
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM contatos")
                total_contatos = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM voluntarios")
                total_voluntarios = cursor.fetchone()[0]
                conn.close()
                self.send_json({
                    "sucesso": True,
                    "total_contatos": total_contatos,
                    "total_voluntarios": total_voluntarios
                })
            except Exception as e:
                self.send_json({"erro": str(e)}, 500)
            return

        elif path == '/api/mensagens':
            try:
                conn = get_db_connection()
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM contatos ORDER BY id DESC LIMIT 100")
                rows = [dict(r) for r in cursor.fetchall()]
                conn.close()
                self.send_json(rows)
            except Exception as e:
                self.send_json({"erro": str(e)}, 500)
            return

        elif path == '/api/voluntarios':
            try:
                conn = get_db_connection()
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM voluntarios ORDER BY id DESC LIMIT 100")
                rows = [dict(r) for r in cursor.fetchall()]
                conn.close()
                self.send_json(rows)
            except Exception as e:
                self.send_json({"erro": str(e)}, 500)
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

        if path == '/api/contato':
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
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO contatos (nome, email, telefone, assunto, mensagem, data_envio)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (nome, email, telefone_formatado, assunto, mensagem, data_envio))
                conn.commit()
                conn.close()

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
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO voluntarios (nome, email, whatsapp, area_interesse, disponibilidade, experiencia, data_envio)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (nome, email, whatsapp_formatado, area_interesse, disponibilidade, experiencia, data_envio))
                conn.commit()
                conn.close()

                self.send_json({
                    "sucesso": True,
                    "mensagem": "Inscrição de voluntariado recebida com alegria! Entraremos em contato via WhatsApp/E-mail."
                })
            except Exception as e:
                self.send_json({"sucesso": False, "erro": f"Erro ao salvar: {str(e)}"}, 500)
            return

        elif path == '/api/voluntario/excluir':
            vol_id = body_json.get('id')
            if not vol_id:
                self.send_json({"sucesso": False, "erro": "ID do voluntário não informado."}, 400)
                return
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM voluntarios WHERE id = ?", (vol_id,))
                conn.commit()
                conn.close()
                self.send_json({"sucesso": True, "mensagem": "Inscrição de voluntário apagada com sucesso!"})
            except Exception as e:
                self.send_json({"sucesso": False, "erro": f"Erro ao excluir: {str(e)}"}, 500)
            return

        elif path == '/api/contato/excluir':
            contato_id = body_json.get('id')
            if not contato_id:
                self.send_json({"sucesso": False, "erro": "ID da mensagem não informado."}, 400)
                return
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM contatos WHERE id = ?", (contato_id,))
                conn.commit()
                conn.close()
                self.send_json({"sucesso": True, "mensagem": "Mensagem de contato apagada com sucesso!"})
            except Exception as e:
                self.send_json({"sucesso": False, "erro": f"Erro ao excluir: {str(e)}"}, 500)
            return

        elif path == '/api/config':
            # Atualiza o config.json com novas informações passadas pelo painel administrativo
            try:
                if not body_json or not isinstance(body_json, dict):
                    self.send_json({"sucesso": False, "erro": "Dados inválidos."}, 400)
                    return

                # Salva backup antes de sobrescrever
                backup_file = os.path.join(DATA_DIR, "config.backup.json")
                if os.path.exists(CONFIG_FILE):
                    with open(CONFIG_FILE, 'r', encoding='utf-8') as f_orig:
                        with open(backup_file, 'w', encoding='utf-8') as f_bkp:
                            f_bkp.write(f_orig.read())

                with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                    json.dump(body_json, f, ensure_ascii=False, indent=2)

                self.send_json({
                    "sucesso": True,
                    "mensagem": "Configurações do site salvas com sucesso!"
                })
            except Exception as e:
                self.send_json({"sucesso": False, "erro": f"Erro ao salvar configurações: {str(e)}"}, 500)
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
    httpd = HTTPServer(server_address, ONGRequestHandler)
    print("=" * 65)
    print(f"  [OK] Servidor da ONG / Projeto Social iniciado com sucesso!")
    print(f"  -> Landing Page: http://localhost:{port}")
    print(f"  -> Painel de Edicao (Admin): http://localhost:{port}/admin")
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
