(function () {
  const sendBtn = document.getElementById("send-btn");
  const attachBtn = document.getElementById("attach-btn");
  const uploadInput = document.getElementById("upload-input");
  const promptInput = document.getElementById("prompt-input");

  if (attachBtn && uploadInput) {
    attachBtn.addEventListener("click", () => uploadInput.click());
  }

  if (sendBtn && promptInput) {
    sendBtn.addEventListener("click", () => {
      const text = promptInput.value.trim();
      if (!text) {
        promptInput.focus();
        return;
      }
      alert("هذه نسخة واجهة Frontend تسليمية. اربطها لاحقًا بواجهة Hermes API الحية لإرسال الرسائل فعليًا.");
    });
  }

  if (uploadInput) {
    uploadInput.addEventListener("change", () => {
      if (!uploadInput.files || !uploadInput.files.length) return;
      alert(`تم اختيار ${uploadInput.files.length} ملف/ملفات. هذه نسخة واجهة أمامية جاهزة للربط بخدمة الرفع الحية.`);
    });
  }
})();
