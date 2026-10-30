#!/usr/bin/env python3
"""Estúdio LandPG: transforma um roteiro JSON em artes prontas para o Instagram.

Uso:
  python3 _estudio/estudio.py roteiro.json pasta-de-saida/

Formatos (campo "formato" do roteiro):
  carrossel  -> 1.jpg, 2.jpg ... (1080x1350)
  imagem     -> 1.jpg (1080x1350)
  story      -> 1.jpg, 2.jpg ... (1080x1920)
  reel       -> reel.mp4 (1080x1920, 30 fps, com trilha) + capa.jpg
  story-video-> story.mp4 (1080x1920) + capa.jpg

Veja _estudio/LEIAME.md para os tipos de slide e exemplos.
"""
import base64, html, json, math, os, re, subprocess, sys, urllib.request, wave
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
FPS = 30

LOGO = ('<svg viewBox="0 0 512 512" fill="none"><g fill="#E2AA44" transform="translate(32 32) scale(0.57881137 0.45948718) translate(-240 -147)">'
        '<path d="M958 153C982 138 1009 153 1009 180V360C1009 407 991 433 953 454L626 630C602 643 583 658 569 674C570 630 554 599 520 575L429 520C391 497 391 446 432 420Z"/>'
        '<path d="M283 481L468 598C510 626 532 669 532 721V1045C532 1073 510 1085 486 1069L290 945C256 923 240 895 240 854V507C240 479 259 466 283 481Z"/>'
        '<path d="M965 544C990 529 1014 544 1014 574V845C1014 890 995 920 957 941L622 1120C596 1134 567 1116 567 1086V832C567 777 591 739 635 716Z"/></g></svg>')

# ícones de traço (24x24)
ICONES = {
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "x": '<path d="M6 6l12 12M18 6L6 18"/>',
    "alvo": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.2"/>',
    "relogio": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/>',
    "celular": '<rect x="6.5" y="2.5" width="11" height="19" rx="2.5"/><path d="M10.5 18.5h3"/>',
    "cursor": '<path d="M5 3l14 7-6 2-2 6z"/>',
    "grafico": '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    "estrela": '<path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z"/>',
    "raio": '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
    "olho": '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "chat": '<path d="M21 12a8 8 0 0 1-11.6 7.1L3 21l1.9-6A8 8 0 1 1 21 12z"/>',
    "cadeado": '<rect x="4.5" y="10.5" width="15" height="10.5" rx="2.5"/><path d="M8 10.5V7a4 4 0 0 1 8 0v3.5"/>',
    "camadas": '<path d="M12 3l9 5-9 5-9-5z"/><path d="M3 13l9 5 9-5"/>',
    "seta": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "dinheiro": '<rect x="2.5" y="6" width="19" height="12" rx="2.5"/><circle cx="12" cy="12" r="2.8"/>',
    "lupa": '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
    "pessoas": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M16 4.5a3.5 3.5 0 0 1 0 7M18 14a6.5 6.5 0 0 1 3.5 6"/>',
    "foguete": '<path d="M5 15c-1.5 1.5-2 5-2 5s3.5-.5 5-2"/><path d="M9 15l-3-3c2-6 7-9 14-9 0 7-3 12-9 14z"/><circle cx="15" cy="9" r="1.6"/>',
    "presente": '<rect x="3" y="8" width="18" height="5" rx="1"/><path d="M5 13v8h14v-8M12 8v13M12 8S10.5 3 8 3.8 9 8 12 8zm0 0s1.5-5 4-4.2S15 8 12 8z"/>',
}
CURSOR = ('<svg class="cursor" viewBox="0 0 32 32"><path d="M6 3l20 11-8.5 2.3L13 25z" fill="#fff" stroke="#151619" '
          'stroke-width="2" stroke-linejoin="round"/></svg>')


def ico(nome, cls="ico"):
    corpo = ICONES.get(nome, ICONES["check"])
    svg = f'<svg viewBox="0 0 24 24">{corpo}</svg>'
    return f'<span class="{cls}">{svg}</span>' if cls else svg


def rico(txt):
    """Permite <em>, <b> e <br> no texto; escapa o resto."""
    txt = html.escape(str(txt), quote=False)
    for tag in ("em", "b", "br"):
        txt = txt.replace(f"&lt;{tag}&gt;", f"<{tag}>").replace(f"&lt;/{tag}&gt;", f"</{tag}>")
    return txt.replace("<br>", "<br>").replace("\n", "<br>")


def palavras(txt):
    """Quebra o título em palavras (para animar uma a uma), mantendo os destaques <em>."""
    out, i = [], 0
    for parte in re.split(r"(<em>.*?</em>|<br>|\n)", str(txt)):
        if not parte:
            continue
        if parte in ("<br>", "\n"):
            out.append("<br>"); continue
        em = parte.startswith("<em>")
        miolo = parte[4:-5] if em else parte
        if miolo[:1].isspace() and out:
            out.append(" ")
        for w in re.findall(r"\S+\s*", miolo):
            span = f'<span class="p" style="--i:{i}">{html.escape(w, quote=False)}</span>'
            out.append(f"<em>{span}</em>" if em else span)
            i += 1
    return "".join(out)


def e(d):
    return f'class="e" style="--d:{d}"'


# ---------------- tipos de slide ----------------

def s_capa(s):
    k = f'<div {e(0)}><div class="kicker">{rico(s["kicker"])}</div></div>' if s.get("kicker") else ""
    c = f'<p class="corpo e" style="--d:.9">{rico(s["corpo"])}</p>' if s.get("corpo") else ""
    return f'{k}<h1 class="{s.get("tamanho","g")}">{palavras(s["titulo"])}</h1>{c}'


def s_texto(s):
    k = f'<div {e(0)}><div class="kicker">{rico(s["kicker"])}</div></div>' if s.get("kicker") else ""
    return (f'{k}<h1 class="{s.get("tamanho","")}">{palavras(s["titulo"])}</h1>'
            f'<p class="corpo e" style="--d:.7">{rico(s.get("corpo",""))}</p>')


def s_lista(s):
    itens = ""
    for n, it in enumerate(s["itens"]):
        if isinstance(it, str):
            it = {"texto": it}
        sub = f'<small>{rico(it["sub"])}</small>' if it.get("sub") else ""
        cls = "item ruim" if it.get("ruim") else "item"
        itens += (f'<div class="{cls} e" style="--d:{.5 + n * .22:.2f}">{ico(it.get("icone","check"))}'
                  f'<div class="t">{rico(it["texto"])}{sub}</div></div>')
    k = f'<div {e(0)}><div class="kicker">{rico(s["kicker"])}</div></div>' if s.get("kicker") else ""
    return f'{k}<h1 class="m">{palavras(s["titulo"])}</h1><div class="lista">{itens}</div>'


def s_comparacao(s):
    def col(lado, cls, icone, d):
        li = "".join(f'<li>{ico(icone, None)}<span>{rico(t)}</span></li>' for t in lado["itens"])
        return f'<div class="col {cls} e" style="--d:{d}"><div class="rot">{rico(lado["rotulo"])}</div><ul>{li}</ul></div>'
    return (f'<h1 class="m">{palavras(s["titulo"])}</h1><div class="comp">'
            f'{col(s["esquerda"], "", "x", .5)}{col(s["direita"], "boa", "check", .8)}</div>')


def _pagina(p, pinos=True, cursor=True):
    pin1 = '<span class="pino" style="--d:1.0;right:-18px;top:-30px">1</span>' if pinos else ""
    pin2 = '<span class="pino" style="--d:1.3;right:-30px;top:-26px">2</span>' if pinos else ""
    cur = (f'<span style="--d:1.4;position:absolute;left:72%;top:58%">{CURSOR}</span>' if cursor else "")
    prova = "".join(f"<span>{rico(x)}</span>" for x in p.get("prova", []))
    hero = '<div class="hero"><i></i><i></i><i></i></div>' if p.get("hero", True) else ""
    return (f'<div class="pg">{hero}<div class="mlogo"><span></span>{rico(p.get("marca","Sua marca"))}</div>'
            f'<div style="position:relative"><h3>{rico(p["titulo"])}</h3>{pin1}</div>'
            f'<p>{rico(p.get("sub",""))}</p>'
            f'<div style="position:relative;display:inline-block"><span class="btn">{rico(p.get("botao","Quero agora"))} →</span>{pin2}{cur}</div>'
            f'<div class="prova">{prova}</div></div>')


def s_mockup(s):
    p = s["pagina"]
    notas = "".join(f'<div class="nota"><b>{n + 1}</b>{rico(t)}</div>' for n, t in enumerate(s.get("notas", [])))
    tem_pinos = bool(s.get("notas"))
    return (f'<h1 class="m">{palavras(s["titulo"])}</h1>'
            f'<div class="mock e" style="--d:.5"><div class="barra"><i></i><i></i><i></i>'
            f'<div class="url">{html.escape(p.get("url","seunegocio.landpg.me"))}</div></div>'
            f'{_pagina(p, tem_pinos)}</div><div class="notas e" style="--d:1.6">{notas}</div>')


def s_celular(s):
    k = f'<div {e(0)}><div class="kicker">{rico(s["kicker"])}</div></div>' if s.get("kicker") else ""
    return (f'{k}<h1 class="m" style="text-align:center">{palavras(s["titulo"])}</h1>'
            f'<div class="cel e" style="--d:.5"><div class="tela-cel"><div class="ilha"></div>'
            f'{_pagina(s["pagina"], False)}</div></div>')


def s_dado(s):
    return (f'<div class="numero e" style="--d:0">{rico(s["numero"])}</div>'
            f'<h2 style="margin-top:30px">{palavras(s["titulo"])}</h2>'
            f'<p class="corpo e" style="--d:.8">{rico(s.get("corpo",""))}</p>')


def s_cta(s):
    k = f'<div {e(0)}><div class="kicker">{rico(s.get("kicker","Lista de espera aberta"))}</div></div>'
    c = f'<p class="corpo e" style="--d:.7">{rico(s["corpo"])}</p>' if s.get("corpo") else ""
    return (f'{k}<h1>{palavras(s["titulo"])}</h1>{c}'
            f'<div class="botao e" style="--d:1.0">{rico(s.get("botao","landpg.me"))}{ico("seta", None)}</div>'
            f'<div class="selo e" style="--d:1.3">{rico(s.get("selo","Link na bio · é grátis entrar"))}</div>')


def s_contagem(s):
    blocos = "".join(f'<div><b>{rico(v)}</b><span>{rico(r)}</span></div>' for v, r in s["blocos"])
    k = f'<div {e(0)}><div class="kicker">{rico(s.get("kicker","Contagem regressiva"))}</div></div>'
    c = f'<p class="corpo e" style="--d:1.1">{rico(s["corpo"])}</p>' if s.get("corpo") else ""
    return f'{k}<h1 class="m">{palavras(s["titulo"])}</h1><div class="contagem e" style="--d:.6">{blocos}</div>{c}'


def s_foto(s):
    # o fundo é tratado em montar_tela(); aqui só o texto
    return s_capa(s)


TIPOS = dict(capa=s_capa, texto=s_texto, lista=s_lista, comparacao=s_comparacao, mockup=s_mockup,
             celular=s_celular, dado=s_dado, cta=s_cta, contagem=s_contagem, foto=s_foto)


# ---------------- montagem das telas ----------------

def fundo(foto=None):
    f = f'<div class="foto" style="background-image:url(\'{foto}\')"></div>' if foto else ""
    return f'{f}<div class="brilho"></div><div class="brilho b2"></div><div class="grade"></div><div class="grao"></div><div class="moldura"></div>'


def topo(contador=""):
    return f'<div class="topo"><div class="marca">{LOGO}LandPG</div><div class="contador">{contador}</div></div>'


def rodape(n, total, formato):
    ultimo = n == total
    if formato == "carrossel":
        acao = "landpg.me" if ultimo else "arraste →"
        pts = "".join(f'<i class="{"on" if k == n else ""}"></i>' for k in range(1, total + 1))
        return f'<div class="rodape"><span class="arroba">@landpg.me</span><div class="pontos">{pts}</div><span class="acao">{acao}</span></div>'
    return f'<div class="rodape"><span class="arroba">@landpg.me</span><span class="acao">landpg.me</span></div>'


def miolo(s):
    tipo = s.get("tipo", "texto")
    if tipo not in TIPOS:
        sys.exit(f"Tipo de slide desconhecido: {tipo}. Use um destes: {', '.join(TIPOS)}")
    agua = f'<div class="marca-agua">{html.escape(s["marca_agua"])}</div>' if s.get("marca_agua") else ""
    return agua + f'<div class="conteudo">{TIPOS[tipo](s)}</div>'


def pagina(corpo, alta, anim=False, extra_css=""):
    css = (AQUI / "base.css").as_uri()
    return (f'<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="{css}">'
            f'<style>{extra_css}</style></head><body class="{"anim" if anim else ""}">{corpo}</body></html>')


# ---------------- Gemini (imagens e narração) ----------------

def gemini(modelo, corpo):
    chave = os.environ.get("GEMINI_API_KEY")
    if not chave:
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
    req = urllib.request.Request(url, data=json.dumps(corpo).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "x-goog-api-key": chave})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            dados = json.load(r)
    except urllib.error.HTTPError as err:
        print(f"[gemini] erro {err.code}: {err.read()[:400].decode(errors='ignore')}", file=sys.stderr)
        return None
    for parte in dados.get("candidates", [{}])[0].get("content", {}).get("parts", []):
        if "inlineData" in parte:
            return base64.b64decode(parte["inlineData"]["data"])
    print("[gemini] resposta sem mídia", file=sys.stderr)
    return None


def gerar_imagem(prompt, destino, proporcao):
    modelo = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
    estilo = ("Fotografia editorial premium, luz suave e cinematográfica, tons escuros grafite com acentos dourados quentes, "
              "profundidade de campo rasa, sem texto, sem logotipos, sem marcas d'água. Cena: ")
    img = gemini(modelo, {"contents": [{"parts": [{"text": estilo + prompt}]}],
                          "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": proporcao}}})
    if img:
        Path(destino).write_bytes(img)
        return True
    return False


def gerar_narracao(texto, destino):
    modelo = os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")
    voz = os.environ.get("GEMINI_TTS_VOZ", "Charon")
    pcm = gemini(modelo, {"contents": [{"parts": [{"text": "Leia em português do Brasil, com tom confiante, próximo e animado, ritmo de Reels: " + texto}]}],
                          "generationConfig": {"responseModalities": ["AUDIO"],
                                               "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voz}}}}})
    if not pcm:
        return None
    with wave.open(str(destino), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)
    return len(pcm) / 2 / 24000


# ---------------- trilha sonora sintetizada (sem direitos autorais) ----------------

def trilha(duracao, cortes, destino, sr=44100):
    import numpy as np
    n = int(duracao * sr); t = np.arange(n) / sr
    bpm = 100; bat = 60 / bpm; compasso = bat * 4
    nota = lambda m: 440 * 2 ** ((m - 69) / 12)
    acordes = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]  # Lá m, Fá, Dó, Sol
    mix = np.zeros(n)
    for c in range(int(duracao / compasso) + 1):
        ini = c * compasso; acorde = acordes[c % 4]
        a, b = int(ini * sr), min(n, int((ini + compasso + .6) * sr))
        if a >= n: break
        tt = t[a:b] - ini
        env = np.minimum(1, tt / .5) * np.exp(-tt * .35)
        for m in acorde:
            f = nota(m + 12)
            mix[a:b] += env * .05 * (np.sin(2 * np.pi * f * tt) + .3 * np.sin(2 * np.pi * f * 1.003 * tt) + .12 * np.sin(4 * np.pi * f * tt))
        mix[a:b] += env * .09 * np.sin(2 * np.pi * nota(acorde[0] - 12) * tt)  # baixo
        for k in range(8):  # arpejo suave em colcheias
            s0 = ini + k * bat / 2; s1 = int(s0 * sr)
            if s1 >= n: break
            m = acorde[[0, 1, 2, 1][k % 4]] + 24
            l = min(n - s1, int(.45 * sr)); tk = np.arange(l) / sr
            mix[s1:s1 + l] += .035 * np.exp(-tk * 7) * np.sin(2 * np.pi * nota(m) * tk)
    rng = np.random.default_rng(7)
    for k in range(int(duracao / bat)):  # batida leve
        s0 = int(k * bat * sr); l = min(n - s0, int(.35 * sr)); tk = np.arange(l) / sr
        if k >= 4:
            freq = 45 + 75 * np.exp(-tk * 30)
            mix[s0:s0 + l] += .22 * np.exp(-tk * 9) * np.sin(2 * np.pi * np.cumsum(freq) / sr)
        h0 = s0 + int(bat / 2 * sr); lh = min(n - h0, int(.06 * sr))
        if lh > 0 and k >= 2:
            ruido = np.diff(rng.standard_normal(lh + 1))
            mix[h0:h0 + lh] += .025 * np.exp(-np.arange(lh) / sr * 60) * ruido
    for c in cortes:  # "whoosh" nas trocas de cena
        a = int((c - .45) * sr); l = int(.6 * sr)
        if a < 0 or a + l > n: continue
        tk = np.arange(l) / sr; env = np.sin(np.pi * tk / .6) ** 2
        r = rng.standard_normal(l); r = np.convolve(r, np.ones(6) / 6, "same")
        mix[a:a + l] += .05 * env * r
    fade = int(1.2 * sr); mix[-fade:] *= np.linspace(1, 0, fade); mix[:int(.05 * sr)] *= np.linspace(0, 1, int(.05 * sr))
    mix = mix / (np.abs(mix).max() + 1e-9) * .55
    with wave.open(str(destino), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((mix * 32767).astype("<i2").tobytes())


# ---------------- renderização ----------------

def navegador():
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    exe = "/opt/pw-browsers/chromium"
    return pw, pw.chromium.launch(executable_path=exe if os.path.exists(exe) else None)


def foto_do_slide(s, saida, n, proporcao):
    if s.get("imagem"):
        p = Path(s["imagem"])
        return (p if p.is_absolute() else (RAIZ / p)).resolve().as_uri()
    if s.get("prompt_ia"):
        destino = saida / f"_ia_{n}.png"
        if destino.exists() or gerar_imagem(s["prompt_ia"], destino, proporcao):
            return destino.resolve().as_uri()
        print(f"[aviso] slide {n}: imagem por IA indisponível (sem GEMINI_API_KEY ou erro); usando fundo padrão.", file=sys.stderr)
    return None


def imagens(rot, saida, alta):
    slides = rot["slides"]; total = len(slides); formato = rot["formato"]
    pw, nav = navegador()
    pg = nav.new_page(viewport={"width": 1080, "height": 1920 if alta else 1350})
    feitos = []
    for n, s in enumerate(slides, 1):
        foto = foto_do_slide(s, saida, n, "9:16" if alta else "4:5")
        cont = f"<b>{n:02d}</b> / {total:02d}" if formato == "carrossel" and total > 1 else ""
        corpo = (f'<div class="tela {"alta" if alta else ""} {"tem-foto" if foto else ""}">{fundo(foto)}{topo(cont)}'
                 f'{miolo(s)}{rodape(n, total, formato)}</div>')
        arq = saida / "_tmp.html"; arq.write_text(pagina(corpo, alta), encoding="utf-8")
        pg.goto(arq.as_uri()); pg.evaluate("document.fonts.ready")
        destino = saida / f"{n}.jpg"
        pg.locator(".tela").screenshot(path=str(destino), type="jpeg", quality=93)
        feitos.append(destino)
    nav.close(); pw.stop(); (saida / "_tmp.html").unlink(missing_ok=True)
    return feitos


def video(rot, saida, nome):
    cenas = rot["cenas"]
    wav_voz = saida / "_voz.wav"; dur_voz = None
    if rot.get("narracao"):
        dur_voz = gerar_narracao(rot["narracao"], wav_voz)
        if dur_voz is None:
            print("[aviso] narração indisponível (sem GEMINI_API_KEY ou erro); o vídeo sai só com trilha.", file=sys.stderr)
    durs = [float(c.get("dur", 2.5)) for c in cenas]
    if dur_voz and dur_voz + 1.0 > sum(durs):  # estica a última cena para caber a voz
        durs[-1] += dur_voz + 1.0 - sum(durs)
    total = sum(durs)
    blocos, t0, cortes = [], 0.0, []
    for k, (c, d) in enumerate(zip(cenas, durs)):
        foto = foto_do_slide(c, saida, k + 1, "9:16")
        ultima = k == len(cenas) - 1
        blocos.append(f'<div class="cena {"ultima" if ultima else ""}" style="--t0:{t0:.3f};--fim:{t0 + d:.3f};--dur:{d:.3f}">'
                      f'<div class="dentro {"tem-foto" if foto else ""}">'
                      f'{f"<div class=foto style=background-image:url({chr(39)}{foto}{chr(39)})></div>" if foto else ""}{miolo(c)}</div></div>')
        t0 += d
        if not ultima: cortes.append(t0)
    corpo = (f'<div class="tela alta" style="--total:{total:.3f}">'
             f'<div class="brilho"></div><div class="brilho b2"></div><div class="grade"></div>'
             f'{"".join(blocos)}<div class="grao"></div><div class="moldura"></div>{topo()}'
             f'<div class="rodape"><span class="arroba">@landpg.me</span><span class="acao">landpg.me</span></div>'
             f'<div class="progresso"></div></div>')
    arq = saida / "_tmp.html"; arq.write_text(pagina(corpo, True, anim=True), encoding="utf-8")

    trilha(total, cortes, saida / "_trilha.wav")
    mp4 = saida / f"{nome}.mp4"; quadros = int(math.ceil(total * FPS))
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-",
                           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                           str(saida / "_mudo.mp4")], stdin=subprocess.PIPE)
    pw, nav = navegador()
    pg = nav.new_page(viewport={"width": 1080, "height": 1920})
    pg.goto(arq.as_uri()); pg.evaluate("document.fonts.ready")
    pg.evaluate("window.__ir = t => { for (const a of document.getAnimations()) { a.pause(); a.currentTime = t * 1000; } }")
    tela = pg.locator(".tela")
    capa_t = min(durs[0] - .2, 1.6)
    for q in range(quadros):
        t = q / FPS
        pg.evaluate(f"__ir({t})")
        jpg = tela.screenshot(type="jpeg", quality=92)
        ff.stdin.write(jpg)
        if abs(t - capa_t) < .5 / FPS:
            (saida / "capa.jpg").write_bytes(jpg)
    ff.stdin.close(); ff.wait(); nav.close(); pw.stop()

    # mixagem: trilha mais baixa quando há narração
    if dur_voz:
        filtro = ("[2:a]adelay=600|600,volume=1.6,asplit=2[v1][v2];[1:a]volume=0.4[m];"
                  "[m][v1]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=400[md];"
                  "[md][v2]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]")
        entradas = ["-i", str(saida / "_trilha.wav"), "-i", str(wav_voz)]
    else:
        filtro = "[1:a]volume=0.9,alimiter=limit=0.95[a]"
        entradas = ["-i", str(saida / "_trilha.wav")]
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(saida / "_mudo.mp4"), *entradas, "-filter_complex", filtro,
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
                    "-shortest", "-movflags", "+faststart", str(mp4)], check=True)
    for tmp in ("_tmp.html", "_mudo.mp4", "_trilha.wav", "_voz.wav"):
        (saida / tmp).unlink(missing_ok=True)
    return [mp4, saida / "capa.jpg"]


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    rot = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    saida = Path(sys.argv[2]).resolve(); saida.mkdir(parents=True, exist_ok=True)
    f = rot.get("formato")
    if f in ("carrossel", "imagem"):
        feitos = imagens(rot, saida, alta=False)
    elif f == "story":
        feitos = imagens(rot, saida, alta=True)
    elif f in ("reel", "story-video"):
        feitos = video(rot, saida, "reel" if f == "reel" else "story")
    else:
        sys.exit('Campo "formato" deve ser: carrossel, imagem, story, reel ou story-video')
    for x in feitos:
        print(x)


if __name__ == "__main__":
    main()
