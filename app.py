from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import os
import subprocess
import glob
from dotenv import load_dotenv
import io

load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

MUSIC_DIR = os.path.abspath(os.getenv("MUSIC_DIR", "./music"))
ALLOWED_EXTENSIONS = ('.mp3', '.flac', '.wav', '.aac', '.m4a', '.mp4', '.mkv', '.avi', '.mov')
current_process = None

def get_music_files():
    music_files = []
    for ext in ALLOWED_EXTENSIONS:
        music_files.extend(glob.glob(os.path.join(MUSIC_DIR, f'*{ext}')))
    return music_files

@app.route('/music')
def list_music():
    music_files = get_music_files()
    return jsonify([os.path.basename(f) for f in music_files])

@app.route('/play', methods=['POST'])
def play_music():
    data = request.get_json()
    if not data or 'filename' not in data:
        return jsonify({"error": "Filename is required"}), 400

    filename = data['filename']
    if not any(filename.endswith(ext) for ext in ALLOWED_EXTENSIONS):
        return jsonify({"error": "Invalid file format"}), 400

    full_path = os.path.join(MUSIC_DIR, filename)
    if not os.path.exists(full_path):
        return jsonify({"error": "File not found"}), 404

    print(f"play_music: full_path={full_path}")
    return jsonify({"audioUrl": f"/stream/{filename}"}), 200

@app.route('/play_youtube', methods=['POST'])
def play_youtube():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "URL is required"}), 400

    url = data['url']
    try:
       command = ['yt-dlp', '-f', 'bestaudio', '-g', url]
       process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
       stdout, stderr = process.communicate()
       if stderr:
           return jsonify({"error": f"Error getting audio url from youtube: {stderr.decode()}"}), 500
       audio_url = stdout.decode().strip()
       return jsonify({"audioUrl": audio_url}), 200
    except Exception as e:
        return jsonify({"error": f"Error processing youtube: {str(e)}"}), 500

@app.route('/stop', methods=['POST'])
def stop_music():
    global current_process
    if current_process:
        current_process.send_signal(signal.SIGINT)
        current_process.wait()
        current_process = None
        return jsonify({"message": "Music stopped"}), 200
    else:
        return jsonify({"message": "No music playing"}), 200

@app.route('/stream/<path:filename>')
def stream_music(filename):
    full_path = os.path.join(MUSIC_DIR, filename)
    print(f"stream_music: full_path={full_path}")
    if not os.path.exists(full_path):
        print(f"stream_music: File not found at {full_path}")
        return jsonify({"error": "File not found"}), 404
    try:
        with open(full_path, 'rb') as f:
            data = f.read()
        print(f"stream_music: Read file length: {len(data)}")
        mimetype = 'audio/mpeg'  # default
        if filename.lower().endswith(('.flac', '.ogg')):
            mimetype = 'audio/flac'
        elif filename.lower().endswith('.wav'):
             mimetype = 'audio/wav'
        elif filename.lower().endswith('.aac'):
             mimetype = 'audio/aac'
        elif filename.lower().endswith('.m4a'):
             mimetype = 'audio/mp4'
        elif filename.lower().endswith('.mp4'):
             mimetype = 'audio/mp4'
        elif filename.lower().endswith('.mkv'):
             mimetype = 'audio/x-matroska'
        elif filename.lower().endswith('.avi'):
             mimetype = 'video/avi'
        elif filename.lower().endswith('.mov'):
             mimetype = 'video/quicktime'

        print(f"stream_music: mimetype={mimetype}")
        return send_file(io.BytesIO(data), mimetype=mimetype)
    except Exception as e:
        print(f"stream_music: Error reading file: {str(e)}")
        return jsonify({"error": f"Error reading file: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.getenv("PORT", 5000), debug=True)
