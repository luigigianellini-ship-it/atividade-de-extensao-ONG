# 🌱 Landing Page Completa para ONG / Projeto Social

Landing Page profissional, responsiva, moderna e acolhedora, desenvolvida sob medida para ONGs, coletivos comunitários e projetos sociais.

---

## 📋 Estrutura Completa das 8 Seções

1. **Página Inicial Clara (Hero)**:
   - Frase curta e marcante explicando o que faz e para quem.
   - Foto real e expressiva do trabalho em andamento.
   - 3 botões de ação de alto contraste: **"Doe Agora"**, **"Seja Voluntário"** e **"Fale Conosco"**.
   - Barra superior com alerta para campanhas urgentes (ex.: Volta às Aulas, Inverno Solidário).

2. **Quem Somos**:
   - História real da fundação e motivação da organização.
   - Missão, Visão e Valores fundamentais em cards destacados.
   - Equipe e fundadores com fotos, nomes e minibiografias para gerar máxima credibilidade.

3. **O Que Fazemos**:
   - Descrição das atividades, oficinas e programas regulares (Educação, Esporte, Artes, Nutrição, Jovens).
   - Público atendido (crianças, adolescentes e famílias vulneráveis).
   - Região de atuação e polos comunitários.

4. **Impacto e Resultados**:
   - Números e contadores auditados (Crianças atendidas, Refeições servidas, Oficinas realizadas, Famílias apoiadas).
   - Depoimentos reais de mães, alunos e voluntários com indicação de autorização de imagem.
   - Galeria de fotos com visualizador Lightbox ao clicar.

5. **Como Ajudar**:
   - **Doações Financeiras**: Chave PIX oficial com botão "Copiar Chave", QR Code automático, valores sugeridos rápidos (R$ 30, R$ 60, R$ 120, R$ 250) e dados para transferência bancária.
   - **Voluntariado**: Formulário com seleção de áreas de interesse e disponibilidade de horários.
   - **Doação de Itens**: Tabela de necessidades atuais com status de urgência (alimentos, material escolar, higiene).
   - **Parcerias com Empresas**: Seção focada em diretrizes ESG e leis de incentivo fiscal.

6. **Transparência**:
   - Gráfico de distribuição de recursos (*Para onde vai o dinheiro arrecadado?*).
   - Links para download dos Relatórios Anuais de Atividades e DREs.
   - Documentos oficiais (CNPJ ativo, Estatuto Social registrado, Certidão de OSC, Utilidade Pública).

7. **Contato**:
   - Endereço completo com ponto de referência.
   - Telefone e link direto para WhatsApp (`wa.me`).
   - E-mails institucionais e horário de funcionamento.
   - Links para redes sociais (Instagram, Facebook, YouTube, LinkedIn).
   - Mapa interativo do Google Maps.
   - Formulário de contato funcional conectado à API Python.

8. **Notícias ou Blog**:
   - Cards com eventos, conquistas e campanhas ativas para mostrar que o projeto está vivo e atuante.
   - Leitura completa de artigos em modal integrado.

---

## 🚀 Como Executar o Projeto

### Opção 1: No Windows (Mais Fácil)
Dê um duplo clique no arquivo:
```cmd
iniciar.bat
```
O script detectará o Python instalado no sistema, iniciará o servidor e abrirá o navegador automaticamente em `http://localhost:8000`.

### Opção 2: Linha de Comando (Qualquer Sistema Operacional)
Com o Python instalado, basta executar no terminal:
```bash
python server.py
```
*(Caso esteja usando o MSYS2 ou python específico, use o caminho do seu executável, ex.: `C:\msys64\ucrt64\bin\python.exe server.py`)*

Acesse no seu navegador:
- **Site Principal:** `http://localhost:8000`
- **Painel de Edição (Admin):** `http://localhost:8000/admin`

---

## 🔒 Segurança e Credenciais (GitHub / Produção)

O projeto usa **variáveis de ambiente** via arquivo `.env` para manter todas as senhas fora do GitHub:

1. O arquivo `.env` está registrado no `.gitignore` e **nunca é enviado para o repositório**.
2. O banco de dados SQLite (`data/ong.db`) com as mensagens e voluntários também está protegido pelo `.gitignore`.
3. Para definir seu usuário e senha no servidor ou host:
   - Copie o arquivo `.env.example` para `.env`:
     ```bash
     cp .env.example .env
     ```
   - Edite o `.env` com a sua senha desejada:
     ```env
     ADMIN_USER=admin
     ADMIN_PASSWORD=sua_senha_secreta_aqui
     PORT=8000
     ```
   - O servidor lerá automaticamente as credenciais ao iniciar!

---

## ✏️ Como Colocar as Informações Corretas

Você tem **duas formas super fáceis** de atualizar os textos, fotos e dados do site:

### 1. Pelo Painel de Edição Visual no Navegador (Recomendado)
1. Com o servidor rodando, abra: `http://localhost:8000/admin` (ou clique no link "Editar Informações" no rodapé do site).
2. Você verá abas intuitivas organizadas exatamente pelas seções do site:
   - Altere o nome da ONG, a frase de impacto e a foto do Hero.
   - Atualize a Chave PIX, o Favorecido e os dados bancários.
   - Altere os números de impacto (quantas pessoas foram atendidas).
   - Atualize endereço, WhatsApp, redes sociais e história.
   - Visualize na aba **"Mensagens & Voluntários"** todos os contatos e inscrições recebidos pelo site!
3. Clique em **"Salvar Alterações"** no topo direito. Pronto! O site é atualizado instantaneamente.

### 2. Editando o Arquivo `data/config.json`
Se preferir editar diretamente no código, abra o arquivo:
```
data/config.json
```
Todos os textos, links, imagens e configurações estão organizados em formato JSON legível e bem estruturado. Quando salvar o arquivo, basta recarregar a página no navegador.

---

## 🛠️ Tecnologias Utilizadas

- **Backend:** Python 3 (usa a biblioteca padrão `http.server`, `sqlite3`, `json` - **sem dependências externas**, funciona imediatamente em qualquer máquina sem precisar de `pip install`).
- **Banco de Dados:** SQLite nativo (`data/ong.db`) para armazenar com segurança mensagens de contato e inscrições de voluntários.
- **Frontend:** HTML5 semântico, Tailwind CSS (via CDN), Ícones Lucide, JavaScript ES6 puro, Design 100% Responsivo.
