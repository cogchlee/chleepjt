# AI News Automated Mailing System / 자동화된 AI 뉴스 메일링 시스템

이 시스템은 AI 에이전트, 어시스턴트, 머신러닝, 컴퓨터 비전 관련 최신 뉴스와 논문을 자동으로 수집하여 정해진 스케줄에 맞춰 이메일로 발송합니다.

---

## 📋 목차
- [주요 구성 요소](#주요-구성-요소)
- [설치 및 실행](#설치-및-실행)
- [개선 사항](#개선-사항)
- [로깅 및 모니터링](#로깅-및-모니터링)
- [테스트](#테스트)
- [문제 해결](#문제-해결)

---

## 주요 구성 요소

### Configuration (설정)
#### `config.py` & `.env`
- SMTP 및 이메일 주소 등 민감한 정보를 환경 변수로 관리합니다.
- **자동 설정 검증**: 필수 설정값 누락 시 import 시점에 경고 메시지 출력
- **로깅 설정**: `LOG_LEVEL` 환경 변수로 로깅 레벨 조절 가능

```python
# 필수 환경 변수
SENDER_EMAIL          # 발송자 이메일
SENDER_PASSWORD       # 발송자 비밀번호
RECEIVER_EMAIL        # 수신자 이메일
FORWARD_EMAIL         # (선택) 전달 주소

# 선택 환경 변수
LOG_LEVEL            # "DEBUG", "INFO", "WARNING", "ERROR" (기본값: INFO)
SCHEDULE_TYPE        # "twice_daily" 또는 "10m" 등 (기본값: twice_daily)
```

### News Fetching (뉴스 수집)
#### `news_fetcher.py`
**주요 기능:**
- ✅ 4가지 주제의 Google News RSS 피드에서 뉴스 추출
  - AI Agent, AI Tool, AI Assistant
  - Machine Learning Articles
  - Image Processing, Computer Vision Articles
  - AI, ML, CV 관련 Research Papers
  
- ✅ 주제당 X개씩 추출 (설정 가능)
- ✅ 제목, 링크, 발행일, 핵심 요약 추출
- ✅ **중복 방지**: `sent_links.json`으로 이미 발송한 뉴스 추적
- ✅ **URL 유효성 검사**: Timeout/Connection 에러 처리
- ✅ **자동 번역**: 영문 → 한글 (Google Translate API)
- ✅ **기사 전문 추출**: newspaper3k를 사용한 실제 콘텐츠 파싱
- ✅ **강화된 에러 처리**: 네트워크 에러, 타임아웃, 파싱 오류 등

**개선된 에러 처리:**
```python
# 네트워크 타임아웃 처리
requests.exceptions.Timeout

# 연결 에러 처리  
requests.exceptions.ConnectionError

# JSON 파싱 에러 처리
json.JSONDecodeError

# 피드 파싱 에러 처리
feedparser 예외 처리
```

### Email Sending (이메일 발송)
#### `email_sender.py`
- 추출된 뉴스를 깔끔한 HTML 형식으로 포맷팅
- 다크 테마 적용 (전문적인 외관)
- 주제별로 그룹화된 뉴스 표시
- 영문 / 한글 이중 제목 및 요약
- 수신자 및 선택적 전달 주소로 발송
- **강화된 SMTP 예외 처리**: 인증 실패, SMTP 에러 상세 로깅

### Main Orchestration (메인 오케스트레이션)
#### `main.py`
- 데이터 수집과 메일 발송을 통합하는 진입점
- 스케줄링 기능 (APScheduler 기반)
- **상세한 로깅**: 작업 시작/완료 시간, 처리 결과 기록
- **예외 처리**: 작업 실패 시 스택 트레이스 기록

---

## 설치 및 실행

### 1️⃣ 사전 요구사항
Python 3.8+ 설치 필수

### 2️⃣ 의존성 설치
```bash
pip install -r requirements.txt
```

### 3️⃣ 환경 설정
프로젝트 루트 디렉토리에 `.env` 파일 생성:

```env
# Gmail SMTP 설정 (Gmail App Password 필요)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your_email@gmail.com
SENDER_PASSWORD=your_app_password

# 수신자 설정
RECEIVER_EMAIL=receiver@gmail.com
FORWARD_EMAIL=optional_forwarding@example.com

# 스케줄 타입
SCHEDULE_TYPE=twice_daily  # 또는 "10m", "30m" 등

# 로깅 레벨 (선택사항)
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

**Gmail App Password 생성 방법:**
1. Google 계정의 보안 설정 접속
2. "앱 비밀번호" 활성화
3. 생성된 16자리 비밀번호를 SENDER_PASSWORD에 입력

### 4️⃣ 실행
```bash
python main.py
```

실행 시:
- 즉시 첫 번째 뉴스 발송
- 설정된 스케줄에 따라 반복 실행
- `Ctrl+C`로 중단

---

## 개선 사항

### ✅ 완료된 개선 사항

#### 1. **강화된 에러 처리 (Error Handling)**
- 모든 주요 함수에 try-except 블록 추가
- 네트워크 에러, 타임아웃, 파싱 에러 분류 처리
- SMTP 인증 실패 시 명확한 에러 메시지

#### 2. **상세한 로깅 (Logging)**
- logging 모듈 통합
- 파일 기반 로깅: `ai_news_mailing.log`
- 콘솔 + 파일 동시 출력
- 로깅 레벨 조절 가능 (환경 변수: LOG_LEVEL)

**예시:**
```
2026-02-26 10:30:45,123 - news_fetcher - INFO - Fetching news for topic: AI Agent, AI Tool, AI Assistant
2026-02-26 10:30:45,456 - news_fetcher - DEBUG - Checking link validity: https://example.com
2026-02-26 10:30:46,789 - email_sender - INFO - Sending email to receiver@gmail.com
```

#### 3. **설정 검증 (Configuration Validation)**
- config.py에서 필수 설정값 자동 검증
- 누락된 설정값 시 명확한 에러 메시지
- import 시점에 검증 실행

#### 4. **유닛 테스트 (Unit Tests)**
- `test_news_fetcher.py`: 뉴스 수집 단위 테스트
- `test_email_sender.py`: 이메일 발송 단위 테스트
- Mock 객체를 사용한 독립적인 테스트

---

## 로깅 및 모니터링

### 로그 파일 위치
`pythonMailing/ai_news_mailing.log`

### 로그 레벨별 정보

| 레벨 | 용도 | 예시 |
|------|------|------|
| DEBUG | 상세 디버깅 정보 | 링크 유효성 검사 결과 |
| INFO | 일반 실행 정보 | 뉴스 수집 완료, 이메일 발송 성공 |
| WARNING | 경고 메시지 | 설정값 누락, 번역 실패 |
| ERROR | 에러 메시지 | 네트워크 오류, SMTP 실패 |

### 로깅 레벨 변경
```bash
# 디버깅 모드
LOG_LEVEL=DEBUG python main.py

# 일반 모드 (기본)
LOG_LEVEL=INFO python main.py
```

---

## 테스트

### 모든 테스트 실행
```bash
python -m unittest discover -s . -p "test_*.py"
```

### 특정 테스트 실행
```bash
# news_fetcher 테스트만
python -m unittest test_news_fetcher

# email_sender 테스트만
python -m unittest test_email_sender

# 특정 테스트 메서드
python -m unittest test_news_fetcher.TestSentLinksHandling.test_get_sent_links_empty
```

### 테스트 커버리지
```bash
pip install coverage
coverage run -m unittest discover
coverage report
coverage html  # HTML 리포트 생성
```

---

## 문제 해결

### 1. 이메일 발송 실패

**오류**: `SMTP authentication failed`

**해결방법:**
- SENDER_EMAIL과 SENDER_PASSWORD 확인
- Gmail 사용 시 "App Password" (16자 비밀번호) 사용 필수
- 2단계 인증 활성화 필요

### 2. 뉴스 수집 실패

**오류**: `Failed to fetch feed`

**해결방법:**
- 인터넷 연결 확인
- RSS 피드 URL 유효성 확인
- 로그 파일에서 상세 에러 메시지 확인

### 3. 번역 실패

**오류**: `Translation service connection error`

**해결방법:**
- 인터넷 연결 확인
- Google Translate API 접근성 확인
- 로그에서 DetailError 메시지 확인

### 4. 로그 파일이 없음

파일이 자동 생성되지 않으면 다음 확인:
```bash
# 쓰기 권한 확인
ls -la pythonMailing/

# 필요시 권한 변경
chmod 755 pythonMailing/
```

---

## 의존성 패키지 상세

| 패키지 | 버전 | 용도 |
|--------|------|------|
| feedparser | 최신 | RSS 피드 파싱 |
| python-dotenv | 최신 | 환경 변수 관리 |
| schedule | 최신 | 작업 스케줄링 |
| beautifulsoup4 | 최신 | HTML 파싱 |
| googletrans | 4.0.0-rc1 | 자동 번역 |
| requests | 최신 | HTTP 요청 |
| newspaper3k | 최신 | 기사 콘텐츠 추출 |
| googlenewsdecoder | 최신 | Google News URL 디코딩 |
| lxml_html_clean | 최신 | HTML 정제 |

---

## 버전 정보

- **버전**: 2.0.0 (개선 완료)
- **마지막 업데이트**: 2026-02-26
- **주요 변경사항**: 
  - Logging 통합
  - Error Handling 강화
  - Configuration Validation 추가
  - Unit Tests 추가
