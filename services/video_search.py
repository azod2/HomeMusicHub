import os
from typing import List, Dict, Optional
from googleapiclient.discovery import build
from bilibili_api import search, sync
import asyncio
from datetime import datetime

class VideoSearchService:
    def __init__(self):
        self.youtube = build('youtube', 'v3', 
                           developerKey=os.getenv('YOUTUBE_API_KEY'))
        self.min_duration = int(os.getenv('MIN_VIDEO_DURATION', '60'))
        self.max_duration = int(os.getenv('MAX_VIDEO_DURATION', '1800'))
        self.max_results = int(os.getenv('MAX_SEARCH_RESULTS', '30'))

    def _parse_youtube_duration(self, duration: str) -> int:
        """將 YouTube 的 duration 格式轉換為秒數"""
        import re
        hours = minutes = seconds = 0
        if match := re.search(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration):
            hours = int(match.group(1) or 0)
            minutes = int(match.group(2) or 0)
            seconds = int(match.group(3) or 0)
        return hours * 3600 + minutes * 60 + seconds

    def search_youtube(self, query: str) -> List[Dict]:
        """搜索 YouTube 視頻"""
        try:
            # 執行搜索
            search_response = self.youtube.search().list(
                q=query,
                part='id,snippet',
                maxResults=self.max_results,
                type='video'
            ).execute()

            video_ids = [item['id']['videoId'] for item in search_response['items']]
            
            # 獲取視頻詳細信息
            videos_response = self.youtube.videos().list(
                id=','.join(video_ids),
                part='contentDetails,statistics,snippet'
            ).execute()

            results = []
            for video in videos_response['items']:
                duration = self._parse_youtube_duration(video['contentDetails']['duration'])
                
                # 過濾視頻時長
                if not (self.min_duration <= duration <= self.max_duration):
                    continue

                results.append({
                    'platform': 'youtube',
                    'id': video['id'],
                    'title': video['snippet']['title'],
                    'thumbnail': video['snippet']['thumbnails']['high']['url'],
                    'duration': duration,
                    'view_count': int(video['statistics'].get('viewCount', 0)),
                    'url': f'https://www.youtube.com/watch?v={video["id"]}'
                })

            return results
        except Exception as e:
            print(f"YouTube search error: {str(e)}")
            return []

    async def search_bilibili(self, query: str) -> List[Dict]:
        """搜索 Bilibili 視頻"""
        try:
            # 執行搜索
            search_result = await search.search_by_type(
                keyword=query,
                search_type=search.SearchObjectType.VIDEO,
                page=1
            )

            results = []
            for item in search_result['result'][:self.max_results]:
                # 獲取視頻詳細信息
                duration = item['duration']  # 秒數
                
                # 過濾視頻時長
                if not (self.min_duration <= duration <= self.max_duration):
                    continue

                results.append({
                    'platform': 'bilibili',
                    'id': str(item['aid']),
                    'title': item['title'],
                    'thumbnail': item['pic'],
                    'duration': duration,
                    'view_count': item['play'],
                    'url': f'https://www.bilibili.com/video/{item["bvid"]}'
                })

            return results
        except Exception as e:
            print(f"Bilibili search error: {str(e)}")
            return []

    async def search_all(self, query: str) -> Dict[str, List[Dict]]:
        """同時搜索 YouTube 和 Bilibili"""
        # 創建搜索歷史記錄
        from models import db, SearchHistory
        search_history = SearchHistory(query=query)
        db.session.add(search_history)
        db.session.commit()

        # 執行搜索
        youtube_results = self.search_youtube(query)
        bilibili_results = await self.search_bilibili(query)

        return {
            'youtube': youtube_results,
            'bilibili': bilibili_results
        } 