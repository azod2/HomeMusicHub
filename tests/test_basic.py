import os
import sys
import unittest
import tempfile
import shutil

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import Song, Playlist

class TestBasicFunctionality(unittest.TestCase):
    def setUp(self):
        # 创建临时目录作为音乐目录
        self.test_music_dir = tempfile.mkdtemp()
        app.config['MUSIC_DIR'] = self.test_music_dir
        print(f"\nTest music directory: {self.test_music_dir}")
        
        # 创建测试音乐文件
        self.test_music_file = os.path.join(self.test_music_dir, "test_song.mp3")
        with open(self.test_music_file, "w") as f:
            f.write("test content")
        print(f"Created test file: {self.test_music_file}")

        # 配置测试应用
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.client = app.test_client()

        # 创建数据库表
        with app.app_context():
            db.create_all()

    def tearDown(self):
        # 清理临时文件和数据库
        shutil.rmtree(self.test_music_dir)
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def test_database_initialization(self):
        """测试数据库是否正确初始化"""
        with app.app_context():
            # 检查是否可以创建播放列表
            playlist = Playlist(name="Test Playlist", description="Test Description")
            db.session.add(playlist)
            db.session.commit()
            
            # 验证播放列表是否被正确保存
            saved_playlist = Playlist.query.first()
            self.assertIsNotNone(saved_playlist)
            self.assertEqual(saved_playlist.name, "Test Playlist")

    def test_music_list_endpoint(self):
        """测试音乐列表 API"""
        # 验证文件是否存在
        print(f"\nChecking if test file exists: {self.test_music_file}")
        print(f"File exists: {os.path.exists(self.test_music_file)}")
        print(f"Directory contents: {os.listdir(self.test_music_dir)}")
        
        response = self.client.get('/music')
        print(f"Response status: {response.status_code}")
        data = response.get_json()
        print(f"Response data: {data}")
        
        # 验证返回的是列表
        self.assertIsInstance(data, list)
        
        # 验证测试音乐文件是否在返回结果中
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['title'], "test_song.mp3")
        self.assertEqual(data[0]['source'], "local")

if __name__ == '__main__':
    unittest.main() 