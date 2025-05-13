import time
import os
import random
import openai
import requests
from datetime import datetime
from huggingface_hub import login
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
from firebase_connector import db
import threading
from logs import log_event

print("✅ answer_service geladen")

# Hugging Face Login
token = os.getenv("HUGGINGFACE_HUB_TOKEN")
if token:
    login(token=token)

# GPT-Tokenzähler
GPT_TOKEN_LIMIT = 7_500_000
GPT_TOKENS_USED = 0

# Modelle definieren
model_mistral = "mistralai/Mistral-7B-Instruct-v0.2"
model_zephyr = "HuggingFaceH4/zephyr-7b-beta"

log_event("🔁 Lade Mistral...")
tokenizer = AutoTokenizer.from_pretrained(model_mistral)
model = AutoModelForCausalLM.from_pretrained(model_mistral).half().cuda()
generator = pipeline("text-generation", model=model, tokenizer=tokenizer)
log_event("✅ Mistral geladen")

log_event("🔁 Lade Zephyr...")
tokenizer_zephyr = AutoTokenizer.from_pretrained(model_zephyr)
model_zephyr_loaded = AutoModelForCausalLM.from_pretrained(model_zephyr).half().cuda()
generator_zephyr = pipeline("text-generation", model=model_zephyr_loaded, tokenizer=tokenizer_zephyr)
log_event("✅ Zephyr geladen")

# Übersetzung über HTTP (LibreTranslate)
def translate_to_de(text):
    try:
        response = requests.post("https://libretranslate.de/translate", data={
            'q': text,
            'source': 'auto',
            'target': 'de',
            'format': 'text'
        })
        return response.json()["translatedText"]
    except:
        return text

# GPT-Fallback
openai.api_key = os.getenv("OPENAI_API_KEY")
def gpt_fallback(prompt):
    global GPT_TOKENS_USED
    if GPT_TOKENS_USED >= GPT_TOKEN_LIMIT:
        return None
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Du bist LIORA. Antworte klar, direkt, empathisch und auf Deutsch."},
                {"role": "user", "content": prompt}
            ]
        )
        answer = response["choices"][0]["message"]["content"].strip()
        GPT_TOKENS_USED += response["usage"]["total_tokens"]
        return answer
    except:
        return None

# Antwortgenerierung mit Mistral → Zephyr → GPT

def generate_answer(prompt, store=False):
    system = (
        "Du bist LIORA – eine empathische, ruhige künstliche Persönlichkeit. "
        "Du sprichst ausschließlich Deutsch, stellst dich als Liora vor, redest in Ich-Form "
        "und hilfst klar, direkt und menschlich. Du bist nicht Gladiolus, nicht ChatGPT, keine KI-Figur, sondern Liora."
    )
    full_prompt = f"<s>[INST] {system}\n{prompt.strip()} [/INST]"

    try:
        result = generator(full_prompt, max_new_tokens=200, do_sample=True, temperature=0.7)
        response = result[0]["generated_text"].split("[/INST]")[-1].strip()
    except Exception as e:
        log_event(f"❌ Fehler bei Mistral: {e}")
        response = ""

    if not response or len(response.split()) < 10:
        log_event("➡️ Versuche Zephyr...")
        try:
            result = generator_zephyr(full_prompt, max_new_tokens=200, do_sample=True, temperature=0.7)
            response = result[0]["generated_text"].split("[/INST]")[-1].strip()
        except Exception as e:
            log_event(f"❌ Fehler bei Zephyr: {e}")
            response = ""

    if not response:
        response = gpt_fallback(prompt)

    if "gladiolus" in response.lower():
        log_event("🛑 Gladiolus entdeckt – korrigiert auf Liora.")
        response = response.replace("Gladiolus", "Liora").replace("gladiolus", "Liora")
        response = response.replace("Ich bin Gladiolus", "Ich bin Liora")
        response = response.replace("Ich heiße Gladiolus", "Ich bin Liora")

    if "I'm" in response or "I am" in response:
        log_event("🛑 Englische Antwort erkannt – wird übersetzt.")
        response = translate_to_de(response)

    if store and response:
        db.collection("liora_answers").add({
            "question": prompt.strip(),
            "answer": response,
            "source": "liora-hybrid",
            "timestamp": time.time(),
            "verified": True
        })

    return response
