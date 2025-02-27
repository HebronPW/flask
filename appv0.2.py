from flask import Flask, request, render_template, jsonify
import os
import requests
import yt_dlp
import threading
from pathlib import Path
from datetime import datetime, timedelta
import pytz

app = Flask(__name__)

# Variables predefinidas
PAGE_ID = "306117823384646"  # Reemplaza con tu Page ID
ACCESS_TOKEN = "EAB90CGKiuowBO4cuRmetrToj05V1IbopZAbc4edxFvIJsK1yu3IS3lZAvS8ZBeg6vyAX9ZAG1s75186BjiHzk5ILBzXEZCyvZAZBsoEADsZBTqpMlSwCQcIokEH60Jh6rXF3xrgw6WgRcqsVNYHdtWwFpej3oobyENtr4FsAFXf4h7Az1ZCzqN4ysANZAZAUeoQ5I6m7skzW7ZAsjxNiOs0OdQFuHlUl8miEYm67UZBW8rgZDZD"  # Reemplaza con tu Access Token
est_tz = pytz.timezone("America/New_York")  # Zona horaria EST

# Cola de videos (Lista de tuplas: (ruta_video, descripción, hora_publicación))
video_queue = []

# Función para inicializar la sesión de carga
def initialize_upload_session(page_id, access_token):
    url = f"https://graph.facebook.com/v22.0/{page_id}/video_reels"
    params = {
        "access_token": access_token,
        "upload_phase": "start"
    }
    response = requests.post(url, data=params)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Error al inicializar la sesión: {response.text}")

# Función para subir el video
def upload_video(upload_url, access_token, video_path):
    file_size = os.path.getsize(video_path)
    headers = {
        "Authorization": f"OAuth {access_token}",
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
def publish_reel(page_id, access_token, video_id, description):
    url = f"https://graph.facebook.com/v22.0/{page_id}/video_reels"
    params = {
        "access_token": access_token,
        "video_id": video_id,
        "upload_phase": "finish",
        "video_state": "PUBLISHED",
        "description": description
    }
    response = requests.post(url, data=params)
    if response.status_code == 200:
        return True
    else:
        raise Exception(f"Error al publicar el Reel: {response.text}")

# Función para descargar un video usando yt-dlp
def download_video_with_ytdlp(video_url):
    download_folder = Path("downloads")
    download_folder.mkdir(exist_ok=True)

    try:
        ydl_opts = {
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]",
            "outtmpl": str(download_folder / "%(title)s.%(ext)s"),
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            video_filename = ydl.prepare_filename(info)
            print(f"✅ Video descargado correctamente: {video_filename}")
            return video_filename
    except Exception as e:
        print(f"❌ Error al descargar el video: {str(e)}")
        return None

# Función para procesar y publicar un video
def process_video():
    if not video_queue:
        print("📭 No hay videos en cola.")
        return

    # Tomar el primer video en la cola
    video_path, description, _ = video_queue.pop(0)

    try:
        print(f"🚀 Publicando video: {video_path}")

        # Paso 1: Inicializar la sesión de carga
        upload_data = initialize_upload_session(PAGE_ID, ACCESS_TOKEN)
        video_id = upload_data.get("video_id")
        upload_url = upload_data.get("upload_url")

        # Paso 2: Subir el video
        upload_video(upload_url, ACCESS_TOKEN, video_path)

        # Paso 3: Publicar el Reel
        publish_reel(PAGE_ID, ACCESS_TOKEN, video_id, description)

        print(f"✅ Publicado correctamente: {video_path}")
    except Exception as e:
        print(f"❌ Error al publicar el video: {str(e)}")

    # Si quedan más videos en la cola, programar el siguiente
    if video_queue:
        next_video_time = video_queue[0][2]
        wait_time = (next_video_time - datetime.now(est_tz)).total_seconds()
        threading.Timer(max(wait_time, 0), process_video).start()

# Función para agregar un video a la cola con horario
def schedule_video(video_url, description):
    video_path = download_video_with_ytdlp(video_url)
    
    if video_path:
        now_est = datetime.now(est_tz)
        publish_time = now_est + timedelta(minutes=1)  # Publicar en 1 minuto

        video_queue.append((video_path, description, publish_time))
        print(f"📌 Video programado: {video_path} a las {publish_time.strftime('%Y-%m-%d %H:%M:%S')} EST")

        # Si es el único en la cola, iniciar el proceso
        if len(video_queue) == 1:
            threading.Timer(60, process_video).start()
    else:
        print("⚠️ No se pudo descargar el video, no se programará.")

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        video_url = request.form["video_url"]
        description = request.form["description"]
        
        schedule_video(video_url, description)
        return "✅ Video descargado y programado para publicación."
    
    return """
    <html>
    <head><title>Publicar Reel</title></head>
    <body>
        <h1>Publicar Reel en Facebook desde YouTube</h1>
        <form method="POST">
            <label>Enlace del video:</label><br>
            <input type="url" name="video_url" required><br><br>
            <label>Descripción:</label><br>
            <textarea name="description" required></textarea><br><br>
            <button type="submit">Programar Publicación</button>
        </form>
    </body>
    </html>
    """

@app.route("/queue")
def queue():
    return render_template("queue.html", video_queue=video_queue)

if __name__ == "__main__":
    app.run(debug=True)
