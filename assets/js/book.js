const CATEGORY_COLORS = {
  "Fiction": ["#7c3aed", "#4c1d95"],
  "Children": ["#ec4899", "#9d174d"],
  "Science": ["#0ea5e9", "#075985"],
  "History": ["#f59e0b", "#92400e"],
  "Islam & Religion": ["#10b981", "#065f46"],
  "Philosophy": ["#6366f1", "#312e81"],
  "Self-Help": ["#ef4444", "#7f1d1d"],
  "Business": ["#14b8a6", "#134e4a"],
  "Poetry": ["#d946ef", "#701a75"],
  "Technology": ["#06b6d4", "#155e75"],
  "Psychology": ["#8b5cf6", "#4c1d95"],
  "Strategy": ["#f97316", "#7c2d12"],
  "AI & Computing": ["#22d3ee", "#0e7490"],
  "Biography": ["#a78bfa", "#5b21b6"],
  "Society": ["#84cc16", "#3f6212"],
  "Sports & Games": ["#eab308", "#854d0e"],
  "Language & Reference": ["#64748b", "#1e293b"],
};

function fmtSize(bytes) {
  return bytes >= 1048576
    ? (bytes / 1048576).toFixed(1) + " MB"
    : Math.round(bytes / 1024) + " KB";
}

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

async function init() {
  const id = new URLSearchParams(location.search).get("id");
  const titleEl = document.getElementById("rTitle");
  if (!id) {
    location.replace("/");
    return;
  }
  let books = [];
  try {
    const res = await fetch("data/books.json");
    books = await res.json();
  } catch {
    titleEl.textContent = "Failed to load";
    return;
  }

  const book = books.find((b) => b.id === id);
  if (!book) {
    titleEl.textContent = "Book not found";
    document.getElementById("rCat").hidden = true;
    document.getElementById("rDesc").textContent =
      "This book is not in the library any more. Browse the full collection from the home page.";
    document.querySelector(".viewer-wrap").hidden = true;
    return;
  }

  const [c1, c2] = CATEGORY_COLORS[book.category] || ["#475569", "#1e293b"];
  document.title = `${book.title} — ${book.author} | Fahad.com`;
  document.getElementById("rCat").textContent = book.category;
  titleEl.textContent = book.title;
  document.getElementById("rAuthor").textContent = book.year
    ? `${book.author} · ${book.year}`
    : book.author;
  document.getElementById("rDesc").textContent = book.desc;
  document.getElementById("rMeta").innerHTML = `
    <span>📄 ${book.pages || "?"} pages</span>
    <span>💾 ${fmtSize(book.size)}</span>
    <span>🏷️ ${book.category}</span>`;

  const cover = document.getElementById("miniCover");
  cover.style.setProperty("--c1", c1);
  cover.style.setProperty("--c2", c2);
  if (book.cover) {
    cover.innerHTML = `<img class="mc-img" src="${esc(book.cover)}" alt=""
      onerror="this.remove()">`;
  } else {
    cover.innerHTML = `<div class="mc-title">${esc(book.title)}</div><div class="mc-author">${esc(book.author)}</div>`;
  }

  const dl = document.getElementById("rDownload");
  const dl2 = document.getElementById("rDownload2");
  const open = document.getElementById("rOpen");

  // A PDF that fit in the deployment is served from here; the rest come from the public
  // mirror, and if that mirror is unreachable the raw GitHub URL is the last try. A
  // dead link is worse than a slow one, so each source is tried in turn.
  const sources = [];
  if (book.local && book.file) sources.push(book.file);
  if (book.pdf) sources.push(book.pdf);
  if (book.pdf_raw && book.pdf_raw !== book.pdf) sources.push(book.pdf_raw);
  if (!sources.length) sources.push("pdfs/" + encodeURIComponent(book.id) + ".pdf");
  const sourceNote = document.getElementById("rSource");
  if (sourceNote) {
    sourceNote.textContent = book.local
      ? "PDF is hosted on fahad.com"
      : "PDF is served from our public mirror — same file, one click away";
  }
  // the mirror is a convenience, never the only way in: Gutenberg's own reader stays
  // one click away for every book
  const pg = document.getElementById("rGutenberg");
  if (pg && book.gid) {
    pg.href = `https://www.gutenberg.org/ebooks/${book.gid}`;
    pg.hidden = false;
  }

  function setTarget(a) {
    a.href = sources[0];
    a.removeAttribute("download");
    a.target = "_blank";
    a.rel = "noopener";
  }
  setTarget(dl);
  setTarget(dl2);
  setTarget(open);

  // The PDF can be several MB, so it is not attached to the page: the reader arrives
  // here, sees the cover and a button, and the viewer only fetches the file on click.
  const viewer = document.getElementById("viewer");
  const idle = document.getElementById("viewerIdle");
  const idleRead = document.getElementById("idleRead");
  const idleCover = document.getElementById("idleCover");
  const idleText = document.getElementById("idleText");
  const fallback = document.getElementById("viewerFallback");

  if (book.cover) {
    idleCover.src = book.cover;
    idleCover.onerror = () => { idleCover.hidden = true; };
    idleCover.hidden = false;
  }
  idleText.textContent = `${book.pages || "?"} pages · ${fmtSize(book.size)} — loads only when you press Read.`;

  let loaded = false;
  function loadPdf() {
    if (loaded) return;
    loaded = true;
    idleRead.disabled = true;
    idleText.textContent = "Loading PDF…";

    let i = 0;
    function tryNext() {
      if (i >= sources.length) {
        viewer.hidden = true;
        idle.hidden = true;
        fallback.hidden = false;
        return;
      }
      const src = sources[i++];
      viewer.hidden = true;
      idle.hidden = false;
      idleText.textContent = i === 1
        ? "Loading PDF…"
        : "Local copy unavailable — loading from mirror…";
      viewer.src = `${src}#view=FitH&toolbar=1`;
      viewer.hidden = false;
      idle.hidden = true;
    }
    viewer.addEventListener("error", tryNext);
    // a PDF served from another origin can also fail silently: wait for the frame to
    // report a ready document, and if it never does, move on to the next source
    viewer.addEventListener("load", () => {
      try {
        const loc = viewer.contentWindow.location.href;
        if (loc && sources.indexOf(loc.split("#")[0]) === -1) tryNext();
      } catch {
        /* cross-origin: the frame loaded, which is the signal we wanted */
      }
    });
    tryNext();
  }

  idleRead.addEventListener("click", loadPdf);
  idle.addEventListener("click", loadPdf);
}

init();
