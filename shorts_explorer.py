# -*- coding: utf-8 -*-
"""
ShortsExplorer — 쇼츠 주제 탐색기
PyQt5 기반 단일 파일 앱. 영상 제작 기능 없음.
"어떤 쇼츠 주제를 만들까"를 찾는 것에만 집중.
"""

import sys
import os
import json
import re
import webbrowser
import datetime
from collections import Counter

import requests
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QProgressBar, QComboBox, QSpinBox, QRadioButton, QButtonGroup, QDateEdit,
    QTextEdit, QScrollArea, QGroupBox, QCheckBox, QListWidget, QListWidgetItem,
    QMessageBox, QDialog, QDialogButtonBox, QFormLayout, QSplitter, QFrame,
    QSizePolicy, QAbstractItemView, QFileDialog, QMenu, QAction, QMenuBar
)
from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal, QDate, QDateTime, QTimer, QSize
)
from PyQt5.QtGui import QFont, QColor, QPixmap, QPalette

# matplotlib 임베딩
try:
    import matplotlib
    matplotlib.use('Qt5Agg')
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

# yt-dlp
try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False

# ─────────────────────────────────────────────────────────────────────────────
# 경로 설정
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(BASE_DIR, 'settings.json')
FAVORITES_PATH = os.path.join(BASE_DIR, 'favorites.json')
CACHE_PATH = os.path.join(BASE_DIR, 'videos.json')
REPORTS_DIR = os.path.join(BASE_DIR, 'reports')

os.makedirs(REPORTS_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# 패턴 정의
# ─────────────────────────────────────────────────────────────────────────────
HOOK_PATTERNS = [
    ("질문형",       r"[?？]|왜 |어떻게|뭘까|뭐길래|아세요|있을까"),
    ("충격·선언형",  r"충격|소름|경악|실화|대박|레전드|미친|역대급|난리"),
    ("경고·금지형",  r"절대|조심|주의|하지 ?마|큰일|위험|망함"),
    ("인용·대사형",  r'[\""]|라고 (했|하더|말)|했더니'),
    ("숫자·조건형",  r"\d"),
    ("인물 소개형",  r"(남성|여성|남자|여자|사람|분|할머니|할아버지)|씨는 "),
]

TITLE_PATTERNS = [
    ("질문형",      r"[?？]|^왜 |어떻게|뭐길래|무슨 일"),
    ("인용·대사형", r'[\""][^\""\""].{3,}[\""]'),
    ("숫자·랭킹형", r"(TOP|탑)\s?\d|\d+\s?(위|가지|개|명|배)"),
    ("반전·폭로형", r"알고\s?보니|사실은|충격|반전|정체|진실"),
    ("경고·금지형", r"절대|조심|주의|하지\s?마|위험"),
    ("공감·상황형", r"하는\s?사람|할\s?때|공감|현실|특징|유형"),
    ("명령·권유형", r"하세요|해보세요|보세요|꼭 "),
]

COMMENT_TYPES = [
    ("웃음·리액션",   r"ㅋ|ㅎㅎ|ㄷㄷ|헐|대박|미쳤|소름|레전드"),
    ("감동·칭찬",     r"감동|멋지|대단|존경|눈물|감사|응원|최고"),
    ("공감·내경험",   r"나도|저도|공감|맞아|겪|예전에|경험"),
    ("걱정·안타까움", r"안타깝|불쌍|걱정|슬프|어떡해"),
    ("화남·비난",     r"짜증|화나|어이없|한심|답답"),
    ("반박·지적",     r"아니 |틀렸|잘못|거짓|사실이 아"),
    ("정보 덧붙임",   r"사실|원래|정확히|참고로|출처"),
    ("질문",          r"[?？]|인가요|나요\b|일까"),
]

STOP_WORDS = {
    '이', '가', '을', '를', '의', '에', '은', '는', '으로', '로', '와', '과',
    '도', '에서', '하고', '하는', '이다', '이고', '이며', '것', '수', '그',
    '저', '나', '우리', '다', '좀', '잘', '더', '또', '그리고', '하지만',
    '그런데', '아', '어', '음', '뭐', '왜', '어떻게', '무슨', '진짜', '정말',
}

# ─────────────────────────────────────────────────────────────────────────────
# 설정 관리
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_SETTINGS = {
    "youtube_api_key": "",
    "deepseek_api_key": "",
    "min_views": 300000,
    "period_days": 30,
    "max_results": 25,
    "channel_videos": 40,
    "keywords": [],
    "overseas_keywords": [],
    "overseas_countries": ["US", "GB", "JP"]
}


def load_settings():
    if not os.path.exists(SETTINGS_PATH):
        save_settings(DEFAULT_SETTINGS)
        return dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # 누락 키 보완
        for k, v in DEFAULT_SETTINGS.items():
            if k not in data:
                data[k] = v
        return data
    except Exception:
        return dict(DEFAULT_SETTINGS)


def save_settings(settings):
    with open(SETTINGS_PATH, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# 캐시 관리
# ─────────────────────────────────────────────────────────────────────────────
def load_cache():
    if not os.path.exists(CACHE_PATH):
        return {}
    try:
        with open(CACHE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def save_cache(cache):
    with open(CACHE_PATH, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def get_cache_key(params):
    return json.dumps(params, sort_keys=True, ensure_ascii=False)


def is_cache_valid(entry, hours=1):
    ts = entry.get('timestamp', 0)
    return (datetime.datetime.now().timestamp() - ts) < hours * 3600


# ─────────────────────────────────────────────────────────────────────────────
# 즐겨찾기 관리
# ─────────────────────────────────────────────────────────────────────────────
def load_favorites():
    if not os.path.exists(FAVORITES_PATH):
        return []
    try:
        with open(FAVORITES_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


def save_favorites_list(favorites):
    with open(FAVORITES_PATH, 'w', encoding='utf-8') as f:
        json.dump(favorites, f, ensure_ascii=False, indent=2)


def add_favorite(video, tag='나중에만들것', memo=''):
    favorites = load_favorites()
    video_id = video.get('video_id', '')
    # 중복 체크
    for fav in favorites:
        if fav.get('video_id') == video_id:
            return False
    entry = dict(video)
    entry['tag'] = tag
    entry['memo'] = memo
    entry['saved_at'] = datetime.datetime.now().isoformat()
    favorites.append(entry)
    save_favorites_list(favorites)
    return True


# ─────────────────────────────────────────────────────────────────────────────
# 분석 함수
# ─────────────────────────────────────────────────────────────────────────────
def analyze_hook_type(title):
    if not title:
        return "기타"
    for name, pattern in HOOK_PATTERNS:
        if re.search(pattern, title):
            return name
    return "기타"


def analyze_title_pattern(title):
    if not title:
        return "기타"
    for name, pattern in TITLE_PATTERNS:
        if re.search(pattern, title):
            return name
    return "기타"


def calc_vs_ratio(view_count, subscriber_count):
    if subscriber_count and subscriber_count > 0:
        return round(view_count / subscriber_count, 2)
    return 0.0


def extract_keywords(titles_list):
    all_words = []
    for title in titles_list:
        if not title:
            continue
        # 한글, 영어, 숫자만 추출
        words = re.findall(r'[가-힣a-zA-Z0-9]+', title)
        for w in words:
            if len(w) >= 2 and w not in STOP_WORDS:
                all_words.append(w)
    return Counter(all_words).most_common(20)


def group_by_channel_size(videos):
    small = []   # 1만 미만
    medium = []  # 1만 이상 ~ 10만 미만
    large = []   # 10만 이상
    for v in videos:
        subs = v.get('subscriber_count', 0) or 0
        if subs < 10000:
            small.append(v)
        elif subs < 100000:
            medium.append(v)
        else:
            large.append(v)
    return small, medium, large


def analyze_comment_type(comment_text):
    for name, pattern in COMMENT_TYPES:
        if re.search(pattern, comment_text):
            return name
    return "기타"


def parse_duration_to_seconds(duration_str):
    """ISO 8601 duration (PT1M30S) → seconds"""
    if not duration_str:
        return 0
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
    if not match:
        return 0
    h = int(match.group(1) or 0)
    m = int(match.group(2) or 0)
    s = int(match.group(3) or 0)
    return h * 3600 + m * 60 + s


def duration_filter_seconds(filter_str):
    """필터명 → 최대 초"""
    mapping = {
        '60초 이하': 60,
        '2분 이하': 120,
        '3분 이하': 180,
        '전체': 99999,
    }
    return mapping.get(filter_str, 99999)


# ─────────────────────────────────────────────────────────────────────────────
# YouTube API
# ─────────────────────────────────────────────────────────────────────────────
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
YOUTUBE_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
YOUTUBE_PLAYLIST_URL = "https://www.googleapis.com/youtube/v3/playlistItems"


def get_channel_id(channel_input, api_key):
    """채널 URL 또는 이름으로 채널 ID 추출"""
    # URL에서 채널 ID 직접 추출
    match = re.search(r'youtube\.com/channel/([A-Za-z0-9_-]+)', channel_input)
    if match:
        return match.group(1)
    # @핸들
    match = re.search(r'youtube\.com/@([A-Za-z0-9_.-]+)', channel_input)
    if match:
        handle = match.group(1)
        try:
            resp = requests.get(
                YOUTUBE_SEARCH_URL,
                params={'part': 'snippet', 'type': 'channel', 'q': handle,
                        'key': api_key, 'maxResults': 1},
                timeout=10
            )
            items = resp.json().get('items', [])
            if items:
                return items[0]['snippet']['channelId']
        except Exception:
            pass
    # 일반 이름 검색
    if channel_input.strip():
        try:
            resp = requests.get(
                YOUTUBE_SEARCH_URL,
                params={'part': 'snippet', 'type': 'channel', 'q': channel_input,
                        'key': api_key, 'maxResults': 1},
                timeout=10
            )
            items = resp.json().get('items', [])
            if items:
                return items[0]['snippet']['channelId']
        except Exception:
            pass
    return None


def get_subscriber_count(channel_id, api_key):
    try:
        resp = requests.get(
            YOUTUBE_CHANNELS_URL,
            params={'part': 'statistics', 'id': channel_id, 'key': api_key},
            timeout=10
        )
        items = resp.json().get('items', [])
        if items:
            stats = items[0].get('statistics', {})
            return int(stats.get('subscriberCount', 0))
    except Exception:
        pass
    return 0


def get_video_details_batch(video_ids, api_key):
    """최대 50개 video_id → 상세 정보 dict"""
    results = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i+50]
        try:
            resp = requests.get(
                YOUTUBE_VIDEOS_URL,
                params={
                    'part': 'snippet,statistics,contentDetails',
                    'id': ','.join(batch),
                    'key': api_key
                },
                timeout=15
            )
            for item in resp.json().get('items', []):
                vid = item['id']
                snippet = item.get('snippet', {})
                stats = item.get('statistics', {})
                content = item.get('contentDetails', {})
                results[vid] = {
                    'video_id': vid,
                    'title': snippet.get('title', ''),
                    'channel_name': snippet.get('channelTitle', ''),
                    'channel_id': snippet.get('channelId', ''),
                    'thumbnail': snippet.get('thumbnails', {}).get('medium', {}).get('url', ''),
                    'published_at': snippet.get('publishedAt', ''),
                    'view_count': int(stats.get('viewCount', 0)),
                    'like_count': int(stats.get('likeCount', 0)),
                    'comment_count': int(stats.get('commentCount', 0)),
                    'duration': parse_duration_to_seconds(content.get('duration', '')),
                    'subscriber_count': 0,
                }
        except Exception:
            pass
    return results


def search_videos(keyword, channel_query, period, duration_filter, min_views,
                  max_subscribers, max_results, api_key):
    """YouTube 검색 → 상세 정보 포함 비디오 목록"""
    if not api_key:
        raise ValueError("YouTube API 키가 설정되지 않았습니다.")

    cache = load_cache()
    cache_key = get_cache_key({
        'fn': 'search_videos', 'keyword': keyword, 'channel_query': channel_query,
        'period': str(period), 'duration_filter': duration_filter,
        'min_views': min_views, 'max_subscribers': max_subscribers, 'max_results': max_results
    })
    if cache_key in cache and is_cache_valid(cache[cache_key]):
        return cache[cache_key]['data']

    params = {
        'part': 'snippet',
        'type': 'video',
        'maxResults': min(max_results, 50),
        'key': api_key,
        'videoDuration': 'short',  # YouTube API: <4분
        'order': 'viewCount',
    }

    query_parts = []
    if keyword:
        query_parts.append(keyword)
    if channel_query:
        query_parts.append(channel_query)
    if query_parts:
        params['q'] = ' '.join(query_parts)

    # 기간 처리
    now = datetime.datetime.utcnow()
    if period == '30d':
        published_after = (now - datetime.timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
        params['publishedAfter'] = published_after
    elif isinstance(period, tuple) and len(period) == 2:
        params['publishedAfter'] = period[0] + 'T00:00:00Z'
        params['publishedBefore'] = period[1] + 'T23:59:59Z'

    try:
        resp = requests.get(YOUTUBE_SEARCH_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        raise ConnectionError(f"YouTube API 요청 실패: {e}")

    items = data.get('items', [])
    video_ids = [item['id']['videoId'] for item in items if item.get('id', {}).get('videoId')]

    if not video_ids:
        return []

    details = get_video_details_batch(video_ids, api_key)

    # 채널별 구독자 수 조회 (중복 방지)
    channel_subs = {}
    for vid_id, vid in details.items():
        ch_id = vid.get('channel_id', '')
        if ch_id and ch_id not in channel_subs:
            channel_subs[ch_id] = get_subscriber_count(ch_id, api_key)
        if ch_id:
            vid['subscriber_count'] = channel_subs.get(ch_id, 0)

    max_dur = duration_filter_seconds(duration_filter)
    results = []
    for vid_id in video_ids:
        vid = details.get(vid_id)
        if not vid:
            continue
        # 조회수 필터
        if vid['view_count'] < min_views:
            continue
        # 영상 길이 필터
        if vid['duration'] > max_dur:
            continue
        # 구독자 수 필터 (0 = 무제한)
        if max_subscribers and max_subscribers > 0:
            if vid['subscriber_count'] > max_subscribers:
                continue
        # VS 비율 계산
        vid['vs_ratio'] = calc_vs_ratio(vid['view_count'], vid['subscriber_count'])
        vid['hook_type'] = analyze_hook_type(vid['title'])
        vid['title_pattern'] = analyze_title_pattern(vid['title'])
        vid['url'] = f"https://www.youtube.com/watch?v={vid_id}"
        results.append(vid)

    # VS 비율 높은 순 정렬
    results.sort(key=lambda x: x.get('vs_ratio', 0), reverse=True)

    # 캐시 저장
    cache[cache_key] = {
        'timestamp': datetime.datetime.now().timestamp(),
        'data': results
    }
    save_cache(cache)

    return results


def get_channel_videos(channel_url, max_videos, api_key):
    """채널 URL/이름 → uploads playlist 비디오 목록"""
    if not api_key:
        raise ValueError("YouTube API 키가 설정되지 않았습니다.")

    channel_id = get_channel_id(channel_url, api_key)
    if not channel_id:
        raise ValueError(f"채널을 찾을 수 없습니다: {channel_url}")

    # uploads playlist ID = UC → UU
    uploads_playlist_id = 'UU' + channel_id[2:]

    video_ids = []
    next_page_token = None
    while len(video_ids) < max_videos:
        params = {
            'part': 'contentDetails',
            'playlistId': uploads_playlist_id,
            'maxResults': min(50, max_videos - len(video_ids)),
            'key': api_key,
        }
        if next_page_token:
            params['pageToken'] = next_page_token
        try:
            resp = requests.get(YOUTUBE_PLAYLIST_URL, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            raise ConnectionError(f"YouTube API 요청 실패: {e}")

        for item in data.get('items', []):
            vid_id = item.get('contentDetails', {}).get('videoId', '')
            if vid_id:
                video_ids.append(vid_id)

        next_page_token = data.get('nextPageToken')
        if not next_page_token:
            break

    if not video_ids:
        return []

    details = get_video_details_batch(video_ids, api_key)
    subs = get_subscriber_count(channel_id, api_key)

    results = []
    for vid_id in video_ids:
        vid = details.get(vid_id)
        if not vid:
            continue
        vid['subscriber_count'] = subs
        vid['vs_ratio'] = calc_vs_ratio(vid['view_count'], subs)
        vid['hook_type'] = analyze_hook_type(vid['title'])
        vid['title_pattern'] = analyze_title_pattern(vid['title'])
        vid['url'] = f"https://www.youtube.com/watch?v={vid_id}"
        results.append(vid)

    results.sort(key=lambda x: x.get('vs_ratio', 0), reverse=True)
    return results


def get_video_detail(video_id, api_key):
    details = get_video_details_batch([video_id], api_key)
    vid = details.get(video_id)
    if vid:
        ch_id = vid.get('channel_id', '')
        if ch_id:
            vid['subscriber_count'] = get_subscriber_count(ch_id, api_key)
        vid['vs_ratio'] = calc_vs_ratio(vid['view_count'], vid['subscriber_count'])
        vid['hook_type'] = analyze_hook_type(vid['title'])
        vid['title_pattern'] = analyze_title_pattern(vid['title'])
        vid['url'] = f"https://www.youtube.com/watch?v={video_id}"
    return vid


def search_overseas(keywords, countries, min_views, api_key):
    """해외 각 country 기준 검색"""
    results = []
    for country in countries:
        for kw in keywords:
            try:
                resp = requests.get(
                    YOUTUBE_SEARCH_URL,
                    params={
                        'part': 'snippet',
                        'type': 'video',
                        'q': kw,
                        'regionCode': country,
                        'videoDuration': 'short',
                        'order': 'viewCount',
                        'maxResults': 20,
                        'key': api_key,
                    },
                    timeout=15
                )
                resp.raise_for_status()
                items = resp.json().get('items', [])
                video_ids = [i['id']['videoId'] for i in items if i.get('id', {}).get('videoId')]
                if not video_ids:
                    continue
                details = get_video_details_batch(video_ids, api_key)
                for vid_id, vid in details.items():
                    if vid['view_count'] >= min_views:
                        vid['country'] = country
                        vid['vs_ratio'] = calc_vs_ratio(vid['view_count'], vid.get('subscriber_count', 0))
                        vid['url'] = f"https://www.youtube.com/watch?v={vid_id}"
                        results.append(vid)
            except Exception:
                continue
    # 중복 제거
    seen = set()
    unique = []
    for v in results:
        if v['video_id'] not in seen:
            seen.add(v['video_id'])
            unique.append(v)
    unique.sort(key=lambda x: x.get('view_count', 0), reverse=True)
    return unique


# ─────────────────────────────────────────────────────────────────────────────
# yt-dlp 자막
# ─────────────────────────────────────────────────────────────────────────────
def fetch_subtitles(video_id):
    if not YTDLP_AVAILABLE:
        return ""
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        ydl_opts = {
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['ko', 'en'],
            'skip_download': True,
            'quiet': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            subs = info.get('subtitles', {}) or info.get('automatic_captions', {})
            for lang in ['ko', 'en']:
                if lang in subs and subs[lang]:
                    texts = []
                    for entry in subs[lang]:
                        if isinstance(entry, dict) and 'data' in entry:
                            texts.append(entry['data'])
                    return '\n'.join(texts)
        return ""
    except Exception:
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# YouTube 댓글
# ─────────────────────────────────────────────────────────────────────────────
def analyze_comments(video_id, api_key):
    if not api_key:
        return {}
    try:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/commentThreads",
            params={
                'part': 'snippet',
                'videoId': video_id,
                'maxResults': 100,
                'order': 'relevance',
                'key': api_key,
            },
            timeout=15
        )
        items = resp.json().get('items', [])
        type_counter = Counter()
        for item in items:
            text = item.get('snippet', {}).get('topLevelComment', {}).get('snippet', {}).get('textDisplay', '')
            t = analyze_comment_type(text)
            type_counter[t] += 1
        return dict(type_counter)
    except Exception:
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# DeepSeek AI
# ─────────────────────────────────────────────────────────────────────────────
def call_deepseek(prompt, api_key, model="deepseek-chat"):
    if not api_key:
        raise ValueError("DeepSeek API 키가 설정되지 않았습니다.")
    response = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2000
        },
        timeout=60
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def ai_analyze_pattern(videos_data, api_key):
    titles = [v.get('title', '') for v in videos_data[:30]]
    titles_text = '\n'.join(f"- {t}" for t in titles if t)
    prompt = f"""아래는 유튜브 쇼츠 영상 제목 목록입니다.
공통적인 성공 패턴, 후킹 전략, 주제 경향을 분석해주세요.
한국어로 답변하고, 핵심만 간결하게 정리해주세요.

제목 목록:
{titles_text}

분석 항목:
1. 공통 후킹 전략 (상위 3가지)
2. 자주 사용된 제목 구조
3. 인기 주제 카테고리
4. 성공 요인 종합 분석"""
    return call_deepseek(prompt, api_key)


def ai_suggest_topics(analysis_result, videos_data, api_key):
    titles = [v.get('title', '') for v in videos_data[:20]]
    titles_text = '\n'.join(f"- {t}" for t in titles if t)
    prompt = f"""아래 분석 결과와 인기 쇼츠 제목을 참고하여,
한국 유튜브 쇼츠 리메이크 주제 5개를 추천해주세요.

[분석 결과]
{analysis_result}

[참고 인기 영상 제목]
{titles_text}

각 주제마다 다음 형식으로 답변하세요:
---
주제 N: [주제명]
제목 초안 1: 
제목 초안 2:
제목 초안 3:
후킹 전략:
참고 영상:
---"""
    return call_deepseek(prompt, api_key)


def ai_translate_overseas(overseas_videos, api_key):
    entries = overseas_videos[:10]
    text = '\n'.join(f"- [{v.get('country','')}] {v.get('title','')}" for v in entries)
    prompt = f"""아래는 해외에서 인기 있는 유튜브 쇼츠 영상 제목입니다.
한국 시청자가 공감할 수 있는 주제로 재해석하고, 
한국 문화에 맞게 변환된 제목 초안을 각 영상당 2개씩 제안해주세요.

해외 인기 영상:
{text}

형식:
원제: [원제]
해석: [주제 설명]
한국판 제목 1:
한국판 제목 2:"""
    return call_deepseek(prompt, api_key)


def ai_competitor_analysis(my_channel_videos, competitor_videos, api_key):
    my_titles = set(v.get('title', '') for v in my_channel_videos)
    competitor_titles = [v.get('title', '') for v in competitor_videos
                         if v.get('view_count', 0) > 100000][:20]
    comp_text = '\n'.join(f"- {t}" for t in competitor_titles if t)
    my_text = '\n'.join(f"- {t}" for t in list(my_titles)[:20] if t)
    prompt = f"""내 채널 영상 제목과 경쟁 채널 인기 영상 제목을 비교하여,
내가 아직 다루지 않았지만 경쟁 채널에서 잘 된 주제를 찾아 제안해주세요.

[내 채널 영상]
{my_text}

[경쟁 채널 인기 영상]
{comp_text}

분석 결과:
1. 경쟁 채널이 잘 된 주제 중 내가 안 다룬 것 (상위 5개)
2. 내가 보완할 수 있는 전략"""
    return call_deepseek(prompt, api_key)


# ─────────────────────────────────────────────────────────────────────────────
# HTML 리포트 생성
# ─────────────────────────────────────────────────────────────────────────────
def generate_html_report(data):
    now = datetime.datetime.now()
    filename = f"report_{now.strftime('%Y%m%d_%H%M%S')}.html"
    filepath = os.path.join(REPORTS_DIR, filename)

    videos = data.get('videos', [])
    analysis = data.get('analysis', '')
    topics = data.get('topics', '')
    favorites = data.get('favorites', [])

    hook_counter = Counter(v.get('hook_type', '기타') for v in videos)
    title_counter = Counter(v.get('title_pattern', '기타') for v in videos)

    hook_labels = json.dumps(list(hook_counter.keys()), ensure_ascii=False)
    hook_values = json.dumps(list(hook_counter.values()))
    title_labels = json.dumps(list(title_counter.keys()), ensure_ascii=False)
    title_values = json.dumps(list(title_counter.values()))

    # 트렌드 데이터
    trend_dates = []
    trend_views = []
    for v in sorted(videos, key=lambda x: x.get('published_at', '')):
        pub = v.get('published_at', '')
        if pub:
            trend_dates.append(pub[:10])
            trend_views.append(v.get('view_count', 0))

    trend_labels = json.dumps(trend_dates)
    trend_data = json.dumps(trend_views)

    # 즐겨찾기 테이블 행
    fav_rows = ''
    for fav in favorites:
        fav_rows += f"""<tr>
            <td><a href="{fav.get('url','')}" target="_blank" style="color:#e94560;">{fav.get('title','')}</a></td>
            <td>{fav.get('channel_name','')}</td>
            <td>{fav.get('view_count',0):,}</td>
            <td>{fav.get('tag','')}</td>
            <td>{fav.get('memo','')}</td>
        </tr>"""

    # 검색 영상 테이블 행
    video_rows = ''
    for v in videos[:50]:
        video_rows += f"""<tr>
            <td><a href="{v.get('url','')}" target="_blank" style="color:#e94560;">{v.get('title','')[:60]}</a></td>
            <td>{v.get('channel_name','')}</td>
            <td>{v.get('view_count',0):,}</td>
            <td>{v.get('vs_ratio',0)}</td>
            <td>{v.get('hook_type','')}</td>
            <td>{v.get('published_at','')[:10]}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ShortsExplorer 리포트 — {now.strftime('%Y-%m-%d %H:%M')}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #1a1a2e; color: #eee; font-family: 'Segoe UI', sans-serif; padding: 20px; }}
  h1 {{ color: #e94560; margin-bottom: 20px; font-size: 1.8em; }}
  h2 {{ color: #e94560; margin: 30px 0 15px; font-size: 1.3em; border-left: 4px solid #e94560; padding-left: 10px; }}
  .charts-row {{ display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 30px; }}
  .chart-box {{ background: #16213e; border-radius: 10px; padding: 20px; flex: 1; min-width: 300px; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 30px; background: #16213e; border-radius: 10px; overflow: hidden; }}
  th {{ background: #0f3460; color: #e94560; padding: 10px; text-align: left; }}
  td {{ padding: 8px 10px; border-bottom: 1px solid #0f3460; color: #ccc; font-size: 0.9em; }}
  tr:hover {{ background: #0f3460; }}
  .analysis-box {{ background: #16213e; border-radius: 10px; padding: 20px; white-space: pre-wrap; color: #ccc; line-height: 1.6; margin-bottom: 30px; }}
  .footer {{ color: #666; font-size: 0.8em; margin-top: 40px; text-align: center; }}
</style>
</head>
<body>
<h1>📊 ShortsExplorer 리포트</h1>
<p style="color:#888; margin-bottom:30px;">생성일시: {now.strftime('%Y년 %m월 %d일 %H:%M:%S')}</p>

<h2>📈 분석 차트</h2>
<div class="charts-row">
  <div class="chart-box">
    <h3 style="color:#ccc; margin-bottom:15px;">후킹 유형 분포</h3>
    <canvas id="hookChart"></canvas>
  </div>
  <div class="chart-box">
    <h3 style="color:#ccc; margin-bottom:15px;">제목 패턴 분포</h3>
    <canvas id="titleChart"></canvas>
  </div>
</div>
<div class="chart-box" style="margin-bottom:30px;">
  <h3 style="color:#ccc; margin-bottom:15px;">업로드 트렌드</h3>
  <canvas id="trendChart"></canvas>
</div>

<h2>🤖 AI 분석 결과</h2>
<div class="analysis-box">{analysis if analysis else '(분석 결과 없음)'}</div>

<h2>💡 추천 주제</h2>
<div class="analysis-box">{topics if topics else '(추천 주제 없음)'}</div>

<h2>🔍 검색 결과 영상 (상위 50개)</h2>
<table>
  <thead><tr><th>제목</th><th>채널</th><th>조회수</th><th>VS비율</th><th>후킹유형</th><th>업로드일</th></tr></thead>
  <tbody>{video_rows}</tbody>
</table>

<h2>⭐ 즐겨찾기</h2>
<table>
  <thead><tr><th>제목</th><th>채널</th><th>조회수</th><th>태그</th><th>메모</th></tr></thead>
  <tbody>{fav_rows}</tbody>
</table>

<div class="footer">ShortsExplorer — MIT License</div>

<script>
const hookCtx = document.getElementById('hookChart').getContext('2d');
new Chart(hookCtx, {{
  type: 'doughnut',
  data: {{
    labels: {hook_labels},
    datasets: [{{ data: {hook_values}, backgroundColor: ['#e94560','#0f3460','#533483','#e84393','#2980b9','#27ae60','#f39c12'] }}]
  }},
  options: {{ plugins: {{ legend: {{ labels: {{ color: '#ccc' }} }} }} }}
}});

const titleCtx = document.getElementById('titleChart').getContext('2d');
new Chart(titleCtx, {{
  type: 'doughnut',
  data: {{
    labels: {title_labels},
    datasets: [{{ data: {title_values}, backgroundColor: ['#e94560','#0f3460','#533483','#e84393','#2980b9','#27ae60','#f39c12'] }}]
  }},
  options: {{ plugins: {{ legend: {{ labels: {{ color: '#ccc' }} }} }} }}
}});

const trendCtx = document.getElementById('trendChart').getContext('2d');
new Chart(trendCtx, {{
  type: 'line',
  data: {{
    labels: {trend_labels},
    datasets: [{{
      label: '조회수',
      data: {trend_data},
      borderColor: '#e94560',
      backgroundColor: 'rgba(233,69,96,0.1)',
      tension: 0.3,
      fill: true
    }}]
  }},
  options: {{
    scales: {{
      x: {{ ticks: {{ color: '#888' }}, grid: {{ color: '#333' }} }},
      y: {{ ticks: {{ color: '#888' }}, grid: {{ color: '#333' }} }}
    }},
    plugins: {{ legend: {{ labels: {{ color: '#ccc' }} }} }}
  }}
}});
</script>
</body>
</html>"""

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)
    return filepath


# ─────────────────────────────────────────────────────────────────────────────
# QThread Workers
# ─────────────────────────────────────────────────────────────────────────────
class SearchWorker(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    progress = pyqtSignal(int, str)

    def __init__(self, keyword, channel_query, period, duration_filter,
                 min_views, max_subscribers, max_results, api_key):
        super().__init__()
        self.keyword = keyword
        self.channel_query = channel_query
        self.period = period
        self.duration_filter = duration_filter
        self.min_views = min_views
        self.max_subscribers = max_subscribers
        self.max_results = max_results
        self.api_key = api_key

    def run(self):
        try:
            self.progress.emit(20, "YouTube 검색 중...")
            results = search_videos(
                self.keyword, self.channel_query, self.period,
                self.duration_filter, self.min_views, self.max_subscribers,
                self.max_results, self.api_key
            )
            self.progress.emit(100, f"완료: {len(results)}개 영상")
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class ChannelWorker(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    progress = pyqtSignal(int, str)

    def __init__(self, channel_url, max_videos, api_key):
        super().__init__()
        self.channel_url = channel_url
        self.max_videos = max_videos
        self.api_key = api_key

    def run(self):
        try:
            self.progress.emit(20, "채널 분석 중...")
            results = get_channel_videos(self.channel_url, self.max_videos, self.api_key)
            self.progress.emit(100, f"완료: {len(results)}개 영상")
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class DirectLinkWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    progress = pyqtSignal(int, str)

    def __init__(self, url_or_id, api_key):
        super().__init__()
        self.url_or_id = url_or_id
        self.api_key = api_key

    def run(self):
        try:
            self.progress.emit(20, "영상 정보 가져오는 중...")
            # video_id 추출
            match = re.search(r'(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{11})', self.url_or_id)
            vid_id = match.group(1) if match else self.url_or_id.strip()
            vid = get_video_detail(vid_id, self.api_key)
            self.progress.emit(100, "완료")
            self.finished.emit(vid)
        except Exception as e:
            self.error.emit(str(e))


class AnalysisWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    progress = pyqtSignal(int, str)

    def __init__(self, videos, api_key_yt, api_key_ds):
        super().__init__()
        self.videos = videos
        self.api_key_yt = api_key_yt
        self.api_key_ds = api_key_ds

    def run(self):
        try:
            result = {}
            total = len(self.videos)

            # 훅 유형 집계
            hook_counter = Counter()
            title_counter = Counter()
            comment_counter = Counter()

            for i, vid in enumerate(self.videos):
                self.progress.emit(int((i+1)/total*50), f"분석 중... ({i+1}/{total})")
                hook_counter[vid.get('hook_type', '기타')] += 1
                title_counter[vid.get('title_pattern', '기타')] += 1

                if self.api_key_yt:
                    comments = analyze_comments(vid.get('video_id', ''), self.api_key_yt)
                    for t, c in comments.items():
                        comment_counter[t] += c

            self.progress.emit(60, "키워드 추출 중...")
            titles = [v.get('title', '') for v in self.videos]
            keywords = extract_keywords(titles)

            self.progress.emit(70, "채널 규모별 분류 중...")
            small, medium, large = group_by_channel_size(self.videos)

            result = {
                'hook_counter': dict(hook_counter),
                'title_counter': dict(title_counter),
                'comment_counter': dict(comment_counter),
                'keywords': keywords,
                'small': small,
                'medium': medium,
                'large': large,
                'videos': self.videos,
            }
            self.progress.emit(100, "분석 완료")
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class AIWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    progress = pyqtSignal(int, str)

    def __init__(self, prompt_fn, *args):
        super().__init__()
        self.prompt_fn = prompt_fn
        self.args = args

    def run(self):
        try:
            self.progress.emit(50, "AI 분석 중...")
            result = self.prompt_fn(*self.args)
            self.progress.emit(100, "완료")
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class OverseasWorker(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    progress = pyqtSignal(int, str)

    def __init__(self, keywords, countries, min_views, api_key):
        super().__init__()
        self.keywords = keywords
        self.countries = countries
        self.min_views = min_views
        self.api_key = api_key

    def run(self):
        try:
            self.progress.emit(20, "해외 영상 수집 중...")
            results = search_overseas(self.keywords, self.countries, self.min_views, self.api_key)
            self.progress.emit(100, f"완료: {len(results)}개")
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 설정 다이얼로그
# ─────────────────────────────────────────────────────────────────────────────
class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ 설정")
        self.setMinimumWidth(500)
        self.settings = dict(settings)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        # YouTube API 키 + 유효성 검사 버튼
        yt_row = QHBoxLayout()
        self.yt_key_edit = QLineEdit(self.settings.get('youtube_api_key', ''))
        self.yt_key_edit.setEchoMode(QLineEdit.Password)
        self.yt_key_edit.setPlaceholderText("YouTube Data API v3 키")
        yt_row.addWidget(self.yt_key_edit)
        self.yt_show_btn = QPushButton("👁")
        self.yt_show_btn.setFixedWidth(30)
        self.yt_show_btn.setCheckable(True)
        self.yt_show_btn.toggled.connect(
            lambda on: self.yt_key_edit.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password))
        yt_row.addWidget(self.yt_show_btn)
        self.yt_check_btn = QPushButton("유효성 확인")
        self.yt_check_btn.setFixedWidth(90)
        self.yt_check_btn.clicked.connect(self._check_yt_key)
        yt_row.addWidget(self.yt_check_btn)
        self.yt_status_label = QLabel("")
        yt_row.addWidget(self.yt_status_label)
        form.addRow("YouTube API 키:", yt_row)

        # DeepSeek API 키 + 유효성 검사 버튼
        ds_row = QHBoxLayout()
        self.ds_key_edit = QLineEdit(self.settings.get('deepseek_api_key', ''))
        self.ds_key_edit.setEchoMode(QLineEdit.Password)
        self.ds_key_edit.setPlaceholderText("DeepSeek API 키")
        ds_row.addWidget(self.ds_key_edit)
        self.ds_show_btn = QPushButton("👁")
        self.ds_show_btn.setFixedWidth(30)
        self.ds_show_btn.setCheckable(True)
        self.ds_show_btn.toggled.connect(
            lambda on: self.ds_key_edit.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password))
        ds_row.addWidget(self.ds_show_btn)
        self.ds_check_btn = QPushButton("유효성 확인")
        self.ds_check_btn.setFixedWidth(90)
        self.ds_check_btn.clicked.connect(self._check_ds_key)
        ds_row.addWidget(self.ds_check_btn)
        self.ds_status_label = QLabel("")
        ds_row.addWidget(self.ds_status_label)
        form.addRow("DeepSeek API 키:", ds_row)

        self.min_views_spin = QSpinBox()
        self.min_views_spin.setRange(0, 100000000)
        self.min_views_spin.setSingleStep(10000)
        self.min_views_spin.setValue(self.settings.get('min_views', 300000))
        form.addRow("최소 조회수:", self.min_views_spin)

        self.max_results_spin = QSpinBox()
        self.max_results_spin.setRange(1, 50)
        self.max_results_spin.setValue(self.settings.get('max_results', 25))
        form.addRow("최대 검색 결과:", self.max_results_spin)

        self.channel_videos_spin = QSpinBox()
        self.channel_videos_spin.setRange(1, 200)
        self.channel_videos_spin.setValue(self.settings.get('channel_videos', 40))
        form.addRow("채널 영상 수:", self.channel_videos_spin)

        self.overseas_kw_edit = QLineEdit(', '.join(self.settings.get('overseas_keywords', [])))
        self.overseas_kw_edit.setPlaceholderText("예: shorts, reels, trending")
        form.addRow("해외 검색 키워드:", self.overseas_kw_edit)

        self.overseas_countries_edit = QLineEdit(', '.join(self.settings.get('overseas_countries', ['US', 'GB', 'JP'])))
        self.overseas_countries_edit.setPlaceholderText("예: US, GB, JP, FR")
        form.addRow("해외 검색 국가:", self.overseas_countries_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _check_yt_key(self):
        key = self.yt_key_edit.text().strip()
        if not key:
            self.yt_status_label.setText("❌ 키 없음")
            self.yt_status_label.setStyleSheet("color: red;")
            return
        self.yt_check_btn.setEnabled(False)
        self.yt_status_label.setText("확인 중...")
        try:
            resp = requests.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={"part": "snippet", "id": "dQw4w9WgXcQ", "key": key},
                timeout=10
            )
            if resp.status_code == 200:
                self.yt_status_label.setText("✅ 유효")
                self.yt_status_label.setStyleSheet("color: #00e676;")
            elif resp.status_code == 400:
                self.yt_status_label.setText("❌ 키 오류")
                self.yt_status_label.setStyleSheet("color: red;")
            elif resp.status_code == 403:
                self.yt_status_label.setText("❌ 권한 없음 (API 미활성화)")
                self.yt_status_label.setStyleSheet("color: orange;")
            else:
                self.yt_status_label.setText(f"❌ 오류 {resp.status_code}")
                self.yt_status_label.setStyleSheet("color: red;")
        except Exception as e:
            self.yt_status_label.setText("❌ 네트워크 오류")
            self.yt_status_label.setStyleSheet("color: red;")
        finally:
            self.yt_check_btn.setEnabled(True)

    def _check_ds_key(self):
        key = self.ds_key_edit.text().strip()
        if not key:
            self.ds_status_label.setText("❌ 키 없음")
            self.ds_status_label.setStyleSheet("color: red;")
            return
        self.ds_check_btn.setEnabled(False)
        self.ds_status_label.setText("확인 중...")
        try:
            resp = requests.post(
                "https://api.deepseek.com/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": "deepseek-chat",
                      "messages": [{"role": "user", "content": "hi"}],
                      "max_tokens": 1},
                timeout=15
            )
            if resp.status_code == 200:
                self.ds_status_label.setText("✅ 유효")
                self.ds_status_label.setStyleSheet("color: #00e676;")
            elif resp.status_code == 401:
                self.ds_status_label.setText("❌ 인증 실패")
                self.ds_status_label.setStyleSheet("color: red;")
            elif resp.status_code == 402:
                self.ds_status_label.setText("⚠️ 크레딧 부족")
                self.ds_status_label.setStyleSheet("color: orange;")
            else:
                self.ds_status_label.setText(f"❌ 오류 {resp.status_code}")
                self.ds_status_label.setStyleSheet("color: red;")
        except Exception as e:
            self.ds_status_label.setText("❌ 네트워크 오류")
            self.ds_status_label.setStyleSheet("color: red;")
        finally:
            self.ds_check_btn.setEnabled(True)

    def get_settings(self):
        self.settings['youtube_api_key'] = self.yt_key_edit.text().strip()
        self.settings['deepseek_api_key'] = self.ds_key_edit.text().strip()
        self.settings['min_views'] = self.min_views_spin.value()
        self.settings['max_results'] = self.max_results_spin.value()
        self.settings['channel_videos'] = self.channel_videos_spin.value()
        kws = [k.strip() for k in self.overseas_kw_edit.text().split(',') if k.strip()]
        self.settings['overseas_keywords'] = kws
        countries = [c.strip().upper() for c in self.overseas_countries_edit.text().split(',') if c.strip()]
        self.settings['overseas_countries'] = countries
        return self.settings


# ─────────────────────────────────────────────────────────────────────────────
# 탭1: 검색
# ─────────────────────────────────────────────────────────────────────────────
class SearchTab(QWidget):
    videos_updated = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = load_settings()
        self.current_videos = []
        self.worker = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ── 검색 조건 ──
        search_group = QGroupBox("검색 조건")
        sg_layout = QVBoxLayout(search_group)

        # 키워드
        kw_row = QHBoxLayout()
        kw_row.addWidget(QLabel("키워드:"))
        self.kw_edit = QLineEdit()
        self.kw_edit.setPlaceholderText("여러 개는 쉼표로 구분 (예: 다이어트, 운동)")
        kw_row.addWidget(self.kw_edit)
        sg_layout.addLayout(kw_row)

        # 채널
        ch_row = QHBoxLayout()
        ch_row.addWidget(QLabel("채널명/URL:"))
        self.ch_edit = QLineEdit()
        self.ch_edit.setPlaceholderText("예: @channel_name 또는 채널 URL")
        ch_row.addWidget(self.ch_edit)
        self.ch_analyze_btn = QPushButton("채널 분석")
        self.ch_analyze_btn.clicked.connect(self.analyze_channel)
        ch_row.addWidget(self.ch_analyze_btn)
        sg_layout.addLayout(ch_row)

        # 기간
        period_row = QHBoxLayout()
        period_row.addWidget(QLabel("기간:"))
        self.period_bg = QButtonGroup(self)
        self.period_all = QRadioButton("전체")
        self.period_30d = QRadioButton("최근 1달")
        self.period_custom = QRadioButton("직접 설정")
        self.period_30d.setChecked(True)
        for rb in [self.period_all, self.period_30d, self.period_custom]:
            self.period_bg.addButton(rb)
            period_row.addWidget(rb)
        period_row.addStretch()
        self.date_from = QDateEdit()
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        self.date_from.setDate(QDate.currentDate().addDays(-30))
        self.date_from.setEnabled(False)
        self.date_to = QDateEdit()
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setEnabled(False)
        period_row.addWidget(QLabel("시작:"))
        period_row.addWidget(self.date_from)
        period_row.addWidget(QLabel("끝:"))
        period_row.addWidget(self.date_to)
        self.period_custom.toggled.connect(self.date_from.setEnabled)
        self.period_custom.toggled.connect(self.date_to.setEnabled)
        sg_layout.addLayout(period_row)

        # 필터 행
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("영상 길이:"))
        self.duration_combo = QComboBox()
        self.duration_combo.addItems(['60초 이하', '2분 이하', '3분 이하', '전체'])
        filter_row.addWidget(self.duration_combo)
        filter_row.addSpacing(20)
        filter_row.addWidget(QLabel("최소 조회수:"))
        self.min_views_spin = QSpinBox()
        self.min_views_spin.setRange(0, 100000000)
        self.min_views_spin.setSingleStep(10000)
        self.min_views_spin.setValue(self.settings.get('min_views', 300000))
        filter_row.addWidget(self.min_views_spin)
        filter_row.addSpacing(20)
        filter_row.addWidget(QLabel("최대 구독자(0=무제한):"))
        self.max_subs_spin = QSpinBox()
        self.max_subs_spin.setRange(0, 100000000)
        self.max_subs_spin.setSingleStep(10000)
        self.max_subs_spin.setValue(0)
        filter_row.addWidget(self.max_subs_spin)
        filter_row.addStretch()
        sg_layout.addLayout(filter_row)

        layout.addWidget(search_group)

        # ── 버튼 행 ──
        btn_row = QHBoxLayout()
        self.search_btn = QPushButton("🔍 검색")
        self.search_btn.setFixedHeight(36)
        self.search_btn.clicked.connect(self.do_search)
        btn_row.addWidget(self.search_btn)
        self.direct_btn = QPushButton("🔗 직링크 분석")
        self.direct_btn.setFixedHeight(36)
        self.direct_btn.clicked.connect(self.direct_link_analyze)
        btn_row.addWidget(self.direct_btn)
        btn_row.addStretch()
        self.fav_btn = QPushButton("⭐ 즐겨찾기 추가")
        self.fav_btn.setFixedHeight(36)
        self.fav_btn.clicked.connect(self.add_to_favorites)
        btn_row.addWidget(self.fav_btn)
        self.ai_btn = QPushButton("🤖 AI 분석")
        self.ai_btn.setFixedHeight(36)
        self.ai_btn.clicked.connect(self.request_ai_analysis)
        btn_row.addWidget(self.ai_btn)
        layout.addLayout(btn_row)

        # ── 진행 상태 ──
        prog_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(18)
        self.progress_bar.setValue(0)
        prog_row.addWidget(self.progress_bar)
        self.status_label = QLabel("준비")
        prog_row.addWidget(self.status_label)
        layout.addLayout(prog_row)

        # ── 결과 테이블 ──
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(9)
        self.result_table.setHorizontalHeaderLabels([
            '✓', '썸네일URL', '제목', '채널명', '조회수', '구독자', 'VS비율', '제목패턴', '업로드일'
        ])
        self.result_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.result_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.result_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.result_table.setAlternatingRowColors(True)
        self.result_table.verticalHeader().setVisible(False)
        self.result_table.setColumnWidth(0, 30)
        self.result_table.setColumnWidth(1, 0)   # 숨김
        self.result_table.setColumnHidden(1, True)
        # 제목 더블클릭 → 유튜브 영상 열기
        self.result_table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        layout.addWidget(self.result_table)

    def _on_cell_double_clicked(self, row, col):
        """제목 셀 더블클릭 시 유튜브 영상 열기"""
        if row < len(self.current_videos):
            vid = self.current_videos[row]
            url = vid.get('url', '')
            if not url:
                video_id = vid.get('video_id', '')
                url = f"https://www.youtube.com/watch?v={video_id}" if video_id else ''
            if url:
                webbrowser.open(url)

    def get_period(self):
        if self.period_all.isChecked():
            return 'all'
        elif self.period_30d.isChecked():
            return '30d'
        else:
            return (
                self.date_from.date().toString('yyyy-MM-dd'),
                self.date_to.date().toString('yyyy-MM-dd')
            )

    def do_search(self):
        self.settings = load_settings()
        api_key = self.settings.get('youtube_api_key', '')
        if not api_key:
            QMessageBox.warning(self, "API 키 없음",
                                "YouTube API 키가 설정되지 않았습니다.\n메뉴 > 설정에서 API 키를 입력하세요.")
            return

        keyword = self.kw_edit.text().strip()
        channel_q = self.ch_edit.text().strip()
        if not keyword and not channel_q:
            QMessageBox.information(self, "입력 필요", "키워드 또는 채널명을 입력하세요.")
            return

        self.search_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.status_label.setText("검색 중...")

        self.worker = SearchWorker(
            keyword=keyword,
            channel_query='',
            period=self.get_period(),
            duration_filter=self.duration_combo.currentText(),
            min_views=self.min_views_spin.value(),
            max_subscribers=self.max_subs_spin.value(),
            max_results=self.settings.get('max_results', 25),
            api_key=api_key
        )
        self.worker.finished.connect(self._on_search_done)
        self.worker.error.connect(self._on_error)
        self.worker.progress.connect(self._on_progress)
        self.worker.start()

    def analyze_channel(self):
        self.settings = load_settings()
        api_key = self.settings.get('youtube_api_key', '')
        if not api_key:
            QMessageBox.warning(self, "API 키 없음", "YouTube API 키가 설정되지 않았습니다.")
            return
        channel_url = self.ch_edit.text().strip()
        if not channel_url:
            QMessageBox.information(self, "입력 필요", "채널명 또는 URL을 입력하세요.")
            return

        self.ch_analyze_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.status_label.setText("채널 분석 중...")

        self.worker = ChannelWorker(
            channel_url=channel_url,
            max_videos=self.settings.get('channel_videos', 40),
            api_key=api_key
        )
        self.worker.finished.connect(self._on_search_done)
        self.worker.error.connect(self._on_error)
        self.worker.progress.connect(self._on_progress)
        self.worker.start()

    def direct_link_analyze(self):
        self.settings = load_settings()
        api_key = self.settings.get('youtube_api_key', '')
        if not api_key:
            QMessageBox.warning(self, "API 키 없음", "YouTube API 키가 설정되지 않았습니다.")
            return

        url, ok = self._input_dialog("직링크 분석", "YouTube URL 또는 영상 ID 입력:")
        if not ok or not url:
            return

        self.direct_btn.setEnabled(False)
        self.progress_bar.setValue(0)

        self.worker = DirectLinkWorker(url_or_id=url, api_key=api_key)
        self.worker.finished.connect(self._on_direct_done)
        self.worker.error.connect(self._on_error)
        self.worker.progress.connect(self._on_progress)
        self.worker.start()

    def _input_dialog(self, title, label):
        from PyQt5.QtWidgets import QInputDialog
        return QInputDialog.getText(self, title, label)

    def _on_direct_done(self, vid):
        self.direct_btn.setEnabled(True)
        if vid:
            self._on_search_done([vid])
        else:
            QMessageBox.warning(self, "오류", "영상 정보를 가져올 수 없습니다.")

    def _on_search_done(self, videos):
        self.search_btn.setEnabled(True)
        self.ch_analyze_btn.setEnabled(True)
        self.direct_btn.setEnabled(True)
        self.current_videos = videos
        self._populate_table(videos)
        self.videos_updated.emit(videos)

    def _on_error(self, msg):
        self.search_btn.setEnabled(True)
        self.ch_analyze_btn.setEnabled(True)
        self.direct_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("오류")
        QMessageBox.critical(self, "오류", f"검색 중 오류가 발생했습니다:\n{msg}\n\n네트워크 상태와 API 키를 확인하세요.")

    def _on_progress(self, value, msg):
        self.progress_bar.setValue(value)
        self.status_label.setText(msg)

    def _populate_table(self, videos):
        self.result_table.setRowCount(0)
        for vid in videos:
            row = self.result_table.rowCount()
            self.result_table.insertRow(row)

            chk = QCheckBox()
            chk_widget = QWidget()
            chk_layout = QHBoxLayout(chk_widget)
            chk_layout.addWidget(chk)
            chk_layout.setAlignment(Qt.AlignCenter)
            chk_layout.setContentsMargins(0, 0, 0, 0)
            self.result_table.setCellWidget(row, 0, chk_widget)

            thumb_item = QTableWidgetItem(vid.get('thumbnail', ''))
            self.result_table.setItem(row, 1, thumb_item)

            self.result_table.setItem(row, 2, QTableWidgetItem(vid.get('title', '')))
            self.result_table.setItem(row, 3, QTableWidgetItem(vid.get('channel_name', '')))
            self.result_table.setItem(row, 4, QTableWidgetItem(f"{vid.get('view_count', 0):,}"))
            self.result_table.setItem(row, 5, QTableWidgetItem(f"{vid.get('subscriber_count', 0):,}"))
            self.result_table.setItem(row, 6, QTableWidgetItem(str(vid.get('vs_ratio', 0))))
            self.result_table.setItem(row, 7, QTableWidgetItem(vid.get('title_pattern', '')))
            pub = vid.get('published_at', '')[:10]
            self.result_table.setItem(row, 8, QTableWidgetItem(pub))

        self.result_table.resizeRowsToContents()

    def get_checked_videos(self):
        checked = []
        for row in range(self.result_table.rowCount()):
            chk_widget = self.result_table.cellWidget(row, 0)
            if chk_widget:
                chk = chk_widget.findChild(QCheckBox)
                if chk and chk.isChecked():
                    if row < len(self.current_videos):
                        checked.append(self.current_videos[row])
        return checked

    def get_selected_video(self):
        selected = self.result_table.selectedItems()
        if selected:
            row = selected[0].row()
            if row < len(self.current_videos):
                return self.current_videos[row]
        return None

    def add_to_favorites(self):
        vid = self.get_selected_video()
        if not vid:
            QMessageBox.information(self, "선택 필요", "즐겨찾기에 추가할 영상을 선택하세요.")
            return
        if add_favorite(vid):
            QMessageBox.information(self, "완료", f"즐겨찾기에 추가되었습니다:\n{vid.get('title', '')}")
        else:
            QMessageBox.information(self, "알림", "이미 즐겨찾기에 있는 영상입니다.")

    def request_ai_analysis(self):
        checked = self.get_checked_videos()
        if not checked:
            vid = self.get_selected_video()
            if vid:
                checked = [vid]
        if not checked:
            QMessageBox.information(self, "선택 필요", "분석할 영상을 체크박스로 선택하세요.")
            return
        # 분석 탭으로 이동 — 메인 윈도우(QMainWindow)를 안전하게 탐색
        widget = self.parentWidget()
        while widget is not None:
            if isinstance(widget, QMainWindow):
                widget.switch_to_analysis(checked)
                break
            widget = widget.parentWidget()

    def reload_settings(self):
        self.settings = load_settings()
        self.min_views_spin.setValue(self.settings.get('min_views', 300000))


# ─────────────────────────────────────────────────────────────────────────────
# 탭2: 분석
# ─────────────────────────────────────────────────────────────────────────────
class AnalysisTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = load_settings()
        self.selected_videos = []
        self.analysis_result = {}
        self.ai_result = ''
        self.worker = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # 선택 영상 목록
        top_group = QGroupBox("분석 대상 영상")
        top_layout = QVBoxLayout(top_group)
        self.video_list = QListWidget()
        self.video_list.setMaximumHeight(120)
        top_layout.addWidget(self.video_list)
        layout.addWidget(top_group)

        # 실행 버튼
        btn_row = QHBoxLayout()
        self.run_btn = QPushButton("📊 대본/댓글 분석 실행")
        self.run_btn.setFixedHeight(36)
        self.run_btn.clicked.connect(self.run_analysis)
        btn_row.addWidget(self.run_btn)
        self.ai_btn = QPushButton("🤖 AI 공통점 분석")
        self.ai_btn.setFixedHeight(36)
        self.ai_btn.clicked.connect(self.run_ai_analysis)
        btn_row.addWidget(self.ai_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # 진행 상태
        prog_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(18)
        prog_row.addWidget(self.progress_bar)
        self.status_label = QLabel("준비")
        prog_row.addWidget(self.status_label)
        layout.addLayout(prog_row)

        # 결과 스크롤 영역
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.result_widget = QWidget()
        self.result_layout = QVBoxLayout(self.result_widget)
        self.result_layout.setSpacing(12)
        scroll.setWidget(self.result_widget)
        layout.addWidget(scroll)

        # 통계 텍스트
        self.hook_label = QLabel("훅 유형 분포: (분석 전)")
        self.hook_label.setWordWrap(True)
        self.result_layout.addWidget(self.hook_label)

        self.title_label = QLabel("제목 패턴 분포: (분석 전)")
        self.title_label.setWordWrap(True)
        self.result_layout.addWidget(self.title_label)

        self.comment_label = QLabel("댓글 반응 유형: (분석 전)")
        self.comment_label.setWordWrap(True)
        self.result_layout.addWidget(self.comment_label)

        self.keyword_label = QLabel("핵심 키워드 Top20: (분석 전)")
        self.keyword_label.setWordWrap(True)
        self.result_layout.addWidget(self.keyword_label)

        self.channel_size_label = QLabel("채널 규모별: (분석 전)")
        self.channel_size_label.setWordWrap(True)
        self.result_layout.addWidget(self.channel_size_label)

        # 트렌드 그래프
        if MATPLOTLIB_AVAILABLE:
            self.figure = Figure(figsize=(8, 3), facecolor='#16213e')
            self.canvas = FigureCanvas(self.figure)
            self.canvas.setMinimumHeight(200)
            self.result_layout.addWidget(self.canvas)

        # AI 결과
        ai_group = QGroupBox("AI 분석 결과")
        ai_layout = QVBoxLayout(ai_group)
        self.ai_text = QTextEdit()
        self.ai_text.setReadOnly(True)
        self.ai_text.setPlaceholderText("AI 분석 버튼을 클릭하면 결과가 여기에 표시됩니다.")
        self.ai_text.setMinimumHeight(150)
        ai_layout.addWidget(self.ai_text)
        self.result_layout.addWidget(ai_group)
        self.result_layout.addStretch()

    def set_videos(self, videos):
        self.selected_videos = videos
        self.video_list.clear()
        for v in videos:
            self.video_list.addItem(f"[{v.get('view_count',0):,}뷰] {v.get('title','')}")

    def run_analysis(self):
        if not self.selected_videos:
            QMessageBox.information(self, "선택 필요", "검색 탭에서 영상을 선택(체크)한 후 분석하세요.")
            return
        self.settings = load_settings()
        self.run_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.status_label.setText("분석 중...")

        self.worker = AnalysisWorker(
            self.selected_videos,
            self.settings.get('youtube_api_key', ''),
            self.settings.get('deepseek_api_key', '')
        )
        self.worker.finished.connect(self._on_analysis_done)
        self.worker.error.connect(self._on_error)
        self.worker.progress.connect(self._on_progress)
        self.worker.start()

    def _on_analysis_done(self, result):
        self.run_btn.setEnabled(True)
        self.analysis_result = result

        # 훅 유형
        hook = result.get('hook_counter', {})
        hook_text = "  ".join(f"{k}: {v}개" for k, v in
                               sorted(hook.items(), key=lambda x: -x[1]))
        self.hook_label.setText(f"🎯 훅 유형 분포:\n{hook_text}")

        # 제목 패턴
        tp = result.get('title_counter', {})
        tp_text = "  ".join(f"{k}: {v}개" for k, v in
                             sorted(tp.items(), key=lambda x: -x[1]))
        self.title_label.setText(f"📝 제목 패턴 분포:\n{tp_text}")

        # 댓글
        comm = result.get('comment_counter', {})
        if comm:
            comm_text = "  ".join(f"{k}: {v}개" for k, v in
                                  sorted(comm.items(), key=lambda x: -x[1]))
            self.comment_label.setText(f"💬 댓글 반응 유형:\n{comm_text}")

        # 키워드
        kws = result.get('keywords', [])
        kw_text = ", ".join(f"{w}({c})" for w, c in kws)
        self.keyword_label.setText(f"🔑 핵심 키워드 Top20:\n{kw_text}")

        # 채널 규모별
        small = result.get('small', [])
        medium = result.get('medium', [])
        large = result.get('large', [])
        self.channel_size_label.setText(
            f"📊 채널 규모별:\n"
            f"  1만 미만: {len(small)}개  |  "
            f"  1만~10만: {len(medium)}개  |  "
            f"  10만 이상: {len(large)}개"
        )

        # 트렌드 그래프
        if MATPLOTLIB_AVAILABLE:
            self._draw_trend(result.get('videos', []))

        self.status_label.setText("분석 완료")
        self.progress_bar.setValue(100)

    def _draw_trend(self, videos):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_facecolor('#1a1a2e')
        self.figure.patch.set_facecolor('#16213e')

        dates = []
        views = []
        for v in videos:
            pub = v.get('published_at', '')
            if pub:
                try:
                    dt = datetime.datetime.fromisoformat(pub.replace('Z', '+00:00'))
                    dates.append(dt)
                    views.append(v.get('view_count', 0))
                except Exception:
                    pass

        if dates:
            ax.scatter(dates, views, color='#e94560', alpha=0.7, s=40)
            ax.set_xlabel('업로드 날짜', color='#888')
            ax.set_ylabel('조회수', color='#888')
            ax.tick_params(colors='#888')
            for spine in ax.spines.values():
                spine.set_edgecolor('#333')
            self.figure.autofmt_xdate()

        self.canvas.draw()

    def run_ai_analysis(self):
        if not self.selected_videos:
            QMessageBox.information(self, "선택 필요", "먼저 영상을 선택하세요.")
            return
        self.settings = load_settings()
        api_key = self.settings.get('deepseek_api_key', '')
        if not api_key:
            QMessageBox.warning(self, "API 키 없음",
                                "DeepSeek API 키가 설정되지 않았습니다.\n메뉴 > 설정에서 입력하세요.")
            return

        self.ai_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.status_label.setText("AI 분석 중...")

        self.worker = AIWorker(ai_analyze_pattern, self.selected_videos, api_key)
        self.worker.finished.connect(self._on_ai_done)
        self.worker.error.connect(self._on_error)
        self.worker.progress.connect(self._on_progress)
        self.worker.start()

    def _on_ai_done(self, result):
        self.ai_btn.setEnabled(True)
        self.ai_result = result
        self.ai_text.setPlainText(result)
        self.status_label.setText("AI 분석 완료")
        self.progress_bar.setValue(100)

    def _on_error(self, msg):
        self.run_btn.setEnabled(True)
        self.ai_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("오류")
        QMessageBox.critical(self, "오류", f"분석 중 오류:\n{msg}")

    def _on_progress(self, value, msg):
        self.progress_bar.setValue(value)
        self.status_label.setText(msg)

    def reload_settings(self):
        self.settings = load_settings()


# ─────────────────────────────────────────────────────────────────────────────
# 탭3: 주제 추천
# ─────────────────────────────────────────────────────────────────────────────
class TopicTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = load_settings()
        self.analysis_result = {}
        self.videos = []
        self.overseas_videos = []
        self.worker = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ── 리메이크 주제 추천 ──
        remake_group = QGroupBox("🎯 리메이크 주제 추천")
        rg_layout = QVBoxLayout(remake_group)

        btn_row = QHBoxLayout()
        self.suggest_btn = QPushButton("💡 리메이크 주제 추천 받기")
        self.suggest_btn.setFixedHeight(36)
        self.suggest_btn.clicked.connect(self.run_suggest)
        btn_row.addWidget(self.suggest_btn)

        self.fav_suggest_btn = QPushButton("⭐ 즐겨찾기 기반 추천")
        self.fav_suggest_btn.setFixedHeight(36)
        self.fav_suggest_btn.clicked.connect(self.run_fav_suggest)
        btn_row.addWidget(self.fav_suggest_btn)
        btn_row.addStretch()
        rg_layout.addLayout(btn_row)

        self.prog_bar = QProgressBar()
        self.prog_bar.setFixedHeight(18)
        self.prog_label = QLabel("준비")
        prog_row = QHBoxLayout()
        prog_row.addWidget(self.prog_bar)
        prog_row.addWidget(self.prog_label)
        rg_layout.addLayout(prog_row)

        # 카드 영역
        self.cards_scroll = QScrollArea()
        self.cards_scroll.setWidgetResizable(True)
        self.cards_widget = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_widget)
        self.cards_layout.setSpacing(10)
        self.cards_scroll.setWidget(self.cards_widget)
        self.cards_scroll.setMinimumHeight(250)
        rg_layout.addWidget(self.cards_scroll)

        layout.addWidget(remake_group)

        # ── 해외→국내 변환 ──
        overseas_group = QGroupBox("🌍 해외 → 국내 변환")
        og_layout = QVBoxLayout(overseas_group)

        ov_btn_row = QHBoxLayout()
        self.overseas_btn = QPushButton("🌐 해외 수집 실행")
        self.overseas_btn.setFixedHeight(36)
        self.overseas_btn.clicked.connect(self.run_overseas)
        ov_btn_row.addWidget(self.overseas_btn)
        self.convert_btn = QPushButton("🔄 한국 시청자용 주제로 변환")
        self.convert_btn.setFixedHeight(36)
        self.convert_btn.clicked.connect(self.run_convert)
        ov_btn_row.addWidget(self.convert_btn)
        ov_btn_row.addStretch()
        og_layout.addLayout(ov_btn_row)

        self.overseas_list = QListWidget()
        self.overseas_list.setMaximumHeight(150)
        og_layout.addWidget(self.overseas_list)

        self.convert_text = QTextEdit()
        self.convert_text.setReadOnly(True)
        self.convert_text.setPlaceholderText("변환 결과가 여기에 표시됩니다.")
        self.convert_text.setMaximumHeight(200)
        og_layout.addWidget(self.convert_text)

        layout.addWidget(overseas_group)

    def set_analysis(self, analysis_result, videos):
        self.analysis_result = analysis_result
        self.videos = videos

    def run_suggest(self):
        self.settings = load_settings()
        api_key = self.settings.get('deepseek_api_key', '')
        if not api_key:
            QMessageBox.warning(self, "API 키 없음",
                                "DeepSeek API 키가 설정되지 않았습니다.")
            return
        if not self.videos:
            QMessageBox.information(self, "데이터 없음",
                                    "먼저 검색 탭에서 검색하고 분석 탭에서 분석을 실행하세요.")
            return

        self.suggest_btn.setEnabled(False)
        self.prog_bar.setValue(0)
        self.prog_label.setText("AI 주제 추천 중...")

        ai_text = self.analysis_result.get('ai_result', '') or \
                  f"인기 영상 {len(self.videos)}개 분석 결과"

        self.worker = AIWorker(ai_suggest_topics, ai_text, self.videos, api_key)
        self.worker.finished.connect(self._on_suggest_done)
        self.worker.error.connect(self._on_error)
        self.worker.progress.connect(self._on_progress)
        self.worker.start()

    def run_fav_suggest(self):
        self.settings = load_settings()
        api_key = self.settings.get('deepseek_api_key', '')
        if not api_key:
            QMessageBox.warning(self, "API 키 없음", "DeepSeek API 키가 설정되지 않았습니다.")
            return

        favs = load_favorites()
        if not favs:
            QMessageBox.information(self, "즐겨찾기 없음",
                                    "즐겨찾기에 저장된 영상이 없습니다.")
            return

        self.fav_suggest_btn.setEnabled(False)
        self.prog_bar.setValue(0)
        self.prog_label.setText("즐겨찾기 기반 추천 중...")

        self.worker = AIWorker(ai_suggest_topics, "즐겨찾기 기반 분석", favs, api_key)
        self.worker.finished.connect(self._on_suggest_done)
        self.worker.error.connect(self._on_error)
        self.worker.progress.connect(self._on_progress)
        self.worker.start()

    def _on_suggest_done(self, result):
        self.suggest_btn.setEnabled(True)
        self.fav_suggest_btn.setEnabled(True)
        self.prog_bar.setValue(100)
        self.prog_label.setText("추천 완료")
        self._display_topic_cards(result)

    def _display_topic_cards(self, text):
        # 기존 카드 제거
        while self.cards_layout.count():
            child = self.cards_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # 구분자로 분리
        sections = re.split(r'---+', text)
        card_count = 0
        for section in sections:
            section = section.strip()
            if not section:
                continue
            card = QGroupBox(f"💡 추천 주제 {card_count + 1}")
            card_layout = QVBoxLayout(card)
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setPlainText(section)
            text_edit.setMinimumHeight(120)
            text_edit.setMaximumHeight(200)
            card_layout.addWidget(text_edit)
            self.cards_layout.addWidget(card)
            card_count += 1
            if card_count >= 5:
                break

        if card_count == 0:
            # 분리 안 됐으면 전체 표시
            card = QGroupBox("💡 AI 추천 결과")
            cl = QVBoxLayout(card)
            te = QTextEdit()
            te.setReadOnly(True)
            te.setPlainText(text)
            te.setMinimumHeight(200)
            cl.addWidget(te)
            self.cards_layout.addWidget(card)

        self.cards_layout.addStretch()

    def run_overseas(self):
        self.settings = load_settings()
        api_key = self.settings.get('youtube_api_key', '')
        if not api_key:
            QMessageBox.warning(self, "API 키 없음", "YouTube API 키가 설정되지 않았습니다.")
            return

        keywords = self.settings.get('overseas_keywords', [])
        if not keywords:
            keywords = ['shorts', 'trending']

        countries = self.settings.get('overseas_countries', ['US', 'GB', 'JP'])
        min_views = self.settings.get('min_views', 300000)

        self.overseas_btn.setEnabled(False)
        self.prog_bar.setValue(0)
        self.prog_label.setText("해외 수집 중...")

        self.worker = OverseasWorker(keywords, countries, min_views, api_key)
        self.worker.finished.connect(self._on_overseas_done)
        self.worker.error.connect(self._on_error)
        self.worker.progress.connect(self._on_progress)
        self.worker.start()

    def _on_overseas_done(self, videos):
        self.overseas_btn.setEnabled(True)
        self.overseas_videos = videos
        self.overseas_list.clear()
        for v in videos:
            self.overseas_list.addItem(
                f"[{v.get('country','')}] [{v.get('view_count',0):,}뷰] {v.get('title','')}"
            )
        self.prog_label.setText(f"해외 수집 완료: {len(videos)}개")
        self.prog_bar.setValue(100)

    def run_convert(self):
        self.settings = load_settings()
        api_key = self.settings.get('deepseek_api_key', '')
        if not api_key:
            QMessageBox.warning(self, "API 키 없음", "DeepSeek API 키가 설정되지 않았습니다.")
            return
        if not self.overseas_videos:
            QMessageBox.information(self, "데이터 없음", "먼저 해외 수집을 실행하세요.")
            return

        self.convert_btn.setEnabled(False)
        self.prog_bar.setValue(0)
        self.prog_label.setText("변환 중...")

        self.worker = AIWorker(ai_translate_overseas, self.overseas_videos, api_key)
        self.worker.finished.connect(self._on_convert_done)
        self.worker.error.connect(self._on_error)
        self.worker.progress.connect(self._on_progress)
        self.worker.start()

    def _on_convert_done(self, result):
        self.convert_btn.setEnabled(True)
        self.convert_text.setPlainText(result)
        self.prog_label.setText("변환 완료")
        self.prog_bar.setValue(100)

    def _on_error(self, msg):
        self.suggest_btn.setEnabled(True)
        self.fav_suggest_btn.setEnabled(True)
        self.overseas_btn.setEnabled(True)
        self.convert_btn.setEnabled(True)
        self.prog_bar.setValue(0)
        self.prog_label.setText("오류")
        QMessageBox.critical(self, "오류", f"오류 발생:\n{msg}")

    def _on_progress(self, value, msg):
        self.prog_bar.setValue(value)
        self.prog_label.setText(msg)

    def reload_settings(self):
        self.settings = load_settings()


# ─────────────────────────────────────────────────────────────────────────────
# 탭4: 리포트
# ─────────────────────────────────────────────────────────────────────────────
class ReportTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = load_settings()
        self.current_videos = []
        self.analysis_result = {}
        self.worker = None
        self._build_ui()
        self._load_report_history()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        splitter = QSplitter(Qt.Vertical)

        # ── 즐겨찾기 ──
        fav_group = QGroupBox("⭐ 즐겨찾기")
        fav_layout = QVBoxLayout(fav_group)

        self.fav_table = QTableWidget()
        self.fav_table.setColumnCount(6)
        self.fav_table.setHorizontalHeaderLabels(['제목', '채널', '조회수', '태그', '메모', '저장일'])
        self.fav_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.fav_table.setAlternatingRowColors(True)
        self.fav_table.verticalHeader().setVisible(False)
        fav_layout.addWidget(self.fav_table)

        fav_btn_row = QHBoxLayout()
        self.refresh_fav_btn = QPushButton("🔄 새로고침")
        self.refresh_fav_btn.clicked.connect(self.load_favorites_table)
        fav_btn_row.addWidget(self.refresh_fav_btn)
        self.remove_fav_btn = QPushButton("🗑️ 선택 삭제")
        self.remove_fav_btn.clicked.connect(self.remove_favorite)
        fav_btn_row.addWidget(self.remove_fav_btn)
        fav_btn_row.addStretch()
        fav_layout.addLayout(fav_btn_row)

        splitter.addWidget(fav_group)

        # ── 경쟁 채널 분석 ──
        comp_group = QGroupBox("🏆 내 채널 경쟁 분석")
        cg_layout = QVBoxLayout(comp_group)

        ch_row = QHBoxLayout()
        ch_row.addWidget(QLabel("내 채널 URL:"))
        self.my_ch_edit = QLineEdit()
        self.my_ch_edit.setPlaceholderText("예: https://www.youtube.com/@mychannel")
        ch_row.addWidget(self.my_ch_edit)
        self.comp_btn = QPushButton("🔍 경쟁 채널 분석 실행")
        self.comp_btn.setFixedHeight(32)
        self.comp_btn.clicked.connect(self.run_competitor_analysis)
        ch_row.addWidget(self.comp_btn)
        cg_layout.addLayout(ch_row)

        self.comp_text = QTextEdit()
        self.comp_text.setReadOnly(True)
        self.comp_text.setPlaceholderText("분석 결과가 여기에 표시됩니다.")
        self.comp_text.setMaximumHeight(180)
        cg_layout.addWidget(self.comp_text)

        splitter.addWidget(comp_group)

        layout.addWidget(splitter)

        # ── 진행 상태 ──
        prog_row = QHBoxLayout()
        self.prog_bar = QProgressBar()
        self.prog_bar.setFixedHeight(18)
        prog_row.addWidget(self.prog_bar)
        self.prog_label = QLabel("준비")
        prog_row.addWidget(self.prog_label)
        layout.addLayout(prog_row)

        # ── 리포트 생성 ──
        report_row = QHBoxLayout()
        self.gen_btn = QPushButton("📄 오늘의 리포트 생성")
        self.gen_btn.setFixedHeight(36)
        self.gen_btn.clicked.connect(self.generate_report)
        report_row.addWidget(self.gen_btn)
        report_row.addStretch()
        layout.addLayout(report_row)

        # ── 히스토리 ──
        hist_group = QGroupBox("📂 리포트 히스토리")
        hist_layout = QVBoxLayout(hist_group)
        self.hist_list = QListWidget()
        self.hist_list.setMaximumHeight(120)
        self.hist_list.itemDoubleClicked.connect(self.open_report)
        hist_layout.addWidget(self.hist_list)
        layout.addWidget(hist_group)

        self.load_favorites_table()

    def load_favorites_table(self):
        favorites = load_favorites()
        self.fav_table.setRowCount(0)
        TAG_OPTIONS = ['나중에만들것', '참고용', '이미만든것']
        for fav in favorites:
            row = self.fav_table.rowCount()
            self.fav_table.insertRow(row)

            title_item = QTableWidgetItem(fav.get('title', ''))
            title_item.setData(Qt.UserRole, fav.get('video_id', ''))
            self.fav_table.setItem(row, 0, title_item)
            self.fav_table.setItem(row, 1, QTableWidgetItem(fav.get('channel_name', '')))
            self.fav_table.setItem(row, 2, QTableWidgetItem(f"{fav.get('view_count', 0):,}"))

            # 태그 콤보박스 (인라인 편집)
            tag_combo = QComboBox()
            for opt in TAG_OPTIONS:
                tag_combo.addItem(opt)
            current_tag = fav.get('tag', '나중에만들것')
            if current_tag in TAG_OPTIONS:
                tag_combo.setCurrentText(current_tag)
            tag_combo.currentTextChanged.connect(
                lambda t, r=row, vid=fav.get('video_id', ''): self._update_tag(vid, t)
            )
            self.fav_table.setCellWidget(row, 3, tag_combo)

            memo_item = QTableWidgetItem(fav.get('memo', ''))
            self.fav_table.setItem(row, 4, memo_item)

            saved = fav.get('saved_at', '')[:10]
            self.fav_table.setItem(row, 5, QTableWidgetItem(saved))

        self.fav_table.itemChanged.connect(self._on_fav_item_changed)

    def _update_tag(self, video_id, tag):
        favorites = load_favorites()
        for fav in favorites:
            if fav.get('video_id') == video_id:
                fav['tag'] = tag
        save_favorites_list(favorites)

    def _on_fav_item_changed(self, item):
        if item.column() == 4:  # 메모
            row = item.row()
            title_item = self.fav_table.item(row, 0)
            if title_item:
                video_id = title_item.data(Qt.UserRole)
                if video_id:
                    favorites = load_favorites()
                    for fav in favorites:
                        if fav.get('video_id') == video_id:
                            fav['memo'] = item.text()
                    save_favorites_list(favorites)

    def remove_favorite(self):
        selected = self.fav_table.selectedItems()
        if not selected:
            QMessageBox.information(self, "선택 필요", "삭제할 항목을 선택하세요.")
            return
        row = selected[0].row()
        title_item = self.fav_table.item(row, 0)
        if not title_item:
            return
        video_id = title_item.data(Qt.UserRole)
        reply = QMessageBox.question(self, "삭제 확인",
                                     f"즐겨찾기에서 삭제하시겠습니까?\n{title_item.text()}",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            favorites = load_favorites()
            favorites = [f for f in favorites if f.get('video_id') != video_id]
            save_favorites_list(favorites)
            self.load_favorites_table()

    def run_competitor_analysis(self):
        self.settings = load_settings()
        api_key = self.settings.get('youtube_api_key', '')
        ds_key = self.settings.get('deepseek_api_key', '')
        if not api_key:
            QMessageBox.warning(self, "API 키 없음", "YouTube API 키가 설정되지 않았습니다.")
            return
        if not ds_key:
            QMessageBox.warning(self, "API 키 없음", "DeepSeek API 키가 설정되지 않았습니다.")
            return

        my_ch = self.my_ch_edit.text().strip()
        if not my_ch:
            QMessageBox.information(self, "입력 필요", "내 채널 URL을 입력하세요.")
            return

        if not self.current_videos:
            QMessageBox.information(self, "데이터 없음",
                                    "검색 탭에서 먼저 검색을 실행하세요.")
            return

        self.comp_btn.setEnabled(False)
        self.prog_bar.setValue(0)
        self.prog_label.setText("내 채널 분석 중...")

        def run_comp():
            my_videos = get_channel_videos(my_ch, 40, api_key)
            return ai_competitor_analysis(my_videos, self.current_videos, ds_key)

        self.worker = AIWorker(run_comp)
        self.worker.finished.connect(self._on_comp_done)
        self.worker.error.connect(self._on_error)
        self.worker.progress.connect(self._on_progress)
        self.worker.start()

    def _on_comp_done(self, result):
        self.comp_btn.setEnabled(True)
        self.comp_text.setPlainText(result)
        self.prog_label.setText("분석 완료")
        self.prog_bar.setValue(100)

    def generate_report(self):
        data = {
            'videos': self.current_videos,
            'analysis': self.analysis_result.get('ai_result', ''),
            'topics': '',
            'favorites': load_favorites(),
        }
        try:
            filepath = generate_html_report(data)
            self._load_report_history()
            webbrowser.open(filepath)
            self.prog_label.setText("리포트 생성 완료")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"리포트 생성 실패:\n{e}")

    def _load_report_history(self):
        self.hist_list.clear()
        if not os.path.exists(REPORTS_DIR):
            return
        files = sorted(
            [f for f in os.listdir(REPORTS_DIR) if f.endswith('.html')],
            reverse=True
        )
        for f in files:
            self.hist_list.addItem(f)

    def open_report(self, item):
        filepath = os.path.join(REPORTS_DIR, item.text())
        if os.path.exists(filepath):
            webbrowser.open(filepath)

    def set_data(self, videos, analysis_result):
        self.current_videos = videos
        self.analysis_result = analysis_result

    def _on_error(self, msg):
        self.comp_btn.setEnabled(True)
        self.prog_bar.setValue(0)
        self.prog_label.setText("오류")
        QMessageBox.critical(self, "오류", f"오류 발생:\n{msg}")

    def _on_progress(self, value, msg):
        self.prog_bar.setValue(value)
        self.prog_label.setText(msg)

    def reload_settings(self):
        self.settings = load_settings()


# ─────────────────────────────────────────────────────────────────────────────
# 메인 윈도우
# ─────────────────────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        self.setWindowTitle("ShortsExplorer — 쇼츠 주제 탐색기")
        self.setMinimumSize(1100, 750)

        self._build_menu()
        self._build_tabs()
        self._connect_tabs()

    def _build_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("파일")
        settings_action = QAction("⚙️ 설정", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self.open_settings)
        file_menu.addAction(settings_action)
        file_menu.addSeparator()
        quit_action = QAction("종료", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        help_menu = menubar.addMenu("도움말")
        about_action = QAction("ShortsExplorer 정보", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def _build_tabs(self):
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.search_tab = SearchTab(self)
        self.analysis_tab = AnalysisTab(self)
        self.topic_tab = TopicTab(self)
        self.report_tab = ReportTab(self)

        self.tabs.addTab(self.search_tab, "🔍 검색")
        self.tabs.addTab(self.analysis_tab, "📊 분석")
        self.tabs.addTab(self.topic_tab, "💡 주제 추천")
        self.tabs.addTab(self.report_tab, "📋 리포트")

    def _connect_tabs(self):
        # 검색 결과 → 분석/리포트 탭으로 전달
        self.search_tab.videos_updated.connect(self._on_videos_updated)
        # 분석 완료 → 주제/리포트 탭으로 전달
        self.analysis_tab.worker  # reference

    def _on_videos_updated(self, videos):
        self.report_tab.set_data(videos, {})

    def switch_to_analysis(self, videos):
        self.analysis_tab.set_videos(videos)
        self.tabs.setCurrentIndex(1)

    def open_settings(self):
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec_() == QDialog.Accepted:
            self.settings = dlg.get_settings()
            save_settings(self.settings)
            # 모든 탭 설정 갱신
            self.search_tab.reload_settings()
            self.analysis_tab.reload_settings()
            self.topic_tab.reload_settings()
            self.report_tab.reload_settings()
            QMessageBox.information(self, "저장 완료", "설정이 저장되었습니다.")

    def show_about(self):
        QMessageBox.about(
            self,
            "ShortsExplorer 정보",
            "ShortsExplorer — 쇼츠 주제 탐색기\n\n"
            "버전: 1.0.0\n"
            "영상 제작 기능 없음. 주제 탐색에만 집중.\n\n"
            "필요 패키지:\n"
            "  pip install PyQt5 requests yt-dlp matplotlib\n\n"
            "MIT License"
        )

    def closeEvent(self, event):
        event.accept()


# ─────────────────────────────────────────────────────────────────────────────
# 엔트리포인트
# ─────────────────────────────────────────────────────────────────────────────
def main():
    # settings.json 없으면 생성
    if not os.path.exists(SETTINGS_PATH):
        save_settings(DEFAULT_SETTINGS)

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # 다크 팔레트
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(26, 26, 46))
    palette.setColor(QPalette.WindowText, QColor(238, 238, 238))
    palette.setColor(QPalette.Base, QColor(22, 33, 62))
    palette.setColor(QPalette.AlternateBase, QColor(15, 52, 96))
    palette.setColor(QPalette.ToolTipBase, QColor(26, 26, 46))
    palette.setColor(QPalette.ToolTipText, QColor(238, 238, 238))
    palette.setColor(QPalette.Text, QColor(238, 238, 238))
    palette.setColor(QPalette.Button, QColor(22, 33, 62))
    palette.setColor(QPalette.ButtonText, QColor(238, 238, 238))
    palette.setColor(QPalette.BrightText, QColor(233, 69, 96))
    palette.setColor(QPalette.Link, QColor(233, 69, 96))
    palette.setColor(QPalette.Highlight, QColor(233, 69, 96))
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)

    window = MainWindow()
    window.show()

    # API 키 미설정 시 안내
    settings = load_settings()
    if not settings.get('youtube_api_key'):
        QTimer.singleShot(500, lambda: QMessageBox.information(
            window,
            "시작 안내",
            "YouTube API 키가 설정되지 않았습니다.\n\n"
            "메뉴 > 파일 > 설정 (Ctrl+,)에서\n"
            "API 키를 입력하면 검색 기능을 사용할 수 있습니다.\n\n"
            "API 키 발급:\n"
            "• YouTube: https://console.cloud.google.com/\n"
            "• DeepSeek: https://platform.deepseek.com/"
        ))

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
