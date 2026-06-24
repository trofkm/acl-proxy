(function () {
  "use strict";

  const createForm = document.getElementById("create-form");
  const emailInput = document.getElementById("email-input");
  const emailError = document.getElementById("email-error");
  const ttlInput = document.getElementById("ttl-input");
  const tokenDialog = document.getElementById("token-dialog");
  const tokenInput = document.getElementById("token-value");
  const copyBtn = document.getElementById("copy-btn");
  const doneBtn = document.getElementById("done-btn");
  const confirmDialog = document.getElementById("confirm-dialog");
  const confirmCancel = document.getElementById("confirm-cancel");
  const confirmDelete = document.getElementById("confirm-delete");
  const confirmPrefix = document.getElementById("confirm-token-prefix");
  const confirmHosts = document.getElementById("confirm-token-hosts");
  const tbody = document.getElementById("token-table-body");
  const tokenCount = document.getElementById("token-count");
  const pagination = document.getElementById("pagination");

  let pendingTokenHash = null;
  let pendingPrefix = null;
  let pendingHosts = null;
  let currentPage = 1;
  const pageSize = 20;

  function formatTtl(ttl) {
    if (!ttl || ttl <= 0) return "\u2014";
    if (ttl >= 86400) return Math.round(ttl / 86400) + "d";
    if (ttl >= 3600) return Math.round(ttl / 3600) + "h";
    if (ttl >= 60) return Math.round(ttl / 60) + "m";
    return ttl + "s";
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  function escapeAttr(str) {
    return str
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function renderPagination(page, total, size) {
    const pages = Math.ceil(total / size);
    if (pages <= 1) {
      pagination.innerHTML = "";
      return;
    }
    let html = "";
    if (page > 1) {
      html +=
        '<button type="button" data-page="' +
        (page - 1) +
        '">&larr; Prev</button>';
    }
    html += "<span> Page " + page + " of " + pages + " </span>";
    if (page < pages) {
      html +=
        '<button type="button" data-page="' +
        (page + 1) +
        '">Next &rarr;</button>';
    }
    pagination.innerHTML = html;
  }

  function renderTable(data) {
    tokenCount.textContent = data.total ? "(" + data.total + ")" : "";
    if (!data.tokens || data.tokens.length === 0) {
      tbody.innerHTML =
        '<tr><td colspan="7" class="empty-state">No tokens yet. Create your first one above.</td></tr>';
      renderPagination(1, 0, pageSize);
      return;
    }
    let html = "";
    for (let i = 0; i < data.tokens.length; i++) {
      const t = data.tokens[i];
      html +=
        "<tr>" +
        "<td><code>" +
        escapeHtml(t.token.substring(0, 8)) +
        "...</code></td>" +
        "<td>" +
        escapeHtml(t.hosts) +
        "</td>" +
        "<td>" +
        (t.email ? escapeHtml(t.email) : "\u2014") +
        "</td>" +
        "<td>" +
        (t.comment ? escapeHtml(t.comment) : "\u2014") +
        "</td>" +
        "<td>" +
        (t.created_at ? escapeHtml(t.created_at) : "\u2014") +
        "</td>" +
        "<td>" +
        formatTtl(t.ttl) +
        "</td>" +
        '<td><button type="button" class="destructive delete-btn" data-token-hash="' +
        escapeAttr(t.token) +
        '" data-prefix="' +
        escapeAttr(t.token.substring(0, 8)) +
        '" data-hosts="' +
        escapeAttr(t.hosts) +
        '">Delete</button></td>' +
        "</tr>";
    }
    tbody.innerHTML = html;
    renderPagination(data.page, data.total, data.size);
  }

  async function refreshTable(page) {
    page = page || currentPage;
    currentPage = page;
    try {
      const resp = await fetch(
        "/api/tokens?page=" + page + "&size=" + pageSize,
        {
          headers: { Accept: "application/json" },
        },
      );
      if (!resp.ok) throw new Error("Failed to fetch tokens");
      const data = await resp.json();
      renderTable(data);
      return data;
    } catch (err) {
      console.error("refreshTable:", err);
      tbody.innerHTML =
        '<tr><td colspan="7" class="empty-state">Failed to load tokens. Please try again.</td></tr>';
      tokenCount.textContent = "";
      pagination.innerHTML = "";
      return null;
    }
  }

  pagination.addEventListener("click", function (e) {
    const btn = e.target.closest("button[data-page]");
    if (btn) refreshTable(parseInt(btn.getAttribute("data-page"), 10));
  });

  function activatePreset(ttl) {
    ttlInput.value = ttl;
    document.querySelectorAll(".ttl-preset").forEach(function (b) {
      b.classList.toggle("active", b.getAttribute("data-ttl") === ttl);
    });
  }

  document.querySelectorAll(".ttl-preset").forEach(function (btn) {
    btn.addEventListener("click", function () {
      activatePreset(this.getAttribute("data-ttl"));
    });
  });

  const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s.]+$/;

  function validateEmailField() {
    const raw = emailInput.value.trim();
    if (!raw) {
      emailInput.classList.remove("input-error");
      emailError.textContent = "";
      return true;
    }
    if (!EMAIL_RE.test(raw)) {
      emailInput.classList.add("input-error");
      emailError.textContent = "Invalid email address";
      return false;
    }
    emailInput.classList.remove("input-error");
    emailError.textContent = "";
    return true;
  }

  emailInput.addEventListener("input", validateEmailField);

  createForm.addEventListener("submit", async function (e) {
    e.preventDefault();
    if (!validateEmailField()) {
      emailInput.focus();
      return;
    }
    const submitBtn = createForm.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.setAttribute("aria-busy", "true");

    const fd = new FormData(createForm);
    const body = { hosts: fd.get("hosts") || "" };
    const ttlRaw = fd.get("ttl_seconds");
    if (ttlRaw) body.ttl_seconds = parseInt(ttlRaw, 10);
    const emailVal = fd.get("email");
    if (emailVal) body.email = emailVal;
    const commentVal = fd.get("comment");
    if (commentVal) body.comment = commentVal;

    try {
      const resp = await fetch("/api/tokens", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!resp.ok) {
        let detail = "Failed to create token";
        try {
          const err = await resp.json();
          detail = err.detail || detail;
        } catch (_) {}
        throw new Error(detail);
      }
      const data = await resp.json();
      tokenInput.value = data.token;
      tokenDialog.showModal();
      tokenInput.select();
    } catch (err) {
      alert("Error: " + err.message);
    } finally {
      submitBtn.disabled = false;
      submitBtn.removeAttribute("aria-busy");
    }
  });

  copyBtn.addEventListener("click", async function () {
    const showCopied = function () {
      copyBtn.textContent = "Copied \u2713";
      copyBtn.disabled = true;
      setTimeout(function () {
        copyBtn.textContent = "Copy to clipboard";
        copyBtn.disabled = false;
      }, 1500);
    };
    if (navigator.clipboard && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(tokenInput.value);
        showCopied();
        return;
      } catch (_) {}
    }
    tokenInput.focus();
    tokenInput.select();
    try {
      if (document.execCommand("copy")) {
        showCopied();
        return;
      }
    } catch (_) {}
    alert(
      "Could not copy automatically. Press Ctrl+C (or Cmd+C) to copy the selected token.",
    );
  });

  doneBtn.addEventListener("click", function () {
    tokenDialog.close();
  });

  tokenDialog.addEventListener("close", function () {
    createForm.reset();
    document.querySelectorAll(".ttl-preset").forEach(function (b) {
      b.classList.remove("active");
    });
    refreshTable(1);
  });

  tbody.addEventListener("click", function (e) {
    const btn = e.target.closest(".delete-btn");
    if (!btn) return;
    pendingTokenHash = btn.getAttribute("data-token-hash");
    pendingPrefix = btn.getAttribute("data-prefix");
    pendingHosts = btn.getAttribute("data-hosts");
    confirmPrefix.textContent = pendingPrefix + "...";
    confirmHosts.textContent = pendingHosts;
    confirmDialog.showModal();
  });

  confirmCancel.addEventListener("click", function () {
    confirmDialog.close();
  });

  confirmDelete.addEventListener("click", async function () {
    if (!pendingTokenHash) {
      confirmDialog.close();
      return;
    }
    confirmDialog.close();
    try {
      const resp = await fetch("/api/tokens/" + pendingTokenHash, {
        method: "DELETE",
        headers: { Accept: "application/json" },
      });
      if (!resp.ok) {
        let detail = "Failed to delete token";
        try {
          const err = await resp.json();
          detail = err.detail || detail;
        } catch (_) {}
        throw new Error(detail);
      }
      const data = await refreshTable(currentPage);
      if (
        data &&
        data.tokens.length === 0 &&
        data.total > 0 &&
        currentPage > 1
      ) {
        await refreshTable(currentPage - 1);
      }
    } catch (err) {
      alert("Error: " + err.message);
    } finally {
      pendingTokenHash = null;
      pendingPrefix = null;
      pendingHosts = null;
    }
  });

  confirmDialog.addEventListener("close", function () {
    if (
      document.activeElement &&
      typeof document.activeElement.blur === "function"
    ) {
      document.activeElement.blur();
    }
  });

  refreshTable(1);
})();
