// The "Modern Classics" shelf: books that are still in copyright, so they are not
// hosted here. Each card shows a written digest, official buy/borrow links, and free
// public-domain books from this library on the same subject.

let modern = [];
let freeBooks = {};
let activeTopic = "All";
let query = "";

const list = document.getElementById("modernList");
const chips = document.getElementById("modernChips");
const searchInput = document.getElementById("modernSearch");
const meta = document.getElementById("modernMeta");
const emptyBox = document.getElementById("modernEmpty");

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function searchUrl(base, book) {
  return base + encodeURIComponent(book.title + " " + book.author);
}

function freeHtml(book) {
  return `
    <a class="free-link" href="book.html?id=${encodeURIComponent(book.id)}">
      <img src="${esc(book.cover)}" alt="" loading="lazy" decoding="async" onerror="this.remove()">
      <span class="free-txt">
        <span class="free-label">Free alternative</span>
        <span class="free-title">${esc(book.title)}</span>
        <span class="free-author">${esc(book.author)}</span>
      </span>
      <span class="free-go">Read →</span>
    </a>`;
}

function cardHtml(b) {
  const alts = (b.free || []).map((id) => freeBooks[id]).filter(Boolean);
  return `
    <article class="mcard" data-topic="${esc(b.topic)}">
      <div class="mcard-head">
        <span class="mcat">${esc(b.topic)}</span>
        <h2>${esc(b.title)}</h2>
        <p class="mauthor">${esc(b.author)}${b.year ? " · " + b.year : ""}</p>
        <p class="mpitch">${esc(b.pitch)}</p>
      </div>

      <div class="mcard-body">
        <details class="mdigest">
          <summary>Read the digest</summary>
          <p>${esc(b.digest)}</p>
        </details>

        <div class="mnotfree">
          <strong>Not for download.</strong> This title is still under copyright, so there is no copy on fahad.com.
          Get it from an official seller, or borrow it:
        </div>

        <div class="mbuy">
          <a class="btn btn-primary" href="${searchUrl("https://www.amazon.com/s?k=", b)}" target="_blank" rel="noopener nofollow">Buy ↗</a>
          <a class="btn btn-link" href="${searchUrl("https://books.google.com/books?q=", b)}" target="_blank" rel="noopener nofollow">Preview ↗</a>
          <a class="btn btn-link" href="${searchUrl("https://openlibrary.org/search?q=", b)}" target="_blank" rel="noopener nofollow">Borrow ↗</a>
        </div>

        ${alts.length ? `
        <div class="mfree">
          <h3>Free on this site — same subject</h3>
          ${alts.map(freeHtml).join("")}
        </div>` : !freeLoaded ? `
        <div class="mfree">
          <h3>Free on this site — same subject</h3>
          <p class="mfree-loading">Loading free classics…</p>
        </div>` : ""}
      </div>
    </article>`;
}

function renderChips() {
  const counts = {};
  for (const b of modern) counts[b.topic] = (counts[b.topic] || 0) + 1;
  const topics = ["All", ...Object.keys(counts).sort((a, z) => counts[z] - counts[a])];
  chips.innerHTML = topics
    .map((t) => {
      const n = t === "All" ? modern.length : counts[t];
      return `<button class="chip${t === activeTopic ? " active" : ""}" data-topic="${esc(t)}">${esc(t)}<span class="count">${n}</span></button>`;
    })
    .join("");
  chips.querySelectorAll(".chip").forEach((el) =>
    el.addEventListener("click", () => {
      activeTopic = el.dataset.topic;
      renderChips();
      render();
    })
  );
}

function render() {
  const q = query.trim().toLowerCase();
  const rows = modern.filter((b) => {
    if (activeTopic !== "All" && b.topic !== activeTopic) return false;
    if (!q) return true;
    return (b.title + " " + b.author + " " + b.pitch + " " + b.topic).toLowerCase().includes(q);
  });

  list.innerHTML = rows.map(cardHtml).join("");
  emptyBox.hidden = rows.length > 0;
  meta.textContent =
    rows.length === modern.length
      ? `${modern.length} recommended titles`
      : `${rows.length} of ${modern.length} recommended titles`;
}

let debounce;
searchInput.addEventListener("input", (e) => {
  clearTimeout(debounce);
  const v = e.target.value;
  debounce = setTimeout(() => {
    query = v;
    render();
  }, 140);
});

async function init() {
  // Cards render from modern.json alone. The free-classic links are an extra: if
  // that payload is slow or fails, the shelf still shows every title instead of
  // blanking out, so this must never be a Promise.all that throws together.
  try {
    const m = await fetch("data/modern.json").then((r) => r.json());
    modern = Array.isArray(m) ? m : [];
  } catch {
    emptyBox.hidden = false;
    emptyBox.querySelector("h3").textContent = "Shelf failed to load";
    return;
  }

  renderStats();
  renderChips();
  render();

  loadFreeBooks();
}

let freeLoaded = false;

// A tiny purpose-built map of just the classics this shelf links to — a few KB,
// against several MB for the full library catalog. 10s cap so a slow connection
// costs the free links and nothing else.
function loadFreeBooks() {
  fetch("data/modern_free.json")
    .then((r) => (r.ok ? r.json() : []))
    .then((rows) => {
      for (const b of rows) freeBooks[b.id] = b;
      freeLoaded = true;
      render();
    })
    .catch(() => { freeLoaded = true; });
}

function renderStats() {
  const topics = new Set(modern.map((b) => b.topic));
  const freeIds = new Set();
  for (const b of modern) for (const id of b.free || []) freeIds.add(id);

  const set = (el, n) => {
    const node = document.getElementById(el);
    if (node) node.textContent = n.toLocaleString("en-US");
  };
  set("statTitles", modern.length);
  set("statTopics", topics.size);
  set("statFree", freeIds.size);
}

init();
