(function () {
  // The dashboard is mounted under /ui/ by Traefik. Keep API and file links
  // under that mount instead of accidentally calling the domain root.
  const APP_BASE = window.location.pathname.startsWith("/ui") ? "/ui" : "";
  const apiUrl = (path) => `${APP_BASE}${path}`;
  const publicUrl = (path) => {
    if (!path) return "";
    if (/^https?:\/\//i.test(path)) return path;
    return `${APP_BASE}${path.startsWith("/") ? path : `/${path}`}`;
  };
  const sendBtn = document.getElementById("send-btn");
  const attachBtn = document.getElementById("attach-btn");
  const uploadInput = document.getElementById("upload-input");
  const promptInput = document.getElementById("prompt-input");
  const chatThread = document.querySelector(".chat-thread");
  const inboxList = document.querySelector(".inbox-list");
  const inboxCount = document.getElementById("inbox-count");
  const inboxSearch = document.getElementById("inbox-search");
  const tabButtons = Array.from(document.querySelectorAll(".tab-btn"));
  const itemDialog = document.getElementById("item-dialog");
  const itemDialogTitle = document.getElementById("item-dialog-title");
  const itemDialogBody = document.getElementById("item-dialog-body");
  const itemDialogClose = document.getElementById("item-dialog-close");
  let inboxItems = [];
  let activeInboxFilter = "all";

  init();

  function init() {
    bindEvents();
    loadInbox();
    loadChatHistory();
  }

  function bindEvents() {
    if (attachBtn && uploadInput) {
      attachBtn.addEventListener("click", () => uploadInput.click());
    }
    if (sendBtn && promptInput) {
      sendBtn.addEventListener("click", sendMessage);
    }
    if (promptInput) {
      promptInput.addEventListener("keydown", (event) => {
        if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
          sendMessage();
        }
      });
    }
    if (uploadInput) {
      uploadInput.addEventListener("change", uploadFiles);
    }
    if (itemDialogClose && itemDialog) {
      itemDialogClose.addEventListener("click", () => itemDialog.close());
    }
    if (inboxSearch) {
      inboxSearch.addEventListener("input", applyInboxFilters);
    }
    tabButtons.forEach((button) => {
      button.addEventListener("click", () => {
        activeInboxFilter = button.dataset.filter || "all";
        tabButtons.forEach((btn) => btn.classList.toggle("is-active", btn === button));
        applyInboxFilters();
      });
    });
    document.addEventListener("click", handleDelegatedClicks);
  }

  async function loadChatHistory() {
    try {
      const resp = await fetch(apiUrl("/api/chat/history"), { cache: "no-store" });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      renderChatHistory(data.messages || []);
    } catch (error) {
      appendBubble("assistant", `تعذر تحميل السجل: ${error.message}`);
    }
  }

  function renderChatHistory(messages) {
    if (!chatThread) return;
    chatThread.innerHTML = "";
    if (!messages.length) {
      appendBubble("assistant", "مرحبًا. الشات متصل الآن بـ Hermes، ويمكنك البدء من هنا.");
      return;
    }
    messages.forEach((message) => {
      if (!message || !message.content) return;
      appendBubble(message.role === "user" ? "user" : "assistant", message.content);
    });
  }

  function appendBubble(role, text) {
    if (!chatThread) return;
    const bubble = document.createElement("div");
    bubble.className = `bubble ${role}`;
    bubble.innerHTML = `
      <span class="who">${role === "user" ? "أنت" : "Hermes"}</span>
      <p></p>
    `;
    bubble.querySelector("p").textContent = text;
    chatThread.appendChild(bubble);
    chatThread.scrollTop = chatThread.scrollHeight;
  }

  async function sendMessage() {
    const text = (promptInput?.value || "").trim();
    if (!text) {
      promptInput?.focus();
      return;
    }
    appendBubble("user", text);
    promptInput.value = "";
    if (sendBtn) {
      sendBtn.disabled = true;
      sendBtn.textContent = "جارٍ الإرسال...";
    }
    try {
      const resp = await fetch(apiUrl("/api/chat"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || data.error || `HTTP ${resp.status}`);
      appendBubble("assistant", data.reply || "تم التنفيذ لكن الرد كان فارغًا.");
    } catch (error) {
      appendBubble("assistant", `فشل الاتصال بـ Hermes: ${error.message}`);
    } finally {
      if (sendBtn) {
        sendBtn.disabled = false;
        sendBtn.textContent = "إرسال";
      }
    }
  }

  async function loadInbox() {
    try {
      const resp = await fetch(apiUrl("/api/inbox?limit=24"), { cache: "no-store" });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      inboxItems = data.items || [];
      applyInboxFilters();
    } catch (error) {
      if (inboxList) {
        inboxList.innerHTML = `<div class="file-card"><div class="file-body"><strong>تعذر تحميل الصندوق</strong><span>${error.message}</span></div></div>`;
      }
    }
  }

  function applyInboxFilters() {
    const searchTerm = (inboxSearch?.value || "").trim().toLowerCase();
    const filtered = inboxItems.filter((item) => {
      const hasFile = Boolean(item.file || item.file_url);
      const isUpload = item.kind === "upload";
      const textBlob = `${item.title || ""} ${item.service || ""} ${item.content || ""}`.toLowerCase();
      const matchesSearch = !searchTerm || textBlob.includes(searchTerm);
      let matchesType = true;
      if (activeInboxFilter === "files") matchesType = hasFile;
      else if (activeInboxFilter === "text") matchesType = !hasFile;
      else if (activeInboxFilter === "upload") matchesType = isUpload;
      return matchesSearch && matchesType;
    });
    renderInbox(filtered);
    if (inboxCount) {
      inboxCount.textContent = `${filtered.length} عنصر`;
    }
  }

  function renderInbox(items) {
    if (!inboxList) return;
    if (!items.length) {
      inboxList.innerHTML = `<div class="file-card"><div class="file-body"><strong>الصندوق فارغ</strong><span>لا توجد عناصر بعد.</span></div></div>`;
      return;
    }
    inboxList.innerHTML = items.map((item) => {
      const fileLink = publicUrl(item.file_url || item.file || "");
      const meta = item.created_at ? new Date(item.created_at).toLocaleString("ar") : "";
      const service = item.service || "غير محدد";
      return `
        <div class="file-card">
          <div class="file-icon">${item.type === "file" || fileLink ? "📎" : "📄"}</div>
          <div class="file-body">
            <strong>${escapeHtml(item.title || "بدون عنوان")}</strong>
            <span>مرسل من: ${escapeHtml(service)}</span>
            <small>${escapeHtml(meta)}</small>
            ${item.content ? `<p class="inbox-preview">${escapeHtml(item.content.slice(0, 180))}</p>` : ""}
            <div class="item-actions">
              <button class="btn ghost open-detail" type="button" data-item-id="${escapeHtml(item.id || "")}">عرض التفاصيل</button>
              ${fileLink ? `<a class="btn ghost open-file" href="${fileLink}" target="_blank" rel="noopener noreferrer">فتح الملف</a>` : ""}
            </div>
          </div>
        </div>
      `;
    }).join("");
  }

  async function handleDelegatedClicks(event) {
    const detailBtn = event.target.closest(".open-detail");
    if (detailBtn) {
      const itemId = detailBtn.getAttribute("data-item-id");
      if (itemId) {
        await openItemDetails(itemId);
      }
    }
  }

  async function openItemDetails(itemId) {
    try {
      const resp = await fetch(apiUrl(`/api/inbox/item/${encodeURIComponent(itemId)}`), {
        cache: "no-store",
      });
      const item = await resp.json();
      if (!resp.ok) throw new Error(item.error || `HTTP ${resp.status}`);
      if (itemDialogTitle) itemDialogTitle.textContent = item.title || "تفاصيل العنصر";
      const pieces = [];
      pieces.push(`الخدمة: ${item.service || "غير محدد"}`);
      pieces.push(`التاريخ: ${item.created_at || "-"}`);
      if (Array.isArray(item.tags) && item.tags.length) {
        pieces.push(`الوسوم: ${item.tags.join(", ")}`);
      }
      if (item.content) {
        pieces.push("");
        pieces.push(item.content);
      }
      if (item.file_url || item.file) {
        pieces.push("");
        pieces.push(`رابط الملف: ${location.origin}${publicUrl(item.file_url || item.file)}`);
      }
      if (itemDialogBody) itemDialogBody.textContent = pieces.join("\n");
      if (itemDialog) itemDialog.showModal();
    } catch (error) {
      appendBubble("assistant", `تعذر فتح العنصر: ${error.message}`);
    }
  }

  async function uploadFiles() {
    const files = Array.from(uploadInput?.files || []);
    if (!files.length) return;
    for (const file of files) {
      const resp = await fetch(apiUrl("/api/inbox/upload"), {
        method: "POST",
        headers: {
          "X-Filename": file.name,
          "X-Title": file.name,
          "X-Sender": "manual-upload",
          "Content-Type": file.type || "application/octet-stream",
        },
        body: file,
      });
      if (!resp.ok) {
        const text = await resp.text();
        appendBubble("assistant", `فشل رفع ${file.name}: ${text}`);
      }
    }
    uploadInput.value = "";
    await loadInbox();
  }

  function escapeHtml(text) {
    return String(text)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }
})();
