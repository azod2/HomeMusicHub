from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, UTC

db = SQLAlchemy()

# 播放列表和歌曲的关联表
playlist_songs = db.Table('playlist_songs',
    db.Column('playlist_id', db.Integer, db.ForeignKey('playlist.id'), primary_key=True),
    db.Column('song_id', db.Integer, db.ForeignKey('song.id'), primary_key=True)
)

class Playlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    songs = db.relationship('Song', secondary=playlist_songs, lazy='dynamic',
                          backref=db.backref('playlists', lazy=True))

class Song(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    artist = db.Column(db.String(200))
    duration = db.Column(db.Integer)  # 持续时间（秒）
    source = db.Column(db.String(20))  # 'local', 'youtube', 'bilibili'
    source_id = db.Column(db.String(100))  # 对于在线视频，存储视频ID
    thumbnail_url = db.Column(db.String(500))  # 缩略图URL
    url = db.Column(db.String(500))  # 视频URL
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    local_path = db.Column(db.String(500))  # 本地文件路径（如果已下载）
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'artist': self.artist,
            'duration': self.duration,
            'source': self.source,
            'source_id': self.source_id,
            'thumbnail_url': self.thumbnail_url,
            'url': self.url,
            'local_path': self.local_path
        }

class SearchHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    query = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

class PlayHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    song_id = db.Column(db.Integer, db.ForeignKey('song.id'), nullable=False)
    played_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    song = db.relationship('Song', backref=db.backref('play_history', lazy=True))

class DownloadQueue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    song_id = db.Column(db.Integer, db.ForeignKey('song.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, downloading, completed, failed
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    completed_at = db.Column(db.DateTime)
    error_message = db.Column(db.String(500))
    song = db.relationship('Song', backref=db.backref('download_queue', lazy=True)) 