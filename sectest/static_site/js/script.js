/* =========================================================================
   SecTest — script.js
   Funções compartilhadas por todas as páginas do site.
   Cada função verifica se os elementos que precisa existem antes de rodar,
   já que nem toda página tem os mesmos elementos (ex: formulário de
   cadastro só existe em cadastro.html).
   ========================================================================= */

document.addEventListener('DOMContentLoaded', () => {
  initMobileMenu();
  initActiveNavLink();
  initScrollHeader();
  initScrollReveal();
  initFooterYear();
  initCadastroForm();
  initContatoForm();
  initAdminPanel();
});

/* ---------- Menu mobile ---------- */
function initMobileMenu() {
  const toggle = document.getElementById('menuToggle');
  const nav = document.getElementById('mainNav');
  if (!toggle || !nav) return;

  toggle.addEventListener('click', () => {
    const isOpen = nav.classList.toggle('is-open');
    toggle.classList.toggle('is-active', isOpen);
    toggle.setAttribute('aria-expanded', String(isOpen));
  });

  // Fecha o menu ao clicar em um link (importante em telas menores)
  nav.querySelectorAll('.nav-link').forEach((link) => {
    link.addEventListener('click', () => {
      nav.classList.remove('is-open');
      toggle.classList.remove('is-active');
      toggle.setAttribute('aria-expanded', 'false');
    });
  });
}

/* ---------- Marca o link ativo no menu conforme a página atual ---------- */
function initActiveNavLink() {
  const links = document.querySelectorAll('.nav-link');
  if (!links.length) return;

  let currentPage = window.location.pathname.split('/').pop();
  if (currentPage === '') currentPage = 'index.html';

  links.forEach((link) => {
    if (link.getAttribute('href') === currentPage) {
      link.classList.add('active');
    }
  });
}

/* ---------- Cabeçalho muda de aparência ao rolar a página ---------- */
function initScrollHeader() {
  const header = document.getElementById('siteHeader');
  if (!header) return;

  const onScroll = () => {
    header.classList.toggle('is-scrolled', window.scrollY > 12);
  };
  onScroll();
  window.addEventListener('scroll', onScroll, { passive: true });
}

/* ---------- Animação suave ao rolar (fade + slide) ---------- */
function initScrollReveal() {
  const items = document.querySelectorAll('.reveal');
  if (!items.length) return;

  if (!('IntersectionObserver' in window)) {
    items.forEach((el) => el.classList.add('is-visible'));
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.15 }
  );

  items.forEach((el) => observer.observe(el));
}

/* ---------- Atualiza o ano no rodapé ---------- */
function initFooterYear() {
  const yearEl = document.getElementById('year');
  if (yearEl) yearEl.textContent = new Date().getFullYear();
}

/* ---------- Utilitários de validação ---------- */
function isValidEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
}

function isValidPhone(value) {
  const digits = value.replace(/\D/g, '');
  return digits.length >= 10 && digits.length <= 11;
}

function maskPhone(value) {
  const digits = value.replace(/\D/g, '').slice(0, 11);
  if (digits.length > 10) {
    return digits.replace(/(\d{2})(\d{5})(\d{0,4})/, '($1) $2-$3').replace(/-$/, '');
  }
  if (digits.length > 5) {
    return digits.replace(/(\d{2})(\d{4})(\d{0,4})/, '($1) $2-$3').replace(/-$/, '');
  }
  if (digits.length > 2) {
    return digits.replace(/(\d{2})(\d{0,5})/, '($1) $2');
  }
  return digits;
}

function setFieldError(field, message) {
  field.classList.add('is-invalid');
  const errorEl = field.closest('.form-group')?.querySelector('.form-error');
  if (errorEl) {
    errorEl.textContent = message;
    errorEl.classList.add('is-visible');
  }
}

function clearFieldError(field) {
  field.classList.remove('is-invalid');
  const errorEl = field.closest('.form-group')?.querySelector('.form-error');
  if (errorEl) {
    errorEl.textContent = '';
    errorEl.classList.remove('is-visible');
  }
}

/* ---------- Formulário de cadastro (cadastro.html) ---------- */
function initCadastroForm() {
  const form = document.getElementById('cadastroForm');
  if (!form) return;

  const phoneField = document.getElementById('telefone');
  if (phoneField) {
    phoneField.addEventListener('input', () => {
      phoneField.value = maskPhone(phoneField.value);
    });
  }

  const requiredFields = form.querySelectorAll('[required]');

  function validateField(field) {
    if (field.type === 'checkbox') {
      if (!field.checked) {
        setFieldError(field, 'É necessário concordar para continuar.');
        return false;
      }
      clearFieldError(field);
      return true;
    }
    if (!field.value.trim()) {
      setFieldError(field, 'Este campo é obrigatório.');
      return false;
    }
    if (field.type === 'email' && !isValidEmail(field.value)) {
      setFieldError(field, 'Informe um e-mail válido.');
      return false;
    }
    if (field.id === 'telefone' && !isValidPhone(field.value)) {
      setFieldError(field, 'Informe um telefone válido, com DDD.');
      return false;
    }
    clearFieldError(field);
    return true;
  }

  requiredFields.forEach((field) => {
    field.addEventListener('input', () => clearFieldError(field));
    field.addEventListener('blur', () => validateField(field));
  });

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    let isValid = true;
    let firstInvalid = null;

    requiredFields.forEach((field) => {
      if (!validateField(field)) {
        isValid = false;
        if (!firstInvalid) firstInvalid = field;
      }
    });

    if (!isValid) {
      firstInvalid?.focus();
      return;
    }

    const successPanel = document.getElementById('cadastroSuccess');
    form.classList.add('hidden');
    successPanel?.classList.remove('hidden');
    successPanel?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  });
}

/* ---------- Formulário de contato (contato.html) ---------- */
function initContatoForm() {
  const form = document.getElementById('contatoForm');
  if (!form) return;

  const requiredFields = form.querySelectorAll('[required]');

  requiredFields.forEach((field) => {
    field.addEventListener('input', () => clearFieldError(field));
  });

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    let isValid = true;
    let firstInvalid = null;

    requiredFields.forEach((field) => {
      let fieldValid = true;
      if (!field.value.trim()) {
        fieldValid = false;
        setFieldError(field, 'Este campo é obrigatório.');
      } else if (field.type === 'email' && !isValidEmail(field.value)) {
        fieldValid = false;
        setFieldError(field, 'Informe um e-mail válido.');
      } else {
        clearFieldError(field);
      }
      if (!fieldValid) {
        isValid = false;
        if (!firstInvalid) firstInvalid = field;
      }
    });

    if (!isValid) {
      firstInvalid?.focus();
      return;
    }

    const successPanel = document.getElementById('contatoSuccess');
    form.classList.add('hidden');
    successPanel?.classList.remove('hidden');
    successPanel?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  });
}

/* ---------- Painel administrativo (admin.html) ----------
   Este projeto é somente front-end (sem back-end/banco de dados), então
   os registros abaixo são fictícios e servem apenas para demonstrar a
   interface do painel. Em um cenário real, viriam de um servidor
   autenticado, e a senha nunca ficaria escrita no código-fonte. */
function initAdminPanel() {
  const loginForm = document.getElementById('adminLoginForm');
  if (!loginForm) return;

  const DEMO_USER = 'admin';
  const DEMO_PASS = 'admin123';

  const loginSection = document.getElementById('adminLogin');
  const dashboardSection = document.getElementById('adminDashboard');
  const loginError = document.getElementById('loginError');
  const logoutBtn = document.getElementById('logoutBtn');
  const searchInput = document.getElementById('tableSearch');
  const tableBody = document.getElementById('registrationsTableBody');

  const mockRegistrations = [
    { empresa: 'TechNova Soluções', responsavel: 'Mariana Costa', email: 'mariana@technova.com.br', servico: 'Monitoramento 24/7', data: '02/08/2026' },
    { empresa: 'Distribuidora Boa Vista', responsavel: 'Rafael Souza', email: 'rafael@boavista.com.br', servico: 'Conformidade LGPD', data: '05/08/2026' },
    { empresa: 'Construtora Horizonte', responsavel: 'Juliana Alves', email: 'juliana@horizonteeng.com.br', servico: 'Auditoria e Pentest', data: '07/08/2026' },
    { empresa: 'Clínica Vida Plena', responsavel: 'Eduardo Lima', email: 'eduardo@vidaplena.com.br', servico: 'Consultoria', data: '10/08/2026' },
    { empresa: 'Studio Criativo Aurora', responsavel: 'Beatriz Fernandes', email: 'beatriz@auroracriativo.com.br', servico: 'Treinamento de Equipes', data: '13/08/2026' },
    { empresa: 'Mercado Central Express', responsavel: 'Carlos Mendes', email: 'carlos@mercadocentral.com.br', servico: 'Resposta a Incidentes', data: '15/08/2026' },
    { empresa: 'Rota Logística Ltda.', responsavel: 'Fernanda Rocha', email: 'fernanda@rotalog.com.br', servico: 'Monitoramento 24/7', data: '17/08/2026' },
  ];

  function renderTable(rows) {
    if (!tableBody) return;
    if (!rows.length) {
      tableBody.innerHTML = '<tr><td colspan="5" style="text-align:center; color: var(--color-fog);">Nenhum resultado encontrado.</td></tr>';
      return;
    }
    tableBody.innerHTML = rows
      .map(
        (row) => `
      <tr>
        <td>${row.empresa}</td>
        <td>${row.responsavel}</td>
        <td>${row.email}</td>
        <td><span class="badge">${row.servico}</span></td>
        <td class="mono">${row.data}</td>
      </tr>`
      )
      .join('');
  }

  function updateStats(rows) {
    const statTotal = document.getElementById('statTotal');
    const statWeek = document.getElementById('statWeek');
    const statMessages = document.getElementById('statMessages');
    const statActive = document.getElementById('statActive');
    if (statTotal) statTotal.textContent = rows.length;
    if (statWeek) statWeek.textContent = Math.min(4, rows.length);
    if (statMessages) statMessages.textContent = '3';
    if (statActive) statActive.textContent = Math.max(rows.length - 2, 0);
  }

  loginForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const user = document.getElementById('adminUser').value.trim();
    const pass = document.getElementById('adminPass').value.trim();

    if (user === DEMO_USER && pass === DEMO_PASS) {
      loginSection.classList.add('hidden');
      dashboardSection.classList.remove('hidden');
      if (loginError) loginError.textContent = '';
      renderTable(mockRegistrations);
      updateStats(mockRegistrations);
    } else if (loginError) {
      loginError.textContent = 'Usuário ou senha inválidos. Tente novamente.';
    }
  });

  logoutBtn?.addEventListener('click', () => {
    dashboardSection.classList.add('hidden');
    loginSection.classList.remove('hidden');
    loginForm.reset();
  });

  searchInput?.addEventListener('input', (e) => {
    const term = e.target.value.toLowerCase().trim();
    const filtered = mockRegistrations.filter(
      (row) =>
        row.empresa.toLowerCase().includes(term) ||
        row.responsavel.toLowerCase().includes(term) ||
        row.servico.toLowerCase().includes(term)
    );
    renderTable(filtered);
  });
}
