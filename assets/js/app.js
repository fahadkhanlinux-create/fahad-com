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

const CATEGORY_ORDER = [
  "AI & Computing", "Self-Help", "Business", "Science", "Technology",
  "Psychology", "Philosophy", "Biography", "Society", "History",
  "Strategy", "Children", "Sports & Games", "Language & Reference",
  "Poetry", "Fiction", "Islam & Religion",
];

const PAGE_SIZE = 48;

let books = [];
let activeCat = "All";
let query = "";
let shown = PAGE_SIZE;
let catCounts = {};

const grid = document.getElementById("grid");
const chips = document.getElementById("chips");
const searchInput = document.getElementById("search");
const resultsMeta = document.getElementById("resultsMeta");
const empty = document.getElementById("empty");
const loadMoreWrap = document.getElementById("loadMoreWrap");
const loadMoreBtn = document.getElementById("loadMore");
const heroBadge = document.getElementById("heroBadge");
const sentinel = document.getElementById("sentinel");

function colors(cat) {
  return CATEGORY_COLORS[cat] || ["#475569", "#1e293b"];
}

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

function pdfUrl(b) {
  // prefer the copy hosted on this site, fall back to the public mirror
  return b.pdf || "pdfs/" + encodeURIComponent(b.id) + ".pdf";
}



function byline(b) {
  return b.year ? `${b.author} · ${b.year}` : b.author;
}

function coverHtml(b) {
  // Every card has a page-1 thumbnail rendered at build time. Those already print the
  // title, so the generated overlay is only shown when there is no image: once the
  // image loads it is flagged and the overlay steps aside, leaving a clean cover.
  const style = `background:linear-gradient(150deg,var(--c1),var(--c2))`;
  return `
    <span class="c-art" style="${style}">
      ${b.cover ? `<img class="c-img" src="${esc(b.cover)}" alt="" loading="lazy" decoding="async"
            onload="this.parentNode.classList.add('has-cover')"
            onerror="this.remove()">` : ""}
      <span class="c-cat">${esc(b.category)}</span>
      <div class="c-text">
        <div class="c-title">${esc(b.title)}</div>
        <div class="c-author">${esc(b.author)}</div>
        ${b.year ? `<div class="c-year">${esc(b.year)}</div>` : ""}
      </div>
    </span>`;
}

function cardHtml(b) {
  const [c1, c2] = colors(b.category);
  // book.html rather than clean /book: extensionless URLs 404 on GitHub Pages, and
  // this keeps one link working on both Vercel and Pages
  const href = "book.html?id=" + encodeURIComponent(b.id);
  return `
    <article class="card">
      <a class="cover" style="--c1:${c1};--c2:${c2}" href="${href}">
        ${coverHtml(b)}
      </a>
      <div class="card-body">
        <div>
          <h3>${esc(b.title)}</h3>
          <div class="author">${esc(byline(b))}</div>
        </div>
        ${b.desc ? `<p class="desc">${esc(b.desc)}</p>` : ""}
        <div class="meta-row">
          <span>📄 ${b.pages || "?"} pages</span>
          <span>💾 ${fmtSize(b.size)}</span>
        </div>
        <div class="card-actions">
          <a class="btn btn-primary" href="${href}">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 5.5A2.5 2.5 0 0 1 4.5 3H10a2 2 0 0 1 2 2v14a2 2 0 0 0-2-2H4.5A2.5 2.5 0 0 1 2 14.5z"/><path d="M22 5.5A2.5 2.5 0 0 0 19.5 3H14a2 2 0 0 0-2 2v14a2 2 0 0 1 2-2h5.5a2.5 2.5 0 0 0 2.5-2.5z"/></svg>
            Read Online
          </a>
          <a class="btn btn-ghost" href="${esc(pdfUrl(b))}" target="_blank" rel="noopener" download title="Download PDF">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3v12m0 0 4-4m-4 4-4-4"/><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/></svg>
          </a>
        </div>
      </div>
    </article>`;
}

function renderChips() {
  const cats = ["All", ...CATEGORY_ORDER.filter((c) => catCounts[c])];
  chips.innerHTML = cats
    .map((c) => {
      const n = c === "All" ? books.length : catCounts[c] || 0;
      return `<button class="chip${c === activeCat ? " active" : ""}" data-cat="${esc(c)}">
        ${esc(c)}<span class="count">${n}</span>
      </button>`;
    })
    .join("");
  chips.querySelectorAll(".chip").forEach((el) =>
    el.addEventListener("click", () => {
      activeCat = el.dataset.cat;
      shown = PAGE_SIZE;
      renderChips();
      render();
    })
  );
}

function filtered() {
  const q = query.trim().toLowerCase();
  return books.filter((b) => {
    if (activeCat !== "All" && b.category !== activeCat) return false;
    if (!q) return true;
    return (
      b.title.toLowerCase().includes(q) ||
      b.author.toLowerCase().includes(q) ||
      b.category.toLowerCase().includes(q) ||
      (b.desc && b.desc.toLowerCase().includes(q))
    );
  });
}

function render() {
  const list = filtered();
  const slice = list.slice(0, shown);
  grid.innerHTML = slice.map(cardHtml).join("");
  empty.hidden = list.length > 0;

  const remaining = list.length - slice.length;
  loadMoreWrap.hidden = remaining <= 0;
  loadMoreBtn.textContent = `Load ${Math.min(PAGE_SIZE, remaining)} more`;

  const label = list.length === books.length
    ? `${books.length.toLocaleString()} books available`
    : `${list.length.toLocaleString()} of ${books.length.toLocaleString()} books`;
  resultsMeta.textContent = remaining > 0
    ? `${label} · showing ${slice.length.toLocaleString()}`
    : label;
}

loadMoreBtn.addEventListener("click", () => {
  shown += PAGE_SIZE;
  render();
});

const observer = new IntersectionObserver(
  (entries) => {
    if (entries[0].isIntersecting && !loadMoreWrap.hidden) {
      shown += PAGE_SIZE;
      render();
    }
  },
  { rootMargin: "600px" }
);
observer.observe(sentinel);

let debounce;
searchInput.addEventListener("input", (e) => {
  clearTimeout(debounce);
  const v = e.target.value;
  debounce = setTimeout(() => {
    query = v;
    shown = PAGE_SIZE;
    render();
  }, 140);
});

async function init() {
  try {
    const res = await fetch("data/catalog.json");
    books = await res.json();
  } catch {
    empty.hidden = false;
    empty.querySelector("h3").textContent = "Failed to load library";
    return;
  }
  if (!Array.isArray(books) || books.length === 0) {
    empty.hidden = false;
    empty.querySelector("h3").textContent = "Library is empty";
    return;
  }
  catCounts = {};
  for (const b of books) catCounts[b.category] = (catCounts[b.category] || 0) + 1;

  const cats = Object.keys(catCounts).length;
  heroBadge.textContent = `${books.length.toLocaleString()} Books · ${cats} Categories · 100% Free & Legal`;
  renderChips();
  render();
}

init();