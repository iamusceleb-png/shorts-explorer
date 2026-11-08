# 🎯 ShortsExplorer — 쇼츠 주제 탐색기

유튜브 쇼츠에서 터지는 주제를 찾아주는 분석 전용 도구입니다.

---

## ⬇️ 다운로드

[![다운로드](https://img.shields.io/badge/⬇%20Download-ShortsExplorer.exe-brightgreen?style=for-the-badge)](https://github.com/iamusceleb-png/shorts-explorer/releases/latest)

> Windows 10/11 64bit / Python 설치 불필요 / 더블클릭 실행

---

## 🚀 시작하는 법

### 1단계 — 프로그램 실행
`ShortsExplorer.exe` 더블클릭

### 2단계 — API 키 2개 입력
상단 메뉴 **파일 → ⚙️ 설정** 클릭 후 아래 두 키를 입력하고 확인

---

## 🔑 API 키 발급 방법

### YouTube API 키 (무료)

1. [console.cloud.google.com](https://console.cloud.google.com) 접속 (구글 계정으로 로그인)
2. 상단 **"프로젝트 선택"** → **새 프로젝트** → 이름 아무거나 입력 → **만들기**
3. 왼쪽 메뉴 **API 및 서비스** → **라이브러리**
4. 검색창에 `YouTube Data API v3` 검색 → 클릭 → **사용 설정**
5. 왼쪽 메뉴 **사용자 인증 정보** → 상단 **+ 사용자 인증 정보 만들기** → **API 키**
6. 생성된 키 복사 → 프로그램 설정에 붙여넣기

---

### DeepSeek API 키 (사실상 무료)

1. [platform.deepseek.com](https://platform.deepseek.com) 접속 → 회원가입
2. 로그인 후 왼쪽 메뉴 **API Keys** 클릭
3. **Create new secret key** → 키 복사 → 프로그램 설정에 붙여넣기

> 💡 가입 시 무료 크레딧 제공. 쇼츠 분석 1회 = 약 1~2원 수준으로 사실상 무료입니다.

---

## ✨ 주요 기능

| 탭 | 기능 |
|---|---|
| 🔍 검색 | 키워드/채널 검색, VS비율(조회수÷구독자) 자동 정렬 |
| 📊 분석 | 훅유형·제목패턴·댓글반응 분포, 핵심 키워드 Top20 |
| 💡 주제 추천 | AI 리메이크 주제 5개, 해외→한국 주제 변환 |
| 📋 리포트 | 즐겨찾기·메모, 경쟁채널 분석, HTML 리포트 저장 |

---

## ⌨️ 단축키

| 키 | 동작 |
|---|---|
| Ctrl + , | 설정 열기 |
| F5 | 검색 새로고침 |
