# ShortsExplorer — 쇼츠 주제 탐색기

## 설치
```
pip install PyQt5 requests yt-dlp matplotlib
```

## API 키 발급
- YouTube Data API v3: https://console.cloud.google.com/
  1. 프로젝트 생성 → API 및 서비스 → YouTube Data API v3 활성화
  2. 사용자 인증 정보 → API 키 생성
- DeepSeek API: https://platform.deepseek.com/
  1. 회원가입 → API Keys → Create API Key

## 실행
```
python shorts_explorer.py
```

## 빌드 (Windows .exe)
```
pip install pyinstaller
pyinstaller --onefile --windowed --name ShortsExplorer shorts_explorer.py
# dist/ShortsExplorer.exe 생성됨
```

## 저작권
MIT License. YouTube Data API, DeepSeek API 각각의 이용약관을 준수하세요.
