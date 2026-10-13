#!/usr/init/env python3
"""
username_scanner.py (Versión Coherente y Estética)
Escanea nombres cortos y palabras con significado en Discord, Instagram y TikTok.
"""

from __future__ import annotations

import logging
import os
import unicodedata
import time
from typing import Optional, List, Dict

import requests

# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")

WEBHOOKS: Dict[str, str] = {
    "3_letras": os.environ.get("WEBHOOK_3_LETRAS", ""),
    "4_letras": os.environ.get("WEBHOOK_4_LETRAS", ""),
    "palabras_en": os.environ.get("WEBHOOK_EN", ""),
    "palabras_es": os.environ.get("WEBHOOK_ES", ""),
    "otros": os.environ.get("WEBHOOK_OTROS", "")
}

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

# ──────────────────────────────────────────────
# Palabras base limpias, cortas y coherentes
# ──────────────────────────────────────────────
EN_WORDS: List[str] = [
    # 3 y 4 letras estéticas / gamer / tech
    "zen", "max", "pro", "nox", "lux", "rex", "vex", "fox", "sky", "ray", 
    "ash", "ian", "kai", "neo", "ion", "Byte", "core", "void", "flux", "echo",
    "zero", "101", "apex", "edge", "node", "link", "grid", "wave", "frost", "nova",
    "pulse", "cyan", "onyx", "lunar", "solar", "ghost", "1up", "ciph"
]

ES_WORDS: List[str] = [
    "zen", "max", "pro", "sol", "luz", "mar", "rey", "voz", "red", "ion",
    "eco", "ola", "cruz", "flux", "nube", "fuego", "hielo", "brillo", "ritmo",
    "pulso", "sombra", "cuervo", "cifra", "azur", "onix", "nodo", "raiz"
]

# ──────────────────────────────────────────────
# Generador y Clasificador Inteligente
# ──────────────────────────────────────────────

def normalize(w: str) -> str:
    w = w.lower()
    w = unicodedata.normalize("NFD", w)
    w = "".join(c for c in w if unicodedata.category(c) != "Mn")
    return "".join(c for c in w if c.isalnum() or c == "_")


def clasificar_categoria(username: str) -> str:
    """Clasifica el username según su longitud y tipo para enviarlo al canal correcto."""
    clean_name = username.replace("_", "").replace(".", "")
    
    if len(clean_name) == 3:
        return "3_letras"
    elif len(clean_name) == 4:
        return "4_letras"
    elif username in [normalize(w) for w in EN_WORDS]:
        return "palabras_en"
    elif username in [normalize(w) for w in ES_WORDS]:
        return "palabras_es"
    else:
        return "otros"


def gen_candidates() -> List[str]:
    """Genera exclusivamente usernames limpios, cortos y con sentido."""
    out: set[str] = set()

    clean_en = [normalize(w) for w in EN_WORDS]
    clean_es = [normalize(w) for w in ES_WORDS]
    all_clean = list(set(clean_en + clean_es))

    # 1. Añadir palabras base individuales que midan entre 3 y 6 letras
    for w in all_clean:
        if 3 <= len(w) <= 6:
            out.add(w)

    # 2. Combinaciones limpias de 2 palabras cortas (ej: dark + void -> darkvoid)
    # Solo si el resultado total mide entre 4 y 8 letras para que no sean kilométricos
    short_words = [w for w in all_clean if len(w) <= 4]
    for a in short_words:
        for b in short_words:
            if a != b:
                combo = a + b
                if 4 <= len(combo) <= 8:
                    out.add(combo)

    # 3. Sufijos estéticos limpios (sin números aleatorios feos)
    # Ejemplo: zenx, luxy, void_
    aesthetic_suffixes = ["", "x", "z", "_"]
    base_list = list(out)
    for w in base_list:
        if len(w) <= 5:
            for s in aesthetic_suffixes:
                cand = w + s
                if 3 <= len(cand) <= 6:
                    out.add(cand)

    return sorted(list(out), key=len)


# ──────────────────────────────────────────────
# Checkers (Discord, Instagram, TikTok)
# ──────────────────────────────────────────────

def check_discord(username: str, token: str) -> Optional[bool]:
    h = {"Authorization": f"Bot {token}", "Content-Type": "application/json"}
    url = "https://discord.com/api/v10/users/@me"

    try:
        r = requests.get(url, headers=h, timeout=10)
        if r.status_code != 200:
            return None

        orig = r.json().get("global_name") or r.json().get("username")
        r = requests.patch(url, headers=h, json={"global_name": username}, timeout=10)
        available = (r.status_code == 200)

        if orig and available:
            requests.patch(url, headers=h, json={"global_name": orig}, timeout=10)

        return available
    except Exception:
        return None


def check_instagram(username: str) -> Optional[bool]:
    url = f"https://www.instagram.com/{username}/"
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=10, allow_redirects=True)
        if r.status_code == 404:
            return True
        if r.status_code == 200:
            if "isn't available" in r.text or "not available" in r.text:
                return True
            return False
        return False
    except Exception:
        return None


def check_tiktok(username: str) -> Optional[bool]:
    url = f"https://www.tiktok.com/@{username}"
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=10, allow_redirects=True)
        if r.status_code == 404:
            return True
        if r.status_code == 200:
            if "user not found" in r.text.lower() or "page doesn't exist" in r.text.lower():
                return True
            if f"@{username}" in r.text:
                return False
            return True
        return None
    except Exception:
        return None


# ──────────────────────────────────────────────
# Notificación por Canal Específico
# ──────────────────────────────────────────────

def send_discord_webhook(username: str, platform: str) -> None:
    categoria = clasificar_categoria(username)
    webhook_url = WEBHOOKS.get(categoria) or WEBHOOKS.get("otros")

    if not webhook_url:
        log.warning(f"No hay webhook configurado para la categoría: {categoria}")
        return
        
    payload = {
        "embeds": [
            {
                "title": f"🎉 ¡Username Disponible ({categoria.upper().replace('_', ' ')})!",
                "color": 65280,
                "fields": [
                    {"name": "Usuario", "value": f"`{username}`", "inline": True},
                    {"name": "Plataforma", "value": platform, "inline": True}
                ],
                "footer": {"text": f"Categoría: {categoria}"}
            }
        ]
    }
    
    try:
        r = requests.post(webhook_url, json=payload, timeout=10)
        if r.status_code != 204:
            log.warning(f"Error enviando webhook a {categoria}: {r.status_code}")
    except Exception as e:
        log.warning(f"Webhook exception: {e}")


# ──────────────────────────────────────────────
# Main Execution Loop (Infinito)
# ──────────────────────────────────────────────

def main() -> None:
    # Generamos la lista de candidatos una sola vez al arrancar
    log.info("Generando lista base de candidatos coherentes y limpios...")
    candidates = gen_candidates()
    log.info(f"Total de candidatos únicos en la lista: {len(candidates)}")

    # Bucle infinito para que nunca se detenga
    ronda = 1
    while True:
        log.info(f"=== INICIANDO RONDA DE ESCANEO #{ronda} ===")

        for i, username in enumerate(candidates, 1):
            log.info(f"[Ronda {ronda}] [{i}/{len(candidates)}] Probando: {username}")

            # 1. Discord
            if DISCORD_BOT_TOKEN:
                if check_discord(username, DISCORD_BOT_TOKEN) is True:
                    log.info(f"¡DISCORD DISPONIBLE!: {username}")
                    send_discord_webhook(username, "Discord")
                time.sleep(2)

            # 2. Instagram
            if check_instagram(username) is True:
                log.info(f"¡INSTAGRAM DISPONIBLE!: {username}")
                send_discord_webhook(username, "Instagram")
            time.sleep(2)

            # 3. TikTok
            if check_tiktok(username) is True:
                log.info(f"¡TIKTOK DISPONIBLE!: {username}")
                send_discord_webhook(username, "TikTok")

            # Pausa aleatoria entre cada usuario individual (8 a 15 segundos)
            time.sleep(random.uniform(8, 15))

        log.info(f"=== RONDA #{ronda} TERMINADA ===")
        ronda += 1

        # Descanso largo antes de empezar la siguiente ronda completa
        # Por ejemplo, 3 horas (10800 segundos) para proteger tu IP de bloqueos
        horas_de_espera = 3
        log.info(f"Durmiendo el bot durante {horas_de_espera} horas para evitar bloqueos de IP...")
        time.sleep(horas_de_espera * 3600)


if __name__ == "__main__":
    main()