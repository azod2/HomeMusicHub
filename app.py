from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import os
import subprocess
import glob
from dotenv import load_dotenv
import io
from models import db, Song, Playlist, SearchHistory, PlayHistory, DownloadQueue

load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# 数据库配置
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///music_hub.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# 设置默认音乐目录
app.config.setdefault('MUSIC_DIR', os.path.abspath(os.getenv("MUSIC_DIR", "./music")))
ALLOWED_EXTENSIONS = ('.mp3', '.flac', '.wav', '.aac', '.m4a', '.mp4', '.mkv', '.avi', '.mov')
current_process = None

# 创建数据库表
with app.app_context():
    db.create_all()

def get_music_files():
    music_files = []
    music_dir = app.config['MUSIC_DIR']
    for ext in ALLOWED_EXTENSIONS:
        music_files.extend(glob.glob(os.path.join(music_dir, f'*{ext}')))
    return music_files

@app.route('/music')
def list_music():
    music_files = get_music_files()
    print(f"Found music files: {music_files}")  # 添加调试信息
    
    # 将本地音乐文件同步到数据库
    with app.app_context():
        for file_path in music_files:
            filename = os.path.basename(file_path)
            existing_song = Song.query.filter_by(local_path=file_path).first()
            if not existing_song:
                new_song = Song(
                    title=filename,
                    source='local',
                    local_path=file_path
                )
                db.session.add(new_song)
        db.session.commit()
        
        # 返回所有本地音乐
        local_songs = Song.query.filter_by(source='local').all()
        return jsonify([song.to_dict() for song in local_songs])

@app.route('/play', methods=['POST'])
def play_music():
    data = request.get_json()
    if not data or 'filename' not in data:
        return jsonify({"error": "Filename is required"}), 400

    filename = data['filename']
    if not any(filename.endswith(ext) for ext in ALLOWED_EXTENSIONS):
        return jsonify({"error": "Invalid file format"}), 400

    full_path = os.path.join(app.config['MUSIC_DIR'], filename)
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
    full_path = os.path.join(app.config['MUSIC_DIR'], filename)
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
