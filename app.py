"""
ELLIOTT - IA ULTIME (Version Ultime)
Chat IA + Images + Voix + Musique + Vision + Code + Memoire Avancee + PWA + Recherche Web
Tout 100% Gratuit!
"""
from flask import Flask, request, Response, send_file, send_from_directory
import requests as _requests
import json as _json
import os
import sys
import time
import threading
import tempfile
import subprocess
import base64
import hashlib
import re
import shutil
from io import BytesIO
from datetime import datetime, timezone
from difflib import SequenceMatcher
from urllib.parse import quote
from dotenv import load_dotenv
load_dotenv()

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import textwrap

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_FILE = os.path.join(BASE_DIR, "memory.json")
GENERATED_DIR = os.path.join(BASE_DIR, "generated")
os.makedirs(GENERATED_DIR, exist_ok=True)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
CHAT_API_GROQ = "https://api.groq.com/openai/v1/chat/completions"
CHAT_API_KILOCODE = "https://api.kilo.ai/api/gateway/v1/chat/completions"
CHAT_MODELS_GROQ = ["llama-3.3-70b-versatile"]
CHAT_MODELS = [
    "kilo-auto/free",
    "nex-agi/nex-n2.5-pro:free",
]
CHAT_TIMEOUT = 25

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = "pNInz6obpgDQGcFmaJgB"
ELEVENLABS_MODEL = "eleven_multilingual_v2"

# =====================================================================
#  WEB SEARCH (Bing + GoogleNews RSS + Wikipedia)
# =====================================================================

def _bing_search(query, num_results=5):
    try:
        from bs4 import BeautifulSoup
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        r = _requests.get(
            f"https://www.bing.com/search?q={quote(query)}&setlang=fr&cc=FR&mkt=fr-FR",
            headers=headers,
            timeout=10,
        )
        soup = BeautifulSoup(r.content, "html.parser")
        results = []
        for li in soup.select("li.b_algo"):
            title_el = li.select_one("h2 a")
            snippet_el = li.select_one(".b_caption p, .b_algoSlug")
            if title_el:
                title_text = title_el.get_text(strip=True)
                if len(title_text) > 3:
                    results.append({
                        "title": title_text,
                        "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
                        "url": title_el.get("href", ""),
                    })
        return results[:num_results]
    except Exception as e:
        print(f"Bing error: {e}")
        return []


def _google_news_search(query, num_results=5):
    try:
        from bs4 import BeautifulSoup
        r = _requests.get(
            "https://news.google.com/rss/search",
            params={"q": query, "hl": "fr", "gl": "FR", "ceid": "FR:fr"},
            timeout=10,
        )
        soup = BeautifulSoup(r.content, "xml")
        results = []
        for item in soup.find_all("item"):
            title = item.find("title").text if item.find("title") else ""
            source = item.find("source").text if item.find("source") else ""
            link = item.find("link").text if item.find("link") else ""
            results.append({"title": title, "snippet": source, "url": link})
        return results[:num_results]
    except Exception as e:
        print(f"GoogleNews error: {e}")
        return []


def _wikipedia_summary(query):
    try:
        headers = {"User-Agent": "ELLIOTT/1.0 (assistant-ia; contact@elliott.ai)"}
        search_url = f"https://fr.wikipedia.org/w/api.php"
        params = {
            "action": "query", "list": "search", "srsearch": query,
            "format": "json", "srlimit": 1,
        }
        r = _requests.get(search_url, params=params, headers=headers, timeout=8)
        data = r.json()
        results = data.get("query", {}).get("search", [])
        if results:
            title = results[0]["title"].replace(" ", "_")
            r2 = _requests.get(
                f"https://fr.wikipedia.org/api/rest_v1/page/summary/{title}",
                headers=headers,
                timeout=8,
            )
            if r2.status_code == 200:
                d = r2.json()
                return {"title": d.get("title", ""), "snippet": d.get("extract", "")[:300], "url": d.get("content_urls", {}).get("desktop", {}).get("page", "")}
    except Exception as e:
        print(f"Wikipedia error: {e}")
    return None


def web_search(query, num_results=5):
    results = _google_news_search(query, num_results)
    if not results:
        results = _bing_search(query, num_results)
    wiki = _wikipedia_summary(query)
    if wiki and not any(wiki["title"].lower() in r["title"].lower() for r in results):
        results.insert(0, wiki)
    return results


def needs_web_search(message):
    search_keywords = [
        "actualite", "aujourd'hui", "cette semaine", "ce mois",
        "meteo", "cours de", "prix actuel", "derniere nouvelle",
        "qui a gagne", "resultat", "2026", "2027",
    ]
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in search_keywords)


# =====================================================================
#  MEMORY SYSTEM (Enhanced)
# =====================================================================
memory_lock = threading.Lock()


def _default_memory():
    return {
        "conversations": [],
        "conversation_summaries": [],
        "topics": {},
        "corrections": [],
        "knowledge_base": {},
        "preferences": {
            "response_style": "medium",
            "language": "fr",
            "favorite_topics": [],
        },
        "stats": {
            "total_conversations": 0,
            "total_messages": 0,
            "topics_learned": 0,
            "corrections_made": 0,
            "thumbs_up": 0,
            "thumbs_down": 0,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "images_generated": 0,
            "music_generated": 0,
            "code_executed": 0,
            "images_analyzed": 0,
            "searches_performed": 0,
            "quality_score_avg": 0.0,
        },
        "feedback": [],
        "quality_log": [],
    }


_memory_cache = None
_memory_dirty = False


def load_memory():
    global _memory_cache
    if _memory_cache is not None:
        return _memory_cache
    try:
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                m = _json.load(f)
            for k, v in _default_memory().items():
                if k not in m:
                    m[k] = v
            _memory_cache = m
            return m
    except Exception:
        pass
    _memory_cache = _default_memory()
    return _memory_cache


def save_memory(m):
    global _memory_cache, _memory_dirty
    _memory_cache = m
    with memory_lock:
        try:
            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                _json.dump(m, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Memory save error: {e}")


def get_memory():
    return load_memory()


def update_memory(update_fn):
    m = load_memory()
    update_fn(m)
    save_memory(m)
    return m


def extract_topics(text):
    topics = []
    keyword_map = {
        "python": "python", "javascript": "javascript", "js": "javascript",
        "html": "html", "css": "css", "react": "react", "node": "nodejs",
        "flask": "flask", "django": "django", "api": "api",
        "machine learning": "machine learning", "ml": "machine learning",
        "ia": "intelligence artificielle", "intelligence artificielle": "intelligence artificielle",
        "deep learning": "deep learning", "neural": "reseau neuronal",
        "image": "images", "photo": "images", "dessin": "images",
        "musique": "musique", "chanson": "musique",
        "video": "video", "film": "video",
        "code": "programmation", "programmer": "programmation", "coder": "programmation",
        "histoire": "ecriture", "ecrire": "ecriture", "texte": "ecriture",
        "maths": "mathematiques", "mathematiques": "mathematiques",
        "science": "sciences", "physique": "sciences",
        "artisanat": "artisanat", "tricot": "artisanat", "crochet": "artisanat",
        "couture": "artisanat", "bricolage": "artisanat",
        "cuisine": "cuisine", "recette": "cuisine",
        "sport": "sport", "fitness": "sport",
        "voyage": "voyage", "tourisme": "voyage",
        "sante": "sante", "medecin": "sante",
        "finance": "finance", "argent": "finance", "bourse": "finance",
    }
    text_lower = text.lower()
    for keyword, topic in keyword_map.items():
        if keyword in text_lower:
            topics.append(topic)
    return list(set(topics)) if topics else ["general"]


def track_topics(m, topics):
    for t in topics:
        if t in m["topics"]:
            m["topics"][t] += 1
        else:
            m["topics"][t] = 1
    m["stats"]["topics_learned"] = len(m["topics"])


def find_relevant_memory(m, message):
    context_parts = []
    relevant_corrections = []
    for corr in m.get("corrections", []):
        if SequenceMatcher(None, message.lower(), corr.get("original", "").lower()).ratio() > 0.4:
            relevant_corrections.append(corr)
    if relevant_corrections:
        context_parts.append("Corrections importantes du passe:")
        for c in relevant_corrections[-3:]:
            context_parts.append(
                f"- '{c.get('original', '')}' -> reponse corrigee: '{c.get('corrected', '')}'"
            )
    for kb_key, kb_val in m.get("knowledge_base", {}).items():
        if SequenceMatcher(None, message.lower(), kb_key.lower()).ratio() > 0.3:
            context_parts.append(f"Connaissance sur '{kb_key}': {kb_val}")
    recent = m.get("conversations", [])[-5:]
    if recent:
        context_parts.append("Conversations recentes:")
        for conv in recent:
            context_parts.append(f"Q: {conv.get('question', '')[:100]}")
            context_parts.append(f"R: {conv.get('answer', '')[:100]}")
    if m.get("preferences", {}).get("favorite_topics"):
        context_parts.append(
            f"Sujets preferes: {', '.join(m['preferences']['favorite_topics'][:5])}"
        )
    return "\n".join(context_parts) if context_parts else ""


def record_correction(m, original, corrected, conversation_id=""):
    m["corrections"].append({
        "original": original,
        "corrected": corrected,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "conversation_id": conversation_id,
    })
    m["stats"]["corrections_made"] = len(m["corrections"])


def record_knowledge(m, topic, info):
    m["knowledge_base"][topic] = info


def calculate_confidence(response_text):
    if not response_text or len(response_text.strip()) < 5:
        return 0.1
    uncertainty_markers = [
        "je ne suis pas sur", "peut-etre", "probablement",
        "il se pourrait", "je pense que", "pas certain",
        "i'm not sure", "maybe", "i think",
        "je ne sais pas", "aucune idee", "impossible de savoir",
    ]
    text_lower = response_text.lower()
    uncertainty_count = sum(1 for marker in uncertainty_markers if marker in text_lower)
    confidence = 1.0
    confidence -= uncertainty_count * 0.15
    if len(response_text) < 30:
        confidence -= 0.1
    if response_text.endswith("?"):
        confidence -= 0.05
    return max(0.1, min(1.0, confidence))


def calculate_quality(answer, topics):
    quality = 0.5
    if len(answer) > 100:
        quality += 0.1
    if len(answer) > 300:
        quality += 0.1
    if "```" in answer:
        quality += 0.1
    if any(m in answer for m in ["- ", "1.", "##", "**"]):
        quality += 0.05
    if len(topics) > 0 and "general" not in topics:
        quality += 0.1
    return min(1.0, quality)


def summarize_old_conversations(m):
    convs = m.get("conversations", [])
    if len(convs) <= 50:
        return
    old = convs[:-20]
    topics_summary = {}
    for c in old:
        for t in c.get("topics", []):
            topics_summary[t] = topics_summary.get(t, 0) + 1
    m["conversation_summaries"] = m.get("conversation_summaries", [])
    m["conversation_summaries"].append({
        "period": f"{old[0].get('timestamp', '')} - {old[-1].get('timestamp', '')}",
        "count": len(old),
        "topics": topics_summary,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    m["conversations"] = convs[-20:]


def semantic_search(message, conversations, max_results=5):
    results = []
    msg_words = set(message.lower().split())
    for conv in conversations:
        conv_text = (conv.get("question", "") + " " + conv.get("answer", "")).lower()
        conv_words = set(conv_text.split())
        if msg_words and conv_words:
            overlap = len(msg_words & conv_words)
            total = len(msg_words | conv_words)
            score = overlap / total if total > 0 else 0
            if message.lower() in conv_text:
                score += 0.5
            if score > 0.1:
                results.append((score, conv))
    results.sort(key=lambda x: x[0], reverse=True)
    return [r[1] for r in results[:max_results]]


# =====================================================================
#  MUSIC GENERATION
# =====================================================================
def generate_music(prompt):
    spaces_to_try = [
        ("facebook/MusicGen", "/predict_batched"),
    ]
    for space, api_name in spaces_to_try:
        try:
            from gradio_client import Client
            client = Client(space, verbose=False)
            melody_file = _create_tone_file()
            result = client.predict(
                texts=prompt,
                melodies=melody_file,
                api_name=api_name,
            )
            if result:
                src = result if isinstance(result, str) else (result[0] if isinstance(result, tuple) else None)
                if src and os.path.exists(str(src)):
                    ext = os.path.splitext(str(src))[1] or ".wav"
                    dest = os.path.join(GENERATED_DIR, f"music_{int(time.time())}{ext}")
                    shutil.copy2(str(src), dest)
                    return dest
        except Exception as e:
            print(f"MusicGen error ({space}): {e}")
            continue
    return _generate_procedural_music(prompt)


def _create_tone_file():
    import wave as _wave
    import math as _math
    import struct as _struct
    sr = 44100
    dur = 3
    freq = 440
    filename = os.path.join(tempfile.gettempdir(), "melody_tone.wav")
    with _wave.open(filename, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        for i in range(int(sr * dur)):
            v = int(32767 * 0.3 * _math.sin(2 * _math.pi * freq * i / sr))
            w.writeframes(_struct.pack("<h", v))
    return filename


def _generate_procedural_music(prompt):
    import wave as _wave
    import math as _math
    import struct as _struct
    try:
        sr = 44100
        duration = 10
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()
        seed_val = int(prompt_hash[:8], 16) % 1000
        base_freq = 220 + (seed_val % 440)
        tempo = 2 + (seed_val % 6)
        filename = os.path.join(GENERATED_DIR, f"music_{int(time.time())}.wav")
        with _wave.open(filename, "w") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            for i in range(int(sr * duration)):
                t = i / sr
                freq1 = base_freq * (1 + 0.5 * _math.sin(2 * _math.pi * tempo * t))
                freq2 = base_freq * 1.5 * (1 + 0.3 * _math.sin(2 * _math.pi * (tempo * 0.7) * t))
                freq3 = base_freq * 2 * (1 + 0.2 * _math.sin(2 * _math.pi * (tempo * 1.3) * t))
                envelope = _math.sin(_math.pi * t / duration)
                val = (
                    0.3 * _math.sin(2 * _math.pi * freq1 * t) +
                    0.15 * _math.sin(2 * _math.pi * freq2 * t) +
                    0.1 * _math.sin(2 * _math.pi * freq3 * t)
                ) * envelope
                sample = int(32767 * max(-1, min(1, val)))
                w.writeframes(_struct.pack("<h", sample))
        return filename
    except Exception as e:
        print(f"Procedural music error: {e}")
        return None


# =====================================================================
#  VISION / IMAGE ANALYSIS
# =====================================================================
def analyze_image_url(url):
    try:
        r = _requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            return "Impossible de charger l'image."
        content_type = r.headers.get("content-type", "")
        is_img = "image" in content_type or any(
            url.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"]
        )
        if not is_img:
            return "L'URL ne pointe pas vers une image."
        info = ""
        try:
            from PIL import Image
            img = Image.open(BytesIO(r.content))
            info = f"Image {img.format}, {img.size[0]}x{img.size[1]} pixels, mode {img.mode}"
            if img.mode == "RGB":
                img_small = img.resize((50, 50))
                pixels = list(img_small.getdata())
                avg_r = sum(p[0] for p in pixels) // len(pixels)
                avg_g = sum(p[1] for p in pixels) // len(pixels)
                avg_b = sum(p[2] for p in pixels) // len(pixels)
                info += f", couleur dominante: rgb({avg_r},{avg_g},{avg_b})"
        except Exception:
            info = f"Image chargee ({len(r.content)} octets)"
        b64 = base64.b64encode(r.content).decode("utf-8")
        ai_desc = _describe_image_with_ai(b64, content_type)
        return ai_desc if ai_desc else info
    except Exception as e:
        return f"Erreur d'analyse: {str(e)}"


def analyze_image_b64(data_url):
    try:
        if "," in data_url:
            header, b64data = data_url.split(",", 1)
        else:
            header = "data:image/png;base64"
            b64data = data_url
        content_type = "image/png"
        if "jpeg" in header or "jpg" in header:
            content_type = "image/jpeg"
        img_bytes = base64.b64decode(b64data)
        info = ""
        try:
            from PIL import Image
            img = Image.open(BytesIO(img_bytes))
            info = f"Image {img.format}, {img.size[0]}x{img.size[1]} pixels"
        except Exception:
            info = f"Image chargee ({len(img_bytes)} octets)"
        ai_desc = _describe_image_with_ai(b64data, content_type)
        return ai_desc if ai_desc else info
    except Exception as e:
        return f"Erreur d'analyse: {str(e)}"


def _describe_image_with_ai(base64_image, content_type):
    for model in CHAT_MODELS:
        try:
            messages = [
                {"role": "system", "content": "Tu es un assistant IA expert en vision par ordinateur. Tu decris les images en detail en francais. Sois precis et descriptif."},
                {"role": "user", "content": [
                    {"type": "text", "text": "Decris cette image en detail en francais: qu'est-ce qu'on voit, les couleurs, les objets, l'ambiance?"},
                    {"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{base64_image}"}}
                ]}
            ]
            r = _requests.post(
                CHAT_API_KILOCODE,
                json={"model": model, "messages": messages, "max_tokens": 500, "temperature": 0.5},
                timeout=30,
            )
            if r.status_code == 200:
                data = r.json()
                if "choices" in data and data["choices"]:
                    content = data["choices"][0].get("message", {}).get("content", "")
                    if content and len(content.strip()) > 10:
                        return content
        except Exception:
            continue
    return None


# =====================================================================
#  CODE EXECUTOR
# =====================================================================
BLOCKED_KEYWORDS = [
    "os.system", "subprocess", "shutil.rmtree", "__import__('os')",
    "__import__(\"os\")", "eval(", "execfile", "compile(",
    "import ctypes", "import socket", "import multiprocessing",
]


def execute_python_code(code, timeout=10):
    if len(code) > 10000:
        return {"error": "Code trop long (max 10000 caracteres)"}
    code_lower = code.lower()
    for kw in BLOCKED_KEYWORDS:
        if kw.lower() in code_lower:
            return {"error": f"Commande non autorisee detectee: {kw}"}
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=tempfile.gettempdir(),
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"},
        )
        return {
            "stdout": result.stdout[-5000:] if result.stdout else "",
            "stderr": result.stderr[-2000:] if result.stderr else "",
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Timeout: le code a depasse {timeout} secondes"}
    except Exception as e:
        return {"error": str(e)}


# =====================================================================
#  CHAT API
# =====================================================================
def chat_ia(message, history, memory_context="", web_context="", voice_mode=False):
    if voice_mode:
        system = (
            "Tu es ELLIOTT, un assistant IA vocal intelligent et conversationnel. "
            "Tu reponds toujours en francais. Tu parles comme un ami intelligent, pas comme un robot. "
            "IMPORTANT: Quand on te parle a voix, reponds de facon COURTE et NATURELLE (1-3 phrases). "
            "Jamais de markdown, pas de listes a puces, pas de codes. "
            "Sois chaleureux, direct, et utile. Tu peux: expliquer, conseiller, raconter, rechercher. "
            "Tu t'adaptes a l'humeur de l'utilisateur. Sois precis mais concis."
        )
    else:
        system = (
            "Tu es ELLIOTT, un assistant IA super intelligent, polyvalent et serviable. "
            "Tu reponds toujours en francais. Tu es expert en: programmation, technologie, "
            "sciences, art, musique, creation, artisanat, cuisine, et bien plus. "
            "Tu peux: coder, expliquer, creer, ecrire, traduire, analyser, conseiller. "
            "Tu es creatif, precis et amical. Tu reponds en markdown avec du code formate. "
            "Tu t'adaptes au style de l'utilisateur. "
            "Quand tu recois des resultats de recherche web, integre-les dans ta reponse de facon naturelle et utile."
        )
    if memory_context:
        system += f"\n\nContexte memoire (souviens-toi de ceci pour repondre mieux):\n{memory_context}"
    if web_context:
        system += web_context

    messages = [{"role": "system", "content": system}]
    for msg in history[-10:]:
        messages.append(msg)
    messages.append({"role": "user", "content": message})

    max_tok = 200 if voice_mode else 1024

    if GROQ_API_KEY:
        try:
            r = _requests.post(
                CHAT_API_GROQ,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                json={"model": CHAT_MODELS_GROQ[0], "messages": messages, "max_tokens": max_tok, "temperature": 0.7},
                timeout=15,
            )
            if r.status_code == 200:
                data = r.json()
                content = data["choices"][0]["message"]["content"]
                if content and len(content.strip()) > 0:
                    return content
        except Exception as e:
            print(f"Groq error: {e}")

    for model in CHAT_MODELS:
        try:
            r = _requests.post(
                CHAT_API_KILOCODE,
                json={"model": model, "messages": messages, "max_tokens": max_tok, "temperature": 0.7},
                timeout=CHAT_TIMEOUT,
            )
            if r.status_code == 200:
                data = r.json()
                if "choices" in data and data["choices"]:
                    content = data["choices"][0]["message"]["content"]
                    if content and len(content.strip()) > 0:
                        return content
        except Exception as e:
            print(f"KiloCode error ({model}): {e}")

    return "Je suis temporairement indisponible. Verifiez votre connexion internet."


def generate_image(prompt):
    try:
        encoded = _requests.utils.quote(prompt)
        return (
            f"https://image.pollinations.ai/prompt/{encoded}"
            "?width=1024&height=768&nologo=true"
        )
    except Exception as e:
        print(f"Image error: {e}")
        return None


def _generate_tts(text):
    try:
        clean = text.replace("\n", " ").replace("#", "").replace("*", "").replace("`", "")
        clean = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', clean)[:500]
        if len(clean) < 2:
            return None

        audio_id = hashlib.md5(clean.encode()).hexdigest()[:12]
        audio_path = os.path.join(GENERATED_DIR, f"el_{audio_id}.mp3")

        if os.path.exists(audio_path):
            return f"/generated/el_{audio_id}.mp3"

        if ELEVENLABS_API_KEY:
            try:
                url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
                headers = {
                    "xi-api-key": ELEVENLABS_API_KEY,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg",
                }
                payload = {
                    "text": clean,
                    "model_id": ELEVENLABS_MODEL,
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
                }
                r = _requests.post(url, json=payload, headers=headers, timeout=20)
                if r.status_code == 200 and len(r.content) > 1000:
                    with open(audio_path, "wb") as f:
                        f.write(r.content)
                    return f"/generated/el_{audio_id}.mp3"
                else:
                    print(f"ElevenLabs error {r.status_code}: {r.text[:300]}")
            except Exception as e:
                print(f"ElevenLabs error: {e}")

        fallback_path = os.path.join(GENERATED_DIR, f"tts_{audio_id}.mp3")
        gurl = f"https://translate.google.com/translate_tts?ie=UTF-8&q={quote(clean)}&tl=fr&client=tw-ob"
        gheaders = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r2 = _requests.get(gurl, headers=gheaders, timeout=10)
        if r2.status_code == 200 and len(r2.content) > 1000:
            with open(fallback_path, "wb") as f:
                f.write(r2.content)
            return f"/generated/tts_{audio_id}.mp3"

    except Exception as e:
        print(f"TTS gen error: {e}")
    return None


# =====================================================================
#  FAST RESPONSES
# =====================================================================
FAST_RESPONSES = {
    "bonjour": {
        "text": (
            "Bonjour! Je suis **ELLIOTT**, votre assistant IA ultime. Je peux:\n\n"
            "- **Coder** dans toutes les langages\n"
            "- **Generer des images** et de la **musique**\n"
            "- **Analyser des images** avec la vision IA\n"
            "- **Executer du code** Python\n"
            "- **Rechercher** sur le web\n"
            "- **Expliquer** n'importe quel sujet\n"
            "- **Ecrire** des histoires, articles\n"
            "- **Apprendre** de nos conversations\n\n"
            "Que puis-je faire pour vous?"
        ),
        "speak": "Bonjour! Je suis ELLIOTT, votre assistant IA.",
    },
    "salut": {
        "text": "Salut! Je suis **ELLIOTT**. Comment puis-je vous aider aujourd'hui?",
        "speak": "Salut! Je suis ELLIOTT.",
    },
    "merci": {
        "text": "Avec plaisir! N'hesitez pas si vous avez d'autres questions.",
        "speak": "Avec plaisir!",
    },
    "qui es tu": {
        "text": (
            "Je suis **ELLIOTT**, un assistant IA revolutionnaire!\n\n"
            "- Je **recherche** sur le web en temps reel\n"
            "- Je **genere** de la musique et des images\n"
            "- Je **分析** les images avec la vision IA\n"
            "- Je **execute** du code Python\n"
            "- Je **'apprends** de nos conversations\n"
            "- Je **retiens** vos preferences\n\n"
            "100% gratuit, 100% pour vous!"
        ),
        "speak": "Je suis ELLIOTT, votre assistant IA revolutionnaire.",
    },
}

FAST_KEYS = sorted(FAST_RESPONSES.keys(), key=len, reverse=True)
_WORD_INDEX = {}
for _key in FAST_RESPONSES:
    for _word in _key.split():
        _WORD_INDEX.setdefault(_word, []).append(_key)


def get_fast_response(message):
    resp = FAST_RESPONSES.get(message)
    if resp is not None:
        return resp
    words = message.split()
    if len(words) <= 3:
        for key in FAST_KEYS:
            if key in message:
                return FAST_RESPONSES[key]
    for word in words:
        if len(words) <= 3:
            candidates = _WORD_INDEX.get(word)
            if candidates:
                return FAST_RESPONSES[max(candidates, key=len)]
    return None


# =====================================================================
#  IMAGE DETECTION
# =====================================================================
IMAGE_PATTERNS = [
    "generer une image", "generer image", "genere une image", "genere image",
    "creer une image", "creer image", "cree une image", "cree image",
    "create an image", "make an image", "generate an image",
    "une image de", "une image d'un", "une image d'une",
    "image de", "image d'un", "image d'une",
    "photo de", "photo d'un", "photo d'une",
    "dessin de", "dessin d'un", "dessin d'une",
    "illustration de", "illustration d'un",
    "peins moi", "dessine moi", "montre moi une image",
]


def is_image_request(message):
    msg = message.lower().strip()
    for pat in IMAGE_PATTERNS:
        if pat in msg:
            return True
    return False


def extract_image_prompt(message):
    msg = message.lower().strip()
    for pat in sorted(IMAGE_PATTERNS, key=len, reverse=True):
        if pat in msg:
            idx = msg.index(pat) + len(pat)
            rest = message[idx:].strip()
            for prefix in [" de ", " d'un ", " d'une ", " d'"]:
                rest = rest.replace(prefix, " ", 1)
            for prefix in ["de ", "d'un ", "d'une ", "d'"]:
                if rest.startswith(prefix):
                    rest = rest[len(prefix):]
            rest = rest.strip().strip("'").strip('"').strip(".")
            if len(rest) >= 2:
                return rest
    return message.strip()


# =====================================================================
#  MUSIC DETECTION
# =====================================================================
MUSIC_PATTERNS = [
    "generer une musique", "generer de la musique", "genere une musique",
    "creer une musique", "creer de la musique", "cree une musique",
    "compose une musique", "compose de la musique",
    "generer une chanson", "creer une chanson",
    "je veux de la musique", "j'aimerais de la musique",
    "musique pour", "chanson pour", "melodie pour",
]


def is_music_request(message):
    msg = message.lower().strip()
    for pat in MUSIC_PATTERNS:
        if pat in msg:
            return True
    return False


def extract_music_prompt(message):
    msg = message.lower().strip()
    for pat in sorted(MUSIC_PATTERNS, key=len, reverse=True):
        if pat in msg:
            idx = msg.index(pat) + len(pat)
            rest = message[idx:].strip()
            for prefix in [" de ", " d'un ", " d'une ", " d'"]:
                rest = rest.replace(prefix, " ", 1)
            for prefix in ["de ", "d'un ", "d'une ", "d'"]:
                if rest.startswith(prefix):
                    rest = rest[len(prefix):]
            rest = rest.strip().strip("'").strip('"').strip(".")
            if len(rest) >= 2:
                return rest
    return message.strip() if message.strip() else "calm ambient music"


# =====================================================================
#  CONVERSATION STORE
# =====================================================================
conversations = {}


# =====================================================================
#  CORRECTION DETECTION
# =====================================================================
CORRECTION_PATTERNS = [
    "c'est faux", "c'est incorrect", "non", "pas du tout",
    "c'est pas ca", "c'est pas vrai", "c'est faux",
    "tu as tort", "c'est mal", "faux",
    "correction", "en fait c'est", "en realite",
]


def is_correction(message):
    msg = message.lower().strip()
    for pat in CORRECTION_PATTERNS:
        if pat in msg:
            return True
    return False


# =====================================================================
#  PWA ICONS GENERATION
# =====================================================================
def generate_pwa_icons():
    try:
        from PIL import Image, ImageDraw, ImageFont
        for size in [192, 512]:
            img = Image.new("RGB", (size, size), (99, 102, 241))
            draw = ImageDraw.Draw(img)
            try:
                font = ImageFont.truetype("arial.ttf", size // 2)
            except Exception:
                font = ImageFont.load_default()
            bbox = draw.textbbox((0, 0), "E", font=font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            draw.text(((size - w) // 2, (size - h) // 2 - bbox[1]), "E", fill="white", font=font)
            img.save(os.path.join(GENERATED_DIR, f"icon-{size}.png"))
        print("PWA icons generated.")
    except Exception as e:
        print(f"Icon generation error: {e}")


# =====================================================================
#  CHART GENERATION
# =====================================================================
CHART_KEYWORDS = [
    "graphique", "chart", "graph", "diagramme", "courbe",
    "histogramme", "camembert", "barres", "courbe",
    "visualisation", "stats", "statistiques",
]


def is_chart_request(message):
    msg = message.lower().strip()
    return any(kw in msg for kw in CHART_KEYWORDS)


def generate_chart(prompt):
    try:
        prompt_lower = prompt.lower()
        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(8, 5))
        fig.patch.set_facecolor('#0f0f15')
        ax.set_facecolor('#0f0f15')

        if any(w in prompt_lower for w in ["camembert", "pie", "cercle"]):
            labels = ['Produits A', 'Produits B', 'Produits C', 'Produits D', 'Autres']
            sizes = [35, 25, 20, 12, 8]
            colors = ['#6366f1', '#a855f7', '#3b82f6', '#22c55e', '#f97316']
            explode = (0.05, 0.05, 0.05, 0.05, 0.05)
            wedges, texts, autotexts = ax.pie(
                sizes, labels=labels, autopct='%1.1f%%',
                startangle=90, colors=colors, explode=explode,
                textprops={'color': 'white', 'fontsize': 11}
            )
            for t in autotexts:
                t.set_fontsize(10)
            ax.set_title('Repartition des donnees', color='white', fontsize=14, fontweight='bold')
        elif any(w in prompt_lower for w in ["courbe", "line", "tendance", "evolution"]):
            months = ['Jan', 'Fev', 'Mar', 'Avr', 'Mai', 'Jun', 'Jul', 'Aou', 'Sep', 'Oct', 'Nov', 'Dec']
            data = [45, 62, 55, 78, 82, 91, 87, 95, 88, 102, 110, 118]
            ax.plot(months, data, color='#6366f1', linewidth=2.5, marker='o', markersize=6, markerfacecolor='#a855f7')
            ax.fill_between(range(len(months)), data, alpha=0.15, color='#6366f1')
            ax.set_title('Evolution temporelle', color='white', fontsize=14, fontweight='bold')
            ax.set_ylabel('Valeur', color='#8888aa', fontsize=11)
            ax.tick_params(colors='#8888aa')
            ax.grid(True, alpha=0.2, color='#333355')
        else:
            categories = ['Ventes\nQ1', 'Ventes\nQ2', 'Ventes\nQ3', 'Ventes\nQ4']
            values = [234, 312, 278, 395]
            colors_bar = ['#6366f1', '#a855f7', '#3b82f6', '#22c55e']
            bars = ax.bar(categories, values, color=colors_bar, width=0.6, edgecolor='none')
            for bar, val in zip(bars, values):
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 8,
                        str(val), ha='center', va='bottom', color='white', fontweight='bold', fontsize=12)
            ax.set_title('Diagramme en barres', color='white', fontsize=14, fontweight='bold')
            ax.set_ylabel('Valeur', color='#8888aa', fontsize=11)
            ax.tick_params(colors='#8888aa')
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['left'].set_color('#333355')
            ax.spines['bottom'].set_color('#333355')
            ax.grid(True, axis='y', alpha=0.15, color='#333355')

        plt.tight_layout()
        filename = f"chart_{int(time.time())}.png"
        filepath = os.path.join(GENERATED_DIR, filename)
        fig.savefig(filepath, dpi=150, facecolor=fig.get_facecolor(), edgecolor='none', bbox_inches='tight')
        plt.close(fig)
        return f"/generated/{filename}"
    except Exception as e:
        print(f"Chart error: {e}")
        plt.close('all')
        return None


# =====================================================================
#  PDF / DOCUMENT ANALYSIS
# =====================================================================
def extract_pdf_text(pdf_bytes):
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text_parts.append(t)
        return "\n\n".join(text_parts)
    except ImportError:
        pass
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(BytesIO(pdf_bytes))
        text_parts = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
        return "\n\n".join(text_parts)
    except ImportError:
        pass
    return None


def analyze_document_b64(data_url):
    try:
        if "," in data_url:
            header, b64data = data_url.split(",", 1)
        else:
            b64data = data_url
        pdf_bytes = base64.b64decode(b64data)
        text = extract_pdf_text(pdf_bytes)
        if not text:
            return None, "Impossible d'extraire le texte du PDF."
        preview = text[:3000]
        summary = None
        for model in CHAT_MODELS:
            try:
                r = _requests.post(
                    CHAT_API_KILOCODE,
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": "Tu es un assistant expert en analyse de documents. Resume et analyse le texte suivant en francais."},
                            {"role": "user", "content": f"Analyse et resume ce document:\n\n{preview}"},
                        ],
                        "max_tokens": 800,
                        "temperature": 0.5,
                    },
                    timeout=30,
                )
                if r.status_code == 200:
                    data = r.json()
                    if "choices" in data and data["choices"]:
                        summary = data["choices"][0].get("message", {}).get("content", "")
                        if summary and len(summary.strip()) > 20:
                            break
            except Exception:
                continue
        return text, summary
    except Exception as e:
        return None, f"Erreur: {str(e)}"


# =====================================================================
#  HTML TEMPLATE
# =====================================================================
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>ELLIOTT - IA Ultime</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🧠</text></svg>">
<meta name="theme-color" content="#6366f1">
<meta name="description" content="ELLIOTT - Assistant IA ultime: Chat, Images, Musique, Vision, Code">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="ELLIOTT">
<link rel="manifest" href="/manifest.json">
<link rel="apple-touch-icon" href="/icon/192.png">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{padding-top:env(safe-area-inset-top);padding-bottom:env(safe-area-inset-bottom)}
:root{
  --bg:#08080f;--bgc:#111118;--bgh:#1c1c2a;--bd:#252538;
  --tx:#eeeef5;--txd:#7b7b95;--txdd:#55556e;
  --ac:#7c5cfc;--ach:#9f7fff;--acg:rgba(124,92,252,.15);
  --bl:#3b82f6;--gn:#22c55e;--rd:#ef4444;--pp:#c084fc;
  --or:#f59e0b;--cy:#06b6d4;
  --r:12px;--r2:16px;
  --glow:0 0 24px rgba(124,92,252,.35);
  --glow-sm:0 0 12px rgba(124,92,252,.2);
}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",sans-serif;background:var(--bg);color:var(--tx);min-height:100vh;display:flex;overflow:hidden}
::selection{background:var(--ac);color:#fff}
::-webkit-scrollbar{width:5px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--bd);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:var(--txdd)}

.sidebar{width:280px;background:var(--bgc);border-right:1px solid var(--bd);display:flex;flex-direction:column;height:100vh;position:fixed;left:0;top:0;z-index:10;transition:transform .3s}
.sidebar-header{padding:20px;border-bottom:1px solid var(--bd)}
.logo{display:flex;align-items:center;gap:12px}
.logo-icon{width:44px;height:44px;background:linear-gradient(135deg,var(--ac),var(--pp));border-radius:12px;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:16px;color:#fff;box-shadow:var(--glow-sm)}
.logo-text{font-size:18px;font-weight:700;background:linear-gradient(135deg,var(--ac),var(--pp));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.logo-sub{font-size:11px;color:var(--txd);margin-top:2px}
.menu{flex:1;padding:12px;overflow-y:auto}
.menu-title{font-size:10px;font-weight:600;color:var(--txdd);text-transform:uppercase;letter-spacing:1px;padding:8px 12px;margin-top:8px}
.menu-item{display:flex;align-items:center;gap:10px;padding:10px 14px;border-radius:var(--r);cursor:pointer;transition:all .2s;color:var(--txd);font-size:13px;font-weight:500;border:1px solid transparent}
.menu-item:hover{background:var(--acg);color:var(--tx);border-color:rgba(99,102,241,.2)}
.menu-item.active{background:var(--acg);color:var(--ac);border-color:rgba(99,102,241,.3);box-shadow:var(--glow-sm)}
.menu-item svg{width:18px;height:18px;flex-shrink:0}
.sidebar-footer{padding:14px;border-top:1px solid var(--bd)}
.status{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--gn)}
.status-dot{width:7px;height:7px;background:var(--gn);border-radius:50%;animation:pulse 2s infinite;box-shadow:0 0 6px var(--gn)}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}

.main{flex:1;margin-left:280px;display:flex;flex-direction:column;height:100vh}
.header{padding:14px 24px;border-bottom:1px solid var(--bd);display:flex;align-items:center;justify-content:space-between;background:rgba(15,15,21,.8);backdrop-filter:blur(20px);position:sticky;top:0;z-index:5}
.header-left{display:flex;align-items:center;gap:12px}
.header-title{font-size:15px;font-weight:600}
.header-subtitle{font-size:11px;color:var(--txd)}
.header-actions{display:flex;gap:6px;align-items:center}
.header-btn{width:34px;height:34px;border-radius:8px;border:1px solid var(--bd);background:transparent;color:var(--txd);cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .2s}
.header-btn:hover{background:var(--acg);color:var(--ac);border-color:rgba(99,102,241,.3)}
.header-btn.active{background:var(--ac);color:#fff;border-color:var(--ac);box-shadow:var(--glow-sm)}
.header-btn svg{width:16px;height:16px}

.chat{flex:1;overflow-y:auto;padding:24px;display:flex;flex-direction:column;gap:16px;scroll-behavior:smooth}
.message{display:flex;gap:10px;max-width:80%;animation:fadeIn .3s ease}
@keyframes fadeIn{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}
.message.user{align-self:flex-end;flex-direction:row-reverse}
.message-avatar{width:34px;height:34px;border-radius:10px;display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:13px;font-weight:600}
.message.user .message-avatar{background:linear-gradient(135deg,var(--bl),var(--cy))}
.message.assistant .message-avatar{background:linear-gradient(135deg,var(--ac),var(--pp));box-shadow:var(--glow-sm)}
.message-avatar svg{width:16px;height:16px}
.message-content{background:var(--bgc);padding:14px 18px;border-radius:var(--r2);line-height:1.7;font-size:14px;border:1px solid var(--bd);position:relative}
.message.user .message-content{background:linear-gradient(135deg,rgba(59,130,246,.15),rgba(6,182,212,.1));border-color:rgba(59,130,246,.2)}
.message-content strong{color:var(--ac)}
.message.user .message-content strong{color:var(--cy)}
.message-content code{background:var(--bgh);padding:2px 6px;border-radius:4px;font-family:"Fira Code",monospace;font-size:13px;color:var(--cy)}
.message-content pre{background:var(--bgh);padding:14px;border-radius:var(--r);overflow-x:auto;margin:10px 0;border:1px solid var(--bd)}
.message-content pre code{background:0 0;padding:0;color:var(--tx)}
.message-content img{max-width:100%;border-radius:var(--r);margin:8px 0;border:1px solid var(--bd)}
.message-content h1,.message-content h2,.message-content h3{color:var(--ac);margin:12px 0 6px}

.msg-actions{display:flex;gap:4px;margin-top:8px;flex-wrap:wrap}
.msg-action-btn{width:30px;height:30px;border-radius:8px;border:1px solid var(--bd);background:transparent;color:var(--txd);cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .2s}
.msg-action-btn:hover{background:var(--acg);color:var(--ac);border-color:rgba(99,102,241,.3)}
.msg-action-btn.liked{background:rgba(34,197,94,.15);color:var(--gn);border-color:var(--gn)}
.msg-action-btn.disliked{background:rgba(239,68,68,.15);color:var(--rd);border-color:var(--rd)}
.msg-action-btn svg{width:13px;height:13px}

.confidence-bar{height:3px;background:var(--bd);border-radius:2px;margin-top:8px;overflow:hidden}
.confidence-fill{height:100%;border-radius:2px;transition:width .5s ease}
.confidence-high{background:linear-gradient(90deg,var(--gn),var(--cy))}
.confidence-medium{background:linear-gradient(90deg,var(--or),var(--or))}
.confidence-low{background:linear-gradient(90deg,var(--rd),var(--pp))}

.typing{display:flex;gap:5px;padding:6px 0}
.typing-dot{width:7px;height:7px;background:var(--ac);border-radius:50%;animation:typingBounce 1.4s infinite ease-in-out}
.typing-dot:nth-child(2){animation-delay:.2s}
.typing-dot:nth-child(3){animation-delay:.4s}
@keyframes typingBounce{0%,80%,100%{transform:scale(.5);opacity:.3}40%{transform:scale(1);opacity:1}}
.ai-badge{display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border-radius:10px;font-size:9px;font-weight:600;margin-top:6px;background:var(--acg);color:var(--ac);border:1px solid rgba(99,102,241,.2)}
.search-badge{display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border-radius:10px;font-size:9px;font-weight:600;margin-top:4px;background:rgba(59,130,246,.15);color:var(--bl);border:1px solid rgba(59,130,246,.2)}

.suggestions{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.suggestion{padding:6px 12px;background:var(--bgh);border:1px solid var(--bd);border-radius:20px;font-size:12px;color:var(--txd);cursor:pointer;transition:all .2s}
.suggestion:hover{background:var(--acg);color:var(--ac);border-color:rgba(99,102,241,.3)}

.input-container{padding:16px 24px 24px;background:linear-gradient(to top,var(--bg),transparent)}
.input-wrapper{display:flex;gap:6px;background:var(--bgc);border:1px solid var(--bd);border-radius:var(--r2);padding:6px;transition:all .2s}
.input-wrapper:focus-within{border-color:var(--ac);box-shadow:var(--glow-sm)}
.chat-input{flex:1;background:transparent;border:none;padding:10px 14px;color:var(--tx);font-size:14px;font-family:inherit;outline:0;min-width:0}
.chat-input::placeholder{color:var(--txdd)}
.action-btn{width:42px;height:42px;border-radius:var(--r);border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .2s;background:var(--bgh);color:var(--txd);border:1px solid var(--bd)}
.action-btn:hover{color:var(--tx);border-color:var(--ac);background:var(--acg)}
.action-btn svg{width:18px;height:18px}
.send-btn{background:linear-gradient(135deg,var(--ac),var(--pp));color:#fff;border:none;box-shadow:var(--glow-sm)}
.send-btn:hover{transform:scale(1.05);box-shadow:var(--glow)}
.mic-btn.recording{background:var(--rd);color:#fff;border-color:var(--rd);animation:micPulse 1s infinite}
@keyframes micPulse{0%,100%{box-shadow:0 0 0 0 rgba(239,68,68,.5)}50%{box-shadow:0 0 0 8px rgba(239,68,68,0)}}

.voice-overlay{position:fixed;top:0;left:0;width:100%;height:100%;background:linear-gradient(180deg,#0f0a1a 0%,#1a1030 50%,#0f0a1a 100%);z-index:9999;display:none;flex-direction:column;align-items:center;justify-content:center;opacity:0;transition:opacity .3s}
.voice-overlay.visible{display:flex;opacity:1}
.voice-header{position:absolute;top:0;left:0;right:0;display:flex;justify-content:space-between;align-items:center;padding:20px 24px}
.voice-title{font-size:16px;font-weight:600;color:var(--pp);letter-spacing:1px}
.voice-close{width:40px;height:40px;border-radius:50%;border:1px solid rgba(255,255,255,.15);background:rgba(255,255,255,.05);color:#fff;font-size:24px;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .2s}
.voice-close:hover{background:rgba(255,255,255,.15)}
.voice-body{display:flex;flex-direction:column;align-items:center;gap:24px}
.voice-circle{width:180px;height:180px;border-radius:50%;background:linear-gradient(135deg,rgba(99,102,241,.2),rgba(139,92,246,.2));border:3px solid rgba(139,92,246,.4);display:flex;align-items:center;justify-content:center;cursor:pointer;transition:all .4s ease;position:relative}
.voice-circle:hover{transform:scale(1.05);border-color:var(--pp)}
.voice-circle.voice-idle{background:linear-gradient(135deg,rgba(99,102,241,.15),rgba(139,92,246,.15))}
.voice-circle.voice-listening{background:linear-gradient(135deg,rgba(34,197,94,.2),rgba(16,185,129,.2));border-color:#22c55e;animation:voicePulse 1.5s infinite}
.voice-circle.voice-thinking{background:linear-gradient(135deg,rgba(251,191,36,.2),rgba(245,158,11,.2));border-color:#f59e0b;animation:voicePulse 1s infinite}
.voice-circle.voice-speaking{background:linear-gradient(135deg,rgba(139,92,246,.3),rgba(99,102,241,.3));border-color:var(--pp);animation:voicePulse .8s infinite}
@keyframes voicePulse{0%,100%{box-shadow:0 0 0 0 rgba(139,92,246,.4)}50%{box-shadow:0 0 0 20px rgba(139,92,246,0)}}
.voice-icon{width:60px;height:60px;color:var(--pp)}
.voice-status{font-size:20px;font-weight:600;color:var(--tx);text-align:center;min-height:28px}
.voice-text{font-size:16px;color:var(--txd);text-align:center;max-width:400px;min-height:24px;font-style:italic;line-height:1.5}
.voice-waves{display:flex;align-items:center;gap:4px;height:40px;opacity:0;transition:opacity .3s}
.voice-waves.active{opacity:1}
.voice-wave{width:4px;background:var(--pp);border-radius:2px;animation:waveAnim 1.2s ease-in-out infinite}
.voice-wave:nth-child(1){animation-delay:0s;height:12px}
.voice-wave:nth-child(2){animation-delay:.15s;height:20px}
.voice-wave:nth-child(3){animation-delay:.3s;height:28px}
.voice-wave:nth-child(4){animation-delay:.15s;height:20px}
.voice-wave:nth-child(5){animation-delay:0s;height:12px}
@keyframes waveAnim{0%,100%{transform:scaleY(.4)}50%{transform:scaleY(1)}}
.voice-hint{font-size:12px;color:rgba(255,255,255,.3);margin-top:16px}

.welcome{text-align:center;padding:60px 24px;max-width:600px;margin:0 auto;width:100%}
.welcome-icon{width:80px;height:80px;background:linear-gradient(135deg,var(--ac),var(--pp));border-radius:20px;display:flex;align-items:center;justify-content:center;margin:0 auto 20px;box-shadow:var(--glow)}
.welcome-icon svg{width:40px;height:40px}
.welcome h2{font-size:22px;margin-bottom:6px;background:linear-gradient(135deg,var(--tx),var(--ac));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.welcome p{color:var(--txd);margin-bottom:24px;font-size:14px}
.welcome-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}
.welcome-card{background:var(--bgc);border:1px solid var(--bd);border-radius:var(--r2);padding:18px 14px;cursor:pointer;transition:all .25s}
.welcome-card:hover{border-color:var(--ac);transform:translateY(-3px);box-shadow:var(--glow-sm)}
.welcome-card-icon{width:38px;height:38px;background:var(--acg);border-radius:10px;display:flex;align-items:center;justify-content:center;margin:0 auto 10px}
.welcome-card-icon svg{width:18px;height:18px;color:var(--ac)}
.welcome-card h4{font-size:13px;margin-bottom:3px}
.welcome-card p{font-size:11px;color:var(--txd);margin:0}

.dashboard{display:none;padding:24px;overflow-y:auto;flex:1}
.dashboard.visible{display:block}
.dash-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:24px}
.dash-card{background:var(--bgc);border:1px solid var(--bd);border-radius:var(--r2);padding:20px;text-align:center;transition:all .2s}
.dash-card:hover{border-color:var(--ac);box-shadow:var(--glow-sm)}
.dash-num{font-size:28px;font-weight:700;background:linear-gradient(135deg,var(--ac),var(--pp));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.dash-label{font-size:11px;color:var(--txd);margin-top:4px;text-transform:uppercase;letter-spacing:.5px}
.dash-section{background:var(--bgc);border:1px solid var(--bd);border-radius:var(--r2);padding:20px;margin-bottom:16px}
.dash-section h3{font-size:14px;margin-bottom:12px;color:var(--ac)}
.topic-bar{display:flex;align-items:center;gap:10px;margin-bottom:8px}
.topic-name{font-size:12px;color:var(--txd);min-width:120px}
.topic-fill-bg{flex:1;height:6px;background:var(--bd);border-radius:3px;overflow:hidden}
.topic-fill{height:100%;background:linear-gradient(90deg,var(--ac),var(--pp));border-radius:3px;transition:width .5s}
.topic-count{font-size:11px;color:var(--txdd);min-width:30px;text-align:right}

.correction-item{padding:10px;border:1px solid var(--bd);border-radius:var(--r);margin-bottom:8px;font-size:12px}
.correction-item .orig{color:var(--rd);text-decoration:line-through}
.correction-item .corr{color:var(--gn)}
.correction-item .corr-time{color:var(--txdd);font-size:10px;margin-top:4px}

.tool-panel{max-width:700px;margin:0 auto}
.tool-panel h2{font-size:18px;margin-bottom:16px;background:linear-gradient(135deg,var(--ac),var(--pp));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.tool-input{width:100%;padding:12px 16px;background:var(--bgh);border:1px solid var(--bd);border-radius:var(--r);color:var(--tx);font-size:14px;font-family:inherit;outline:0;margin-bottom:12px;transition:all .2s}
.tool-input:focus{border-color:var(--ac);box-shadow:var(--glow-sm)}
textarea.tool-input{min-height:200px;resize:vertical;font-family:"Fira Code",Consolas,monospace;font-size:13px;line-height:1.5}
.tool-btn{padding:10px 20px;background:linear-gradient(135deg,var(--ac),var(--pp));color:#fff;border:none;border-radius:var(--r);cursor:pointer;font-size:14px;font-weight:600;transition:all .2s;display:inline-flex;align-items:center;gap:8px}
.tool-btn:hover{transform:translateY(-1px);box-shadow:var(--glow)}
.tool-btn:disabled{opacity:.5;cursor:not-allowed;transform:none}
.tool-btn svg{width:16px;height:16px}
.tool-result{margin-top:16px;padding:16px;background:var(--bgh);border:1px solid var(--bd);border-radius:var(--r);font-family:"Fira Code",monospace;font-size:13px;white-space:pre-wrap;max-height:400px;overflow-y:auto;line-height:1.5}
.tool-result.success{border-color:var(--gn);color:var(--gn)}
.tool-result.error{border-color:var(--rd);color:var(--rd)}
.tool-hint{font-size:12px;color:var(--txd);margin-bottom:12px}
.tool-row{display:flex;gap:8px;align-items:center;margin-bottom:12px}

.music-player{margin-top:12px;padding:12px;background:var(--bgh);border:1px solid var(--bd);border-radius:var(--r)}
.music-player audio{width:100%;height:36px}

@keyframes glowPulse{0%,100%{box-shadow:var(--glow-sm)}50%{box-shadow:var(--glow)}}
.glow-animate{animation:glowPulse 3s infinite}

.install-btn{padding:6px 12px;background:linear-gradient(135deg,var(--gn),var(--cy));color:#fff;border:none;border-radius:var(--r);cursor:pointer;font-size:12px;font-weight:600;display:none;align-items:center;gap:4px}
.install-btn:hover{transform:scale(1.05)}

/* PARTICLES CANVAS */
#particlesCanvas{position:fixed;top:0;left:0;width:100%;height:100%;z-index:0;pointer-events:none;opacity:.6}

/* SVG AVATAR */
.avatar-svg-wrap{width:120px;height:120px;position:relative}
.avatar-svg-wrap.header-avatar{width:36px;height:36px}
.avatar-svg{width:100%;height:100%}
.avatar-float{animation:avatarFloat 4s ease-in-out infinite}
@keyframes avatarFloat{0%,100%{transform:translateY(0)}50%{transform:translateY(-8px)}}
.avatar-eye{transition:all .3s}
.avatar-thinking .avatar-eye{animation:avatarThinkEye 1.5s ease-in-out infinite}
@keyframes avatarThinkEye{0%,100%{transform:translateY(0)}50%{transform:translateY(-4px)}}
.avatar-speaking .avatar-mouth{animation:avatarSpeakMouth .3s ease-in-out infinite alternate}
@keyframes avatarSpeakMouth{0%{ry:4}100%{ry:8}}
.avatar-glow{filter:drop-shadow(0 0 8px rgba(99,102,241,.6));transition:filter .5s}
.avatar-glow-active{filter:drop-shadow(0 0 20px rgba(99,102,241,.9)) drop-shadow(0 0 40px rgba(168,85,247,.4))}
.avatar-gear{transform-origin:center;opacity:0;transition:opacity .3s}
.avatar-thinking .avatar-gear{opacity:1;animation:gearSpin 2s linear infinite}
@keyframes gearSpin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}
.avatar-wave-arc{opacity:0;transition:opacity .3s}
.avatar-listening .avatar-wave-arc{opacity:1;animation:waveArc 1.2s ease-in-out infinite}
@keyframes waveArc{0%,100%{opacity:.3;transform:scale(.9)}50%{opacity:.8;transform:scale(1.1)}}

/* TYPEWRITER */
.typewriter-cursor{display:inline-block;width:2px;height:1em;background:var(--ac);margin-left:2px;animation:blink .8s step-end infinite;vertical-align:text-bottom}
@keyframes blink{0%,100%{opacity:1}50%{opacity:0}}
.typewriter-done .typewriter-cursor{display:none}

/* TRANSITIONS */
.view-transition{animation:viewFadeIn .35s ease}
@keyframes viewFadeIn{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}

/* PULSE BTN */
.pulse-active{animation:pulseBtn 1.5s ease-in-out infinite}
@keyframes pulseBtn{0%,100%{box-shadow:0 0 0 0 rgba(99,102,241,.5)}50%{box-shadow:0 0 0 10px rgba(99,102,241,0)}}

/* CHART MSG */
.chart-msg-img{max-width:100%;border-radius:var(--r);border:1px solid var(--bd);margin:8px 0;cursor:pointer;transition:transform .2s}
.chart-msg-img:hover{transform:scale(1.02)}

/* DOC MSG */
.doc-badge{display:inline-flex;align-items:center;gap:4px;padding:3px 10px;border-radius:10px;font-size:10px;font-weight:600;margin-top:6px;background:rgba(249,115,22,.15);color:var(--or);border:1px solid rgba(249,115,22,.25)}
.doc-preview{font-size:12px;color:var(--txd);max-height:200px;overflow-y:auto;padding:10px;background:var(--bgh);border:1px solid var(--bd);border-radius:var(--r);margin-top:8px;font-family:"Fira Code",monospace;line-height:1.5;white-space:pre-wrap}
.doc-upload-btn{position:relative;overflow:hidden}
.doc-upload-btn input[type=file]{position:absolute;inset:0;opacity:0;cursor:pointer}

@media(max-width:768px){
  .sidebar{transform:translateX(-100%);z-index:999;width:80vw;position:fixed;top:0;left:0;height:100vh}
  .sidebar.open{transform:translateX(0)}
  .sidebar-overlay{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.5);z-index:998}
  .sidebar-overlay.active{display:block}
  .main{margin-left:0;width:100vw;overflow-x:hidden}
  .header{padding:10px 12px;position:sticky;top:0;z-index:50}
  .header-title{font-size:14px}
  .header-subtitle{font-size:10px}
  .header-btn{width:32px;height:32px}
  .header-btn svg{width:14px;height:14px}
  #menuToggle{display:flex!important}
  .install-btn{font-size:11px;padding:4px 10px}
  .chat{padding:12px 10px;gap:10px}
  .message{max-width:92%;gap:6px}
  .message-content{padding:10px 12px;font-size:13px;line-height:1.5;border-radius:14px}
  .message-avatar{width:28px;height:28px;border-radius:8px}
  .msg-action-btn{width:26px;height:26px}
  .msg-action-btn svg{width:11px;height:11px}
  .input-container{padding:8px 10px 16px}
  .input-wrapper{padding:4px;gap:4px;border-radius:16px;flex-wrap:nowrap;overflow-x:auto;-webkit-overflow-scrolling:touch}
  .chat-input{padding:8px 10px;font-size:16px;min-width:0}
  .action-btn{width:36px;height:36px;flex-shrink:0}
  .action-btn svg{width:16px;height:16px}
  .voice-btn{display:flex}
  .welcome{padding:30px 16px}
  .welcome-icon{width:60px;height:60px;border-radius:16px}
  .welcome-icon svg{width:30px;height:30px}
  .welcome h2{font-size:18px}
  .welcome p{font-size:13px;margin-bottom:16px}
  .welcome-grid{grid-template-columns:1fr 1fr;gap:8px}
  .welcome-card{padding:12px 10px}
  .welcome-card-icon{width:32px;height:32px;border-radius:8px}
  .welcome-card-icon svg{width:14px;height:14px}
  .welcome-card h4{font-size:12px}
  .welcome-card p{font-size:10px}
  .dash-grid{grid-template-columns:repeat(2,1fr);gap:8px}
  .dash-card{padding:14px 8px}
  .dash-num{font-size:22px}
  .dash-label{font-size:10px}
  .dash-section{padding:14px}
  .tool-panel{padding:0 4px}
  .tool-panel h2{font-size:16px}
  .tool-input{padding:10px 12px;font-size:14px}
  textarea.tool-input{min-height:150px}
  .tool-btn{padding:8px 14px;font-size:13px}
  .tool-btn svg{width:14px;height:14px}
  .tool-result{padding:12px;font-size:12px;max-height:300px}
  .suggestions{gap:4px}
  .suggestion{padding:5px 10px;font-size:11px}
  .music-player{padding:10px}
  .voice-circle{width:150px;height:150px}
  .voice-icon{width:50px;height:50px}
  .voice-status{font-size:16px}
  .voice-header{padding:12px 16px}
  .voice-close{width:36px;height:36px;font-size:20px}
}
@media(max-width:380px){
  .welcome-grid{grid-template-columns:1fr}
  .dash-grid{grid-template-columns:1fr 1fr}
  .input-wrapper{flex-wrap:wrap}
  .action-btn{width:34px;height:34px}
}
</style>
</head>
<body>
<div class="sidebar-overlay" id="sidebarOverlay" onclick="toggleSidebar()"></div>
<canvas id="particlesCanvas"></canvas>

<aside class="sidebar" id="sidebar">
  <div class="sidebar-header">
    <div class="logo">
      <div class="logo-icon glow-animate avatar-float" id="sidebarAvatar">
        <svg viewBox="0 0 100 100" class="avatar-svg">
          <defs><linearGradient id="avatarGrad" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" style="stop-color:#818cf8"/><stop offset="100%" style="stop-color:#c084fc"/></linearGradient></defs>
          <circle cx="50" cy="52" r="34" fill="url(#avatarGrad)" opacity=".15" stroke="#818cf8" stroke-width="2"/>
          <circle cx="37" cy="46" r="7" fill="#818cf8" class="avatar-eye"><animate attributeName="r" values="7;7;6;7" dur="3s" repeatCount="indefinite"/></circle>
          <circle cx="63" cy="46" r="7" fill="#818cf8" class="avatar-eye"><animate attributeName="r" values="7;7;6;7" dur="3s" repeatCount="indefinite" begin=".5s"/></circle>
          <circle cx="37" cy="46" r="3" fill="#0f0f15"/><circle cx="63" cy="46" r="3" fill="#0f0f15"/>
          <ellipse cx="50" cy="64" rx="10" ry="4" fill="none" stroke="#818cf8" stroke-width="2" stroke-linecap="round"/>
          <line x1="50" y1="18" x2="50" y2="10" stroke="#818cf8" stroke-width="2" stroke-linecap="round"/>
          <circle cx="50" cy="8" r="3" fill="#a855f7"/>
          <circle cx="28" cy="58" r="2" fill="#6366f1" opacity=".5"/>
          <circle cx="72" cy="58" r="2" fill="#6366f1" opacity=".5"/>
        </svg>
      </div>
      <div><div class="logo-text">ELLIOTT</div><div class="logo-sub">IA Ultime</div></div>
    </div>
  </div>
  <nav class="menu">
    <div class="menu-title">Navigation</div>
    <div class="menu-item active" onclick="showView('chat',this)">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
      Chat IA
    </div>
    <div class="menu-item" onclick="showView('dashboard',this)">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
      Tableau de bord
    </div>

    <div class="menu-title">Outils IA</div>
    <div class="menu-item" onclick="sendImage()">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
      Generer Image
    </div>
    <div class="menu-item" onclick="showView('music',this)">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>
      Generer Musique
    </div>
    <div class="menu-item" onclick="showView('code',this)">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
      Editeur de Code
    </div>
    <div class="menu-item" onclick="showView('vision',this)">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
      Analyser Image
    </div>
    <div class="menu-item" onclick="showView('search',this)">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
      Recherche Web
    </div>

    <div class="menu-title">Sujets Populaires</div>
    <div class="menu-item" onclick="sendQuick('Explique le machine learning simplement')">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
      IA / ML
    </div>
    <div class="menu-item" onclick="sendQuick('Ecris un script Python elegant pour fibonacci')">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
      Python
    </div>
    <div class="menu-item" onclick="sendQuick('Conseils pour debuter en tricot')">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>
      Artisanat
    </div>
    <div class="menu-item" onclick="sendQuick('Raconte-moi une histoire courte et fascinante')">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
      Histoire
    </div>
  </nav>
  <div class="sidebar-footer">
    <div class="status">
      <div class="status-dot"></div>
      <span id="statusText">En ligne</span>
    </div>
  </div>
</aside>

<main class="main">
  <header class="header">
    <div class="header-left">
      <button class="header-btn" id="menuToggle" onclick="toggleSidebar()" style="display:none">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
      </button>
      <div>
        <div class="header-title">ELLIOTT <span class="ai-badge">100% Gratuit</span></div>
        <div class="header-subtitle" id="headerSubtitle">Pret a discuter</div>
      </div>
    </div>
    <div class="header-actions">
      <button class="install-btn" id="installBtn" onclick="installPWA()" title="Installer l'app">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        Installer
      </button>
      <button class="header-btn active" id="autoSpeakBtn" onclick="toggleAutoSpeak()" title="Parler auto (ON)">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>
      </button>
      <button class="header-btn" onclick="clearChat()" title="Nouvelle conversation">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14"/></svg>
      </button>
      <button class="header-btn" onclick="loadDashboard()" title="Memoire">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
      </button>
    </div>
  </header>

  <div class="chat" id="chatMessages">
    <div class="welcome" id="welcomeScreen">
      <div class="welcome-icon glow-animate avatar-glow" id="welcomeAvatar">
        <svg viewBox="0 0 100 100" class="avatar-svg">
          <defs><linearGradient id="wAvatarGrad" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" style="stop-color:#fff"/><stop offset="100%" style="stop-color:#c084fc"/></linearGradient></defs>
          <circle cx="50" cy="52" r="34" fill="url(#wAvatarGrad)" opacity=".15" stroke="#fff" stroke-width="2"/>
          <circle cx="37" cy="46" r="7" fill="#fff" class="avatar-eye"><animate attributeName="r" values="7;7;6;7" dur="3s" repeatCount="indefinite"/></circle>
          <circle cx="63" cy="46" r="7" fill="#fff" class="avatar-eye"><animate attributeName="r" values="7;7;6;7" dur="3s" repeatCount="indefinite" begin=".5s"/></circle>
          <circle cx="37" cy="46" r="3" fill="#0f0f15"/><circle cx="63" cy="46" r="3" fill="#0f0f15"/>
          <ellipse cx="50" cy="64" rx="10" ry="4" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round"/>
          <line x1="50" y1="18" x2="50" y2="10" stroke="#fff" stroke-width="2" stroke-linecap="round"/>
          <circle cx="50" cy="8" r="3" fill="#fff" opacity=".8"/>
          <g class="avatar-gear"><circle cx="18" cy="32" r="5" fill="none" stroke="#a855f7" stroke-width="1.5" stroke-dasharray="3 2"><animateTransform attributeName="transform" type="rotate" from="0 18 32" to="360 18 32" dur="3s" repeatCount="indefinite"/></circle></g>
        </svg>
      </div>
      <h2>Bonjour! Je suis ELLIOTT</h2>
      <p>IA <strong>revolutionnaire</strong> qui apprend, retient et s'ameliore!</p>
      <div class="welcome-grid">
        <div class="welcome-card" onclick="sendQuick('Explique le machine learning simplement')">
          <div class="welcome-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg></div>
          <h4>Apprendre</h4><p>ML, code, sciences</p>
        </div>
        <div class="welcome-card" onclick="sendImage()">
          <div class="welcome-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg></div>
          <h4>Creer</h4><p>Images magiques</p>
        </div>
        <div class="welcome-card" onclick="showView('music',document.querySelectorAll('.menu-item')[3])">
          <div class="welcome-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg></div>
          <h4>Musique</h4><p>Generez de la musique</p>
        </div>
        <div class="welcome-card" onclick="showView('code',document.querySelectorAll('.menu-item')[5])">
          <div class="welcome-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg></div>
          <h4>Code</h4><p>Executer du Python</p>
        </div>
      </div>
    </div>
  </div>

  <div class="dashboard" id="dashboardView">
    <div class="dash-grid">
      <div class="dash-card"><div class="dash-num" id="dConv">0</div><div class="dash-label">Conversations</div></div>
      <div class="dash-card"><div class="dash-num" id="dTopics">0</div><div class="dash-label">Sujets Appris</div></div>
      <div class="dash-card"><div class="dash-num" id="dCorr">0</div><div class="dash-label">Corrections</div></div>
      <div class="dash-card"><div class="dash-num" id="dThumbs">0</div><div class="dash-label">Appreciations</div></div>
      <div class="dash-card"><div class="dash-num" id="dImages">0</div><div class="dash-label">Images</div></div>
      <div class="dash-card"><div class="dash-num" id="dMusic">0</div><div class="dash-label">Musiques</div></div>
      <div class="dash-card"><div class="dash-num" id="dCode">0</div><div class="dash-label">Code Execute</div></div>
      <div class="dash-card"><div class="dash-num" id="dSearch">0</div><div class="dash-label">Recherches</div></div>
      <div class="dash-card"><div class="dash-num" id="dQuality">0%</div><div class="dash-label">Qualite Moy.</div></div>
      <div class="dash-card"><div class="dash-num" id="dUptime">0m</div><div class="dash-label">Temps Actif</div></div>
    </div>
    <div class="dash-section">
      <h3>Sujets les plus demandes</h3>
      <div id="topicsList"></div>
    </div>
    <div class="dash-section">
      <h3>Corrections recentes</h3>
      <div id="correctionsList"></div>
    </div>
    <div class="dash-section">
      <h3>Resumes de conversations passees</h3>
      <div id="summariesList"></div>
    </div>
  </div>

  <div class="dashboard" id="musicView">
    <div class="tool-panel">
      <h2>Generateur de Musique IA</h2>
      <p class="tool-hint">Decrivez la musique que vous souhaitez et ELLIOTT la generera pour vous avec MusicGen.</p>
      <input type="text" class="tool-input" id="musicPrompt" placeholder="Ex: musique electronique rythmique et energisante..." maxlength="500" onkeypress="if(event.key==='Enter')generateMusic()">
      <button class="tool-btn" id="musicGenBtn" onclick="generateMusic()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
        Generer la Musique
      </button>
      <div id="musicResult"></div>
    </div>
  </div>

  <div class="dashboard" id="codeView">
    <div class="tool-panel">
      <h2>Editeur de Code Python</h2>
      <p class="tool-hint">Ecrivez du Python et executer-le directement. Le code est execute dans un environnement securise avec timeout.</p>
      <textarea class="tool-input" id="codeEditor" placeholder="# Ecrivez votre code Python ici...&#10;print('Bonjour ELLIOTT!')" spellcheck="false"></textarea>
      <div class="tool-row">
        <button class="tool-btn" id="execBtn" onclick="executeCode()">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
          Executer
        </button>
        <button class="tool-btn" onclick="document.getElementById('codeEditor').value=''" style="background:var(--bgh);color:var(--txd)">
          Effacer
        </button>
      </div>
      <div id="codeResult"></div>
    </div>
  </div>

  <div class="dashboard" id="visionView">
    <div class="tool-panel">
      <h2>Analyse d'Image (Vision IA)</h2>
      <p class="tool-hint">Envoyez une URL d'image ou uploadez un fichier pour l'analyser avec l'intelligence artificielle.</p>
      <input type="text" class="tool-input" id="imageUrlInput" placeholder="Collez une URL d'image ici..." maxlength="2000" onkeypress="if(event.key==='Enter')analyzeImageUrl()">
      <div class="tool-row">
        <button class="tool-btn" onclick="analyzeImageUrl()">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          Analyser l'URL
        </button>
        <label class="tool-btn" style="cursor:pointer;background:var(--bgh);color:var(--txd)">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
          Uploader un fichier
          <input type="file" accept="image/*" onchange="handleImageUpload(event)" style="display:none">
        </label>
      </div>
      <div id="visionResult"></div>
    </div>
  </div>

  <div class="dashboard" id="searchView">
    <div class="tool-panel">
      <h2>Recherche Web</h2>
      <p class="tool-hint">Recherchez sur internet. Les resultats sont utilises pour enrichir les reponses de l'IA.</p>
      <input type="text" class="tool-input" id="searchInput" placeholder="Tapez votre recherche..." maxlength="500" onkeypress="if(event.key==='Enter')doWebSearch()">
      <button class="tool-btn" onclick="doWebSearch()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        Rechercher
      </button>
      <div id="searchResults" style="margin-top:16px"></div>
    </div>
  </div>

  <div class="input-container">
    <div class="input-wrapper">
      <button class="action-btn mic-btn" id="micBtn" onclick="toggleMic()" title="Micro">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
      </button>
      <input type="text" class="chat-input" id="chatInput" placeholder="Tapez ou dites votre question..." maxlength="2000" onkeypress="if(event.key==='Enter')sendMessage()">
      <button class="action-btn" onclick="sendImage()" title="Generer image">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
      </button>
      <label class="action-btn doc-upload-btn" title="Analyser un document">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
        <input type="file" accept=".pdf,.doc,.docx,.txt,.csv" onchange="handleDocUpload(event)" style="display:none">
      </label>
      <label class="action-btn" title="Uploader une image" style="cursor:pointer">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
        <input type="file" accept="image/*" onchange="handleChatImageUpload(event)" style="display:none">
      </label>
      <button class="action-btn" onclick="showView('music',document.querySelectorAll('.menu-item')[3])" title="Generer musique">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>
      </button>
      <button class="action-btn voice-btn" onclick="toggleVoiceMode()" title="Mode vocal" style="background:linear-gradient(135deg,#8b5cf6,#6366f1);color:#fff;border:none">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
      </button>
      <button class="action-btn send-btn" onclick="sendMessage()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
      </button>
    </div>
  </div>
</main>

<div class="voice-overlay" id="voiceOverlay">
  <div class="voice-header">
    <span class="voice-title">Agent Vocal ELLIOTT</span>
    <button class="voice-close" onclick="toggleVoiceMode()">&times;</button>
  </div>
  <div class="voice-body">
    <div class="voice-circle" id="voiceCircle" onclick="onVoiceCircleClick()">
      <svg viewBox="0 0 100 100" class="avatar-svg avatar-float" id="voiceAvatar">
        <defs>
          <linearGradient id="vAvatarGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" style="stop-color:#818cf8"/><stop offset="100%" style="stop-color:#c084fc"/>
          </linearGradient>
          <filter id="avatarGlow"><feGaussianBlur stdDeviation="2" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
        </defs>
        <circle cx="50" cy="52" r="34" fill="url(#vAvatarGrad)" opacity=".2" stroke="#818cf8" stroke-width="2.5" filter="url(#avatarGlow)"/>
        <!-- Antenna -->
        <line x1="50" y1="18" x2="50" y2="6" stroke="#818cf8" stroke-width="2.5" stroke-linecap="round"/>
        <circle cx="50" cy="5" r="4" fill="#a855f7"><animate attributeName="r" values="4;5;4" dur="1.5s" repeatCount="indefinite"/></circle>
        <!-- Eyes -->
        <circle cx="37" cy="44" r="8" fill="#818cf8" class="avatar-eye" filter="url(#avatarGlow)"/>
        <circle cx="63" cy="44" r="8" fill="#818cf8" class="avatar-eye" filter="url(#avatarGlow)"/>
        <circle cx="37" cy="44" r="3.5" fill="#0f0f15" class="avatar-pupil"/>
        <circle cx="63" cy="44" r="3.5" fill="#0f0f15" class="avatar-pupil"/>
        <circle cx="35" cy="42" r="1.5" fill="#fff" opacity=".7"/>
        <circle cx="61" cy="42" r="1.5" fill="#fff" opacity=".7"/>
        <!-- Mouth -->
        <ellipse cx="50" cy="65" rx="12" ry="4" fill="none" stroke="#818cf8" stroke-width="2.5" stroke-linecap="round" class="avatar-mouth"/>
        <!-- Cheeks -->
        <circle cx="26" cy="56" r="4" fill="#a855f7" opacity=".15"/>
        <circle cx="74" cy="56" r="4" fill="#a855f7" opacity=".15"/>
        <!-- Gears (thinking) -->
        <g class="avatar-gear" transform="translate(14,28)">
          <circle r="5" fill="none" stroke="#c084fc" stroke-width="1.5" stroke-dasharray="3 2"><animateTransform attributeName="transform" type="rotate" from="0 0 0" to="360 0 0" dur="2s" repeatCount="indefinite"/></circle>
        </g>
        <g class="avatar-gear" transform="translate(86,28)">
          <circle r="4" fill="none" stroke="#c084fc" stroke-width="1.5" stroke-dasharray="2 2"><animateTransform attributeName="transform" type="rotate" from="360 0 0" to="0 0 0" dur="1.5s" repeatCount="indefinite"/></circle>
        </g>
        <!-- Sound waves (speaking) -->
        <path d="M85 44 Q92 50 85 56" fill="none" stroke="#818cf8" stroke-width="2" stroke-linecap="round" class="avatar-wave-arc" opacity=".6"/>
        <path d="M90 40 Q100 50 90 60" fill="none" stroke="#818cf8" stroke-width="1.5" stroke-linecap="round" class="avatar-wave-arc" opacity=".4" style="animation-delay:.3s"/>
      </svg>
    </div>
    <div class="voice-status" id="voiceStatus">Appuyez pour parler</div>
    <div class="voice-text" id="voiceText"></div>
    <div class="voice-waves" id="voiceWaves">
      <div class="voice-wave"></div><div class="voice-wave"></div><div class="voice-wave"></div>
      <div class="voice-wave"></div><div class="voice-wave"></div>
    </div>
    <div class="voice-hint">Dites "arrête" pour couper la voix</div>
  </div>
</div>

<script>
var convId='c_'+Date.now();
var synth=window.speechSynthesis;
var autoSpeak=true;
var recognition=null;
var isRecording=false;
var SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;
var startTime=Date.now();
var pendingFeedback={};
var msgCount=0;
var currentUtterance=null;

function parler(texte){
  if(!texte)return;
  window.speechSynthesis.cancel();
  var c=texte.replace(/\n/g,' ').replace(/[#\-*>|_`\[\]]/g,'').replace(/\s+/g,' ').trim();
  if(!c||c.length<2)return;
  fetch('/api/elevenlabs-tts',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({text:c.substring(0,500)})})
  .then(function(r){if(!r.ok)throw 'fail';return r.blob()})
  .then(function(blob){
    var u=URL.createObjectURL(blob);
    var a=new Audio(u);
    a.onended=function(){URL.revokeObjectURL(u);};
    a.onerror=function(){URL.revokeObjectURL(u);fallbackSpeak(c);};
    a.play().catch(function(){URL.revokeObjectURL(u);fallbackSpeak(c);});
  })
  .catch(function(){fallbackSpeak(c);});
}

function fallbackSpeak(text){
  currentUtterance=new SpeechSynthesisUtterance(text);
  currentUtterance.lang='fr-FR';currentUtterance.rate=0.95;currentUtterance.pitch=1.0;
  var voix=window.speechSynthesis.getVoices();
  var v=voix.find(function(x){return x.lang&&x.lang.startsWith('fr')&&(x.name.indexOf('Siri')!==-1||x.name.indexOf('Thomas')!==-1||x.name.indexOf('Premium')!==-1);})
    ||voix.find(function(x){return x.lang&&x.lang.startsWith('fr');});
  if(v)currentUtterance.voice=v;
  window.speechSynthesis.speak(currentUtterance);
}

document.addEventListener('touchstart',function(){window.speechSynthesis.getVoices();},{passive:true});
window.speechSynthesis.getVoices();
if(window.speechSynthesis.onvoiceschanged!==undefined){
  window.speechSynthesis.onvoiceschanged=function(){window.speechSynthesis.getVoices();};
}

if(SpeechRecognition){
  recognition=new SpeechRecognition();
  recognition.continuous=false;
  recognition.interimResults=true;
  recognition.lang='fr-FR';
  recognition.maxAlternatives=1;
}

function toggleAutoSpeak(){
  autoSpeak=!autoSpeak;
  document.getElementById('autoSpeakBtn').classList.toggle('active',autoSpeak);
}

function toggleMic(){
  if(!recognition){alert('Non supporte');return;}
  if(isRecording){
    recognition.stop();
    isRecording=false;
  }else{
    var unlock=new SpeechSynthesisUtterance('');
    window.speechSynthesis.speak(unlock);
    synth.cancel();
    recognition.start();
    isRecording=true;
  }
}

var voiceMode=false;
var voiceState='idle';
var voiceAudio=null;
var voiceConvId='voice_'+Date.now();

function toggleVoiceMode(){
  voiceMode=!voiceMode;
  var o=document.getElementById('voiceOverlay');
  if(voiceMode){
    o.classList.add('visible');
    voiceState='idle';
    updateVoiceUI();
  }else{
    o.classList.remove('visible');
    if(voiceAudio){voiceAudio.pause();voiceAudio=null;}
    if(recognition&&isRecording){recognition.stop();isRecording=false;}
    synth.cancel();
    document.getElementById('voiceWaves').classList.remove('active');
  }
}

function updateVoiceUI(){
  var c=document.getElementById('voiceCircle');
  var s=document.getElementById('voiceStatus');
  c.className='voice-circle voice-'+voiceState;
  var labels={idle:'Appuyez pour parler',listening:'Je vous ecoute...',thinking:'Je reflechis...',speaking:'Je parle...'};
  s.textContent=labels[voiceState]||'';
  setAvatarState(voiceState);
  if(window.elliottParticles)window.elliottParticles.setSpeaking(voiceState==='speaking'||voiceState==='thinking');
}

function onVoiceCircleClick(){
  if(voiceState==='idle'||voiceState==='listening'){
    startVoiceListen();
  }else if(voiceState==='speaking'){
    stopVoiceSpeak();
  }
}

function startVoiceListen(){
  if(!recognition){alert('Non supporte');return;}
  synth.cancel();
  if(voiceAudio){voiceAudio.pause();voiceAudio=null;}
  voiceState='listening';
  updateVoiceUI();
  document.getElementById('voiceText').textContent='...';
  document.getElementById('voiceWaves').classList.remove('active');
  var unlock=new SpeechSynthesisUtterance('');
  window.speechSynthesis.speak(unlock);
  synth.cancel();
  try{recognition.start();isRecording=true;}catch(e){}
}

function stopVoiceSpeak(){
  synth.cancel();
  if(voiceAudio){voiceAudio.pause();voiceAudio=null;}
  document.getElementById('voiceWaves').classList.remove('active');
  voiceState='idle';
  updateVoiceUI();
  setTimeout(function(){startVoiceListen();},500);
}

function voiceSend(text){
  if(!text)return;
  voiceState='thinking';
  updateVoiceUI();
  document.getElementById('voiceText').textContent=text;
  fetch('/api/voice-chat',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({message:text,conversation_id:voiceConvId})})
  .then(function(r){return r.json()})
  .then(function(d){
    document.getElementById('voiceText').textContent=d.text||'';
    var phrases = d.text.match(/[^.!?]+[.!?]+/g) || [d.text];
    playPhrasesSequentially(phrases, 0);
  })
  .catch(function(){
    voiceState='idle';
    updateVoiceUI();
  });
}

function playPhrasesSequentially(phrases, index){
  if(index >= phrases.length){
    voiceState='idle';
    updateVoiceUI();
    return;
  }
  var phrase = phrases[index].trim();
  if(!phrase){ playPhrasesSequentially(phrases, index+1); return; }
  fetch('/api/tts-only',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({text:phrase})})
  .then(function(r){return r.json()})
  .then(function(d){
    if(d.audio_url){
      voiceState='speaking';
      updateVoiceUI();
      fetch(d.audio_url).then(function(r){return r.blob()}).then(function(blob){
        var u=URL.createObjectURL(blob);
        var audio=new Audio(u);
        document.getElementById('voiceWaves').classList.add('active');
        parlser=phrase;
        audio.onended=function(){
          URL.revokeObjectURL(u);
          document.getElementById('voiceWaves').classList.remove('active');
          playPhrasesSequentially(phrases, index+1);
        };
        audio.play();
      });
    } else {
      voiceSpeakBrowser(phrase);
      playPhrasesSequentially(phrases, index+1);
    }
  })
  .catch(function(){
    voiceSpeakBrowser(phrase);
    playPhrasesSequentially(phrases, index+1);
  });
}

function voiceSpeakURL(url,text){
  voiceState='speaking';
  updateVoiceUI();
  document.getElementById('voiceWaves').classList.add('active');
  parlser=text;
  fetch(url).then(function(r){return r.blob()}).then(function(blob){
    var u=URL.createObjectURL(blob);
    voiceAudio=new Audio(u);
    voiceAudio.onended=function(){
      document.getElementById('voiceWaves').classList.remove('active');
      URL.revokeObjectURL(u);
      if(voiceMode){voiceState='idle';updateVoiceUI();setTimeout(function(){startVoiceListen();},800);}
    };
    voiceAudio.onerror=function(){
      URL.revokeObjectURL(u);
      voiceSpeakBrowser(text);
    };
    voiceAudio.play().catch(function(){
      URL.revokeObjectURL(u);
      voiceSpeakBrowser(text);
    });
  }).catch(function(){
    voiceSpeakBrowser(text);
  });
}

function voiceSpeakBrowser(text){
  if(!text)return;
  voiceState='speaking';
  updateVoiceUI();
  document.getElementById('voiceWaves').classList.add('active');
  window.speechSynthesis.cancel();
  var c=text.replace(/\n/g,' ').replace(/[#\-*>|_`\[\]]/g,'').replace(/\s+/g,' ').trim();
  if(!c||c.length<2)return;
  fetch('/api/elevenlabs-tts',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({text:c.substring(0,500)})})
  .then(function(r){if(!r.ok)throw 'fail';return r.blob()})
  .then(function(blob){
    var u=URL.createObjectURL(blob);
    var a=new Audio(u);
    a.onended=function(){
      URL.revokeObjectURL(u);
      document.getElementById('voiceWaves').classList.remove('active');
      if(voiceMode){voiceState='idle';updateVoiceUI();setTimeout(function(){startVoiceListen();},800);}
    };
    a.onerror=function(){
      URL.revokeObjectURL(u);
      voiceFallbackBrowser(c);
    };
    a.play().catch(function(){URL.revokeObjectURL(u);voiceFallbackBrowser(c);});
  }).catch(function(){voiceFallbackBrowser(c);});
}

function voiceFallbackBrowser(text){
  window.speechSynthesis.cancel();
  var u=new SpeechSynthesisUtterance(text);
  u.lang='fr-FR';u.rate=0.95;u.pitch=1.0;
  var voix=window.speechSynthesis.getVoices();
  var v=voix.find(function(x){return x.lang&&x.lang.startsWith('fr')&&(x.name.indexOf('Siri')!==-1||x.name.indexOf('Thomas')!==-1||x.name.indexOf('Premium')!==-1);})
    ||voix.find(function(x){return x.lang&&x.lang.startsWith('fr');});
  if(v)u.voice=v;
  u.onend=function(){
    document.getElementById('voiceWaves').classList.remove('active');
    if(voiceMode){voiceState='idle';updateVoiceUI();setTimeout(function(){startVoiceListen();},800);}
  };
  window.speechSynthesis.speak(u);
}

if(recognition){
  var origOnResult=recognition.onresult;
  var origOnEnd=recognition.onend;
  recognition.onresult=function(e){
    var t='';
    for(var i=e.resultIndex;i<e.results.length;i++){t+=e.results[i][0].transcript;}
    if(voiceMode){
      document.getElementById('voiceText').textContent=t;
      document.getElementById('chatInput').value=t;
    }else{
      document.getElementById('chatInput').value=t;
    }
  };
  recognition.onend=function(){
    isRecording=false;
    document.getElementById('micBtn').classList.remove('recording');
    if(voiceMode){
      var msg=document.getElementById('chatInput').value.trim();
      if(msg){
        if(msg.toLowerCase().indexOf('arrete')!==-1||msg.toLowerCase().indexOf('stop')!==-1){
          voiceState='idle';updateVoiceUI();return;
        }
        voiceSend(msg);
      }else{
        voiceState='idle';updateVoiceUI();
      }
    }else{
      var msg2=document.getElementById('chatInput').value.trim();
      if(msg2)sendMessage();
    }
  };
}

function toggleSidebar(){var s=document.getElementById('sidebar');var o=document.getElementById('sidebarOverlay');s.classList.toggle('open');o.classList.toggle('active');}

function showView(view,el){
  document.querySelectorAll('.menu-item').forEach(function(i){i.classList.remove('active')});
  if(el)el.classList.add('active');
  var views=['chatMessages','dashboardView','musicView','codeView','visionView','searchView'];
  var viewMap={chat:'chatMessages',dashboard:'dashboardView',music:'musicView',code:'codeView',vision:'visionView',search:'searchView'};
  views.forEach(function(v){
    var e=document.getElementById(v);
    if(v==='chatMessages'){e.style.display='none';}
    else{e.className='dashboard';}
  });
  var target=document.getElementById(viewMap[view]);
  if(view==='chat'){target.style.display='flex';}
  else{target.className='dashboard visible';}
  if(view==='dashboard')loadDashboard();
}

function sendQuick(t){document.getElementById('chatInput').value=t;sendMessage();}

function escapeHtml(s){var d=document.createElement('div');d.appendChild(document.createTextNode(s));return d.innerHTML;}

function formatMarkdown(c){
  var out=escapeHtml(c);
  out=out.replace(/```(\w*)\n([\s\S]*?)```/g,function(m,lang,code){return '<pre><code class="lang-'+lang+'">'+code+'</code></pre>';});
  out=out.replace(/`([^`]+)`/g,'<code>$1</code>');
  out=out.replace(/\*\*(.*?)\*\*/g,'<strong>$1</strong>');
  out=out.replace(/\*(.*?)\*/g,'<em>$1</em>');
  out=out.replace(/^### (.+)$/gm,'<h3 style="color:var(--ac)">$1</h3>');
  out=out.replace(/^## (.+)$/gm,'<h2 style="color:var(--ac);font-size:16px;margin:10px 0 4px">$1</h2>');
  out=out.replace(/^# (.+)$/gm,'<h1 style="color:var(--ac);font-size:18px;margin:10px 0 4px">$1</h1>');
  out=out.replace(/^- (.+)$/gm,'<li style="margin-left:16px">$1</li>');
  out=out.replace(/^\d+\. (.+)$/gm,'<li style="margin-left:16px">$1</li>');
  out=out.replace(/\n/g,'<br>');
  return out;
}

function confidenceClass(conf){
  if(conf>=0.7)return 'confidence-high';
  if(conf>=0.4)return 'confidence-medium';
  return 'confidence-low';
}

function addMessage(c,u,opts){
  opts=opts||{};
  var chat=document.getElementById('chatMessages');
  var w=document.getElementById('welcomeScreen');
  if(w)w.remove();
  var m=document.createElement('div');
  m.className='message '+(u?'user':'assistant');
  m.id='msg_'+(++msgCount);
  var a=u?'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></svg>';
  var content=u?escapeHtml(c):formatMarkdown(c);
  var h='<div class="message-avatar">'+a+'</div><div class="message-content">'+content;
  if(!u&&!opts.noBadge){
    h+='<div class="ai-badge">ELLIOTT IA</div>';
    if(opts.searchUsed){h+='<div class="search-badge">Recherche web utilisee</div>';}
    if(typeof opts.confidence==='number'){
      h+='<div class="confidence-bar"><div class="confidence-fill '+confidenceClass(opts.confidence)+'" style="width:'+(opts.confidence*100)+'%"></div></div>';
    }
    var mid=m.id;
    h+='<div class="msg-actions">';
    h+='<button class="msg-action-btn" onclick="speakMsg(\''+mid+'\')" title="Ecouter"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg></button>';
    h+='<button class="msg-action-btn" onclick="copyMsg(\''+mid+'\')" title="Copier"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg></button>';
    h+='<button class="msg-action-btn" id="thumbUp_'+mid+'" onclick="sendFeedback(\''+mid+'\',true)" title="Utile"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg></button>';
    h+='<button class="msg-action-btn" id="thumbDn_'+mid+'" onclick="sendFeedback(\''+mid+'\',false)" title="Pas utile"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/></svg></button>';
    h+='</div>';
  }
  h+='</div>';
  m.innerHTML=h;
  chat.appendChild(m);
  chat.scrollTop=chat.scrollHeight;
  window._lastResponse=c;
  window._lastResponseEl=m;
  return m;
}

function addImageMessage(imgUrl,prompt,text){
  var chat=document.getElementById('chatMessages');
  var w=document.getElementById('welcomeScreen');
  if(w)w.remove();
  var m=document.createElement('div');
  m.className='message assistant';
  var av='<div class="message-avatar"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></svg></div>';
  var content='<div style="max-width:100%"><img src="'+escapeHtml(imgUrl)+'" alt="'+escapeHtml(prompt)+'" style="max-width:100%;border-radius:12px;display:block;border:1px solid var(--bd)" onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'block\'"><div style="color:var(--rd);display:none">Image non chargee.</div>';
  if(text)content+='<div style="margin-top:8px;color:var(--txd);font-size:13px">'+escapeHtml(text)+'</div>';
  if(prompt)content+='<div style="margin-top:4px;color:var(--txdd);font-size:11px">Prompt: '+escapeHtml(prompt)+'</div>';
  content+='</div><div class="ai-badge">ELLIOTT IA</div>';
  m.innerHTML=av+'<div class="message-content">'+content+'</div>';
  chat.appendChild(m);
  chat.scrollTop=chat.scrollHeight;
}

function addMusicMessage(audioUrl, prompt){
  var chat=document.getElementById('chatMessages');
  var w=document.getElementById('welcomeScreen');
  if(w)w.remove();
  var m=document.createElement('div');
  m.className='message assistant';
  var av='<div class="message-avatar"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></svg></div>';
  var content='<div style="max-width:100%">';
  content+='<div style="margin-bottom:8px;color:var(--tx);font-size:14px">🎵 Musique generee: <strong>'+escapeHtml(prompt)+'</strong></div>';
  content+='<div class="music-player"><audio controls src="'+escapeHtml(audioUrl)+'"></audio></div>';
  content+='</div><div class="ai-badge">ELLIOTT IA</div>';
  m.innerHTML=av+'<div class="message-content">'+content+'</div>';
  chat.appendChild(m);
  chat.scrollTop=chat.scrollHeight;
}

function showTyping(t){
  var chat=document.getElementById('chatMessages');
  var w=document.getElementById('welcomeScreen');
  if(w)w.remove();
  var m=document.createElement('div');
  m.className='message assistant';
  m.id='typingMsg';
  m.innerHTML='<div class="message-avatar"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></svg></div><div class="message-content"><div class="typing"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div><div style="font-size:12px;color:var(--txd);margin-top:4px">'+(t||'Reflexion...')+'</div></div>';
  chat.appendChild(m);
  chat.scrollTop=chat.scrollHeight;
}

function hideTyping(){var t=document.getElementById('typingMsg');if(t)t.remove();}

function playAudioUrl(url){
  if(!url)return;
  fetch(url).then(function(r){return r.blob()}).then(function(blob){
    var u=URL.createObjectURL(blob);
    var a=new Audio(u);
    a.onended=function(){URL.revokeObjectURL(u);setTimeout(function(){setAvatarState('idle');},500);};
    a.onerror=function(){URL.revokeObjectURL(u);parler(window._lastResponse||'');};
    var p=a.play();
    if(p&&p.catch)p.catch(function(){
      URL.revokeObjectURL(u);
      parler(window._lastResponse||'');
    });
  }).catch(function(){
    parler(window._lastResponse||'');
  });
}

function speakText(text){
  if(!text)return;
  window._lastResponse=text;
  if(autoSpeak)parler(text);
}

function speakMsg(id){
  var el=document.getElementById(id);
  if(!el)return;
  var content=el.querySelector('.message-content');
  if(content)parler(content.innerText);
}

function speakLast(){if(window._lastResponse)parler(window._lastResponse);}

function copyMsg(id){
  var el=document.getElementById(id);
  if(!el)return;
  var content=el.querySelector('.message-content');
  if(content)navigator.clipboard.writeText(content.innerText).catch(function(){});
}

function copyText(text){if(text)navigator.clipboard.writeText(text).catch(function(){});}

function sendFeedback(msgId,positive){
  var upBtn=document.getElementById('thumbUp_'+msgId);
  var dnBtn=document.getElementById('thumbDn_'+msgId);
  if(upBtn)upBtn.classList.toggle('liked',positive);
  if(dnBtn)dnBtn.classList.toggle('disliked',!positive);
  fetch('/api/feedback',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({message_id:msgId,positive:positive,conversation_id:convId})});
}

function sendMessage(){
  var i=document.getElementById('chatInput');
  var msg=i.value.trim();
  if(!msg)return;
  synth.cancel();
  addMessage(msg,true);
  i.value='';
  if(isChartRequest(msg)){
    showTyping('Generation du graphique...');
    setAvatarState('thinking');
    if(window.elliottParticles)window.elliottParticles.setSpeaking(true);
    fetch('/api/chart',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({prompt:msg})})
    .then(function(r){return r.json()})
    .then(function(d){
      hideTyping();setAvatarState('idle');
      if(window.elliottParticles)window.elliottParticles.setSpeaking(false);
      if(d.chart_url){
        var chat=document.getElementById('chatMessages');
        var w=document.getElementById('welcomeScreen');
        if(w)w.remove();
        var m=document.createElement('div');m.className='message assistant view-transition';
        m.id='msg_'+(++msgCount);
        var av='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></svg>';
        var content='<img class="chart-msg-img" src="'+escapeHtml(d.chart_url)+'" alt="Graphique">';
        if(d.text)content+='<div style="margin-top:8px">'+formatMarkdown(d.text)+'</div>';
        content+='<div class="ai-badge">ELLIOTT IA - Graphique</div>';
        m.innerHTML='<div class="message-avatar"><div style="width:34px;height:34px;border-radius:10px;background:linear-gradient(135deg,var(--ac),var(--pp));display:flex;align-items:center;justify-content:center">'+av+'</div></div><div class="message-content">'+content+'</div>';
        chat.appendChild(m);chat.scrollTop=chat.scrollHeight;
      }else{
        addMessage('Impossible de generer le graphique.',false);
      }
    })
    .catch(function(){hideTyping();setAvatarState('idle');if(window.elliottParticles)window.elliottParticles.setSpeaking(false);addMessage('Erreur lors de la generation du graphique.',false);});
    i.focus();
    return;
  }
  var isSearch=needsWebSearchMsg(msg);
  showTyping(isSearch?'Recherche sur le net...':'Reflexion...');
  document.getElementById('headerSubtitle').textContent=isSearch?'Recherche...':'En reflexion...';
  setAvatarState('thinking');
  if(window.elliottParticles)window.elliottParticles.setSpeaking(true);
  fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({message:msg,conversation_id:convId})})
  .then(function(r){return r.json()})
  .then(function(d){
    hideTyping();
    setAvatarState('idle');
    document.getElementById('headerSubtitle').textContent='Pret a discuter';
    if(d.image_url){
      addImageMessage(d.image_url,d.image_prompt||'',d.text||'Image generee');
      if(autoSpeak&&d.text)speakText(d.text);
      if(window.elliottParticles)window.elliottParticles.setSpeaking(false);
    }else if(d.music_url){
      addMusicMessage(d.music_url,d.music_prompt||msg);
      if(window.elliottParticles)window.elliottParticles.setSpeaking(false);
    }else{
      var conf=typeof d.confidence==='number'?d.confidence:0.8;
      setAvatarState('speaking');
      window._lastResponse=d.text||'Pas de reponse';
      addMessageWithTypewriter(d.text||'Pas de reponse',false,{confidence:conf,searchUsed:d.search_used});
      if(autoSpeak&&d.text){
        parler(d.text);
      }
      setTimeout(function(){if(window.elliottParticles)window.elliottParticles.setSpeaking(false);},3000);
    }
  })
  .catch(function(){
    hideTyping();
    setAvatarState('idle');
    if(window.elliottParticles)window.elliottParticles.setSpeaking(false);
    document.getElementById('headerSubtitle').textContent='Pret a discuter';
    addMessage('Erreur de connexion. Verifiez internet.',false);
  });
  i.focus();
}

function needsWebSearchMsg(msg){
  var patterns=['quel','quoi','comment','pourquoi','quand','ou est','combien','qui est','definition','explique','actualit','nouveau','prix','meteo','meilleur','compar','2024','2025','2026'];
  return patterns.some(function(p){return msg.toLowerCase().indexOf(p)!==-1;})&&msg.split(' ').length>3;
}

function sendImage(){
  var i=document.getElementById('chatInput');
  var msg=i.value.trim();
  if(!msg)msg='Un paysage magique au coucher du soleil';
  addMessage('Image: '+msg,true);
  i.value='';
  showTyping('Generation de l image...');
  fetch('/api/image',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({prompt:msg})})
  .then(function(r){return r.json()})
  .then(function(d){
    hideTyping();
    if(d.url){addImageMessage(d.url,msg,'');}
    else{addMessage('Image non disponible. Verifiez internet.',false);}
  })
  .catch(function(){hideTyping();addMessage('Erreur lors de la generation.',false);});
}

function clearChat(){
  convId='c_'+Date.now();
  window._lastResponse='';
  window._lastResponseEl=null;
  synth.cancel();
  var chat=document.getElementById('chatMessages');
  chat.innerHTML='<div class="welcome" id="welcomeScreen"><div class="welcome-icon glow-animate"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg></div><h2>Bonjour! Je suis ELLIOTT</h2><p>IA <strong>revolutionnaire</strong> qui apprend et s\'ameliore!</p><div class="welcome-grid"><div class="welcome-card" onclick="sendQuick(\'Explique le machine learning simplement\')"><div class="welcome-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg></div><h4>Apprendre</h4><p>ML, code</p></div><div class="welcome-card" onclick="sendImage()"><div class="welcome-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg></div><h4>Creer</h4><p>Images</p></div><div class="welcome-card" onclick="showView(\'music\',document.querySelectorAll(\'.menu-item\')[3])"><div class="welcome-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg></div><h4>Musique</h4><p>Generez</p></div><div class="welcome-card" onclick="showView(\'code\',document.querySelectorAll(\'.menu-item\')[5])"><div class="welcome-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg></div><h4>Code</h4><p>Python</p></div></div></div>';
}

// --- MUSIC ---
function generateMusic(){
  var prompt=document.getElementById('musicPrompt').value.trim();
  if(!prompt){alert('Entrez un descriptif musical.');return;}
  var btn=document.getElementById('musicGenBtn');
  btn.disabled=true;btn.innerHTML='<div class="typing" style="display:inline-flex"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div> Generation...';
  document.getElementById('musicResult').innerHTML='';
  showView('chat',document.querySelector('.menu-item'));
  showTyping('Generation musicale en cours...');
  fetch('/api/music',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({prompt:prompt})})
  .then(function(r){return r.json()})
  .then(function(d){
    hideTyping();btn.disabled=false;btn.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polygon points="5 3 19 12 5 21 5 3"/></svg> Generer la Musique';
    if(d.url){addMusicMessage(d.url,prompt);}
    else{addMessage('Generation musicale echouee. '+ (d.error||''),false);}
  })
  .catch(function(){hideTyping();btn.disabled=false;btn.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polygon points="5 3 19 12 5 21 5 3"/></svg> Generer la Musique';addMessage('Erreur de generation musicale.',false);});
}

// --- CODE ---
function executeCode(){
  var code=document.getElementById('codeEditor').value;
  if(!code.trim()){alert('Ecrivez du code d abord.');return;}
  var btn=document.getElementById('execBtn');
  btn.disabled=true;btn.innerHTML='<div class="typing" style="display:inline-flex"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div> Execution...';
  document.getElementById('codeResult').innerHTML='';
  fetch('/api/execute',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({code:code})})
  .then(function(r){return r.json()})
  .then(function(d){
    btn.disabled=false;btn.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polygon points="5 3 19 12 5 21 5 3"/></svg> Executer';
    var el=document.getElementById('codeResult');
    if(d.error){
      el.className='tool-result error';el.textContent='Erreur: '+d.error;
    }else{
      var out='';
      if(d.stdout)out+='Sortie:\n'+d.stdout;
      if(d.stderr)out+='\nErreurs:\n'+d.stderr;
      if(d.returncode===0&&!d.stderr)out='Code execute avec succes!\n'+(d.stdout||'(pas de sortie)');
      el.className='tool-result '+(d.returncode===0?'success':'error');el.textContent=out||'(pas de sortie)';
    }
  })
  .catch(function(){btn.disabled=false;btn.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polygon points="5 3 19 12 5 21 5 3"/></svg> Executer';document.getElementById('codeResult').className='tool-result error';document.getElementById('codeResult').textContent='Erreur de communication.';});
}

// --- VISION ---
function analyzeImageUrl(){
  var url=document.getElementById('imageUrlInput').value.trim();
  if(!url){alert('Entrez une URL d image.');return;}
  showView('chat',document.querySelector('.menu-item'));
  showTyping('Analyse de l image...');
  fetch('/api/vision',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({url:url})})
  .then(function(r){return r.json()})
  .then(function(d){
    hideTyping();
    if(d.description){
      var chat=document.getElementById('chatMessages');
      var w=document.getElementById('welcomeScreen');
      if(w)w.remove();
      var m=document.createElement('div');m.className='message assistant';
      var av='<div class="message-avatar"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg></div>';
      var content='<img src="'+escapeHtml(url)+'" style="max-width:300px;border-radius:8px;margin-bottom:8px;border:1px solid var(--bd)"><br><strong>Analyse IA:</strong><br>'+formatMarkdown(d.description);
      m.innerHTML=av+'<div class="message-content">'+content+'<div class="ai-badge">Vision IA</div></div>';
      chat.appendChild(m);chat.scrollTop=chat.scrollHeight;
    }else{addMessage('Analyse non disponible.',false);}
  })
  .catch(function(){hideTyping();addMessage("Erreur d'analyse.",false);});
}

function handleImageUpload(event){
  var file=event.target.files[0];
  if(!file)return;
  var reader=new FileReader();
  reader.onload=function(e){
    var b64=e.target.result;
    showView('chat',document.querySelector('.menu-item'));
    showTyping('Analyse de l image uploadee...');
    fetch('/api/vision',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({base64:b64})})
    .then(function(r){return r.json()})
    .then(function(d){
      hideTyping();
      if(d.description){
        var chat=document.getElementById('chatMessages');
        var w=document.getElementById('welcomeScreen');
        if(w)w.remove();
        var m=document.createElement('div');m.className='message assistant';
        var av='<div class="message-avatar"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg></div>';
        var content='<img src="'+b64+'" style="max-width:300px;border-radius:8px;margin-bottom:8px;border:1px solid var(--bd)"><br><strong>Analyse IA:</strong><br>'+formatMarkdown(d.description);
        m.innerHTML=av+'<div class="message-content">'+content+'<div class="ai-badge">Vision IA</div></div>';
        chat.appendChild(m);chat.scrollTop=chat.scrollHeight;
      }else{addMessage('Analyse non disponible.',false);}
    })
    .catch(function(){hideTyping();addMessage("Erreur d'analyse.",false);});
  };
  reader.readAsDataURL(file);
}

// --- SEARCH ---
function doWebSearch(){
  var q=document.getElementById('searchInput').value.trim();
  if(!q){alert('Entrez une requete de recherche.');return;}
  var el=document.getElementById('searchResults');
  el.innerHTML='<div class="tool-hint">Recherche en cours...</div>';
  fetch('/api/search',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({query:q})})
  .then(function(r){return r.json()})
  .then(function(d){
    if(d.results&&d.results.length>0){
      var html='';
      d.results.forEach(function(r,i){
        html+='<div style="padding:12px;border:1px solid var(--bd);border-radius:var(--r);margin-bottom:8px">';
        html+='<div style="font-weight:600;color:var(--ac);margin-bottom:4px">'+escapeHtml(r.title)+'</div>';
        html+='<div style="font-size:12px;color:var(--txd);margin-bottom:4px">'+escapeHtml(r.snippet)+'</div>';
        if(r.url)html+='<a href="'+escapeHtml(r.url)+'" target="_blank" style="font-size:11px;color:var(--cy);text-decoration:none">'+escapeHtml(r.url)+'</a>';
        html+='</div>';
      });
      el.innerHTML=html;
    }else{
      el.innerHTML='<div class="tool-hint">Aucun resultat. Essayez une autre recherche.</div>';
    }
  })
  .catch(function(){el.innerHTML='<div class="tool-hint">Erreur de recherche.</div>';});
}

// --- DASHBOARD ---
function loadDashboard(){
  showView('dashboard',null);
  fetch('/api/memory').then(function(r){return r.json()}).then(function(d){
    var s=d.stats||{};
    document.getElementById('dConv').textContent=s.total_conversations||0;
    document.getElementById('dTopics').textContent=s.topics_learned||0;
    document.getElementById('dCorr').textContent=s.corrections_made||0;
    var thumbs=(s.thumbs_up||0)+(s.thumbs_down||0);
    document.getElementById('dThumbs').textContent=thumbs;
    document.getElementById('dImages').textContent=s.images_generated||0;
    document.getElementById('dMusic').textContent=s.music_generated||0;
    document.getElementById('dCode').textContent=s.code_executed||0;
    document.getElementById('dSearch').textContent=s.searches_performed||0;
    var avgQ=s.quality_score_avg||0;
    document.getElementById('dQuality').textContent=Math.round(avgQ*100)+'%';
    var upMs=Date.now()-startTime;
    var mins=Math.floor(upMs/60000);
    if(mins>60)document.getElementById('dUptime').textContent=Math.floor(mins/60)+'h'+(mins%60)+'m';
    else document.getElementById('dUptime').textContent=mins+'m';

    var topicsDiv=document.getElementById('topicsList');
    topicsDiv.innerHTML='';
    var topics=d.topics||{};
    var sorted=Object.entries(topics).sort(function(a,b){return b[1]-a[1]}).slice(0,10);
    var maxCount=sorted.length>0?sorted[0][1]:1;
    sorted.forEach(function(t){
      var pct=Math.round((t[1]/maxCount)*100);
      topicsDiv.innerHTML+='<div class="topic-bar"><div class="topic-name">'+escapeHtml(t[0])+'</div><div class="topic-fill-bg"><div class="topic-fill" style="width:'+pct+'%"></div></div><div class="topic-count">'+t[1]+'</div></div>';
    });

    var corrDiv=document.getElementById('correctionsList');
    corrDiv.innerHTML='';
    var corrs=d.corrections||[];
    corrs.slice(-10).reverse().forEach(function(c){
      corrDiv.innerHTML+='<div class="correction-item"><div class="orig">'+escapeHtml(c.original||'')+'</div><div class="corr">-> '+escapeHtml(c.corrected||'')+'</div><div class="corr-time">'+escapeHtml(c.timestamp||'')+'</div></div>';
    });
    if(corrs.length===0)corrDiv.innerHTML='<div style="color:var(--txdd);font-size:13px">Aucune correction enregistree.</div>';

    var sumDiv=document.getElementById('summariesList');
    sumDiv.innerHTML='';
    var sums=d.conversation_summaries||[];
    sums.slice(-5).reverse().forEach(function(s){
      var topicList=Object.entries(s.topics||{}).sort(function(a,b){return b[1]-a[1]}).slice(0,5).map(function(t){return t[0]+' ('+t[1]+')'}).join(', ');
      sumDiv.innerHTML+='<div class="correction-item"><div class="corr">'+escapeHtml(s.period||'')+'</div><div style="font-size:11px;color:var(--txd);margin-top:4px">'+s.count+' conversations | Sujets: '+escapeHtml(topicList)+'</div></div>';
    });
    if(sums.length===0)sumDiv.innerHTML='<div style="color:var(--txdd);font-size:13px">Pas encore de resumes.</div>';
  });
}

function updateUptime(){
  var upMs=Date.now()-startTime;
  var mins=Math.floor(upMs/60000);
  var el=document.getElementById('dUptime');
  if(el){
    if(mins>60)el.textContent=Math.floor(mins/60)+'h'+(mins%60)+'m';
    else el.textContent=mins+'m';
  }
}
setInterval(updateUptime,60000);

function checkMobile(){
  var btn=document.getElementById('menuToggle');
  if(window.innerWidth<=768){btn.style.display='flex';}
  else{btn.style.display='none';document.getElementById('sidebar').classList.remove('open');}
}
window.addEventListener('resize',checkMobile);
checkMobile();

// --- PWA ---
var deferredPrompt=null;
window.addEventListener('beforeinstallprompt',function(e){
  e.preventDefault();deferredPrompt=e;
  document.getElementById('installBtn').style.display='inline-flex';
});
function installPWA(){
  if(!deferredPrompt)return;
  deferredPrompt.prompt();
  deferredPrompt.userChoice.then(function(choice){
    if(choice.outcome==='accepted')document.getElementById('installBtn').style.display='none';
    deferredPrompt=null;
  });
}
if('serviceWorker' in navigator){navigator.serviceWorker.register('/sw.js').catch(function(){});}

// ============================================================
// PARTICLES BACKGROUND
// ============================================================
(function(){
  var c=document.getElementById('particlesCanvas');
  if(!c)return;
  var ctx=c.getContext('2d');
  var particles=[];
  var speaking=false;
  var W,H;
  var colors=['rgba(99,102,241,','rgba(168,85,247,','rgba(59,130,246,','rgba(139,92,246,'];

  function resize(){W=c.width=window.innerWidth;H=c.height=window.innerHeight;}
  resize();
  window.addEventListener('resize',resize);

  function initParticles(){
    particles=[];
    var count=Math.min(60,Math.floor(W*H/25000));
    for(var i=0;i<count;i++){
      particles.push({
        x:Math.random()*W,y:Math.random()*H,
        vx:(Math.random()-.5)*.3,vy:(Math.random()-.5)*.3,
        r:Math.random()*2+1,
        color:colors[Math.floor(Math.random()*colors.length)],
        alpha:Math.random()*.3+.1
      });
    }
  }
  initParticles();

  function draw(){
    ctx.clearRect(0,0,W,H);
    for(var i=0;i<particles.length;i++){
      var p=particles[i];
      if(speaking){
        p.x+=p.vx*3;p.y+=p.vy*3;
      }else{
        p.x+=p.vx;p.y+=p.vy;
      }
      if(p.x<0)p.x=W;if(p.x>W)p.x=0;
      if(p.y<0)p.y=H;if(p.y>H)p.y=0;
      ctx.beginPath();
      ctx.arc(p.x,p.y,p.r,0,Math.PI*2);
      ctx.fillStyle=p.color+(speaking?p.alpha*2:p.alpha)+')';
      ctx.fill();
    }
    for(var i=0;i<particles.length;i++){
      for(var j=i+1;j<particles.length;j++){
        var dx=particles[i].x-particles[j].x;
        var dy=particles[i].y-particles[j].y;
        var dist=Math.sqrt(dx*dx+dy*dy);
        if(dist<120){
          ctx.beginPath();
          ctx.moveTo(particles[i].x,particles[i].y);
          ctx.lineTo(particles[j].x,particles[j].y);
          ctx.strokeStyle='rgba(99,102,241,'+(speaking?.15:.06)+')';
          ctx.lineWidth=.5;
          ctx.stroke();
        }
      }
    }
    requestAnimationFrame(draw);
  }
  draw();

  window.elliottParticles={setSpeaking:function(v){speaking=v;}};
})();

// ============================================================
// AVATAR STATE MANAGEMENT
// ============================================================
var avatarState='idle';
function setAvatarState(state){
  avatarState=state;
  var va=document.getElementById('voiceAvatar');
  if(va){
    va.classList.remove('avatar-listening','avatar-thinking','avatar-speaking');
    if(state==='listening')va.classList.add('avatar-listening');
    else if(state==='thinking')va.classList.add('avatar-thinking');
    else if(state==='speaking')va.classList.add('avatar-speaking');
  }
  var wa=document.getElementById('welcomeAvatar');
  if(wa){
    wa.classList.remove('avatar-glow-active');
    if(state==='thinking'||state==='speaking')wa.classList.add('avatar-glow-active');
  }
}

// ============================================================
// TYPEWRITER EFFECT
// ============================================================
var typewriterQueue=[];
var typewriterRunning=false;

function typewriterEffect(element,text,speed,callback){
  speed=speed||12;
  element.innerHTML='';
  var i=0;
  var cursor=document.createElement('span');
  cursor.className='typewriter-cursor';
  function type(){
    if(i<text.length){
      if(text[i]==='<'){
        var end=text.indexOf('>',i);
        if(end!==-1){
          element.innerHTML+=text.substring(i,end+1);
          i=end+1;
        }else{
          element.innerHTML+=text[i];i++;
        }
      }else{
        element.innerHTML+=text[i];i++;
      }
      element.appendChild(cursor);
      var chat=document.getElementById('chatMessages');
      chat.scrollTop=chat.scrollHeight;
      setTimeout(type,speed);
    }else{
      element.classList.add('typewriter-done');
      if(cursor.parentNode)cursor.parentNode.removeChild(cursor);
      if(callback)callback();
      typewriterRunning=false;
      processTypewriterQueue();
    }
  }
  typewriterRunning=true;
  type();
}

function processTypewriterQueue(){
  if(typewriterRunning||typewriterQueue.length===0)return;
  var item=typewriterQueue.shift();
  typewriterEffect(item.element,item.text,item.speed,item.callback);
}

function addMessageWithTypewriter(content,isUser,opts){
  opts=opts||{};
  if(isUser){
    addMessage(content,true);
    return;
  }
  var chat=document.getElementById('chatMessages');
  var w=document.getElementById('welcomeScreen');
  if(w)w.remove();
  var m=document.createElement('div');
  m.className='message assistant view-transition';
  m.id='msg_'+(++msgCount);
  var av='<div class="message-avatar"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></svg></div>';
  var formatted=formatMarkdown(content);
  var h='<div class="message-avatar">'+av.substring(av.indexOf('>')+1,av.lastIndexOf('<'))+'</div><div class="message-content">';
  var actionsHTML='';
  actionsHTML+='<div class="ai-badge">ELLIOTT IA</div>';
  if(opts.searchUsed)actionsHTML+='<div class="search-badge">Recherche web utilisee</div>';
  if(typeof opts.confidence==='number'){
    actionsHTML+='<div class="confidence-bar"><div class="confidence-fill '+confidenceClass(opts.confidence)+'" style="width:'+(opts.confidence*100)+'%"></div></div>';
  }
  var mid=m.id;
  actionsHTML+='<div class="msg-actions">';
  actionsHTML+='<button class="msg-action-btn" onclick="speakMsg(\''+mid+'\')" title="Ecouter"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg></button>';
  actionsHTML+='<button class="msg-action-btn" onclick="copyMsg(\''+mid+'\')" title="Copier"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg></button>';
  actionsHTML+='<button class="msg-action-btn" id="thumbUp_'+mid+'" onclick="sendFeedback(\''+mid+'\',true)" title="Utile"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg></button>';
  actionsHTML+='<button class="msg-action-btn" id="thumbDn_'+mid+'" onclick="sendFeedback(\''+mid+'\',false)" title="Pas utile"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/></svg></button>';
  actionsHTML+='</div>';

  var contentDiv=document.createElement('div');
  contentDiv.className='message-content';
  contentDiv.innerHTML=actionsHTML;
  m.innerHTML=av;
  m.appendChild(contentDiv);
  chat.appendChild(m);
  chat.scrollTop=chat.scrollHeight;
  window._lastResponse=content;
  window._lastResponseEl=m;

  var rendered=formatMarkdown(content);
  typewriterQueue.push({element:contentDiv, text:rendered, speed:8, callback:null});
  processTypewriterQueue();
}

// ============================================================
// CHART DETECTION
// ============================================================
var CHART_KW=['graphique','chart','graph','diagramme','courbe','histogramme','camembert','barres','visualisation'];
function isChartRequest(msg){
  var m=msg.toLowerCase();
  return CHART_KW.some(function(k){return m.indexOf(k)!==-1;});
}

// ============================================================
// DOCUMENT UPLOAD
// ============================================================
function handleDocUpload(event){
  var file=event.target.files[0];
  if(!file)return;
  var reader=new FileReader();
  reader.onload=function(e){
    var b64=e.target.result;
    addMessage('Document: '+file.name,true);
    showTyping('Analyse du document...');
    setAvatarState('thinking');
    fetch('/api/document',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({base64:b64,filename:file.name})})
    .then(function(r){return r.json()})
    .then(function(d){
      hideTyping();setAvatarState('idle');
      if(d.text||d.summary){
        var content='';
        if(d.summary)content+=d.summary;
        if(d.text_preview)content+='<div class="doc-preview">'+escapeHtml(d.text_preview)+'</div>';
        var chat=document.getElementById('chatMessages');
        var w=document.getElementById('welcomeScreen');
        if(w)w.remove();
        var m=document.createElement('div');m.className='message assistant view-transition';
        m.id='msg_'+(++msgCount);
        var av='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>';
        m.innerHTML='<div class="message-avatar"><div style="width:34px;height:34px;border-radius:10px;background:linear-gradient(135deg,var(--or),var(--rd));display:flex;align-items:center;justify-content:center">'+av+'</div></div><div class="message-content">'+formatMarkdown(content)+'<div class="doc-badge">Document Analyse</div></div>';
        chat.appendChild(m);chat.scrollTop=chat.scrollHeight;
        window._lastResponse=content;
        window._lastResponseEl=m;
      }else{
        addMessage('Impossible d\'analyser le document.',false);
      }
    })
    .catch(function(){hideTyping();setAvatarState('idle');addMessage('Erreur lors de l\'analyse du document.',false);});
  };
  reader.readAsDataURL(file);
  event.target.value='';
}

// ============================================================
// CHAT IMAGE UPLOAD (inline analysis)
// ============================================================
function handleChatImageUpload(event){
  var file=event.target.files[0];
  if(!file)return;
  var reader=new FileReader();
  reader.onload=function(e){
    var b64=e.target.result;
    addMessage('Image: '+file.name,true);
    showTyping('Analyse de l image...');
    setAvatarState('thinking');
    if(window.elliottParticles)window.elliottParticles.setSpeaking(true);
    fetch('/api/vision',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({base64:b64})})
    .then(function(r){return r.json()})
    .then(function(d){
      hideTyping();setAvatarState('idle');
      if(window.elliottParticles)window.elliottParticles.setSpeaking(false);
      if(d.description){
        var chat=document.getElementById('chatMessages');
        var w=document.getElementById('welcomeScreen');
        if(w)w.remove();
        var m=document.createElement('div');m.className='message assistant view-transition';
        m.id='msg_'+(++msgCount);
        var av='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>';
        var content='<img src="'+b64+'" style="max-width:300px;border-radius:8px;margin-bottom:8px;border:1px solid var(--bd)"><br><strong>Analyse IA:</strong><br>'+formatMarkdown(d.description);
        m.innerHTML='<div class="message-avatar"><div style="width:34px;height:34px;border-radius:10px;background:linear-gradient(135deg,var(--ac),var(--pp));display:flex;align-items:center;justify-content:center">'+av+'</div></div><div class="message-content">'+content+'<div class="ai-badge">Vision IA</div></div>';
        chat.appendChild(m);chat.scrollTop=chat.scrollHeight;
      }else{
        addMessage('Analyse non disponible.',false);
      }
    })
    .catch(function(){hideTyping();setAvatarState('idle');if(window.elliottParticles)window.elliottParticles.setSpeaking(false);addMessage("Erreur d'analyse.",false);});
  };
  reader.readAsDataURL(file);
  event.target.value='';
}
</script>
</body>
</html>"""

RENDERED_HTML = HTML_TEMPLATE.encode("utf-8")


# =====================================================================
#  PWA ROUTES
# =====================================================================
@app.route("/manifest.json")
def pwa_manifest():
    manifest = {
        "name": "ELLIOTT - IA Ultime",
        "short_name": "ELLIOTT",
        "description": "Assistant IA ultime: Chat, Images, Musique, Vision, Code",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#06060a",
        "theme_color": "#6366f1",
        "orientation": "any",
        "icons": [
            {"src": "/icon/192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
            {"src": "/icon/512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
        ],
    }
    body = _json.dumps(manifest, ensure_ascii=False).encode("utf-8")
    return Response(body, content_type="application/json; charset=utf-8")


@app.route("/sw.js")
def service_worker():
    sw_code = """
const CACHE_NAME='elliott-v1';
const urlsToCache=['/'];
self.addEventListener('install',e=>{e.waitUntil(caches.open(CACHE_NAME).then(c=>c.addAll(urlsToCache)).then(()=>self.skipWaiting()));});
self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(k=>Promise.all(k.filter(k=>k!==CACHE_NAME).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));});
self.addEventListener('fetch',e=>{if(e.request.method!=='GET')return;e.respondWith(caches.match(e.request).then(r=>{return r||fetch(e.request).then(resp=>{if(!resp||resp.status!==200)return resp;const r2=resp.clone();caches.open(CACHE_NAME).then(c=>c.put(e.request,r2));return resp;}).catch(()=>caches.match('/')));}));});
"""
    return Response(sw_code, content_type="application/javascript")


@app.route("/icon/<int:size>.png")
def pwa_icon(size):
    try:
        from PIL import Image, ImageDraw, ImageFont
        cached = os.path.join(GENERATED_DIR, f"icon-{size}.png")
        if os.path.exists(cached):
            return send_file(cached, mimetype="image/png")
        img = Image.new("RGB", (size, size), (99, 102, 241))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", size // 2)
        except Exception:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), "E", font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        draw.text(((size - w) // 2, (size - h) // 2 - bbox[1]), "E", fill="white", font=font)
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        with open(cached, "wb") as f:
            f.write(buf.getvalue())
        buf.seek(0)
        return send_file(buf, mimetype="image/png")
    except Exception:
        img = Image.new("RGB", (size, size), (99, 102, 241))
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return send_file(buf, mimetype="image/png")


# =====================================================================
#  STATIC FILES (generated)
# =====================================================================
@app.route("/generated/<path:filename>")
def serve_generated(filename):
    return send_from_directory(GENERATED_DIR, filename)


# =====================================================================
#  API ROUTES
# =====================================================================
@app.route("/")
def index():
    return Response(RENDERED_HTML, content_type="text/html; charset=utf-8")


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True)
    if not data:
        return Response(b'{"error":"Invalid"}', status=400, content_type="application/json")
    message = data.get("message", "").strip()
    if not message:
        return Response(b'{"error":"Empty"}', status=400, content_type="application/json")
    conv_id = data.get("conversation_id", "default")

    if conv_id not in conversations:
        conversations[conv_id] = []
    if len(conversations[conv_id]) > 20:
        conversations[conv_id] = conversations[conv_id][-10:]

    m = get_memory()
    msg_lower = message.lower()

    m["stats"]["total_messages"] += 1
    save_memory(m)

    # Correction detection
    if is_correction(message) and m["corrections"]:
        last_corr = m["corrections"][-1]
        corrected_text = message
        update_memory(lambda mem: record_correction(mem, last_corr.get("original", ""), corrected_text, conv_id))
        resp = {
            "text": "Merci pour la correction! J'ai retenu: **" + corrected_text + "**. Je m'en souviendrai!",
            "speak": "Merci pour la correction.",
            "confidence": 1.0,
            "fromAI": True,
        }
        body = _json.dumps(resp, ensure_ascii=False).encode("utf-8")
        return Response(body, content_type="application/json; charset=utf-8")

    # Fast responses
    fast = get_fast_response(msg_lower)
    if fast is not None:
        conversations[conv_id].append({"role": "user", "content": message})
        conversations[conv_id].append({"role": "assistant", "content": fast["text"]})
        resp = dict(fast)
        resp["fromAI"] = False
        resp["confidence"] = 1.0
        speak_text = fast.get("speak", fast["text"])[:200]
        resp["audio_url"] = _generate_tts(speak_text)
        body = _json.dumps(resp, ensure_ascii=False).encode("utf-8")
        return Response(body, content_type="application/json; charset=utf-8")

    # Image request
    if is_image_request(message):
        clean_prompt = extract_image_prompt(message)
        if len(clean_prompt) < 3:
            clean_prompt = message
        url = generate_image(clean_prompt)
        if url:
            update_memory(lambda mem: mem["stats"].__setitem__("images_generated", mem["stats"].get("images_generated", 0) + 1))
            resp = {
                "text": "Voici votre image:",
                "image_url": url,
                "image_prompt": clean_prompt,
                "fromAI": True,
                "confidence": 1.0,
            }
        else:
            resp = {"text": "Image non disponible. Verifiez votre connexion.", "fromAI": True, "confidence": 0.5}
        body = _json.dumps(resp, ensure_ascii=False).encode("utf-8")
        return Response(body, content_type="application/json; charset=utf-8")

    # Music request
    if is_music_request(message):
        music_prompt = extract_music_prompt(message)
        result_path = generate_music(music_prompt)
        if result_path:
            filename = os.path.basename(result_path)
            update_memory(lambda mem: mem["stats"].__setitem__("music_generated", mem["stats"].get("music_generated", 0) + 1))
            resp = {
                "text": f"🎵 Musique generee pour: {music_prompt}",
                "music_url": f"/generated/{filename}",
                "music_prompt": music_prompt,
                "fromAI": True,
                "confidence": 1.0,
            }
        else:
            resp = {
                "text": "Generation musicale non disponible. Essayez de reformuler votre demande.",
                "fromAI": True,
                "confidence": 0.3,
            }
        body = _json.dumps(resp, ensure_ascii=False).encode("utf-8")
        return Response(body, content_type="application/json; charset=utf-8")

    # Track topics
    topics = extract_topics(message)
    update_memory(lambda mem: track_topics(mem, topics))
    for t in topics:
        if t != "general":
            update_memory(lambda mem, topic=t, msg=message: record_knowledge(mem, topic, msg))

    # Web search if needed - toujours pour les questions factuelles
    web_context = ""
    search_used = False
    should_search = needs_web_search(message)
    if not should_search:
        question_words = ["qui", "quoi", "ou", "quand", "comment", "pourquoi", "combien", "quel", "quelle", "quels"]
        if any(message.lower().startswith(w) for w in question_words) and len(message.split()) > 3:
            should_search = True
    if should_search:
        results = web_search(message)
        if results:
            web_context = "\n\nIMPORTANT: Voici les resultats de recherche web. Utilise-les pour repondre de facon precise et actualisee:\n"
            for i, r in enumerate(results, 1):
                web_context += f"{i}. {r['title']}: {r['snippet']}\n"
            search_used = True
            update_memory(lambda mem: mem["stats"].__setitem__("searches_performed", mem["stats"].get("searches_performed", 0) + 1))

    # Get memory context
    memory_context = find_relevant_memory(m, message)

    # Get AI response
    conversations[conv_id].append({"role": "user", "content": message})
    ai_response = chat_ia(message, conversations[conv_id], memory_context, web_context)
    conversations[conv_id].append({"role": "assistant", "content": ai_response})

    # Calculate confidence & quality
    confidence = calculate_confidence(ai_response)
    quality = calculate_quality(ai_response, topics)

    # Record conversation in memory
    update_memory(lambda mem: mem["conversations"].append({
        "question": message[:200],
        "answer": ai_response[:200],
        "topics": topics,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "conversation_id": conv_id,
        "quality": quality,
    }))
    update_memory(lambda mem: mem["stats"].__setitem__("total_conversations", len(mem["conversations"])))

    # Update quality average
    all_quality = [c.get("quality", 0.5) for c in m.get("conversations", [])[-20:]]
    avg_quality = sum(all_quality) / len(all_quality) if all_quality else 0.5
    update_memory(lambda mem, q=avg_quality: mem["stats"].__setitem__("quality_score_avg", q))

    # Update favorite topics
    update_memory(lambda mem: mem["preferences"].__setitem__(
        "favorite_topics",
        sorted(mem["topics"].keys(), key=lambda k: mem["topics"][k], reverse=True)[:10],
    ))

    # Summarize old conversations periodically
    m_updated = load_memory()
    summarize_old_conversations(m_updated)
    save_memory(m_updated)

    resp = {
        "text": ai_response,
        "speak": ai_response,
        "confidence": confidence,
        "fromAI": True,
        "search_used": search_used,
        "audio_url": _generate_tts(ai_response),
    }
    body = _json.dumps(resp, ensure_ascii=False).encode("utf-8")
    return Response(body, content_type="application/json; charset=utf-8")


@app.route("/api/image", methods=["POST"])
def api_image():
    data = request.get_json(silent=True)
    if not data:
        return Response(b'{"error":"Invalid"}', status=400, content_type="application/json")
    prompt = data.get("prompt", "").strip()
    if not prompt:
        return Response(b'{"error":"Empty"}', status=400, content_type="application/json")
    url = generate_image(prompt)
    if url:
        update_memory(lambda mem: mem["stats"].__setitem__("images_generated", mem["stats"].get("images_generated", 0) + 1))
        resp = {"url": url, "prompt": prompt}
    else:
        resp = {"error": "Image non disponible"}
    body = _json.dumps(resp, ensure_ascii=False).encode("utf-8")
    return Response(body, content_type="application/json; charset=utf-8")


@app.route("/api/music", methods=["POST"])
def api_music():
    data = request.get_json(silent=True)
    if not data:
        return Response(b'{"error":"Invalid"}', status=400, content_type="application/json")
    prompt = data.get("prompt", "").strip()
    if not prompt:
        return Response(b'{"error":"Empty"}', status=400, content_type="application/json")
    result_path = generate_music(prompt)
    if result_path:
        filename = os.path.basename(result_path)
        update_memory(lambda mem: mem["stats"].__setitem__("music_generated", mem["stats"].get("music_generated", 0) + 1))
        resp = {"url": f"/generated/{filename}", "prompt": prompt}
    else:
        resp = {"error": "Generation musicale echouee"}
    body = _json.dumps(resp, ensure_ascii=False).encode("utf-8")
    return Response(body, content_type="application/json; charset=utf-8")


@app.route("/api/execute", methods=["POST"])
def api_execute():
    data = request.get_json(silent=True)
    if not data:
        return Response(b'{"error":"Invalid"}', status=400, content_type="application/json")
    code = data.get("code", "").strip()
    if not code:
        return Response(b'{"error":"Empty"}', status=400, content_type="application/json")
    timeout = min(data.get("timeout", 10), 30)
    result = execute_python_code(code, timeout)
    update_memory(lambda mem: mem["stats"].__setitem__("code_executed", mem["stats"].get("code_executed", 0) + 1))
    body = _json.dumps(result, ensure_ascii=False).encode("utf-8")
    return Response(body, content_type="application/json; charset=utf-8")


@app.route("/api/vision", methods=["POST"])
def api_vision():
    data = request.get_json(silent=True)
    if not data:
        return Response(b'{"error":"Invalid"}', status=400, content_type="application/json")
    url = data.get("url", "")
    b64 = data.get("base64", "")
    if url:
        result = analyze_image_url(url)
    elif b64:
        result = analyze_image_b64(b64)
    else:
        return Response(b'{"error":"No image"}', status=400, content_type="application/json")
    update_memory(lambda mem: mem["stats"].__setitem__("images_analyzed", mem["stats"].get("images_analyzed", 0) + 1))
    resp = {"description": result}
    body = _json.dumps(resp, ensure_ascii=False).encode("utf-8")
    return Response(body, content_type="application/json; charset=utf-8")


@app.route("/api/search", methods=["POST"])
def api_search():
    data = request.get_json(silent=True)
    if not data:
        return Response(b'{"error":"Invalid"}', status=400, content_type="application/json")
    query = data.get("query", "").strip()
    if not query:
        return Response(b'{"error":"Empty"}', status=400, content_type="application/json")
    results = web_search(query, num_results=8)
    update_memory(lambda mem: mem["stats"].__setitem__("searches_performed", mem["stats"].get("searches_performed", 0) + 1))
    resp = {"results": results or [], "query": query}
    body = _json.dumps(resp, ensure_ascii=False).encode("utf-8")
    return Response(body, content_type="application/json; charset=utf-8")


@app.route("/api/feedback", methods=["POST"])
def api_feedback():
    data = request.get_json(silent=True)
    if not data:
        return Response(b'{"error":"Invalid"}', status=400, content_type="application/json")
    positive = data.get("positive", True)
    conv_id = data.get("conversation_id", "default")

    def update(m):
        if positive:
            m["stats"]["thumbs_up"] = m["stats"].get("thumbs_up", 0) + 1
        else:
            m["stats"]["thumbs_down"] = m["stats"].get("thumbs_down", 0) + 1
        m["feedback"].append({
            "positive": positive,
            "conversation_id": conv_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    update_memory(update)
    return Response(b'{"ok":true}', content_type="application/json")


@app.route("/api/memory", methods=["GET"])
def api_memory():
    m = get_memory()
    body = _json.dumps(m, ensure_ascii=False).encode("utf-8")
    return Response(body, content_type="application/json; charset=utf-8")


@app.route("/api/chart", methods=["POST"])
def api_chart():
    data = request.get_json(silent=True)
    if not data:
        return Response(b'{"error":"Invalid"}', status=400, content_type="application/json")
    prompt = data.get("prompt", "").strip()
    if not prompt:
        return Response(b'{"error":"Empty"}', status=400, content_type="application/json")
    chart_url = generate_chart(prompt)
    if chart_url:
        resp = {"chart_url": chart_url, "prompt": prompt, "text": f"Voici le graphique pour: **{prompt}**"}
    else:
        resp = {"error": "Impossible de generer le graphique"}
    body = _json.dumps(resp, ensure_ascii=False).encode("utf-8")
    return Response(body, content_type="application/json; charset=utf-8")


@app.route("/api/document", methods=["POST"])
def api_document():
    data = request.get_json(silent=True)
    if not data:
        return Response(b'{"error":"Invalid"}', status=400, content_type="application/json")
    b64 = data.get("base64", "")
    filename = data.get("filename", "document")
    if not b64:
        return Response(b'{"error":"No document"}', status=400, content_type="application/json")
    text, summary = analyze_document_b64(b64)
    text_preview = text[:2000] if text else ""
    resp = {
        "text": text_preview,
        "summary": summary,
        "filename": filename,
        "text_preview": text_preview,
    }
    body = _json.dumps(resp, ensure_ascii=False).encode("utf-8")
    return Response(body, content_type="application/json; charset=utf-8")


# =====================================================================
#  EDGE TTS - Voix naturelle cote serveur
# =====================================================================
@app.route("/api/tts", methods=["POST"])
def api_tts():
    """Genere un fichier audio MP3 via Google Translate TTS (rapide, gratuit)"""
    data = request.get_json(silent=True)
    if not data:
        return Response(b'{"error":"Invalid"}', status=400, content_type="application/json")
    text = data.get("text", "").strip()
    if not text:
        return Response(b'{"error":"Empty"}', status=400, content_type="application/json")

    # Limiter a 200 caracteres pour Google Translate
    if len(text) > 200:
        text = text[:200]

    try:
        audio_id = hashlib.md5(text.encode()).hexdigest()[:12]
        audio_path = os.path.join(GENERATED_DIR, f"tts_{audio_id}.mp3")

        if not os.path.exists(audio_path):
            from urllib.parse import quote
            url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={quote(text)}&tl=fr&client=tw-ob"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            r = _requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200 and len(r.content) > 1000:
                with open(audio_path, "wb") as f:
                    f.write(r.content)
            else:
                return Response(
                    _json.dumps({"error": "TTS generation failed"}).encode("utf-8"),
                    status=500,
                    content_type="application/json"
                )

        return send_file(audio_path, mimetype="audio/mpeg")
    except Exception as e:
        return Response(
            _json.dumps({"error": str(e)}).encode("utf-8"),
            status=500,
            content_type="application/json"
        )


@app.route("/api/elevenlabs-tts", methods=["POST"])
def api_elevenlabs_tts():
    """Genere un fichier audio MP3 via ElevenLabs (haute qualite)"""
    data = request.get_json(silent=True)
    if not data:
        return Response(b'{"error":"Invalid"}', status=400, content_type="application/json")
    text = data.get("text", "").strip()
    if not text:
        return Response(b'{"error":"Empty"}', status=400, content_type="application/json")
    if len(text) > 500:
        text = text[:500]

    try:
        audio_id = hashlib.md5(text.encode()).hexdigest()[:12]
        audio_path = os.path.join(GENERATED_DIR, f"el_{audio_id}.mp3")

        if not os.path.exists(audio_path):
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
            headers = {
                "xi-api-key": ELEVENLABS_API_KEY,
                "Content-Type": "application/json",
            }
            body = {
                "text": text,
                "model_id": ELEVENLABS_MODEL,
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                    "style": 0.5,
                    "use_speaker_boost": True,
                },
            }
            r = _requests.post(url, json=body, headers=headers, timeout=30)
            if r.status_code == 200 and len(r.content) > 1000:
                with open(audio_path, "wb") as f:
                    f.write(r.content)
            else:
                return Response(
                    _json.dumps({"error": "ElevenLabs TTS failed"}).encode("utf-8"),
                    status=500,
                    content_type="application/json"
                )

        return send_file(audio_path, mimetype="audio/mpeg")
    except Exception as e:
        return Response(
            _json.dumps({"error": str(e)}).encode("utf-8"),
            status=500,
            content_type="application/json"
        )


@app.route("/api/tts-only", methods=["POST"])
def tts_only():
    """TTS rapide pour le streaming vocal phrase par phrase"""
    data = request.get_json(silent=True)
    if not data:
        return _json.dumps({"audio_url": None})
    text = data.get("text", "").strip()
    if not text:
        return _json.dumps({"audio_url": None})
    audio_url = _generate_tts(text)
    return _json.dumps({"audio_url": audio_url})


@app.route("/api/voice-chat", methods=["POST"])
def api_voice_chat():
    """Chat + TTS rapide pour l'agent vocal"""
    data = request.get_json(silent=True)
    if not data:
        return Response(b'{"error":"Invalid"}', status=400, content_type="application/json")
    message = data.get("message", "").strip()
    conv_id = data.get("conversation_id", "default")
    if not message:
        return Response(b'{"error":"Empty"}', status=400, content_type="application/json")

    if conv_id not in conversations:
        conversations[conv_id] = []
    if len(conversations[conv_id]) > 10:
        conversations[conv_id] = conversations[conv_id][-6:]

    fast = get_fast_response(message.lower())
    if fast is not None:
        conversations[conv_id].append({"role": "user", "content": message})
        conversations[conv_id].append({"role": "assistant", "content": fast["text"]})
        ai_text = fast.get("speak", fast["text"])[:200]
    else:
        conversations[conv_id].append({"role": "user", "content": message})
        m = get_memory()
        memory_context = find_relevant_memory(m, message)
        web_context = ""
        if needs_web_search(message):
            results = web_search(message)
            if results:
                web_context = "\n\nResultats de recherche:\n"
                for i, r in enumerate(results, 1):
                    web_context += f"{i}. {r['title']}: {r['snippet']}\n"
        ai_text = chat_ia(message, conversations[conv_id], memory_context, web_context, voice_mode=True)
        conversations[conv_id].append({"role": "assistant", "content": ai_text})

    clean_text = ai_text.replace("\n", " ").replace("#", "").replace("*", "").replace("`", "")
    clean_text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', clean_text)
    clean_text = clean_text[:200]

    audio_url = None
    try:
        audio_id = hashlib.md5(clean_text.encode()).hexdigest()[:12]
        audio_path = os.path.join(GENERATED_DIR, f"tts_{audio_id}.mp3")

        if not os.path.exists(audio_path):
            from urllib.parse import quote
            url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={quote(clean_text)}&tl=fr&client=tw-ob"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            r = _requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200 and len(r.content) > 1000:
                with open(audio_path, "wb") as f:
                    f.write(r.content)

        if os.path.exists(audio_path) and os.path.getsize(audio_path) > 1000:
            audio_url = f"/generated/tts_{audio_id}.mp3"
    except Exception as e:
        print(f"TTS error: {e}")

    resp = {
        "text": ai_text,
        "audio_url": audio_url,
    }
    body = _json.dumps(resp, ensure_ascii=False).encode("utf-8")
    return Response(body, content_type="application/json; charset=utf-8")


# =====================================================================
#  MAIN
# =====================================================================
if __name__ == "__main__":
    generate_pwa_icons()
    print("=" * 60)
    print("  ELLIOTT - IA Ultime (Version Ultime)")
    print("  http://localhost:5000")
    print("  Chat: KiloCode + Pollinations")
    print("  Images: Pollinations")
    print("  Musique: MusicGen (HuggingFace)")
    print("  Vision: IA Multimodale")
    print("  Charts: Matplotlib")
    print("  Documents: PDF Analysis")
    print("  Code: Python Sandbox")
    print("  Recherche: DuckDuckGo")
    print("  Memoire: " + MEMORY_FILE)
    print("  PWA: Installable sur mobile")
    print("  Avatar: SVG Anime")
    print("  Particles: Canvas Background")
    print("  Typewriter: Text Animation")
    print("  100% GRATUIT!")
    print("=" * 60)
    app.run(debug=False, host="0.0.0.0", port=5000, threaded=True)
