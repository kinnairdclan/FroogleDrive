// Open the share dialog whenever HTMX swaps content into it.
document.addEventListener("htmx:after:swap", (e) => {
  const dialog = e.detail.ctx.target;
  if (dialog?.id === "share-dialog" && !dialog.open) dialog.showModal();
});

// On phones, tapping a file or share opens its details dialog (instead of downloading).
const phone = window.matchMedia("(max-width: 600px)");
document.addEventListener("click", (e) => {
  const item = e.target.closest("[data-details]");
  if (!item || !phone.matches) return;
  e.preventDefault();
  htmx.ajax("GET", item.dataset.details, { target: "#share-dialog" });
});

document.addEventListener("click", async (e) => {
  const closer = e.target.closest("[data-close-dialog]");
  if (closer) {
    closer.closest("dialog")?.close();
    return;
  }
  const btn = e.target.closest("[data-copy]");
  if (!btn) return;
  const input = document.querySelector(btn.dataset.copy);
  try {
    await navigator.clipboard.writeText(input.value);
  } catch {
    // Clipboard API needs HTTPS or localhost; fall back to a selection copy.
    input.select();
    document.execCommand("copy");
  }
  // The button holds both labels (see .copy-btn), so swapping never resizes it.
  btn.classList.add("copied");
  clearTimeout(btn.copiedTimer);
  btn.copiedTimer = setTimeout(() => btn.classList.remove("copied"), 1500);
});

// Select a share link's full text when its field gets focus.
document.addEventListener("focusin", (e) => {
  if (e.target.matches(".copy-row input[readonly]")) e.target.select();
});

// Close the dialog when clicking the backdrop.
document.addEventListener("click", (e) => {
  if (e.target.id === "share-dialog") e.target.close();
});
