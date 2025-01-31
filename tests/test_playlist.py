import os
import sys
import unittest
from unittest.mock import patch, MagicMock
import json

# 添加項目根目錄到 Python 路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import Song, Playlist

class TestPlaylistFunctionality(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app_context = app.app_context()
        self.app_context.push()
        self.client = app.test_client()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_create_playlist(self):
        """測試創建播放列表"""
        response = self.client.post('/playlists', 
                                  json={'name': 'My Playlist', 'description': 'Test playlist'})
        self.assertEqual(response.status_code, 201)
        
        data = json.loads(response.data)
        self.assertEqual(data['name'], 'My Playlist')
        self.assertEqual(data['description'], 'Test playlist')
        self.assertEqual(data['song_count'], 0)

    def test_list_playlists(self):
        """測試獲取播放列表列表"""
        # 創建一些測試播放列表
        playlist1 = Playlist(name='Playlist 1')
        playlist2 = Playlist(name='Playlist 2')
        db.session.add(playlist1)
        db.session.add(playlist2)
        db.session.commit()

        response = self.client.get('/playlists')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['name'], 'Playlist 1')
        self.assertEqual(data[1]['name'], 'Playlist 2')

    def test_get_playlist(self):
        """測試獲取單個播放列表"""
        # 創建測試播放列表和歌曲
        playlist = Playlist(name='Test Playlist')
        song = Song(title='Test Song', source='local')
        db.session.add(playlist)
        db.session.add(song)
        playlist.songs.append(song)
        db.session.commit()

        response = self.client.get(f'/playlists/{playlist.id}')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['name'], 'Test Playlist')
        self.assertEqual(len(data['songs']), 1)
        self.assertEqual(data['songs'][0]['title'], 'Test Song')

    def test_delete_playlist(self):
        """測試刪除播放列表"""
        playlist = Playlist(name='Test Playlist')
        db.session.add(playlist)
        db.session.commit()
        playlist_id = playlist.id

        response = self.client.delete(f'/playlists/{playlist_id}')
        self.assertEqual(response.status_code, 200)
        
        # 驗證播放列表已被刪除
        playlist = db.session.get(Playlist, playlist_id)
        self.assertIsNone(playlist)

    def test_add_song_to_playlist(self):
        """測試添加歌曲到播放列表"""
        # 創建測試播放列表和歌曲
        playlist = Playlist(name='Test Playlist')
        song = Song(title='Test Song', source='local')
        db.session.add(playlist)
        db.session.add(song)
        db.session.commit()

        response = self.client.post(f'/playlists/{playlist.id}/songs', 
                                  json={'song_id': song.id})
        self.assertEqual(response.status_code, 200)
        
        # 驗證歌曲已添加到播放列表
        playlist = db.session.get(Playlist, playlist.id)
        self.assertEqual(len(playlist.songs.all()), 1)
        self.assertEqual(playlist.songs[0].title, 'Test Song')

    @patch('subprocess.Popen')
    def test_add_youtube_url_to_playlist(self, mock_popen):
        """測試通過 YouTube URL 添加歌曲到播放列表"""
        # 模擬 yt-dlp 輸出
        mock_process = MagicMock()
        mock_process.communicate.return_value = (
            json.dumps({
                'title': 'YouTube Test',
                'id': 'test123',
                'thumbnail': 'http://example.com/thumb.jpg',
                'duration': 180
            }).encode(),
            b''
        )
        mock_popen.return_value = mock_process

        # 創建測試播放列表
        playlist = Playlist(name='Test Playlist')
        db.session.add(playlist)
        db.session.commit()

        response = self.client.post(f'/playlists/{playlist.id}/songs', 
                                  json={'url': 'https://www.youtube.com/watch?v=test123'})
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['title'], 'YouTube Test')
        self.assertEqual(data['source'], 'youtube')

    def test_remove_song_from_playlist(self):
        """測試從播放列表中移除歌曲"""
        # 創建測試播放列表和歌曲
        playlist = Playlist(name='Test Playlist')
        song = Song(title='Test Song', source='local')
        db.session.add(playlist)
        db.session.add(song)
        playlist.songs.append(song)
        db.session.commit()

        response = self.client.delete(f'/playlists/{playlist.id}/songs/{song.id}')
        self.assertEqual(response.status_code, 200)
        
        # 驗證歌曲已從播放列表中移除
        playlist = db.session.get(Playlist, playlist.id)
        self.assertEqual(len(playlist.songs.all()), 0)

    @patch('subprocess.Popen')
    def test_import_youtube_playlist(self, mock_popen):
        """測試導入 YouTube 播放列表"""
        # 模擬 yt-dlp 輸出
        mock_process = MagicMock()
        mock_process.communicate.return_value = (
            '\n'.join([
                json.dumps({
                    'title': f'Song {i}',
                    'id': f'id{i}',
                    'thumbnail': f'http://example.com/thumb{i}.jpg',
                    'duration': 180
                }) for i in range(3)
            ]).encode(),
            b''
        )
        mock_popen.return_value = mock_process

        response = self.client.post('/playlists/import', 
                                  json={
                                      'name': 'Imported Playlist',
                                      'url': 'https://www.youtube.com/playlist?list=test123'
                                  })
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['name'], 'Imported Playlist')
        self.assertEqual(data['song_count'], 3)

if __name__ == '__main__':
    unittest.main() 