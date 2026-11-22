"""Busca a lista de folhetos no site da Arquidiocese de São Paulo, baixa os PDFs
recentes e próximos para a pasta do site e gera site/data/folhetos.json.

Roda no GitHub Actions (sem dependências além do Python)."""
import datetime
import html
import json
import os
import re
import sys
import urllib.request
from zoneinfo import ZoneInfo

PAGINA = "https://arquisp.org.br/folheto-povo-de-deus/"
UA = ("Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Mobile Safari/537.36")
SITE = os.path.join(os.path.dirname(__file__), "..", "site")


def baixar(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read()


def texto(s):
    s = re.sub(r"<[^>]*>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s).replace("\xa0", " ")).strip()


def absoluto(href):
    href = html.unescape(href.strip())
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return "https://arquisp.org.br" + href
    return href


def nome_arquivo(url):
    n = url.rsplit("/", 1)[-1]
    n = re.sub(r"[^A-Za-z0-9._-]", "_", n)
    return n or "folheto.pdf"


def ler(pagina):
    itens, vistos = [], set()
    for linha in re.findall(r"<tr[^>]*>(.*?)</tr>", pagina, re.S | re.I):
        cel = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", linha, re.S | re.I)
        if len(cel) < 3:
            continue
        m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", texto(cel[0]))
        if not m:
            continue
        folheto = partitura = primeiro = None
        for href, rot in re.findall(r"<a[^>]+href\s*=\s*[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
                                    linha, re.S | re.I):
            if ".pdf" not in href.lower():
                continue
            r = texto(rot).lower()
            if "partitura" in r:
                partitura = partitura or href
            elif "folheto" in r:
                folheto = folheto or href
            else:
                primeiro = primeiro or href
        folheto = folheto or primeiro
        if not folheto or folheto in vistos:
            continue
        vistos.add(folheto)
        d, mes, a = (int(x) for x in m.groups())
        itens.append({
            "data": datetime.date(a, mes, d).isoformat(),
            "nome": texto(cel[1]) or "Folheto",
            "url": absoluto(folheto),
            "partitura_url": absoluto(partitura) if partitura else None,
        })
    itens.sort(key=lambda i: i["data"])
    return itens


def main():
    pagina = baixar(PAGINA).decode("utf-8", "replace")
    itens = ler(pagina)
    if not itens:
        print("Nenhum folheto encontrado na página — mantendo o site anterior.")
        sys.exit(1)

    hoje = datetime.datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    os.makedirs(os.path.join(SITE, "pdf"), exist_ok=True)
    os.makedirs(os.path.join(SITE, "data"), exist_ok=True)

    lista = []
    for it in itens:
        dia = datetime.date.fromisoformat(it["data"])
        if dia < hoje - datetime.timedelta(days=60):
            continue
        it["arquivo"] = None
        it["partitura_arquivo"] = None
        # guarda uma cópia dos folhetos das últimas 2 semanas e dos próximos 4 meses
        if hoje - datetime.timedelta(days=14) <= dia <= hoje + datetime.timedelta(days=120):
            for chave_url, chave_arq in (("url", "arquivo"), ("partitura_url", "partitura_arquivo")):
                url = it[chave_url]
                if not url:
                    continue
                if chave_arq == "partitura_arquivo" and dia > hoje + datetime.timedelta(days=45):
                    continue
                nome = nome_arquivo(url)
                destino = os.path.join(SITE, "pdf", nome)
                try:
                    dados = baixar(url)
                    if len(dados) < 1000 or not dados.startswith(b"%PDF"):
                        raise ValueError("não parece um PDF")
                    with open(destino, "wb") as f:
                        f.write(dados)
                    it[chave_arq] = "pdf/" + nome
                    print(f"ok  {it['data']}  {nome}  ({len(dados) // 1024} KB)")
                except Exception as e:  # um PDF com problema não derruba o resto
                    print(f"ERRO {it['data']}  {url}: {e}")
        lista.append(it)

    agora = datetime.datetime.now(ZoneInfo("America/Sao_Paulo"))
    with open(os.path.join(SITE, "data", "folhetos.json"), "w", encoding="utf-8") as f:
        json.dump({"atualizado": agora.strftime("%d/%m/%Y %H:%M"), "folhetos": lista},
                  f, ensure_ascii=False, indent=1)
    print(f"{len(lista)} celebrações na lista")


if __name__ == "__main__":
    main()
