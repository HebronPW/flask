from flask import Flask, request, render_template, jsonify
import os
import requests
import yt_dlp
from pathlib import Path

app = Flask(__name__)

# Variables predefinidas
PAGE_ID = "306117823384646"  # Reemplaza con tu Page ID
ACCESS_TOKEN = "EAB90CGKiuowBOymGwoZBfQIly8dlwGrTcjl4koI4hp9hTnXYZC2ZAdKg9nbjAX2YrLhu9dzNmkuyRGj6hmilX4Q944RrZAXzbZB1NCBrmXtiNpzK85TX5dGWPdLNAVjqJxQX1ZC9VF6Y848HdguV42e5rFb1dMBxu8iQWBqjDChzStzAX4ZApBNXdtgPsZB4pcQolNrZASqY7EXUTR3LApjFfcZAtsk9rYapk2VfV7gQZDZD"  # Reemplaza con tu Access Token


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
    # Crear una carpeta para los videos descargados
    download_folder = Path("downloads")
    download_folder.mkdir(exist_ok=True)

    try:
        # Configurar yt-dlp
        ydl_opts = {
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]",
            "outtmpl": str(download_folder / "%(title)s.%(ext)s"),
        }

        # Descargar el video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            video_filename = ydl.prepare_filename(info)
            print(f"Video descargado correctamente: {video_filename}")
            return video_filename
    except Exception as e:
        raise Exception(f"Error al descargar el video: {str(e)}")

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        # Obtener el enlace del video y la descripción
        video_url = request.form["video_url"]
        description = request.form["description"]

        try:
            # Paso 1: Descargar el video
            video_path = download_video_with_ytdlp(video_url)

            # Paso 2: Inicializar la sesión de carga
            upload_data = initialize_upload_session(PAGE_ID, ACCESS_TOKEN)
            video_id = upload_data.get("video_id")
            upload_url = upload_data.get("upload_url")

            # Paso 3: Subir el video
            upload_video(upload_url, ACCESS_TOKEN, video_path)

            # Paso 4: Publicar el Reel
            publish_reel(PAGE_ID, ACCESS_TOKEN, video_id, description)

            return "¡El Reel se ha publicado correctamente en Facebook!"
        except Exception as e:
            return f"Error: {str(e)}"
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Publicar Reel desde YouTube</title>
    </head>
    <body>
        <h1>Publicar Reel en Facebook desde YouTube</h1>
        <form method="POST">
            <label for="video_url">Enlace del video:</label><br>
            <input type="url" name="video_url" id="video_url" placeholder="Pega el enlace aquí" required><br><br>
            <label for="description">Descripción del Reel:</label><br>
            <textarea name="description" id="description" rows="3" cols="50" placeholder="Escribe una descripción" required></textarea><br><br>
            <button type="submit">Publicar Reel</button>
        </form>
    </body>
    </html>
    """

if __name__ == "__main__":
    app.run(debug=True)