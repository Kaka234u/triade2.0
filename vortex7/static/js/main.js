(function () {
  "use strict";

  /* Mobile menu */
  var menuBtn = document.getElementById("mobileMenuBtn");
  var overlay = document.getElementById("mobileNavOverlay");
  if (menuBtn && overlay) {
    menuBtn.addEventListener("click", function () {
      var isOpen = overlay.classList.toggle("open");
      menuBtn.classList.toggle("open", isOpen);
      menuBtn.setAttribute("aria-expanded", isOpen);
      document.body.style.overflow = isOpen ? "hidden" : "";
    });
    overlay.addEventListener("click", function (e) {
      if (e.target === overlay) {
        overlay.classList.remove("open");
        menuBtn.classList.remove("open");
        document.body.style.overflow = "";
      }
    });
  }

  /* Mobile search toggle */
  var searchToggle = document.getElementById("searchToggle");
  var mobileSearch = document.getElementById("mobileSearch");
  if (searchToggle && mobileSearch) {
    searchToggle.addEventListener("click", function () {
      var isOpen = mobileSearch.style.display === "block";
      mobileSearch.style.display = isOpen ? "none" : "block";
      if (!isOpen) {
        var input = mobileSearch.querySelector("input");
        if (input) input.focus();
      }
    });
  }

  /* Flash message dismiss + auto-hide */
  document.querySelectorAll(".flash").forEach(function (flash) {
    var closeBtn = flash.querySelector(".flash-close");
    function dismiss() {
      flash.style.transition = "opacity .3s, transform .3s";
      flash.style.opacity = "0";
      flash.style.transform = "translateX(16px)";
      setTimeout(function () { flash.remove(); }, 300);
    }
    if (closeBtn) closeBtn.addEventListener("click", dismiss);
    setTimeout(dismiss, 4500);
  });

  /* Product detail: option pills (size/color) */
  document.querySelectorAll(".option-pills").forEach(function (group) {
    var name = group.getAttribute("data-name");
    var hiddenInput = group.parentElement.querySelector('input[name="' + name + '"]');
    group.querySelectorAll(".option-pill").forEach(function (pill) {
      pill.addEventListener("click", function () {
        group.querySelectorAll(".option-pill").forEach(function (p) {
          p.classList.remove("selected");
        });
        pill.classList.add("selected");
        if (hiddenInput) hiddenInput.value = pill.getAttribute("data-value");
      });
    });
  });

  /* Product detail: quantity stepper */
  var qtyInput = document.getElementById("qtyInput");
  var qtyMinus = document.getElementById("qtyMinus");
  var qtyPlus = document.getElementById("qtyPlus");
  if (qtyInput && qtyMinus && qtyPlus) {
    qtyMinus.addEventListener("click", function () {
      var val = Math.max(parseInt(qtyInput.min || "1", 10), parseInt(qtyInput.value || "1", 10) - 1);
      qtyInput.value = val;
    });
    qtyPlus.addEventListener("click", function () {
      var max = parseInt(qtyInput.max || "99", 10);
      var val = Math.min(max, parseInt(qtyInput.value || "1", 10) + 1);
      qtyInput.value = val;
    });
  }

  /* Product gallery thumbnails */
  var galleryMain = document.getElementById("galleryMain");
  document.querySelectorAll(".gallery-thumb").forEach(function (thumb) {
    thumb.addEventListener("click", function () {
      document.querySelectorAll(".gallery-thumb").forEach(function (t) {
        t.classList.remove("active");
      });
      thumb.classList.add("active");
      if (galleryMain) galleryMain.src = thumb.getAttribute("data-img");
    });
  });

  /* Header shadow on scroll */
  var header = document.getElementById("siteHeader");
  if (header) {
    var lastScroll = 0;
    window.addEventListener(
      "scroll",
      function () {
        var y = window.scrollY;
        header.style.boxShadow = y > 12 ? "0 8px 24px -12px rgba(0,0,0,0.6)" : "none";
        lastScroll = y;
      },
      { passive: true }
    );
  }

  /* ==========================================================================
     Chatbot VORTEX 7 (respostas por regras, sem API externa)
     ========================================================================== */
  var chatWidget = document.getElementById("chatbotWidget");
  var chatToggle = document.getElementById("chatbotToggle");
  var chatPanel = document.getElementById("chatbotPanel");
  var chatMessages = document.getElementById("chatbotMessages");
  var chatForm = document.getElementById("chatbotForm");
  var chatInput = document.getElementById("chatbotInput");

  if (chatWidget && chatToggle && chatPanel) {
    chatToggle.addEventListener("click", function () {
      var isOpen = chatWidget.classList.toggle("open");
      chatToggle.setAttribute("aria-expanded", isOpen);
      if (isOpen && chatInput) setTimeout(function () { chatInput.focus(); }, 300);
    });

    var rules = [
      { keys: ["frete", "entrega", "prazo", "envio", "chega"], reply: "O frete é calculado no carrinho a partir do seu CEP. Trabalhamos com PAC (5 a 8 dias úteis) e SEDEX (2 a 3 dias úteis). Compras acima de R$ 299,90 têm frete PAC grátis! 📦" },
      { keys: ["pagamento", "pagar", "cartao", "cartão", "pix", "boleto", "parcela"], reply: "Aceitamos Pix (5% de desconto), cartão de crédito em até 3x sem juros e boleto bancário. Você escolhe a forma na tela de checkout. 💳" },
      { keys: ["troca", "devolu", "cancelar", "cancelamento"], reply: "Você tem até 30 dias corridos após o recebimento para solicitar troca ou devolução, desde que o produto esteja sem uso. Veja mais na nossa página de Políticas de Uso. 🔄" },
      { keys: ["tamanho", "numeracao", "numeração", "medida"], reply: "Cada produto tem suas opções de tamanho na própria página do produto. Se ficar em dúvida entre dois tamanhos, recomendamos escolher o maior para melhor caimento. 👕" },
      { keys: ["rastre", "pedido", "status", "acompanhar"], reply: "O rastreio de pedidos ainda não está disponível nesta versão de demonstração da loja — já está nos nossos planos! 🚧" },
      { keys: ["atendente", "humano", "pessoa", "falar com"], reply: "Sem problemas! Preencha o formulário na nossa Central de Atendimento que nossa equipe responde em até 24h úteis. Quer que eu te leve até lá?" },
      { keys: ["desconto", "cupom", "promo", "oferta"], reply: "Nossas ofertas ativas ficam na aba Ofertas do menu principal — sempre com bons descontos em itens selecionados! 🔥" },
      { keys: ["conta", "cadastro", "login", "senha"], reply: "Você pode criar sua conta ou entrar pelo ícone de perfil no topo da página. Leva menos de um minuto! 👤" },
      { keys: ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite"], reply: "Olá! Tudo bem? Como posso te ajudar hoje? Posso falar sobre frete, pagamento, trocas ou tamanhos." },
      { keys: ["obrigado", "obrigada", "valeu", "thanks"], reply: "Por nada! Se precisar de mais alguma coisa, é só chamar. Bons treinos! 💪" },
    ];

    function addMessage(text, from) {
      var el = document.createElement("div");
      el.className = "chatbot-msg chatbot-msg-" + from;
      el.textContent = text;
      chatMessages.appendChild(el);
      chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function botReply(userText) {
      var lower = userText.toLowerCase();
      var matched = null;
      for (var i = 0; i < rules.length; i++) {
        for (var j = 0; j < rules[i].keys.length; j++) {
          if (lower.indexOf(rules[i].keys[j]) !== -1) { matched = rules[i]; break; }
        }
        if (matched) break;
      }
      var reply = matched
        ? matched.reply
        : "Ainda estou aprendendo e não tenho certeza sobre isso. Você pode reformular ou falar direto com nossa equipe na Central de Atendimento. 🙂";

      setTimeout(function () {
        addMessage(reply, "bot");
        if (/atendimento/i.test(reply) || lower.indexOf("atendente") !== -1) {
          var linkBtn = document.createElement("a");
          linkBtn.href = "/atendimento";
          linkBtn.className = "chatbot-chip chatbot-link-chip";
          linkBtn.textContent = "Ir para Atendimento →";
          var wrap = document.createElement("div");
          wrap.className = "chatbot-quick-replies";
          wrap.appendChild(linkBtn);
          chatMessages.appendChild(wrap);
          chatMessages.scrollTop = chatMessages.scrollHeight;
        }
      }, 500);
    }

    if (chatForm) {
      chatForm.addEventListener("submit", function (e) {
        e.preventDefault();
        var text = chatInput.value.trim();
        if (!text) return;
        addMessage(text, "user");
        chatInput.value = "";
        botReply(text);
      });
    }

    document.querySelectorAll(".chatbot-chip[data-msg]").forEach(function (chip) {
      chip.addEventListener("click", function () {
        var msg = chip.getAttribute("data-msg");
        addMessage(msg, "user");
        botReply(msg);
      });
    });
  }
})();

/* Newsletter form (V1: no backend endpoint, simple confirmation) */
function vortexNewsletter(e) {
  e.preventDefault();
  var form = e.target;
  var input = form.querySelector("input[type=email]");
  var btn = form.querySelector("button");
  var originalText = btn.textContent;
  btn.textContent = "Inscrito! ✓";
  btn.disabled = true;
  setTimeout(function () {
    btn.textContent = originalText;
    btn.disabled = false;
    input.value = "";
  }, 2800);
  return false;
}
