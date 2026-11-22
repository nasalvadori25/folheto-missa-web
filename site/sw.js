// Guarda o app e os folhetos no celular para funcionar mesmo sem internet na igreja.
const APP = "folheto-app-v1";
const PDFS = "folheto-pdfs-v1";
const BASE = ["./", "index.html", "manifest.webmanifest", "icon.svg", "icon-180.png", "icon-192.png",
  "pdfjs/pdf.min.js", "pdfjs/pdf.worker.min.js"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(APP).then(c => c.addAll(BASE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(
    ks.filter(k => k !== APP && k !== PDFS).map(k => caches.delete(k))
  )).then(() => self.clients.claim()));
});

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;

  // PDFs: depois de baixado uma vez, abre direto do celular
  if (url.pathname.includes("/pdf/")) {
    e.respondWith(caches.open(PDFS).then(async c => {
      const salvo = await c.match(req, {ignoreSearch: true});
      if (salvo) return salvo;
      const r = await fetch(req);
      if (r.ok && r.status === 200) c.put(req, r.clone());
      return r;
    }));
    return;
  }

  // leitor de PDF: não muda, usa o que está guardado
  if (url.pathname.includes("/pdfjs/")) {
    e.respondWith(caches.match(req).then(s => s || fetch(req).then(r => {
      const copia = r.clone(); caches.open(APP).then(c => c.put(req, copia)); return r;
    })));
    return;
  }

  // página, lista e ícones: tenta a versão nova e, sem internet, usa a guardada
  e.respondWith(fetch(req).then(r => {
    if (r.ok) { const copia = r.clone(); caches.open(APP).then(c => c.put(req, copia)); }
    return r;
  }).catch(() => caches.match(req, {ignoreSearch: true}).then(s => s || caches.match("index.html"))));
});
