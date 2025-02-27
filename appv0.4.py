from flask import Flask, request, render_template, jsonify
import os
import requests
import yt_dlp
import threading
from pathlib import Path
from datetime import datetime, timedelta
import pytz
import json
import time

app = Flask(__name__)

# Configuración de Facebook
PAGE_ID = "306117823384646"
APP_ID = "8853303641422476"
APP_SECRET = "43656dc711e91b81b79e58184d0ce74b"  # Reemplaza esto con el App Secret real desde el panel de desarrolladores
ACCESS_TOKEN = "EAB90CGKiuowBO7J73GVstqqy2DKGU7vNcFhvcXqVHg11yxeZCkueJIwVsET0Hb1L0kJkGlH451q3bPZBrBgLZCoRq7hZCfklRZAlUOUzWhmLlY8bmPg27GnZCoZB53vhL3KPL06GA6ZALRDROLZAPl590JXbN9lhMZCfdxkroUnb2eD2HviBn4QRrRBSH3zKJ0PqwdTbAODuOFeytKfoySKcCcYGSHaZA5eLp5cPWaryXYZD"
est_tz = pytz.timezone("America/New_York")

# Horarios predeterminados en hora del Este (EST)
SCHEDULE_TIMES = ["08:00", "12:00", "19:00"]
QUEUE_FILE = "video_queue.json"

# Función para obtener el token de larga duración
def get_long_lived_token(short_lived_token):
    url = "https://graph.facebook.com/v22.0/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": APP_ID,
        "client_secret": APP_SECRET,
        "fb_exchange_token": short_lived_token
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        print(f"Nuevo token de larga duración: {data['access_token']}")
        print(f"Expira en: {data.get('expires_in')} segundos (aproximadamente 60 días)")
        return data["access_token"]
    else:
        raise Exception(f"Error al obtener token de larga duración: {response.text}")

# Cargar la cola desde un archivo JSON
if os.path.exists(QUEUE_FILE):
    with open(QUEUE_FILE, "r") as f:
        video_queue = json.load(f)
else:
    video_queue = []

# Guardar la cola en el archivo JSON
def save_queue():
    with open(QUEUE_FILE, "w") as f:
        json.dump(video_queue, f, indent=4)

# Función para inicializar la sesión de carga
def initialize_upload_session():
    url = f"https://graph.facebook.com/v22.0/{PAGE_ID}/video_reels"
    params = {"access_token": ACCESS_TOKEN, "upload_phase": "start"}
    response = requests.post(url, data=params)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Error al inicializar la sesión: {response.text}")

# Función para subir el video
def upload_video(upload_url, video_path):
    file_size = os.path.getsize(video_path)
    headers = {
        "Authorization": f"OAuth {ACCESS_TOKEN}",
        "offset": "0",
        "file_size": str(file_size)
    }
    with open(video_path, "rb") as video_file:
        response = requests.post(upload_url, headers=headers, data=video_file)
    if response.status_code == 200:
        return True
    else:
        raise Exception(f"Error al subir el video: {response.text}")

# Función para publicar el Reel
def publish_reel(video_id, description):
    url = f"https://graph.facebook.com/v22.0/{PAGE_ID}/video_reels"
    params = {
        "access_token": ACCESS_TOKEN,
        "video_id": video_id,
        "upload_phase": "finish",
        "video_state": "PUBLISHED",
        "description": description,
    }
    response = requests.post(url, data=params)
    if response.status_code == 200:
        return True
    else:
        raise Exception(f"Error al publicar el Reel: {response.text}")

# Descargar video
def download_video(video_url):
    download_folder = Path("downloads")
    download_folder.mkdir(exist_ok=True)
    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]",
        "outtmpl": str(download_folder / "%(title)s.%(ext)s"),
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            return ydl.prepare_filename(info)
    except Exception as e:
        return None

# Función para programar la publicación de videos
def schedule_video(video_url, description):
    now = datetime.now(est_tz)
    scheduled_dates = [datetime.strptime(v["scheduled_time"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=est_tz) for v in video_queue]

    # Encontrar el próximo horario disponible
    for days_ahead in range(10):
        target_date = now + timedelta(days=days_ahead)
        for schedule_time in SCHEDULE_TIMES:
            scheduled_time = datetime.strptime(target_date.strftime("%Y-%m-%d") + f" {schedule_time}", "%Y-%m-%d %H:%M").replace(tzinfo=est_tz)
            if scheduled_time > now and scheduled_time not in scheduled_dates:
                video_queue.append({
                    "id": len(video_queue),
                    "video_url": video_url,
                    "description": description,
                    "scheduled_time": scheduled_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "status": "pending"
                })
                save_queue()
                return f"Video programado para {scheduled_time.strftime('%Y-%m-%d %H:%M:%S')} EST"
    return "No hay horarios disponibles en los próximos días."

# Hilo para procesar la cola
def process_queue():
    while True:
        now = datetime.now(est_tz)
        for video in video_queue:
            if video["status"] == "pending":
                scheduled_time = datetime.strptime(video["scheduled_time"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=est_tz)
                if scheduled_time <= now:
                    video_path = download_video(video["video_url"])
                    if video_path:
                        try:
                            upload_data = initialize_upload_session()
                            video_id = upload_data.get("video_id")
                            upload_url = upload_data.get("upload_url")
                            upload_video(upload_url, video_path)
                            publish_reel(video_id, video["description"])
                            video["status"] = "uploaded"
                            video["upload_status"] = "success"
                            os.remove(video_path)  # Eliminar el archivo después de subirlo
                        except Exception as e:
                            print(f"Error al publicar el video: {str(e)}")
                            video["upload_status"] = "failed"
                        finally:
                            save_queue()
        time.sleep(60)

threading.Thread(target=process_queue, daemon=True).start()

hashtags = ""

@app.route("/", methods=["GET", "POST"])
def index():
    global video_queue, hashtags
    if request.method == "POST":
        video_url = request.form["video_url"]
        description = request.form["description"]
        hashtags = request.form.get("hashtags", "")  # Obtener hashtags del formulario
        full_description = f"{description} {hashtags}".strip()
        message = schedule_video(video_url, full_description)
        return jsonify({"message": message})
    return render_template("index.html", queue=video_queue, hashtags=hashtags)

@app.route("/edit/<int:video_id>", methods=["POST"])
def edit_video(video_id):
    global video_queue
    if video_id < 0 or video_id >= len(video_queue):
        return jsonify({"error": "ID de video inválido"}), 400

    new_scheduled_time = request.form.get("scheduled_time")
    new_description = request.form.get("description")

    if not new_scheduled_time:
        return jsonify({"error": "La nueva hora programada es obligatoria"}), 400

    try:
        # Convertir la nueva hora programada a un objeto datetime
        new_scheduled_datetime = datetime.strptime(new_scheduled_time, "%Y-%m-%dT%H:%M")
        new_scheduled_datetime = est_tz.localize(new_scheduled_datetime)
        video_queue[video_id]["scheduled_time"] = new_scheduled_datetime.strftime("%Y-%m-%d %H:%M:%S")
        if new_description:
            video_queue[video_id]["description"] = new_description

        save_queue()
        return jsonify({"message": f"Video {video_id} actualizado correctamente"})
    except ValueError:
        return jsonify({"error": "Formato de fecha/hora incorrecto. Usa YYYY-MM-DDTHH:MM"}), 400

# Actualizar el ACCESS_TOKEN al iniciar la aplicación
if __name__ == "__main__":
    try:
        long_lived_token = get_long_lived_token(ACCESS_TOKEN)
        ACCESS_TOKEN = long_lived_token  # Actualiza el token a uno de 60 días
        print(f"Token actualizado exitosamente: {ACCESS_TOKEN}")
    except Exception as e:
        print(f"No se pudo actualizar el token: {e}")
    app.run(debug=True)