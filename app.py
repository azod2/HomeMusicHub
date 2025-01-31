from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import os
import subprocess
import glob
from dotenv import load_dotenv
import io
from models import db, Song, Playlist, SearchHistory, PlayHistory, DownloadQueue
from services.video_search import VideoSearchService
import asyncio
import json
from datetime import datetime, UTC

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

# 初始化服务
video_search_service = VideoSearchService()

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

@app.route('/search')
def search_videos():
    query = request.args.get('q')
    if not query:
        return jsonify({"error": "Query parameter 'q' is required"}), 400

    try:
        # 使用 asyncio 运行异步搜索
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(video_search_service.search_all(query))
        loop.close()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"Search failed: {str(e)}"}), 500

@app.route('/search/history')
def get_search_history():
    try:
        history = db.session.query(SearchHistory).order_by(SearchHistory.created_at.desc()).limit(10).all()
        result = [{
            'query': h.query,
            'created_at': h.created_at.isoformat()
        } for h in history]
        return jsonify(result)
    except Exception as e:
        import traceback
        print(f"Error in get_search_history: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": f"Failed to get search history: {str(e)}"}), 500

@app.route('/playlists', methods=['GET'])
def list_playlists():
    """獲取所有播放列表"""
    try:
        playlists = db.session.query(Playlist).all()
        return jsonify([{
            'id': p.id,
            'name': p.name,
            'description': p.description,
            'created_at': p.created_at.isoformat(),
            'updated_at': p.updated_at.isoformat(),
            'song_count': len(p.songs.all())
        } for p in playlists])
    except Exception as e:
        return jsonify({"error": f"Failed to get playlists: {str(e)}"}), 500

@app.route('/playlists', methods=['POST'])
def create_playlist():
    """創建新的播放列表"""
    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({"error": "Name is required"}), 400

    try:
        playlist = Playlist(
            name=data['name'],
            description=data.get('description', '')
        )
        db.session.add(playlist)
        db.session.commit()
        
        return jsonify({
            'id': playlist.id,
            'name': playlist.name,
            'description': playlist.description,
            'created_at': playlist.created_at.isoformat(),
            'updated_at': playlist.updated_at.isoformat(),
            'song_count': 0
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to create playlist: {str(e)}"}), 500

@app.route('/playlists/<int:playlist_id>', methods=['GET'])
def get_playlist(playlist_id):
    """獲取指定播放列表的詳細信息"""
    try:
        playlist = db.session.get(Playlist, playlist_id)
        if not playlist:
            return jsonify({"error": "Playlist not found"}), 404

        return jsonify({
            'id': playlist.id,
            'name': playlist.name,
            'description': playlist.description,
            'created_at': playlist.created_at.isoformat(),
            'updated_at': playlist.updated_at.isoformat(),
            'songs': [song.to_dict() for song in playlist.songs]
        })
    except Exception as e:
        return jsonify({"error": f"Failed to get playlist: {str(e)}"}), 500

@app.route('/playlists/<int:playlist_id>', methods=['DELETE'])
def delete_playlist(playlist_id):
    """刪除指定的播放列表"""
    try:
        playlist = db.session.get(Playlist, playlist_id)
        if not playlist:
            return jsonify({"error": "Playlist not found"}), 404

        db.session.delete(playlist)
        db.session.commit()
        return jsonify({"message": "Playlist deleted successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to delete playlist: {str(e)}"}), 500

@app.route('/playlists/<int:playlist_id>/songs', methods=['POST'])
def add_song_to_playlist(playlist_id):
    """添加歌曲到播放列表"""
    data = request.get_json()
    if not data or not any(key in data for key in ['song_id', 'url']):
        return jsonify({"error": "Either song_id or url is required"}), 400

    try:
        playlist = db.session.get(Playlist, playlist_id)
        if not playlist:
            return jsonify({"error": "Playlist not found"}), 404

        if 'song_id' in data:
            # 添加現有歌曲
            song = db.session.get(Song, data['song_id'])
            if not song:
                return jsonify({"error": "Song not found"}), 404
        else:
            # 從 URL 創建新歌曲
            url = data['url']
            existing_song = db.session.query(Song).filter_by(url=url).first()
            if existing_song:
                song = existing_song
            else:
                # 獲取視頻信息
                if 'youtube.com' in url or 'youtu.be' in url:
                    command = ['yt-dlp', '--dump-json', url]
                    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    stdout, stderr = process.communicate()
                    if stderr:
                        print(f"Error getting video info: {stderr.decode()}")
                        return jsonify({"error": "Failed to get video info"}), 500
                    
                    try:
                        info = json.loads(stdout.decode())
                        print(f"Video info: {info}")
                        song = Song(
                            title=info['title'],
                            source='youtube',
                            source_id=info['id'],
                            thumbnail_url=info.get('thumbnail'),
                            duration=info.get('duration'),
                            url=url
                        )
                    except Exception as e:
                        print(f"Error parsing video info: {str(e)}")
                        return jsonify({"error": f"Error parsing video info: {str(e)}"}), 500
                elif 'bilibili.com' in url:
                    # TODO: 實現 Bilibili 視頻信息獲取
                    return jsonify({"error": "Bilibili support coming soon"}), 501
                else:
                    return jsonify({"error": "Unsupported URL"}), 400

                db.session.add(song)
                
        playlist.songs.append(song)
        db.session.commit()
        
        return jsonify(song.to_dict())
    except Exception as e:
        import traceback
        print(f"Error in add_song_to_playlist: {str(e)}")
        print(traceback.format_exc())
        db.session.rollback()
        return jsonify({"error": f"Failed to add song to playlist: {str(e)}"}), 500

@app.route('/playlists/<int:playlist_id>/songs/<int:song_id>', methods=['DELETE'])
def remove_song_from_playlist(playlist_id, song_id):
    """從播放列表中移除歌曲"""
    try:
        playlist = db.session.get(Playlist, playlist_id)
        if not playlist:
            return jsonify({"error": "Playlist not found"}), 404

        song = db.session.get(Song, song_id)
        if not song:
            return jsonify({"error": "Song not found"}), 404

        if song not in playlist.songs:
            return jsonify({"error": "Song is not in the playlist"}), 404

        playlist.songs.remove(song)
        db.session.commit()
        
        return jsonify({"message": "Song removed from playlist successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to remove song from playlist: {str(e)}"}), 500

@app.route('/playlists/import', methods=['POST'])
def import_playlist():
    """導入 YouTube 或 Bilibili 播放列表"""
    data = request.get_json()
    if not data or 'url' not in data or 'name' not in data:
        return jsonify({"error": "URL and name are required"}), 400

    try:
        url = data['url']
        if 'youtube.com/playlist' in url:
            # 獲取 YouTube 播放列表信息
            command = ['yt-dlp', '--dump-json', '--flat-playlist', url]
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()
            if stderr:
                print(f"Error getting playlist info: {stderr.decode()}")
                return jsonify({"error": "Failed to get playlist info"}), 500

            try:
                # 創建播放列表
                playlist = Playlist(
                    name=data['name'],
                    description=data.get('description', '')
                )
                db.session.add(playlist)

                # 添加歌曲
                for line in stdout.decode().split('\n'):
                    if not line:
                        continue
                    try:
                        info = json.loads(line)
                        print(f"Song info: {info}")
                        song = Song(
                            title=info['title'],
                            source='youtube',
                            source_id=info['id'],
                            thumbnail_url=info.get('thumbnail'),
                            duration=info.get('duration'),
                            url=f"https://www.youtube.com/watch?v={info['id']}"
                        )
                        db.session.add(song)
                        playlist.songs.append(song)
                    except Exception as e:
                        print(f"Error processing song: {str(e)}")
                        continue

                db.session.commit()
                return jsonify({
                    'id': playlist.id,
                    'name': playlist.name,
                    'description': playlist.description,
                    'song_count': len(playlist.songs.all())
                })
            except Exception as e:
                print(f"Error processing playlist: {str(e)}")
                db.session.rollback()
                return jsonify({"error": f"Error processing playlist: {str(e)}"}), 500
        elif 'bilibili.com' in url:
            # TODO: 實現 Bilibili 播放列表導入
            return jsonify({"error": "Bilibili playlist import coming soon"}), 501
        else:
            return jsonify({"error": "Unsupported URL"}), 400
    except Exception as e:
        import traceback
        print(f"Error in import_playlist: {str(e)}")
        print(traceback.format_exc())
        db.session.rollback()
        return jsonify({"error": f"Failed to import playlist: {str(e)}"}), 500

@app.route('/downloads', methods=['GET'])
def list_downloads():
    """獲取下載隊列"""
    try:
        downloads = db.session.query(DownloadQueue).order_by(DownloadQueue.created_at.desc()).all()
        return jsonify([{
            'id': d.id,
            'song': d.song.to_dict(),
            'status': d.status,
            'created_at': d.created_at.isoformat(),
            'completed_at': d.completed_at.isoformat() if d.completed_at else None,
            'error_message': d.error_message
        } for d in downloads])
    except Exception as e:
        return jsonify({"error": f"Failed to get download queue: {str(e)}"}), 500

@app.route('/downloads', methods=['POST'])
def add_download():
    """添加下載任務"""
    data = request.get_json()
    if not data or not any(key in data for key in ['song_id', 'url']):
        return jsonify({"error": "Either song_id or url is required"}), 400

    try:
        if 'song_id' in data:
            song = db.session.get(Song, data['song_id'])
            if not song:
                return jsonify({"error": "Song not found"}), 404
        else:
            # 從 URL 創建新歌曲
            url = data['url']
            existing_song = db.session.query(Song).filter_by(url=url).first()
            if existing_song:
                song = existing_song
            else:
                if 'youtube.com' in url or 'youtu.be' in url:
                    command = ['yt-dlp', '--dump-json', url]
                    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    stdout, stderr = process.communicate()
                    if stderr:
                        return jsonify({"error": "Failed to get video info"}), 500

                    info = json.loads(stdout.decode())
                    song = Song(
                        title=info['title'],
                        source='youtube',
                        source_id=info['id'],
                        thumbnail_url=info.get('thumbnail'),
                        duration=info.get('duration'),
                        url=url
                    )
                    db.session.add(song)
                elif 'bilibili.com' in url:
                    return jsonify({"error": "Bilibili download not supported yet"}), 501
                else:
                    return jsonify({"error": "Unsupported URL"}), 400

        # 檢查是否已經在下載隊列中
        existing_download = db.session.query(DownloadQueue).filter_by(song_id=song.id).first()
        if existing_download and existing_download.status in ['pending', 'downloading']:
            return jsonify({"error": "Song is already in download queue"}), 400

        # 創建下載任務
        download = DownloadQueue(
            song=song,
            status='pending'
        )
        db.session.add(download)
        db.session.commit()

        # 啟動下載處理（異步）
        asyncio.run_coroutine_threadsafe(process_download(download.id), asyncio.get_event_loop())

        return jsonify({
            'id': download.id,
            'song': song.to_dict(),
            'status': download.status,
            'created_at': download.created_at.isoformat()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to add download: {str(e)}"}), 500

@app.route('/downloads/<int:download_id>', methods=['DELETE'])
def cancel_download(download_id):
    """取消下載任務"""
    try:
        download = db.session.get(DownloadQueue, download_id)
        if not download:
            return jsonify({"error": "Download not found"}), 404

        if download.status not in ['pending', 'downloading']:
            return jsonify({"error": "Cannot cancel completed or failed download"}), 400

        download.status = 'cancelled'
        db.session.commit()

        return jsonify({"message": "Download cancelled successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to cancel download: {str(e)}"}), 500

async def process_download(download_id):
    """處理下載任務"""
    try:
        with app.app_context():
            download = db.session.get(DownloadQueue, download_id)
            if not download or download.status != 'pending':
                return

            download.status = 'downloading'
            db.session.commit()

            song = download.song
            if not song.url:
                raise ValueError("Song URL is missing")

            # 創建下載目錄（如果不存在）
            os.makedirs(app.config['MUSIC_DIR'], exist_ok=True)

            # 設置下載選項
            output_template = os.path.join(app.config['MUSIC_DIR'], '%(title)s.%(ext)s')
            if 'youtube.com' in song.url or 'youtu.be' in song.url:
                command = [
                    'yt-dlp',
                    '-f', 'bestaudio',
                    '-x',  # 提取音頻
                    '--audio-format', 'mp3',  # 轉換為 mp3
                    '--audio-quality', '0',  # 最高音質
                    '-o', output_template,
                    song.url
                ]
            else:
                raise ValueError("Unsupported URL type")

            # 執行下載
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                raise Exception(f"Download failed: {stderr.decode()}")

            # 更新歌曲本地路徑
            downloaded_files = glob.glob(os.path.join(app.config['MUSIC_DIR'], f"{song.title}.*"))
            if downloaded_files:
                song.local_path = downloaded_files[0]
                download.status = 'completed'
                download.completed_at = datetime.now(UTC)
            else:
                raise Exception("Downloaded file not found")

            db.session.commit()

    except Exception as e:
        with app.app_context():
            download = db.session.get(DownloadQueue, download_id)
            if download:
                download.status = 'failed'
                download.error_message = str(e)
                db.session.commit()

# 初始化下載處理器
async def init_download_processor():
    """初始化下載處理器，處理未完成的下載任務"""
    try:
        with app.app_context():
            pending_downloads = db.session.query(DownloadQueue).filter(
                DownloadQueue.status.in_(['pending', 'downloading'])
            ).all()
            
            for download in pending_downloads:
                asyncio.create_task(process_download(download.id))
    except Exception as e:
        print(f"Error initializing download processor: {str(e)}")

# 在應用啟動時初始化下載處理器
def init_app():
    with app.app_context():
        db.create_all()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.create_task(init_download_processor())

init_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.getenv("PORT", 5000), debug=True)
