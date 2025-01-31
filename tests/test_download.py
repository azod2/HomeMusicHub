import os
import sys
import unittest
from unittest.mock import patch, MagicMock
import json
import asyncio
import pytest

# 添加項目根目錄到 Python 路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db, process_download
from models import Song, DownloadQueue

class TestDownloadFunctionality(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['MUSIC_DIR'] = '/tmp/test_music'
        self.app_context = app.app_context()
        self.app_context.push()
        self.client = app.test_client()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_list_downloads(self):
        """測試獲取下載隊列"""
        # 創建測試數據
        song = Song(title='Test Song', source='youtube', url='https://youtube.com/watch?v=test123')
        db.session.add(song)
        download = DownloadQueue(song=song, status='pending')
        db.session.add(download)
        db.session.commit()

        response = self.client.get('/downloads')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['song']['title'], 'Test Song')
        self.assertEqual(data[0]['status'], 'pending')

    @patch('subprocess.Popen')
    def test_add_download_with_url(self, mock_popen):
        """測試通過 URL 添加下載任務"""
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

        response = self.client.post('/downloads', 
                                  json={'url': 'https://www.youtube.com/watch?v=test123'})
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['song']['title'], 'YouTube Test')
        self.assertEqual(data['status'], 'pending')

    def test_add_download_with_existing_song(self):
        """測試通過現有歌曲 ID 添加下載任務"""
        # 創建測試歌曲
        song = Song(title='Test Song', source='youtube', url='https://youtube.com/watch?v=test123')
        db.session.add(song)
        db.session.commit()

        response = self.client.post('/downloads', 
                                  json={'song_id': song.id})
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['song']['title'], 'Test Song')
        self.assertEqual(data['status'], 'pending')

    def test_cancel_download(self):
        """測試取消下載任務"""
        # 創建測試數據
        song = Song(title='Test Song', source='youtube', url='https://youtube.com/watch?v=test123')
        db.session.add(song)
        download = DownloadQueue(song=song, status='pending')
        db.session.add(download)
        db.session.commit()

        response = self.client.delete(f'/downloads/{download.id}')
        self.assertEqual(response.status_code, 200)
        
        # 驗證下載狀態已更新
        download = db.session.get(DownloadQueue, download.id)
        self.assertEqual(download.status, 'cancelled')

    def test_cancel_completed_download(self):
        """測試取消已完成的下載任務（應該失敗）"""
        # 創建測試數據
        song = Song(title='Test Song', source='youtube', url='https://youtube.com/watch?v=test123')
        db.session.add(song)
        download = DownloadQueue(song=song, status='completed')
        db.session.add(download)
        db.session.commit()

        response = self.client.delete(f'/downloads/{download.id}')
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.data)
        self.assertIn('Cannot cancel completed or failed download', data['error'])

    @pytest.mark.asyncio
    async def test_process_download(self):
        """測試下載處理邏輯"""
        # 模擬下載過程
        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_process = MagicMock()
            mock_process.communicate = MagicMock(return_value=(b'', b''))
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            # 創建測試數據
            song = Song(
                title='Test Song',
                source='youtube',
                url='https://youtube.com/watch?v=test123'
            )
            db.session.add(song)
            download = DownloadQueue(song=song, status='pending')
            db.session.add(download)
            db.session.commit()

            # 執行下載處理
            await process_download(download.id)

            # 驗證下載狀態
            download = db.session.get(DownloadQueue, download.id)
            self.assertEqual(download.status, 'completed')

if __name__ == '__main__':
    unittest.main() 