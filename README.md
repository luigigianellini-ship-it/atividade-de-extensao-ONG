# 🌸 Spa Glow Party — Non-Profit Landing Page & Management System

Professional, responsive, modern, and welcoming Landing Page and Web Application developed for **Spa Glow Party** — a social transformation project founded by Rayane Gomes in partnership with Instituto Rainhas da Favela and the Pink Squad (*Esquadrão Rosa*).

---

## 📋 Comprehensive 8-Section Structure

1. **Impactful Hero Section**:
   - Compelling core message highlighting social inclusion and self-esteem through beauty.
   - Real high-resolution photography and video player modal for action and event highlights.
   - Quick action buttons: **"Donate Now"** (Pix & bank transfer), **"Join the Pink Squad"** (volunteer enrollment), and **"Watch Video"**.
   - Campaign banner for urgent community drives and workshops.

2. **About Us (*Quem Somos*)**:
   - Official foundation history (Founded on July 15, 2025).
   - Core Mission, Vision, and Values in highlighted cards.
   - Team & Leadership section featuring Rayane Gomes, Pink Squad (*Esquadrão Rosa*), and Instituto Rainhas da Favela with biographies and official portraits.

3. **What We Do (*O Que Fazemos*)**:
   - Core programs: Professional Beauty Training, Self-Care & Well-being Workshops, Human & Emotional Support, and Community Solidary Wardrobe (*Varal Solidário*).
   - Target audience: vulnerable women, young adults, and families.
   - Regional operations in Uberaba/MG and community hubs.

4. **Impact & Results (*Impacto e Resultados*)**:
   - Dynamic metrics and statistics counters.
   - Interactive video testimonials from students and participants with an integrated modal player.
   - Filterable multimedia gallery (Beauty, Training, Community, Events & Videos) with Lightbox viewer.

5. **How to Help (*Como Ajudar*)**:
   - **Financial Donations**: Official Pix key with one-click copy, automated QR Code, dynamic donation values (R$ 30, R$ 60, R$ 120, R$ 250) linked directly to supplies (brushes, makeup kits, mobile content kits), and bank transfer details.
   - **Volunteer Program (Pink Squad)**: Integrated application card and official Google Forms modal.
   - **Item Donation Wishlist**: Real-time urgent needs table (cosmetics, hair care, hygiene items, clothes).
   - **Corporate Partnerships**: ESG-aligned initiatives and CSR sponsorship options.

6. **Transparency & Governance (*Transparência*)**:
   - Transparent resource allocation breakdown chart.
   - Downloadable official activity reports and partnership agreements (e.g., Casa de Sopa Adolfo Fritz).
   - Legal documents and public utility verification.

7. **Contact & Location (*Contato*)**:
   - Complete physical address and operational information.
   - Direct WhatsApp integration (`wa.me`) and official communication channels.
   - Interactive Google Maps embed.
   - Validated contact form with database persistence and real-time validation.

8. **News & Blog (*Notícias & Blog*)**:
   - Dynamic cards showcasing recent graduations, volunteer events, and community updates.
   - Full article reader modal.

---

## 🚀 How to Run the Project Locally

### Option 1: On Windows (Quick Launch)
Double-click the startup script:
```cmd
iniciar.bat
```
The script detects your local Python installation, starts the HTTP/API server, and automatically launches the website at `http://localhost:8000`.

### Option 2: Command Line (Any Operating System)
With Python 3 installed, run:
```bash
python server.py
```
*(If using MSYS2 or a custom Python path: `C:\msys64\ucrt64\bin\python.exe server.py`)*

Access in your browser:
- **Public Website:** `http://localhost:8000`
- **Admin Control Panel:** `http://localhost:8000/admin`
- **Admin Login:** `http://localhost:8000/login`

---

## 🔒 Security & Environment Configuration

The application uses **environment variables** via a `.env` file to ensure credentials and secret keys are never committed to version control:

1. The `.env` file is listed in `.gitignore` and **never pushed to GitHub**.
2. The SQLite database (`data/ong.db`) is also protected from public repository commits.
3. Configure your production/host variables:
   - Copy `.env.example` to `.env`:
     ```bash
     cp .env.example .env
     ```
   - Customize your environment settings:
     ```env
     ADMIN_USER=admin
     ADMIN_PASSWORD=your_secure_password_here
     PORT=8000
     KVDB_BUCKET_URL=https://kvdb.io/CRiiwUrgTkUsVqFprcTA67/site_config
     KVDB_DB_BACKUP_URL=https://kvdb.io/CRiiwUrgTkUsVqFprcTA67/site_db_backup
     KVDB_HISTORICO_URL=https://kvdb.io/CRiiwUrgTkUsVqFprcTA67/site_db_historico
     ```
   - If no password is provided on startup, a secure temporary access key is generated in the server console.

---

## ✏️ Content Management & Cloud Persistence

You can update site copy, images, Pix keys, and suggested donation values through two convenient methods:

### 1. Web-based Visual Admin Dashboard (Recommended)
1. With the server running, navigate to: `http://localhost:8000/admin` (or click "Painel Admin" in the footer/header).
2. Authenticate with your administrator credentials.
3. Enjoy an intuitive interface with organized tabs corresponding to each website section:
   - Edit project details, slogan, foundation date, and Hero media.
   - Adjust Pix keys, banking information, and suggested donation items.
   - Update impact numbers, news articles, and gallery entries.
   - Review and manage incoming contact messages and volunteer applications in **"Mensagens & Voluntários"**.
   - Use the **"Exportar JSON"** button to download a local backup of `config.json` at any time.
4. Click **"Salvar Alterações"**. The changes sync immediately to both local disk and persistent cloud storage.

### 2. Editing `data/config.json` Directly
If you prefer managing configurations in code:
```
data/config.json
```
All texts, media URLs, links, and parameters are structured in clean, human-readable JSON. Refresh the browser page to see changes.

### ☁️ Resilient Cloud Persistence
- **Bidirectional Cloud Sync**: Content edited in the Admin panel is synced to persistent KVDB storage.
- **Deploy Protection**: Ephemeral containers (such as Render or cloud hosts) automatically restore all Admin configurations and database history upon redeployment, preventing any data loss.
- **Atomic File Writing**: All updates to `config.json` use `.tmp` swap with `os.fsync()` to prevent corruption during sudden server restarts.

---

## 🛠️ Tech Stack

- **Backend:** Python 3 standard library (`http.server`, `sqlite3`, `urllib`, `ssl`, `json`, `threading`) — **zero external dependencies required**, runs anywhere without `pip install`.
- **Database:** SQLite with WAL mode (*Write-Ahead Logging*), 30s busy timeout, and perpetual cloud sync for contacts and volunteers.
- **Cloud Storage:** Integrated with persistent KVDB cloud endpoints and automatic media management.
- **Frontend:** Semantic HTML5, Tailwind CSS (via CDN), Lucide Icons, vanilla ES6+ JavaScript, 100% Mobile-First Responsive Design.
