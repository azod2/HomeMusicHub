import os
import sys
import unittest
from unittest.mock import patch, MagicMock
import json

# 添加項目根目錄到 Python 路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import SearchHistory

class TestSearchFunctionality(unittest.TestCase):
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

    @patch('services.video_search.VideoSearchService.search_youtube')
    @patch('services.video_search.VideoSearchService.search_bilibili')
    def test_search_endpoint(self, mock_bilibili, mock_youtube):
        # 模擬搜索結果
        mock_youtube.return_value = [{
            'platform': 'youtube',
            'id': 'test_id',
            'title': 'Test Video',
            'thumbnail': 'http://example.com/thumb.jpg',
            'duration': 180,
            'view_count': 1000,
            'url': 'http://youtube.com/watch?v=test_id'
        }]
        
        mock_bilibili.return_value = [{
            'platform': 'bilibili',
            'id': '12345',
            'title': '測試視頻',
            'thumbnail': 'http://example.com/thumb.jpg',
            'duration': 180,
            'view_count': 1000,
            'url': 'https://www.bilibili.com/video/BV12345'
        }]

        # 測試搜索
        response = self.client.get('/search?q=test')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('youtube', data)
        self.assertIn('bilibili', data)
        
        # 驗證返回的數據結構
        yt_result = data['youtube'][0]
        self.assertEqual(yt_result['platform'], 'youtube')
        self.assertEqual(yt_result['title'], 'Test Video')
        
        bili_result = data['bilibili'][0]
        self.assertEqual(bili_result['platform'], 'bilibili')
        self.assertEqual(bili_result['title'], '測試視頻')

    def test_search_history(self):
        # 創建一些搜索歷史
        history1 = SearchHistory(query='test1')
        history2 = SearchHistory(query='test2')
        db.session.add(history1)
        db.session.add(history2)
        db.session.commit()

        # 測試歷史記錄 API
        response = self.client.get('/search/history')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['query'], 'test2')
        self.assertEqual(data[1]['query'], 'test1')

    def test_search_without_query(self):
        # 測試沒有查詢參數的情況
        response = self.client.get('/search')
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.data)
        self.assertIn('error', data)

if __name__ == '__main__':
    unittest.main() 