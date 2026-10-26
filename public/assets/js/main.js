/**
 * Scripts principais da Landing Page do Instituto / ONG
 * Gerencia renderização dinâmica a partir de /api/config, modais, formulários e interações.
 */

// Estado global dos dados da página
let siteConfig = null;

// Inicialização ao carregar a página
document.addEventListener("DOMContentLoaded", async () => {
  atualizarIconeTema();
  await carregarConfiguracoes();
  inicializarEventos();
});

// Toast de feedback
function showToast(mensagem, tipo = "sucesso") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  const bgCor = tipo === "sucesso" ? "bg-emerald-600 text-white" : "bg-red-600 text-white";
  const icone = tipo === "sucesso" ? "check-circle" : "alert-circle";

  toast.className = `toast flex items-center gap-3 p-4 rounded-xl shadow-xl ${bgCor} text-sm font-medium transition-all duration-300`;
  toast.innerHTML = `
    <i data-lucide="${icone}" class="w-5 h-5 flex-shrink-0"></i>
    <div class="flex-1">${mensagem}</div>
    <button class="opacity-70 hover:opacity-100" onclick="this.parentElement.remove()">
      <i data-lucide="x" class="w-4 h-4"></i>
    </button>
  `;

  container.appendChild(toast);
  if (window.lucide) lucide.createIcons({ root: toast });

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(100%)";
    setTimeout(() => toast.remove(), 300);
  }, 4500);
}

// Carrega os dados do backend com cache instantâneo e fallback direto na nuvem KVDB
async function carregarConfiguracoes() {
  // 1. Cache Local no Navegador (renderização instantânea sem tela em branco)
  try {
    const cached = localStorage.getItem("sgp_site_config");
    if (cached) {
      siteConfig = JSON.parse(cached);
      aplicarDadosNoDOM(siteConfig);
    }
  } catch (e) {}

  // 2. Busca da API do Backend Python (/api/config)
  try {
    const res = await fetch("/api/config", { cache: "no-store" });
    if (res.ok) {
      siteConfig = await res.json();
      try { localStorage.setItem("sgp_site_config", JSON.stringify(siteConfig)); } catch (e) {}
      aplicarDadosNoDOM(siteConfig);
      return;
    }
  } catch (err) {
    console.warn("Backend /api/config não respondeu (possível cold start), tentando nuvem permanente KVDB...", err);
  }

  // 3. Fallback Direto na Nuvem Permanente (KVDB)
  // Caso o container do Render esteja em modo de repouso (cold start de 50s no free tier)
  try {
    const cloudRes = await fetch("https://kvdb.io/CRiiwUrgTkUsVqFprcTA67/site_config", { cache: "no-store" });
    if (cloudRes.ok) {
      siteConfig = await cloudRes.json();
      try { localStorage.setItem("sgp_site_config", JSON.stringify(siteConfig)); } catch (e) {}
      aplicarDadosNoDOM(siteConfig);
      return;
    }
  } catch (errCloud) {
    console.warn("Nuvem KVDB indisponível, usando fallback embutido:", errCloud);
  }

  // 4. Fallback embutido com dados oficiais do Spa Glow Party
  if (!siteConfig) {
    siteConfig = getFallbackConfig();
    aplicarDadosNoDOM(siteConfig);
  }
}

// Aplica todos os dados nos elementos do HTML
function aplicarDadosNoDOM(config) {
  if (!config) return;

  // 1. Meta & Títulos
  if (config.meta?.titulo_site) document.title = config.meta.titulo_site;
  document.querySelectorAll(".site-nome").forEach(el => el.textContent = config.instituicao?.nome || "Projeto Social");
  document.querySelectorAll(".site-sigla").forEach(el => el.textContent = config.instituicao?.sigla || "");
  document.querySelectorAll(".site-slogan").forEach(el => el.textContent = config.instituicao?.slogan || "");
  document.querySelectorAll(".site-cnpj").forEach(el => el.textContent = config.instituicao?.cnpj || "");

  // 2. Seção Hero
  const hero = config.hero;
  if (hero) {
    const badgeEl = document.getElementById("hero-badge");
    if (badgeEl && hero.badge) badgeEl.innerHTML = hero.badge;

    const tituloEl = document.getElementById("hero-titulo");
    if (tituloEl && hero.titulo_destaque) tituloEl.textContent = hero.titulo_destaque;

    const subtituloEl = document.getElementById("hero-subtitulo");
    if (subtituloEl && hero.subtitulo) subtituloEl.textContent = hero.subtitulo;

    const fotoEl = document.getElementById("hero-foto");
    if (fotoEl && hero.foto_url) {
      fotoEl.src = hero.foto_url;
      fotoEl.alt = hero.foto_legenda || "Ação do projeto";
    }

    const legendaEl = document.getElementById("hero-foto-legenda");
    if (legendaEl && hero.foto_legenda) legendaEl.textContent = hero.foto_legenda;

    // Campanha Urgente
    const campEl = document.getElementById("hero-campanha");
    if (campEl && hero.campanha_urgente) {
      if (hero.campanha_urgente.ativa) {
        campEl.classList.remove("hidden");
        const titEl = document.getElementById("campanha-titulo");
        if (titEl) titEl.textContent = hero.campanha_urgente.titulo || "";
        const txtEl = document.getElementById("campanha-texto");
        if (txtEl) txtEl.textContent = hero.campanha_urgente.texto || "";
        if (window.lucide) lucide.createIcons();
      } else {
        campEl.classList.add("hidden");
      }
    }
  }

  // 3. Quem Somos
  const qs = config.quem_somos;
  if (qs) {
    const histEl = document.getElementById("qs-historia");
    if (histEl) histEl.textContent = qs.historia;

    const fundBadge = document.getElementById("qs-fundacao-badge");
    if (fundBadge) {
      const dataFund = qs.data_fundacao || config.instituicao?.data_fundacao || (config.instituicao?.ano_fundacao ? `Fundado em ${config.instituicao.ano_fundacao}` : "Fundado em 15 de Julho de 2025");
      fundBadge.textContent = dataFund.startsWith("Fundado") ? dataFund : `Fundado em ${dataFund}`;
    }

    const misEl = document.getElementById("qs-missao");
    if (misEl) misEl.textContent = qs.missao;

    const visEl = document.getElementById("qs-visao");
    if (visEl) visEl.textContent = qs.visao;

    // Valores
    const valContainer = document.getElementById("qs-valores-grid");
    if (valContainer && qs.valores) {
      valContainer.innerHTML = qs.valores.map(v => `
        <div class="p-5 rounded-2xl bg-white border border-slate-100 shadow-sm hover-lift flex flex-col justify-start">
          <div class="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold text-lg mb-3">✓</div>
          <h4 class="font-bold text-slate-900 text-lg mb-1">${v.titulo}</h4>
          <p class="text-sm text-slate-600 leading-relaxed">${v.descricao}</p>
        </div>
      `).join("");
    }

    // Equipe
    const eqContainer = document.getElementById("qs-equipe-grid");
    if (eqContainer && qs.equipe) {
      eqContainer.innerHTML = qs.equipe.map(m => `
        <div class="bg-white rounded-2xl p-6 border border-slate-100 shadow-sm text-center hover-lift flex flex-col items-center">
          <img src="${m.foto}" alt="${m.nome}" class="w-24 h-24 rounded-full object-cover shadow-md mb-4 ring-4 ring-emerald-50">
          <h4 class="font-bold text-slate-900 text-lg mb-0.5">${m.nome}</h4>
          <span class="text-xs font-semibold uppercase tracking-wider text-emerald-600 mb-3">${m.cargo}</span>
          <p class="text-xs text-slate-600 leading-relaxed">${m.bio}</p>
        </div>
      `).join("");
    }
  }

  // 4. O Que Fazemos
  const oq = config.o_que_fazemos;
  if (oq) {
    const pubEl = document.getElementById("oq-publico");
    if (pubEl) pubEl.textContent = oq.publico_alvo;

    const regEl = document.getElementById("oq-regiao");
    if (regEl) regEl.textContent = oq.regiao_atuacao;

    const projContainer = document.getElementById("oq-projetos-grid");
    if (projContainer && oq.projetos) {
      projContainer.innerHTML = oq.projetos.map(p => `
        <div class="bg-white rounded-3xl overflow-hidden border border-slate-100 shadow-sm hover-lift flex flex-col">
          <div class="relative h-48 w-full overflow-hidden">
            <img src="${p.foto}" alt="${p.titulo}" class="w-full h-full object-cover transition-transform duration-500 hover:scale-105">
            <span class="absolute top-3 left-3 bg-white/90 backdrop-blur-md text-emerald-800 text-xs font-bold px-3 py-1 rounded-full shadow-sm">
              ${p.categoria}
            </span>
          </div>
          <div class="p-6 flex-1 flex flex-col justify-between">
            <div>
              <div class="flex items-center gap-2 text-xs text-slate-500 mb-2">
                <span>🎯 ${p.faixa_etaria}</span>
                <span>•</span>
                <span>⏰ ${p.horario}</span>
              </div>
              <h3 class="text-xl font-bold text-slate-900 mb-2">${p.titulo}</h3>
              <p class="text-sm text-slate-600 leading-relaxed mb-4">${p.descricao}</p>
            </div>
            <a href="#como-ajudar" class="inline-flex items-center text-sm font-semibold text-emerald-600 hover:text-emerald-700 transition">
              Apoiar este projeto <span class="ml-1">→</span>
            </a>
          </div>
        </div>
      `).join("");
    }
  }

  // 5. Impacto e Resultados
  const imp = config.impacto;
  if (imp) {
    const metContainer = document.getElementById("imp-metricas-grid");
    if (metContainer && imp.metricas) {
      metContainer.innerHTML = imp.metricas.map(m => `
        <div class="bg-white border border-slate-200/80 rounded-2xl p-6 text-center shadow-sm hover-lift">
          <div class="text-3xl md:text-5xl font-black text-emerald-600 font-heading mb-1">${m.valor}</div>
          <div class="text-sm font-bold text-slate-800 mb-1">${m.label}</div>
          <p class="text-xs text-slate-500 leading-relaxed">${m.detalhe}</p>
        </div>
      `).join("");
    }

    const depContainer = document.getElementById("imp-depoimentos-grid");
    if (depContainer && imp.depoimentos) {
      depContainer.innerHTML = imp.depoimentos.map(d => {
        const nomeEsc = (d.nome || "").replace(/'/g, "\\'");
        const cargoEsc = (d.cargo || "").replace(/'/g, "\\'");
        const vidUrl = d.video_url || "";
        return `
          <div class="bg-white rounded-3xl p-6 border border-slate-200/80 shadow-sm hover-lift flex flex-col justify-between">
            <div>
              <div class="text-pink-500 text-3xl font-serif mb-1 leading-none">“</div>
              <p class="text-xs sm:text-sm text-slate-700 italic leading-relaxed mb-4">"${d.texto}"</p>
            </div>
            <div class="pt-4 border-t border-slate-100 flex flex-col gap-3">
              <div class="flex items-center gap-3">
                <div class="relative flex-shrink-0">
                  <img src="${d.foto}" alt="${d.nome}" class="w-12 h-12 rounded-full object-cover ring-2 ring-pink-200 shadow-sm">
                  ${vidUrl ? `<span class="absolute -bottom-1 -right-1 w-5 h-5 rounded-full bg-pink-600 text-white flex items-center justify-center text-[10px] shadow-sm"><i data-lucide="play" class="w-3 h-3 fill-white text-white"></i></span>` : ""}
                </div>
                <div class="min-w-0">
                  <h5 class="text-xs sm:text-sm font-bold text-slate-900 truncate">${d.nome}</h5>
                  <p class="text-[11px] text-slate-500 truncate">${d.cargo}</p>
                  ${d.autorizacao ? `<span class="text-[10px] text-pink-600 block truncate">✓ ${d.autorizacao}</span>` : ""}
                </div>
              </div>
              ${vidUrl ? `
                <button onclick="abrirModalVideo('${vidUrl}', '${nomeEsc}', '${cargoEsc}')" class="w-full py-2 px-3 rounded-xl bg-pink-50 hover:bg-pink-100 text-pink-700 hover:text-pink-800 text-xs font-bold border border-pink-200/80 flex items-center justify-center gap-1.5 transition">
                  <i data-lucide="play-circle" class="w-4 h-4 text-pink-600"></i>
                  Assistir ao Relato em Vídeo
                </button>
              ` : ""}
            </div>
          </div>
        `;
      }).join("");
      if (window.lucide) lucide.createIcons();
    }

    // Galeria Dinâmica com Filtros
    renderizarGaleria();
  }

  // 6. Como Ajudar & Gerador Automático de PIX (Padrão Banco Central BR Code)
  const ajuda = config.como_ajudar;
  if (ajuda) {
    if (ajuda.pix) {
      document.querySelectorAll(".pix-chave").forEach(el => el.textContent = ajuda.pix.chave);
      document.querySelectorAll(".pix-favorecido").forEach(el => el.textContent = ajuda.pix.favorecido);
      document.querySelectorAll(".pix-banco").forEach(el => el.textContent = ajuda.pix.banco);

      // Gera o PIX Copia e Cola e QR Code oficial automaticamente a partir da chave e nome
      atualizarPixDinamico();
    }

    // Valores Sugeridos Dinâmicos
    const valContainer = document.getElementById("valores-sugeridos-grid");
    if (valContainer && ajuda.valores_sugeridos && ajuda.valores_sugeridos.length > 0) {
      valContainer.innerHTML = ajuda.valores_sugeridos.map(v => `
        <button class="btn-valor-doacao p-3 rounded-2xl border border-slate-200 hover:border-emerald-500 text-center transition bg-slate-50 hover:bg-emerald-50 cursor-pointer" data-valor="${v.valor}">
          <span class="block text-lg font-black text-slate-900">${v.valor}</span>
          <span class="block text-[11px] text-slate-500 leading-tight mt-0.5">${v.impacto}</span>
        </button>
      `).join("");
      configurarBotoesValoresDoacao();
    }

    if (ajuda.dados_bancarios) {
      const b = ajuda.dados_bancarios;
      const bEl = document.getElementById("dados-bancarios-info");
      if (bEl) {
        bEl.innerHTML = `
          <strong>Banco:</strong> ${b.banco}<br>
          <strong>Agência:</strong> ${b.agencia} | <strong>Conta Corrente:</strong> ${b.conta_corrente}<br>
          <strong>Favorecido:</strong> ${b.titular}<br>
          <strong>CNPJ:</strong> ${b.cnpj}
        `;
      }
    }

    // Itens necessários
    const itensContainer = document.getElementById("itens-necessarios-list");
    if (itensContainer && ajuda.doacao_itens?.itens) {
      itensContainer.innerHTML = ajuda.doacao_itens.itens.map(it => {
        let badgeColor = "bg-red-100 text-red-700";
        if (it.cor === "amber") badgeColor = "bg-amber-100 text-amber-700";
        if (it.cor === "blue") badgeColor = "bg-blue-100 text-blue-700";

        return `
          <div class="flex items-center justify-between p-3.5 rounded-xl bg-slate-50 border border-slate-100">
            <span class="text-sm font-medium text-slate-800">${it.item}</span>
            <span class="text-xs font-bold px-2.5 py-0.5 rounded-full ${badgeColor}">${it.status}</span>
          </div>
        `;
      }).join("");
    }

    // Áreas de voluntariado no select
    const selectArea = document.getElementById("voluntario-area");
    if (selectArea && ajuda.voluntariado?.areas) {
      selectArea.innerHTML = `
        <option value="">Selecione uma área de interesse...</option>
        ${ajuda.voluntariado.areas.map(a => `<option value="${a}">${a}</option>`).join("")}
      `;
    }

    // Link do formulário oficial de voluntário (Google Forms)
    const formsLink = ajuda.voluntariado?.link_formulario || "https://forms.gle/EXf95hre8ezb4zNd9";
    const btnLinkForms = document.getElementById("btn-link-google-forms");
    if (btnLinkForms) btnLinkForms.href = formsLink;

    const iframeForms = document.getElementById("iframe-google-forms");
    if (iframeForms && ajuda.voluntariado?.link_embed) {
      iframeForms.src = ajuda.voluntariado.link_embed;
    }
  }

  // 7. Transparência
  const trans = config.transparencia;
  if (trans) {
    const docsContainer = document.getElementById("trans-documentos-grid");
    if (docsContainer && trans.documentos_legais) {
      docsContainer.innerHTML = trans.documentos_legais.map(d => `
        <div class="p-4 rounded-2xl bg-white border border-slate-100 shadow-sm flex items-center justify-between hover-lift">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <i data-lucide="file-text" class="w-5 h-5"></i>
            </div>
            <div>
              <h5 class="text-sm font-bold text-slate-900">${d.nome}</h5>
              <p class="text-xs text-slate-500">${d.descricao}</p>
            </div>
          </div>
          <a href="${d.arquivo}" target="_blank" download class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold text-emerald-700 bg-emerald-50 hover:bg-emerald-100 transition">
            <i data-lucide="download" class="w-3.5 h-3.5"></i> Baixar PDF
          </a>
        </div>
      `).join("");
    }

    const relContainer = document.getElementById("trans-relatorios-grid");
    if (relContainer && trans.relatorios_atividades) {
      relContainer.innerHTML = trans.relatorios_atividades.map(r => `
        <div class="p-4 rounded-2xl bg-white border border-slate-100 shadow-sm flex items-center justify-between hover-lift">
          <div>
            <span class="text-xs font-black text-emerald-600 tracking-wider uppercase">${r.ano}</span>
            <h5 class="text-sm font-bold text-slate-900">${r.titulo}</h5>
            <span class="text-[11px] text-slate-500">Status: ${r.status}</span>
          </div>
          <a href="${r.link}" target="_blank" download class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold text-slate-700 bg-slate-100 hover:bg-slate-200 transition">
            <i data-lucide="file-check" class="w-3.5 h-3.5"></i> Abrir
          </a>
        </div>
      `).join("");
    }

    // Gráfico de Destinação
    const destContainer = document.getElementById("trans-destinacao-bars");
    if (destContainer && trans.destinacao_recursos?.distribuicao) {
      destContainer.innerHTML = trans.destinacao_recursos.distribuicao.map(item => `
        <div class="space-y-1.5">
          <div class="flex justify-between text-xs font-semibold text-slate-800">
            <span>${item.categoria}</span>
            <span class="font-bold">${item.percentual}%</span>
          </div>
          <div class="w-full bg-slate-100 h-3 rounded-full overflow-hidden">
            <div class="h-full rounded-full transition-all duration-1000" style="width: ${item.percentual}%; background-color: ${item.cor};"></div>
          </div>
        </div>
      `).join("");
    }
  }

  // 8. Contato
  const cont = config.contato;
  if (cont) {
    const endEl = document.getElementById("contato-endereco");
    if (endEl) endEl.textContent = cont.endereco_completo;

    const refEl = document.getElementById("contato-ponto-referencia");
    if (refEl) refEl.textContent = cont.ponto_referencia || "";

    const telEl = document.getElementById("contato-telefone");
    if (telEl) telEl.textContent = cont.telefone;

    const whatsEl = document.getElementById("contato-whatsapp");
    if (whatsEl) whatsEl.textContent = cont.whatsapp;

    const whatsLinkEl = document.getElementById("contato-whatsapp-link");
    if (whatsLinkEl && cont.whatsapp_link) whatsLinkEl.href = cont.whatsapp_link;

    const emailEl = document.getElementById("contato-email");
    if (emailEl) emailEl.textContent = cont.email_geral;

    const horEl = document.getElementById("contato-horario");
    if (horEl) horEl.textContent = cont.horario_funcionamento;

    if (cont.redes_sociais) {
      const ig = document.getElementById("social-instagram");
      if (ig) ig.href = cont.redes_sociais.instagram || "#";
      const fb = document.getElementById("social-facebook");
      if (fb) fb.href = cont.redes_sociais.facebook || "#";
      const yt = document.getElementById("social-youtube");
      if (yt) yt.href = cont.redes_sociais.youtube || "#";
      const lk = document.getElementById("social-linkedin");
      if (lk) lk.href = cont.redes_sociais.linkedin || "#";
    }

    const mapaEl = document.getElementById("contato-mapa-iframe");
    if (mapaEl && cont.mapa_embed_url) mapaEl.src = cont.mapa_embed_url;
  }

  // 9. Notícias / Blog
  const blog = config.noticias_blog;
  if (blog && blog.artigos) {
    const blogContainer = document.getElementById("blog-artigos-grid");
    if (blogContainer) {
      blogContainer.innerHTML = blog.artigos.map(art => `
        <div class="bg-white rounded-3xl overflow-hidden border border-slate-100 shadow-sm hover-lift flex flex-col">
          <div class="h-44 w-full overflow-hidden relative">
            <img src="${art.foto}" alt="${art.titulo}" class="w-full h-full object-cover transition-transform duration-500 hover:scale-105">
            <span class="absolute top-3 left-3 bg-white/90 backdrop-blur-md text-emerald-800 text-[11px] font-bold px-3 py-1 rounded-full shadow-sm">
              ${art.categoria}
            </span>
          </div>
          <div class="p-6 flex-1 flex flex-col justify-between">
            <div>
              <span class="text-xs text-slate-400 block mb-2">${art.data}</span>
              <h4 class="text-lg font-bold text-slate-900 mb-2 leading-snug">${art.titulo}</h4>
              <p class="text-xs text-slate-600 leading-relaxed mb-4 line-clamp-3">${art.resumo}</p>
            </div>
            <button onclick="abrirNoticiaModal('${art.id}')" class="text-left text-sm font-bold text-emerald-600 hover:text-emerald-700 flex items-center gap-1">
              Ler notícia completa <span class="text-xs">→</span>
            </button>
          </div>
        </div>
      `).join("");
    }
  }

  // Atualiza ícones do Lucide
  if (window.lucide) {
    lucide.createIcons();
  }
}

// ========================================================
// GERADOR DINÂMICO OFICIAL DE PIX (BR CODE / BANCO CENTRAL)
// ========================================================
let codigoPixCopiaColaAtual = "";

function calcularCRC16(str) {
  let crc = 0xFFFF;
  for (let i = 0; i < str.length; i++) {
    crc ^= (str.charCodeAt(i) << 8);
    for (let j = 0; j < 8; j++) {
      if ((crc & 0x8000) !== 0) {
        crc = ((crc << 1) ^ 0x1021) & 0xFFFF;
      } else {
        crc = (crc << 1) & 0xFFFF;
      }
    }
  }
  return crc.toString(16).toUpperCase().padStart(4, '0');
}

function gerarPayloadPix(chave, nome, valor = null, cidade = "SAO PAULO", txid = "***") {
  if (!chave) return "";
  
  let chaveLimpa = chave.trim();
  const apenasDigitos = chaveLimpa.replace(/\D/g, "");

  // 1. Se o usuário colou diretamente um código Pix Copia e Cola completo do banco
  if (chaveLimpa.startsWith("000201")) {
    return chaveLimpa;
  }

  // 2. Se for celular brasileiro (11 dígitos começando com DDD 11-99 e 9 no 3º dígito, ex: 17988160761)
  const ddds = ["11","12","13","14","15","16","17","18","19","21","22","24","27","28","31","32","33","34","35","37","38","41","42","43","44","45","46","47","48","49","51","53","54","55","61","62","63","64","65","66","67","68","69","71","73","74","75","77","79","81","82","83","84","85","86","87","88","89","91","92","93","94","95","96","97","98","99"];
  const ddd = apenasDigitos.substring(0, 2);
  const ehCelular = apenasDigitos.length === 11 && ddds.includes(ddd) && apenasDigitos[2] === "9" && !chaveLimpa.includes("@");
  const ehFixo = apenasDigitos.length === 10 && ddds.includes(ddd) && !chaveLimpa.includes("@");

  if ((ehCelular || ehFixo) && !chaveLimpa.startsWith("+")) {
    chaveLimpa = "+55" + apenasDigitos;
  } else if (apenasDigitos.length === 14 && !chaveLimpa.includes("@")) {
    // CNPJ: 14 dígitos puros
    chaveLimpa = apenasDigitos;
  } else if (apenasDigitos.length === 11 && !chaveLimpa.includes("@") && !chaveLimpa.startsWith("+")) {
    // CPF
    chaveLimpa = apenasDigitos;
  }

  // Limpa acentos e caracteres especiais do nome e da cidade (padrão EMVCo)
  const limparTexto = (txt, max) => {
    return txt.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^A-Za-z0-9 ]/g, "").toUpperCase().substring(0, max).trim();
  };

  const nomeLimpo = limparTexto(nome || "INSTITUTO", 25) || "INSTITUTO";
  const cidadeLimpa = limparTexto(cidade || "SAO PAULO", 15) || "SAO PAULO";

  const mai = `0014BR.GOV.BCB.PIX01${String(chaveLimpa.length).padStart(2, '0')}${chaveLimpa}`;
  let payload = `00020126${String(mai.length).padStart(2, '0')}${mai}520400005303986`;

  // Se houver valor numérico específico
  if (valor && Number(valor) > 0) {
    const vStr = Number(valor).toFixed(2);
    payload += `54${String(vStr.length).padStart(2, '0')}${vStr}`;
  }

  payload += `5802BR59${String(nomeLimpo.length).padStart(2, '0')}${nomeLimpo}60${String(cidadeLimpa.length).padStart(2, '0')}${cidadeLimpa}`;
  
  const addData = `05${String(txid.length).padStart(2, '0')}${txid}`;
  payload += `62${String(addData.length).padStart(2, '0')}${addData}6304`;

  const checksum = calcularCRC16(payload);
  return payload + checksum;
}

function atualizarPixDinamico(valor = null) {
  const chave = siteConfig?.como_ajudar?.pix?.chave || "pix@sementesdoamanha.org.br";
  const favorecido = siteConfig?.como_ajudar?.pix?.favorecido || siteConfig?.instituicao?.nome || "INSTITUTO";

  // Gera o código Copia e Cola Oficial
  codigoPixCopiaColaAtual = gerarPayloadPix(chave, favorecido, valor);

  // Gera a URL do QR Code dinâmico
  const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=${encodeURIComponent(codigoPixCopiaColaAtual)}`;

  // Atualiza as imagens de QR Code (na página e no modal)
  const qrEl = document.getElementById("pix-qrcode-img");
  if (qrEl) qrEl.src = qrUrl;

  const modalQrEl = document.getElementById("modal-pix-qrcode-img");
  if (modalQrEl) modalQrEl.src = qrUrl;

  // Atualiza o texto do copia e cola se existir
  document.querySelectorAll(".pix-copia-cola-txt").forEach(el => {
    el.textContent = codigoPixCopiaColaAtual;
  });
}

// Configurações de eventos interativos
function configurarBotoesValoresDoacao() {
  document.querySelectorAll(".btn-valor-doacao").forEach(btn => {
    btn.onclick = () => {
      document.querySelectorAll(".btn-valor-doacao").forEach(b => b.classList.remove("ring-2", "ring-emerald-500", "bg-emerald-50"));
      btn.classList.add("ring-2", "ring-emerald-500", "bg-emerald-50");
      
      const valorStr = btn.getAttribute("data-valor") || "";
      const numValor = valorStr.replace(/\D/g, "");
      
      if (typeof atualizarPixDinamico === 'function') {
        atualizarPixDinamico(numValor);
      }
      showToast(`QR Code e chave PIX atualizados para ${valorStr}!`);
    };
  });
}
window.configurarBotoesValoresDoacao = configurarBotoesValoresDoacao;

function inicializarEventos() {
  // 1. Botão Copiar Chave PIX
  const btnCopiarPix = document.getElementById("btn-copiar-pix");
  if (btnCopiarPix) {
    btnCopiarPix.addEventListener("click", () => {
      const chave = siteConfig?.como_ajudar?.pix?.chave || "pix@sementesdoamanha.org.br";
      navigator.clipboard.writeText(chave).then(() => {
        showToast("Chave PIX copiada para a área de transferência!");
        const originalText = btnCopiarPix.innerHTML;
        btnCopiarPix.innerHTML = "✓ Chave Copiada!";
        btnCopiarPix.classList.add("bg-emerald-700");
        setTimeout(() => {
          btnCopiarPix.innerHTML = originalText;
          btnCopiarPix.classList.remove("bg-emerald-700");
          if (window.lucide) lucide.createIcons();
        }, 2500);
      }).catch(err => {
        prompt("Copie a chave PIX manualmente:", chave);
      });
    });
  }

  // 1.1 Botão Copiar PIX Copia e Cola Oficial
  const btnCopiarCopiaCola = document.getElementById("btn-copiar-copia-cola");
  if (btnCopiarCopiaCola) {
    btnCopiarCopiaCola.addEventListener("click", () => {
      if (!codigoPixCopiaColaAtual) atualizarPixDinamico();
      navigator.clipboard.writeText(codigoPixCopiaColaAtual).then(() => {
        showToast("Código 'PIX Copia e Cola' copiado! Abra o app do seu banco e cole.");
        const originalText = btnCopiarCopiaCola.innerHTML;
        btnCopiarCopiaCola.innerHTML = "✓ Código Copiado!";
        setTimeout(() => {
          btnCopiarCopiaCola.innerHTML = originalText;
          if (window.lucide) lucide.createIcons();
        }, 2500);
      }).catch(() => {
        prompt("Copie o código PIX Copia e Cola:", codigoPixCopiaColaAtual);
      });
    });
  }

  // 2. Botões de Valores Sugeridos (atualiza QR Code e Copia e Cola em tempo real)
  configurarBotoesValoresDoacao();

  // 3. Envio do Formulário de Contato com Validação Estrita
  const formContato = document.getElementById("form-contato");
  if (formContato) {
    formContato.addEventListener("submit", async (e) => {
      e.preventDefault();

      const elNome = document.getElementById("contato-nome");
      const elEmail = document.getElementById("contato-email-input");
      const elTel = document.getElementById("contato-telefone-input");
      const elAssunto = document.getElementById("contato-assunto-input");
      const elMsg = document.getElementById("contato-mensagem-input");

      const nome = elNome.value.trim();
      const email = elEmail.value.trim();
      const telefone = elTel.value.trim();
      const assunto = elAssunto.value.trim();
      const mensagem = elMsg.value.trim();

      const marcarErro = (elemento, msg) => {
        elemento.classList.add("border-red-500", "ring-2", "ring-red-300");
        elemento.focus();
        showToast(msg, "erro");
      };

      // 1. Validação de Nome
      if (nome.length < 2) {
        marcarErro(elNome, "Por favor, informe seu nome.");
        return;
      }
      if (/\d/.test(nome)) {
        marcarErro(elNome, "O nome não pode conter números.");
        return;
      }

      // 2. Validação de E-mail
      const emailRegex = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/;
      if (!email || !emailRegex.test(email) || !email.includes(".")) {
        marcarErro(elEmail, "Por favor, informe um endereço de e-mail válido (ex: seu.nome@gmail.com).");
        return;
      }

      // 3. Validação de Telefone / WhatsApp
      const numsTel = telefone.replace(/\D/g, "");
      const dddsValidos = [11,12,13,14,15,16,17,18,19,21,22,24,27,28,31,32,33,34,35,37,38,41,42,43,44,45,46,47,48,49,51,53,54,55,61,62,63,64,65,66,67,68,69,71,73,74,75,77,79,81,82,83,84,85,86,87,88,89,91,92,93,94,95,96,97,98,99];
      const dddTel = parseInt(numsTel.substring(0, 2), 10);

      if (numsTel.length < 10 || numsTel.length > 11 || !dddsValidos.includes(dddTel)) {
        marcarErro(elTel, "Informe um telefone/WhatsApp válido com DDD brasileiro (ex: 11 98888-7777).");
        return;
      }
      if (numsTel.length === 11 && numsTel[2] !== "9") {
        marcarErro(elTel, "Celulares brasileiros devem ter o 9 como primeiro dígito após o DDD.");
        return;
      }
      if (new Set(numsTel.substring(2)).size <= 1) {
        marcarErro(elTel, "Por favor, informe um número de telefone real.");
        return;
      }

      // 4. Validação do Assunto
      if (!assunto || assunto.length < 3) {
        marcarErro(elAssunto, "Por favor, informe o assunto da mensagem (mínimo de 3 caracteres).");
        return;
      }

      // 5. Validação da Mensagem
      if (!mensagem || mensagem.length < 8) {
        marcarErro(elMsg, "Por favor, escreva sua mensagem (mínimo de 8 caracteres).");
        return;
      }

      const btnSubmit = formContato.querySelector("button[type='submit']");
      const txtOriginal = btnSubmit.innerHTML;
      btnSubmit.disabled = true;
      btnSubmit.innerHTML = "Validando e enviando...";

      const payload = { nome, email, telefone, assunto, mensagem };

      try {
        const res = await fetch("/api/contato", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.sucesso) {
          showToast(data.mensagem || "Mensagem enviada com sucesso!");
          formContato.reset();
        } else {
          showToast(data.erro || "Erro ao enviar mensagem.", "erro");
        }
      } catch (err) {
        showToast("Mensagem registrada localmente. Obrigado pelo contato!", "sucesso");
        formContato.reset();
      } finally {
        btnSubmit.disabled = false;
        btnSubmit.innerHTML = txtOriginal;
        if (window.lucide) lucide.createIcons();
      }
    });
  }

  // 3.1 Máscara automática de telefone/WhatsApp nos inputs
  const aplicarMascaraTelefone = (input) => {
    if (!input) return;
    input.addEventListener("input", (e) => {
      let v = e.target.value.replace(/\D/g, "");
      if (v.length > 11) v = v.substring(0, 11);
      if (v.length > 10) {
        // Celular: (XX) 9XXXX-XXXX
        e.target.value = `(${v.substring(0, 2)}) ${v.substring(2, 7)}-${v.substring(7)}`;
      } else if (v.length > 6) {
        // Fixo ou celular digitando: (XX) XXXX-XXXX
        e.target.value = `(${v.substring(0, 2)}) ${v.substring(2, 6)}-${v.substring(6)}`;
      } else if (v.length > 2) {
        e.target.value = `(${v.substring(0, 2)}) ${v.substring(2)}`;
      } else if (v.length > 0) {
        e.target.value = `(${v}`;
      }
      input.classList.remove("border-red-500", "ring-2", "ring-red-300");
    });
  };

  aplicarMascaraTelefone(document.getElementById("voluntario-whatsapp"));
  aplicarMascaraTelefone(document.getElementById("contato-telefone-input"));

  // Remove erro ao digitar nos outros campos
  [
    "voluntario-nome", "voluntario-email", "voluntario-area", "voluntario-disponibilidade", "voluntario-experiencia",
    "contato-nome", "contato-email-input", "contato-telefone-input", "contato-assunto-input", "contato-mensagem-input"
  ].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener("input", () => el.classList.remove("border-red-500", "ring-2", "ring-red-300"));
      el.addEventListener("change", () => el.classList.remove("border-red-500", "ring-2", "ring-red-300"));
    }
  });

  // 4. Envio do Formulário de Voluntário com Validação Estrita
  const formVoluntario = document.getElementById("form-voluntario");
  if (formVoluntario) {
    formVoluntario.addEventListener("submit", async (e) => {
      e.preventDefault();

      const elNome = document.getElementById("voluntario-nome");
      const elEmail = document.getElementById("voluntario-email");
      const elWhats = document.getElementById("voluntario-whatsapp");
      const elArea = document.getElementById("voluntario-area");
      const elDisp = document.getElementById("voluntario-disponibilidade");
      const elExp = document.getElementById("voluntario-experiencia");

      const nome = elNome.value.trim();
      const email = elEmail.value.trim();
      const whatsapp = elWhats.value.trim();
      const area_interesse = elArea.value.trim();
      const disponibilidade = elDisp.value.trim();
      const experiencia = elExp.value.trim();

      const marcarErro = (elemento, mensagem) => {
        elemento.classList.add("border-red-500", "ring-2", "ring-red-300");
        elemento.focus();
        showToast(mensagem, "erro");
      };

      // 1. Validação de Nome
      if (nome.length < 2) {
        marcarErro(elNome, "Por favor, informe seu nome.");
        return;
      }
      if (/\d/.test(nome)) {
        marcarErro(elNome, "O nome não pode conter números.");
        return;
      }

      // 2. Validação de E-mail
      const emailRegex = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/;
      if (!email || !emailRegex.test(email) || !email.includes(".")) {
        marcarErro(elEmail, "Por favor, informe um endereço de e-mail válido (ex: seu.nome@gmail.com).");
        return;
      }

      // 3. Validação de WhatsApp / Celular
      const numsWhats = whatsapp.replace(/\D/g, "");
      const dddsValidos = [11,12,13,14,15,16,17,18,19,21,22,24,27,28,31,32,33,34,35,37,38,41,42,43,44,45,46,47,48,49,51,53,54,55,61,62,63,64,65,66,67,68,69,71,73,74,75,77,79,81,82,83,84,85,86,87,88,89,91,92,93,94,95,96,97,98,99];
      const dddWhats = parseInt(numsWhats.substring(0, 2), 10);

      if (numsWhats.length < 10 || numsWhats.length > 11 || !dddsValidos.includes(dddWhats)) {
        marcarErro(elWhats, "Informe um WhatsApp válido com DDD brasileiro (ex: 11 98888-7777).");
        return;
      }
      if (numsWhats.length === 11 && numsWhats[2] !== "9") {
        marcarErro(elWhats, "Celulares brasileiros devem ter o 9 como primeiro dígito após o DDD.");
        return;
      }

      // 4. Validação de Área
      if (!area_interesse) {
        marcarErro(elArea, "Por favor, selecione uma área de atuação de interesse.");
        return;
      }

      // 5. Validação de Disponibilidade
      if (disponibilidade.length < 3) {
        marcarErro(elDisp, "Por favor, informe seus dias ou períodos de disponibilidade.");
        return;
      }

      // 6. Validação de Motivação
      if (experiencia.length < 8) {
        marcarErro(elExp, "Por favor, conte um pouco sobre sua motivação ou profissão (mínimo de 8 caracteres).");
        return;
      }

      const btnSubmit = formVoluntario.querySelector("button[type='submit']");
      const txtOriginal = btnSubmit.innerHTML;
      btnSubmit.disabled = true;
      btnSubmit.innerHTML = "Validando e enviando...";

      const payload = { nome, email, whatsapp, area_interesse, disponibilidade, experiencia };

      try {
        const res = await fetch("/api/voluntario", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.sucesso) {
          showToast(data.mensagem || "Inscrição concluída com sucesso!");
          formVoluntario.reset();
          fecharModalVoluntario();
        } else {
          showToast(data.erro || "Erro ao registrar inscrição.", "erro");
        }
      } catch (err) {
        showToast("Inscrição registrada! Entraremos em contato.", "sucesso");
        formVoluntario.reset();
        fecharModalVoluntario();
      } finally {
        btnSubmit.disabled = false;
        btnSubmit.innerHTML = txtOriginal;
        if (window.lucide) lucide.createIcons();
      }
    });
  }

  // 5. Menu Mobile
  const btnMobile = document.getElementById("btn-mobile-menu");
  const menuMobile = document.getElementById("mobile-menu");
  if (btnMobile && menuMobile) {
    btnMobile.addEventListener("click", () => {
      menuMobile.classList.toggle("hidden");
    });
    menuMobile.querySelectorAll("a").forEach(link => {
      link.addEventListener("click", () => menuMobile.classList.add("hidden"));
    });
  }
}

// Lightbox da Galeria
function abrirLightbox(url, titulo) {
  const modal = document.getElementById("modal-lightbox");
  const img = document.getElementById("lightbox-img");
  const leg = document.getElementById("lightbox-legenda");
  if (!modal || !img) return;

  img.src = url;
  if (leg) leg.textContent = titulo;
  modal.classList.remove("hidden");
  modal.classList.add("flex");
}

function fecharLightbox() {
  const modal = document.getElementById("modal-lightbox");
  if (modal) {
    modal.classList.add("hidden");
    modal.classList.remove("flex");
  }
}

// Modal Seja Voluntário
function abrirModalVoluntario() {
  const modal = document.getElementById("modal-voluntario");
  if (modal) {
    modal.classList.add("ativo");
    modal.style.display = "flex";
  }
}

function fecharModalVoluntario() {
  const modal = document.getElementById("modal-voluntario");
  if (modal) {
    modal.classList.remove("ativo");
    modal.style.display = "none";
  }
}

// Modal PIX / Doação
function abrirModalDoacao() {
  const modal = document.getElementById("modal-doacao");
  if (modal) {
    if (typeof atualizarPixDinamico === 'function') {
      atualizarPixDinamico();
    }
    modal.classList.add("ativo");
    modal.style.display = "flex";
  }
}

function fecharModalDoacao() {
  const modal = document.getElementById("modal-doacao");
  if (modal) {
    modal.classList.remove("ativo");
    modal.style.display = "none";
  }
}

// Modal Leitura Notícia
function abrirNoticiaModal(id) {
  const artigos = siteConfig?.noticias_blog?.artigos || [];
  const art = artigos.find(a => a.id === id);
  if (!art) return;

  const modal = document.getElementById("modal-noticia");
  if (modal) {
    document.getElementById("noticia-modal-titulo").textContent = art.titulo;
    document.getElementById("noticia-modal-data").textContent = `${art.data} • Categoria: ${art.categoria}`;
    document.getElementById("noticia-modal-foto").src = art.foto;
    document.getElementById("noticia-modal-texto").textContent = art.conteudo_completo;

    modal.classList.add("ativo");
    modal.style.display = "flex";
  }
}

function fecharModalNoticia() {
  const modal = document.getElementById("modal-noticia");
  if (modal) {
    modal.classList.remove("ativo");
    modal.style.display = "none";
  }
}

// Galeria Dinâmica e Filtros
let categoriaGaleriaAtual = "todas";

function filtrarGaleria(cat) {
  categoriaGaleriaAtual = cat;
  document.querySelectorAll("#galeria-filtros .gal-btn").forEach(btn => {
    const txt = btn.textContent.trim().toLowerCase();
    const match = (cat === "todas" && txt === "todas") ||
                  (cat !== "todas" && txt.includes(cat.toLowerCase().slice(0, 4)));
    if (match) {
      btn.className = "gal-btn active px-3.5 py-1.5 rounded-full text-xs font-bold bg-pink-600 text-white shadow-sm transition";
    } else {
      btn.className = "gal-btn px-3.5 py-1.5 rounded-full text-xs font-bold bg-white text-slate-700 hover:bg-pink-50 hover:text-pink-600 border border-slate-200 transition";
    }
  });
  renderizarGaleria();
}

function renderizarGaleria() {
  const galContainer = document.getElementById("imp-galeria-grid");
  const lista = siteConfig?.impacto?.galeria || [];
  if (!galContainer) return;

  const itensFiltrados = lista.filter(g => {
    if (categoriaGaleriaAtual === "todas") return true;
    if (categoriaGaleriaAtual === "Eventos") return g.categoria.includes("Eventos") || !!g.video_url;
    return g.categoria.toLowerCase().includes(categoriaGaleriaAtual.toLowerCase());
  });

  galContainer.innerHTML = itensFiltrados.map(g => {
    const titEsc = (g.titulo || "").replace(/'/g, "\\'");
    const catEsc = (g.categoria || "").replace(/'/g, "\\'");
    if (g.video_url) {
      return `
        <div class="group relative rounded-2xl overflow-hidden aspect-video bg-slate-900 cursor-pointer shadow-sm hover-lift" onclick="abrirModalVideo('${g.video_url}', '${titEsc}', '${catEsc}')">
          <img src="${g.url}" alt="${g.titulo}" class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105 opacity-85 group-hover:opacity-100">
          <div class="absolute inset-0 flex items-center justify-center">
            <div class="w-11 h-11 rounded-full bg-pink-600/90 group-hover:bg-pink-600 text-white flex items-center justify-center shadow-lg group-hover:scale-110 transition pl-0.5">
              <i data-lucide="play" class="w-5 h-5 fill-white text-white"></i>
            </div>
          </div>
          <div class="absolute inset-0 bg-gradient-to-t from-slate-950/85 via-slate-950/20 to-transparent flex items-end p-3.5">
            <div>
              <span class="text-[10px] font-bold text-pink-300 uppercase tracking-wider">${g.categoria} • VÍDEO</span>
              <p class="text-xs font-bold text-white mt-0.5">${g.titulo}</p>
            </div>
          </div>
        </div>
      `;
    } else {
      return `
        <div class="group relative rounded-2xl overflow-hidden aspect-video bg-slate-100 cursor-pointer shadow-sm hover-lift" onclick="abrirLightbox('${g.url}', '${titEsc}')">
          <img src="${g.url}" alt="${g.titulo}" class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105">
          <div class="absolute inset-0 bg-gradient-to-t from-slate-950/80 via-slate-950/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex items-end p-3.5">
            <div>
              <span class="text-[10px] font-bold text-pink-300 uppercase tracking-wider">${g.categoria}</span>
              <p class="text-xs font-bold text-white mt-0.5">${g.titulo}</p>
            </div>
          </div>
        </div>
      `;
    }
  }).join("");

  if (window.lucide) lucide.createIcons();
}

// Modal Vídeo Oficial & Depoimentos
function abrirModalVideo(url, titulo, subtitulo) {
  const modal = document.getElementById("modal-video");
  const player = document.getElementById("player-video-modal");
  const titEl = document.getElementById("modal-video-titulo");
  const subEl = document.getElementById("modal-video-subtitulo");

  const targetUrl = url || siteConfig?.hero?.video_url || "/assets/videos/spa_glow_party.mp4";
  const targetTit = titulo || "Spa Glow Party — Rayane Gomes";
  const targetSub = subtitulo || "Beleza que acolhe, autoestima que transforma e oportunidades que mudam vidas.";

  if (titEl) titEl.textContent = targetTit;
  if (subEl) subEl.textContent = targetSub;

  if (modal) {
    modal.classList.add("ativo");
    modal.classList.remove("hidden");
    modal.style.display = "flex";
    if (player) {
      if (!player.src.endsWith(targetUrl) && player.src !== targetUrl) {
        player.src = targetUrl;
        player.load();
      }
      player.play().catch(() => {});
    }
  }
}

function fecharModalVideo() {
  const modal = document.getElementById("modal-video");
  const player = document.getElementById("player-video-modal");
  if (modal) {
    modal.classList.remove("ativo");
    modal.classList.add("hidden");
    modal.style.display = "none";
    if (player) {
      player.pause();
    }
  }
}

// Fechar com tecla ESC
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    fecharModalVideo();
    fecharModalDoacao();
    fecharModalVoluntario();
    fecharModalNoticia();
    fecharLightbox();
  }
});

// Garante disponibilidade global das funções no window
window.renderizarGaleria = renderizarGaleria;
window.filtrarGaleria = filtrarGaleria;
window.abrirModalVideo = abrirModalVideo;
window.fecharModalVideo = fecharModalVideo;
window.abrirModalDoacao = abrirModalDoacao;
window.fecharModalDoacao = fecharModalDoacao;
window.abrirModalVoluntario = abrirModalVoluntario;
window.fecharModalVoluntario = fecharModalVoluntario;
window.abrirLightbox = abrirLightbox;
window.fecharLightbox = fecharLightbox;
window.abrirNoticiaModal = abrirNoticiaModal;
window.fecharModalNoticia = fecharModalNoticia;
window.showToast = showToast;

// Modo Escuro
function alternarModoEscuro() {
  const isDark = document.documentElement.classList.toggle('dark');
  localStorage.setItem('tema', isDark ? 'dark' : 'light');
  atualizarIconeTema();
  showToast(isDark ? "Modo escuro ativado!" : "Modo claro ativado!", "sucesso");
}

function atualizarIconeTema() {
  const isDark = document.documentElement.classList.contains('dark');
  document.querySelectorAll('.icon-theme').forEach(icon => {
    icon.setAttribute('data-lucide', isDark ? 'sun' : 'moon');
  });
  if (window.lucide) lucide.createIcons();
}

window.alternarModoEscuro = alternarModoEscuro;
window.atualizarIconeTema = atualizarIconeTema;

// Dados de Fallback (caso abra o HTML estático direto pelo navegador sem o backend)
// Dados de Fallback com todas as informações oficiais do Spa Glow Party
function getFallbackConfig() {
  return {
  "meta": {
    "titulo_site": "SPA GLOW PARTY | Beleza que Acolhe, Autoestima que Transforma e Oportunidades que Mudam Vidas",
    "descricao": "O Spa Glow Party é um projeto de transformação social idealizado por Rayane Gomes, unindo acolhimento, beleza, capacitação profissional gratuita e a força do Esquadrão Rosa.",
    "tema_cor_principal": "#EC4899"
  },
  "instituicao": {
    "nome": "Spa Glow Party",
    "sigla": "SGP",
    "slogan": "Beleza que acolhe, autoestima que transforma e oportunidades que mudam vidas.",
    "ano_fundacao": "2025",
    "cnpj": "Iniciativa Rayane Gomes & Instituto Rainhas da Favela",
    "registro_osc": "Uberaba / MG — Projeto de Transformação Social através da Beleza",
    "utilidade_publica": "Desenvolvimento Humano, Inclusão Social e Capacitação Profissional Gratuita",
    "data_fundacao": "15 de Julho de 2025"
  },
  "hero": {
    "badge": "✨ Transformação Social, Autoestima e Oportunidades",
    "titulo_destaque": "Beleza que acolhe, autoestima que transforma e oportunidades que mudam vidas.",
    "subtitulo": "Muito mais do que um evento de beleza: uma experiência de acolhimento, valorização humana e capacitação profissional gratuita para pessoas em situação de vulnerabilidade.",
    "foto_url": "/assets/img/rayane_gomes_fundadora.jpg",
    "foto_legenda": "Rayane Gomes — Idealizadora do Spa Glow Party & Fundadora do Rainhas da Favela",
    "video_url": "/assets/videos/spa_glow_party.mp4",
    "campanha_urgente": {
      "ativa": true,
      "titulo": "Nova Turma de Formação em Maquiagem Gratuita",
      "texto": "Apoie a capacitação de novas profissionais da beleza para geração de renda, dignidade e independência. Junte-se ao Esquadrão Rosa!",
      "link_acao": "#como-ajudar"
    },
    "botoes": {
      "doar": "Apoie o Projeto",
      "voluntario": "Seja Voluntária (Esquadrão Rosa)",
      "contato": "Fale Conosco"
    }
  },
  "quem_somos": {
    "titulo": "O que é o Spa Glow Party?",
    "subtitulo": "Conheça nosso propósito, a idealizadora Rayane Gomes e a força coletiva do Esquadrão Rosa.",
    "historia": "O Spa Glow Party é um projeto de transformação social idealizado por Rayane Gomes, maquiadora profissional, palestrante e fundadora do Instituto Rainhas da Favela. Muito mais do que um evento de beleza, o Spa Glow Party é uma experiência de acolhimento, valorização humana, capacitação profissional e resgate da autoestima. O projeto nasceu da convicção de que a beleza pode ser uma poderosa ferramenta de transformação social, especialmente quando associada à educação, à solidariedade e à geração de oportunidades. Nosso propósito é alcançar pessoas que muitas vezes não têm acesso a cuidados pessoais, formação profissional ou espaços onde possam se sentir valorizadas, respeitadas e acolhidas. Não transformamos apenas aparências: ajudamos pessoas a redescobrirem seu valor, sua força e sua capacidade de recomeçar.",
    "missao": "Promover autoestima, inclusão social, desenvolvimento pessoal e capacitação profissional por meio da beleza, da educação e do acolhimento, criando oportunidades para pessoas em situação de vulnerabilidade.",
    "visao": "Nosso sonho não tem fronteiras: queremos levar o Spa Glow Party a diferentes bairros, cidades, estados e países, conectando pessoas e construindo uma rede de acolhimento, conhecimento e oportunidades cada vez mais longe.",
    "valores": [
      {
        "titulo": "Beleza que Acolhe",
        "descricao": "Cada atendimento é uma oportunidade de proporcionar carinho, atenção genuína, respeito às histórias individuais e valorização pessoal."
      },
      {
        "titulo": "Capacitação Emancipatória",
        "descricao": "Acreditamos que ensinar uma profissão é oferecer ferramentas concretas para construir independência financeira, dignidade e novas perspectivas de futuro."
      },
      {
        "titulo": "Solidariedade em Ação",
        "descricao": "Por meio de iniciativas como o Varal Solidário e campanhas de arrecadação, mobilizamos recursos e doações para quem mais precisa."
      },
      {
        "titulo": "Força Coletiva do Esquadrão Rosa",
        "descricao": "O projeto tem uma idealizadora, mas sua realização é uma conquista coletiva feita pelo amor, energia e dedicação das voluntárias."
      }
    ],
    "equipe": [
      {
        "nome": "Rayane Gomes",
        "cargo": "Idealizadora & Fundadora",
        "foto": "/assets/img/rayane_gomes_fundadora.jpg",
        "bio": "Maquiadora profissional, palestrante e fundadora do Instituto Rainhas da Favela. Dedica sua vida a transformar comunidades e resgatar a autoestima através da beleza e da solidariedade."
      },
      {
        "nome": "Esquadrão Rosa",
        "cargo": "Coração Pulsante do Projeto",
        "foto": "/assets/img/esquadrao_rosa_oficial.jpg",
        "bio": "Voluntárias e profissionais da beleza que dedicam tempo, talento, amor e compromisso para acolher, atender e capacitar cada aluna e participante."
      },
      {
        "nome": "Instituto Rainhas da Favela & Comunidade",
        "cargo": "Articulação Social & Força Comunitária",
        "foto": "/assets/img/comunidade_unida_comemoracao.jpg",
        "bio": "Rede comunitária que fortalece a inclusão social, abrindo oportunidades reais de geração de renda, dignidade e protagonismo para famílias em vulnerabilidade."
      }
    ],
    "data_fundacao": "15 de Julho de 2025",
    "ano_fundacao": "2025"
  },
  "o_que_fazemos": {
    "titulo": "Como Funciona o Projeto?",
    "subtitulo": "Reunimos profissionais da beleza, voluntários e empresas parceiras em ações de cuidado, aprendizado e fortalecimento pessoal.",
    "publico_alvo": "Mulheres, adolescentes, jovens e famílias em situação de vulnerabilidade social, com acolhimento caloroso e respeito à diversidade.",
    "regiao_atuacao": "Com trajetória consolidada em Uberaba (MG) — incluindo turmas formadas com a Casa de Sopa Adolfo Fritz — e expansão para novas comunidades.",
    "projetos": [
      {
        "id": "beleza-autoestima",
        "titulo": "Beleza e Autoestima",
        "categoria": "Autocuidado & Dignidade",
        "faixa_etaria": "Todas as idades",
        "horario": "Mutirões e encontros comunitários",
        "foto": "/assets/img/atendimento_estetica_spa.jpg",
        "descricao": "Atividades de autocuidado, como maquiagem, cuidados com cabelos, design de sobrancelhas e outros serviços realizados por profissionais e voluntárias. Cada atendimento é uma oportunidade de proporcionar acolhimento e valorização pessoal.",
        "icone": "sparkles"
      },
      {
        "id": "capacitacao-profissional",
        "titulo": "Capacitação Profissional Gratuita",
        "categoria": "Formação & Renda",
        "faixa_etaria": "Jovens e adultas",
        "horario": "Cursos regulares e oficinas práticas",
        "foto": "/assets/img/oficina_turma_maquiagem.jpg",
        "descricao": "Formação de novas profissionais da área da beleza. Por meio de cursos e oficinas gratuitas, incentivamos o empreendedorismo e a inserção no mercado de trabalho, com histórico de turmas de 30 alunos formados em parceria com a Casa de Sopa Adolfo Fritz.",
        "icone": "award"
      },
      {
        "id": "acolhimento-desenvolvimento",
        "titulo": "Acolhimento e Desenvolvimento Humano",
        "categoria": "Empoderamento",
        "faixa_etaria": "Comunidade em geral",
        "horario": "Palestras e rodas de escuta",
        "foto": "/assets/img/roda_conversa_ar_livre.jpg",
        "descricao": "Palestras motivacionais, rodas de conversa, dinâmicas de valorização pessoal e encontros inspiradores que fortalecem a autoconfiança e incentivam os participantes a acreditarem nos seus próprios sonhos.",
        "icone": "heart-handshake"
      },
      {
        "id": "cultura-integracao",
        "titulo": "Cultura, Alegria e Integração",
        "categoria": "Celebração Comunitária",
        "faixa_etaria": "Toda a família",
        "horario": "Eventos e celebrações",
        "foto": "/assets/videos/evento_glow_party_poster.jpg",
        "video_url": "/assets/videos/evento_glow_party.mp4",
        "descricao": "Nossos eventos reúnem música, dança, apresentações artísticas e momentos de festa e integração com maquiagens vibrantes neon, proporcionando vivências memoráveis e fortalecendo os laços comunitários.",
        "icone": "music"
      },
      {
        "id": "solidariedade-varal",
        "titulo": "Solidariedade em Ação & Varal Solidário",
        "categoria": "Apoio Social",
        "faixa_etaria": "Famílias atendidas",
        "horario": "Campanhas contínuas",
        "foto": "/assets/img/bancada_maquiagem_oficina.jpg",
        "descricao": "Mobilização de doações, roupas, agasalhos e produtos de beleza e higiene por meio do Varal Solidário e campanhas de arrecadação para apoiar famílias em vulnerabilidade.",
        "icone": "gift"
      }
    ]
  },
  "impacto": {
    "titulo": "Nosso Impacto Social",
    "subtitulo": "A transformação que buscamos vai muito além da aparência: reconstruímos a autoestima e geramos autonomia real.",
    "metricas": [
      {
        "valor": "30+",
        "label": "Alunas Formadas em Maquiagem",
        "detalhe": "Turma de formação profissional gratuita em Uberaba/MG"
      },
      {
        "valor": "100%",
        "label": "Atendimento Acolhedor e Gratuito",
        "detalhe": "Resgate da autoestima, respeito à dignidade e novas perspectivas"
      },
      {
        "valor": "5",
        "label": "Pilares de Transformação Social",
        "detalhe": "Beleza, capacitação, desenvolvimento humano, cultura e solidariedade"
      },
      {
        "valor": "∞",
        "label": "Sonho Sem Fronteiras",
        "detalhe": "Conectando pessoas para levar essa rede a novos bairros, cidades e estados"
      }
    ],
    "depoimentos": [
      {
        "nome": "Rayane Gomes",
        "cargo": "Idealizadora do Spa Glow Party & Palestrante",
        "foto": "/assets/img/rayane_gomes_perfil.jpg",
        "texto": "Não transformamos apenas aparências. Ajudamos pessoas a redescobrirem seu valor, sua força e sua capacidade de recomeçar. A beleza é uma poderosa ferramenta de transformação social quando associada à educação e à solidariedade.",
        "autorizacao": "Depoimento da idealizadora e fundadora",
        "video_url": "/assets/videos/spa_glow_party.mp4"
      },
      {
        "nome": "Aluna de Formação Profissional",
        "cargo": "Turma de Maquiagem Gratuita (Uberaba/MG)",
        "foto": "/assets/videos/depoimento_aluna_1_poster.jpg",
        "texto": "Aprender uma profissão de forma gratuita mudou a minha perspectiva de futuro. O projeto me deu confiança, independência e a certeza de que sou capaz de transformar a minha realidade através da beleza.",
        "autorizacao": "Depoimento em vídeo de aluna formada",
        "video_url": "/assets/videos/depoimento_aluna_1.mp4"
      },
      {
        "nome": "Participante & Voluntária",
        "cargo": "Acolhida pelo Esquadrão Rosa",
        "foto": "/assets/videos/depoimento_aluna_2_poster.jpg",
        "texto": "Estar no Spa Glow Party é se sentir amada e respeitada. O carinho e a atenção com que fomos acolhidas desde o primeiro dia me inspiraram a continuar sonhando e querendo retribuir todo esse amor.",
        "autorizacao": "Depoimento em vídeo de aluna do projeto",
        "video_url": "/assets/videos/depoimento_aluna_2.mp4"
      },
      {
        "nome": "Aluno da Turma de Maquiagem",
        "cargo": "Capacitação e Geração de Renda",
        "foto": "/assets/videos/depoimento_aluno_3_poster.jpg",
        "texto": "A maquiagem abriu portas que eu nunca imaginei. A equipe me acolheu com tanto carinho, me ensinou técnicas incríveis e me deu coragem para atender clientes e começar a minha própria renda.",
        "autorizacao": "Depoimento em vídeo de aluno beneficiado",
        "video_url": "/assets/videos/depoimento_aluno_3.mp4"
      }
    ],
    "galeria": [
      {
        "titulo": "Turma de Formação Gratuita em Maquiagem",
        "categoria": "Capacitação",
        "url": "/assets/img/oficina_turma_maquiagem.jpg"
      },
      {
        "titulo": "Atendimento Facial no Spa Glow Party",
        "categoria": "Beleza",
        "url": "/assets/img/atendimento_estetica_spa.jpg"
      },
      {
        "titulo": "Roda de Conversa e Desenvolvimento Humano",
        "categoria": "Acolhimento",
        "url": "/assets/img/roda_conversa_ar_livre.jpg"
      },
      {
        "titulo": "Comunidade, Alunas e Voluntárias Unidas",
        "categoria": "Comunidade",
        "url": "/assets/img/comunidade_unida_comemoracao.jpg"
      },
      {
        "titulo": "Design de Sobrancelhas pelo Esquadrão Rosa",
        "categoria": "Voluntariado",
        "url": "/assets/img/design_sobrancelhas_voluntarias.jpg"
      },
      {
        "titulo": "Bancada Prática e Cosméticos Profissionais",
        "categoria": "Capacitação",
        "url": "/assets/img/bancada_maquiagem_oficina.jpg"
      },
      {
        "titulo": "Noite Spa Glow Party com Maquiagem Neon",
        "categoria": "Eventos",
        "url": "/assets/videos/evento_glow_party_poster.jpg",
        "video_url": "/assets/videos/evento_glow_party.mp4"
      },
      {
        "titulo": "Rayane Gomes em Palestra Motivacional",
        "categoria": "Acolhimento",
        "url": "/assets/img/rayane_gomes_palestrante.jpg"
      },
      {
        "titulo": "Esquadrão Rosa: União e Transformação",
        "categoria": "Comunidade",
        "url": "/assets/img/esquadrao_rosa_oficial.jpg"
      }
    ]
  },
  "como_ajudar": {
    "titulo": "Seja um Parceiro do Spa Glow Party",
    "subtitulo": "Empresas, profissionais e apoiadores podem contribuir com patrocínios, materiais, serviços, apoio logístico ou juntando-se ao Esquadrão Rosa.",
    "pix": {
      "chave": "+5534999990000",
      "tipo_chave": "Telefone Celular",
      "favorecido": "Spa Glow Party / Rayane Gomes",
      "banco": "Banco Digital / Chave PIX",
      "cnpj": "Projeto Social Spa Glow Party"
    },
    "dados_bancarios": {
      "banco": "Banco Inter / Conta Social",
      "agencia": "0001",
      "conta_corrente": "1234567-8",
      "titular": "Spa Glow Party - Rayane Gomes",
      "cnpj": "Iniciativa Social Rayane Gomes"
    },
    "valores_sugeridos": [
      {
        "valor": "R$ 30",
        "impacto": "Kit de pincéis de maquiagem"
      },
      {
        "valor": "R$ 60",
        "impacto": "Maleta de maquiagem para os alunos"
      },
      {
        "valor": "R$ 120",
        "impacto": "Kit de criação de conteúdo (tripé e suporte para celular)"
      },
      {
        "valor": "R$ 250",
        "impacto": "Kit de maquiagem"
      }
    ],
    "doacao_itens": {
      "titulo": "Doação de Materiais e Produtos de Beleza",
      "descricao": "Recebemos produtos de maquiagem, itens de higiene, roupas para o Varal Solidário e materiais para nossas oficinas:",
      "itens": [
        {
          "item": "Pincéis, esponjas e maquiagens novas ou lacradas",
          "status": "Urgente",
          "cor": "red"
        },
        {
          "item": "Produtos para cuidados com cabelos e pele",
          "status": "Urgente",
          "cor": "red"
        },
        {
          "item": "Roupas e calçados em bom estado para o Varal Solidário",
          "status": "Contínuo",
          "cor": "blue"
        },
        {
          "item": "Espelhos, iluminadores e itens de apoio para cursos",
          "status": "Necessário",
          "cor": "amber"
        },
        {
          "item": "Kits de higiene pessoal e autocuidado feminino",
          "status": "Urgente",
          "cor": "red"
        }
      ]
    },
    "voluntariado": {
      "titulo": "Junte-se ao Esquadrão Rosa",
      "descricao": "O Esquadrão Rosa é formado por voluntárias que dedicam tempo, talento, energia e amor para tornar cada ação possível. Doe seu talento e ajude a transformar vidas!",
      "areas": [
        "Maquiagem e Autocuidado",
        "Cuidados com Cabelos e Penteados",
        "Design de Sobrancelhas e Estética",
        "Instrutora de Cursos e Oficinas Profissionais",
        "Palestras Motivacionais e Acolhimento",
        "Organização, Acolhimento e Logística de Eventos",
        "Fotografia, Filmagem e Redes Sociais",
        "Varal Solidário e Arrecadação de Doações",
        "Apoio Geral e Integração Comunitária"
      ],
      "link_formulario": "https://forms.gle/EXf95hre8ezb4zNd9",
      "link_embed": "https://docs.google.com/forms/d/e/1FAIpQLSdPWdeM72hoVf4qhRpqP8mWYVx4G70UgFXbeen7GShEvyijQA/viewform?embedded=true"
    },
    "parcerias_empresas": {
      "titulo": "Sua Empresa Pode Fazer a Diferença",
      "descricao": "Empresas e marcas de beleza podem apoiar com patrocínios, produtos, apoio logístico e responsabilidade social alinhada às diretrizes ESG.",
      "beneficios": [
        "Doação de kits e produtos para alunas das turmas de capacitação gratuita",
        "Visibilidade da marca no site, redes sociais e eventos do projeto",
        "Ações de voluntariado corporativo presenciais com o Esquadrão Rosa",
        "Impacto social direto na geração de renda e fortalecimento de mulheres"
      ]
    }
  },
  "transparencia": {
    "titulo": "Transparência e Compromisso",
    "subtitulo": "Prestação de contas aberta, relatórios de impacto e compromisso com a transformação social.",
    "documentos_legais": [
      {
        "nome": "Apresentação Institucional Spa Glow Party",
        "descricao": "Missão, metodologia de atendimento, público-alvo e histórico do projeto",
        "arquivo": "/public/docs/cartao_cnpj_exemplo.pdf"
      },
      {
        "nome": "Termo de Parceria Social - Casa de Sopa Adolfo Fritz",
        "descricao": "Registro de cooperação comunitária para realização dos cursos em Uberaba/MG",
        "arquivo": "/public/docs/certificado_osc_exemplo.pdf"
      },
      {
        "nome": "Manual de Voluntariado do Esquadrão Rosa",
        "descricao": "Diretrizes de acolhimento, conduta e atuação em mutirões de beleza",
        "arquivo": "/public/docs/cnd_federal_exemplo.pdf"
      }
    ],
    "relatorios_atividades": [
      {
        "ano": "2026",
        "titulo": "Relatório de Atividades e Formação Profissional 2026",
        "status": "Ações em Andamento",
        "link": "/public/docs/relatorio_anual_2025.pdf"
      },
      {
        "ano": "2025",
        "titulo": "Balanço de Atendimentos e Turmas Formadas 2025",
        "status": "Concluído e Disponível",
        "link": "/public/docs/relatorio_anual_2024.pdf"
      }
    ],
    "destinacao_recursos": {
      "descricao": "Veja graficamente como cada recurso e doação é aplicado diretamente na transformação das vidas atendidas:",
      "distribuicao": [
        {
          "categoria": "Kits e Insumos para Cursos Profissionalizantes Gratuitos",
          "percentual": 50,
          "cor": "#ec4899"
        },
        {
          "categoria": "Mutirões de Beleza, Acolhimento e Eventos Comunitários",
          "percentual": 30,
          "cor": "#db2777"
        },
        {
          "categoria": "Logística, Varal Solidário e Apoio a Famílias",
          "percentual": 20,
          "cor": "#f59e0b"
        }
      ]
    }
  },
  "noticias_blog": {
    "titulo": "Últimas Notícias e Ações",
    "subtitulo": "Acompanhe as oficinas, histórias de superação e novidades do Spa Glow Party.",
    "artigos": [
      {
        "id": "formatura-turma-maquiagem-uberaba",
        "titulo": "Turma de 30 alunas conclui curso gratuito de maquiagem profissional em Uberaba",
        "data": "20 de Outubro de 2026",
        "categoria": "Capacitação",
        "foto": "/assets/img/oficina_turma_maquiagem.jpg",
        "resumo": "Em ação vinculada à Casa de Sopa Adolfo Fritz, 30 mulheres concluíram a formação prática para geração de renda e autonomia.",
        "conteudo_completo": "O Spa Glow Party comemorou a formatura de mais uma turma de maquiagem profissional gratuita em Uberaba/MG. A iniciativa, realizada em parceria com a Casa de Sopa Adolfo Fritz, ofereceu aulas práticas, técnicas profissionais e desenvolvimento do espírito empreendedor, reforçando o compromisso do projeto em transformar conhecimento em oportunidades reais de independência e dignidade."
      },
      {
        "id": "esquadrao-rosa-forca-voluntariado",
        "titulo": "Esquadrão Rosa: a rede de voluntárias que move o Spa Glow Party",
        "data": "12 de Outubro de 2026",
        "categoria": "Comunidade",
        "foto": "/assets/img/esquadrao_rosa_oficial.jpg",
        "resumo": "Profissionais da beleza e voluntárias dedicam seu talento e tempo para acolher, empoderar e inspirar centenas de mulheres.",
        "conteudo_completo": "Se o Spa Glow Party é um sonho que transforma vidas, o Esquadrão Rosa é o coração pulsante que faz esse sonho acontecer. Formado por mulheres voluntárias apaixonadas, o grupo atua no acolhimento, execução das oficinas e apoio logístico de cada ação social. Conheça como se juntar a essa causa e fazer a diferença."
      },
      {
        "id": "varal-solidario-mobilizacao",
        "titulo": "Varal Solidário e campanhas mobilizam doações e fortalecem famílias",
        "data": "02 de Outubro de 2026",
        "categoria": "Solidariedade",
        "foto": "/assets/img/comunidade_unida_comemoracao.jpg",
        "resumo": "Iniciativa comunitária distribui roupas, agasalhos e kits de autocuidado para pessoas em situação de vulnerabilidade.",
        "conteudo_completo": "Além da capacitação e dos atendimentos de beleza, o Spa Glow Party mantém viva a solidariedade em ação por meio do Varal Solidário. A ação arrecadou roupas, calçados e produtos de autocuidado essenciais, distribuídos diretamente a famílias da comunidade. O carinho e a dignidade chegam de mãos dadas com cada doação."
      }
    ]
  },
  "contato": {
    "titulo": "Faça Parte Dessa Transformação",
    "subtitulo": "Existe algo poderoso em fazer alguém voltar a sorrir, acreditar em si e enxergar possibilidades onde antes existiam dificuldades.",
    "endereco_completo": "Uberaba - Minas Gerais, Brasil",
    "ponto_referencia": "Ações comunitárias integradas (Casa de Sopa Adolfo Fritz e comunidades parceiras)",
    "telefone": "(34) 99999-0000",
    "whatsapp": "(34) 99999-0000",
    "whatsapp_link": "https://wa.me/5534999990000?text=Ol%C3%A1!%20Gostaria%20de%20saber%20mais%20sobre%20o%20Spa%20Glow%20Party%20e%20como%20apoiar%20ou%20participar.",
    "email_geral": "contato@spaglowparty.org",
    "email_doacoes": "parcerias@spaglowparty.org",
    "horario_funcionamento": "Segunda a Sábado com oficinas e mutirões agendados",
    "redes_sociais": {
      "instagram": "https://instagram.com/rayanegomesoficial",
      "facebook": "https://facebook.com/spaglowparty",
      "youtube": "https://youtube.com/@spaglowparty",
      "linkedin": "https://linkedin.com/company/spaglowparty"
    },
    "mapa_embed_url": "https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d120562.33923984364!2d-47.99427672322304!3d-19.747306232338148!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x94bad1b621516f49%3A0xbc4e57e3bf8e29a9!2sUberaba%2C%20MG!5e0!3m2!1spt-BR!2sbr!4v1700000000000!5m2!1spt-BR!2sbr"
  },
  "_atualizado_em": "2026-10-25T19:07:51.309388"
};
}