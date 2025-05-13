
import time
from datetime import datetime
counter_total = 0
counter_gpt = 0
import time
import gradio as gr
from answer_service import generate_answer, run_queue_loop, generate_question_from_mood, generate_question_from_module
from firebase_connector import db
from threading import Thread
import datetime
from firebase_admin import firestore
from gtts import gTTS
import os
import speech_recognition as sr

# Textantwort
def answer_ui(question):
    return generate_answer(question, store=True)

# HF Fragegenerator
def generate_question_ui(typ, value):
    if typ == "mood":
        return generate_question_from_mood(value)
    elif typ == "module":
        return generate_question_from_module(value)
    else:
        return "Ungültiger Typ."

# Dashboard
def get_queue_stats():
    answered = db.collection("liora_queue").where("status", "==", "answered").stream()
    waiting = db.collection("liora_queue").where("status", "==", "waiting").stream()
    skipped = db.collection("liora_queue").where("status", "==", "skipped").stream()
    count_a = sum(1 for _ in answered)
    count_w = sum(1 for _ in waiting)
    count_s = sum(1 for _ in skipped)
    return f'''
### Liora Queue-Status

- ✅ Beantwortet: {count_a}
- ⏳ Wartend: {count_w}
- ❌ Übersprungen: {count_s}
'''

# TTS
def speak(text):
    tts = gTTS(text=text, lang="de")
    filename = "liora_tts.mp3"
    tts.save(filename)
    return filename

# STT
def speech_to_text_and_respond(audio):
    r = sr.Recognizer()

    if not audio:
        return "Ich konnte keine Audioeingabe finden."

    try:
        audio_path = str(audio)
        with sr.AudioFile(audio_path) as source:
            audio_data = r.record(source)
            try:
                text = r.recognize_google(audio_data, language="de-DE")
            except:
                return "Ich konnte dich leider nicht verstehen."
    except Exception as e:
        return f"Fehler beim Verarbeiten der Datei: {str(e)}"

    if text:
        return generate_answer(text, store=True)
    else:
        return "Ich konnte dich leider nicht verstehen."

# UI
with gr.Blocks() as app:
    with gr.Tab("Fragen an LIORA"):
        gr.Markdown("### Stelle eine Frage an LIORA")
        input_box = gr.Textbox(label="Frage")
        output_box = gr.Textbox(label="Antwort")
        input_box.change(fn=answer_ui, inputs=input_box, outputs=output_box)

    with gr.Tab("Frage generieren"):
        gr.Markdown("### HF-Frage für andere Bots")
        dropdown = gr.Dropdown(choices=["mood", "module"], label="Typ")
        value_box = gr.Textbox(label="Wert", placeholder="traurig oder lernen_mathe")
        result = gr.Textbox(label="Frage")
        gen_btn = gr.Button("💡 Frage generieren")
        gen_btn.click(fn=generate_question_ui, inputs=[dropdown, value_box], outputs=result)

    with gr.Tab("Live Dashboard"):
        gr.Markdown("### Echtzeitübersicht")
        stats_box = gr.Markdown("Wird geladen...")
        refresh_stats = gr.Button("🔄 Aktualisieren")
        refresh_stats.click(fn=get_queue_stats, outputs=stats_box)

    with gr.Tab("LIORA spricht (TTS)"):
        gr.Markdown("### Lass LIORA sprechen")
        tts_input = gr.Textbox(label="Text für Liora")
        tts_audio = gr.Audio(label="Sprachausgabe", autoplay=True)
        speak_btn = gr.Button("🔊 Abspielen")
        speak_btn.click(fn=speak, inputs=tts_input, outputs=tts_audio)

    with gr.Tab("Sprache verstehen (STT)"):
        gr.Markdown("### Sprich mit LIORA über dein Mikrofon")
        mic_input = gr.Audio(type="filepath", label="🎙 Deine Spracheingabe")
        stt_answer_box = gr.Textbox(label="Antwort von LIORA")
        stt_go = gr.Button("🎧 Analysieren & Antworten")
        stt_go.click(fn=speech_to_text_and_respond, inputs=mic_input, outputs=stt_answer_box)

# Start
if __name__ == "__main__":
    def run_review_loop():
        print("Review loop is not implemented yet. Placeholder running.")
        while True:
            time.sleep(60)  # verhindert CPU-Auslastung

    Thread(target=run_queue_loop).start()
    Thread(target=run_review_loop).start()
    app.launch()
