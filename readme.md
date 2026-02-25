# AI News Automated Mailing System / 자동화된 AI 뉴스 메일링 시스템

This system fetches the latest targeted AI-related news (Agents, Assistants, Machine Learning) and sends them via email on a 10-minute schedule.
(이 시스템은 AI 에이전트, 어시스턴트, 머신러닝 관련 최신 뉴스와 논문을 10분마다 수집하여 이메일로 발송합니다.)

## Proposed Changes / 주요 구성 요소

### Configuration / 설정
#### `config.py` & `.env`
- Manages all sensitive credentials (SMTP, emails, forwarding) via environment variables.
- (SMTP 및 이메일 주소 등 민감한 정보를 환경 변수로 관리합니다.)

### News Fetching / 뉴스 수집
#### `news_fetcher.py`
- Fetches news from multiple specific RSS topics:
  1. AI Agent, Assistant, Tool
  2. Machine Learning Articles & Papers
- Extracts the title, link, published date, and a **core summary** for each item.
- (AI 에이전트 및 머신러닝 관련 RSS 피드에서 뉴스/논문의 제목, 링크, 날짜, 그리고 핵심 요약을 추출합니다.)

### Email Sending / 이메일 발송
#### `email_sender.py`
- Formats the fetched news and summaries into a clean HTML email structure.
- Sends the compiled HTML to the receiver and an optional forwarding address.
- (추출된 뉴스와 요약을 깔끔한 HTML 형식으로 구성하여 수신자 및 전달 주소로 발송합니다.)

### Main Orchestration / 전체 오케스트레이션
#### `main.py`
- Serves as the entry point.
- Combines the fetching and sending logic, scheduled to run every 10 minutes.
- (10분마다 데이터를 수집하고 메일을 발송하는 메인 스케줄러입니다.)

## Setup & Verification Plan / 설정 및 실행 계획

### 1. Requirements / 사전 요구사항
Install all Python dependencies:
```bash
pip install -r requirements.txt
```
(의존성 패키지를 설치하세요.)

### 2. Environment Variables / 환경 변수 설정
Create a `.env` file in the root directory:
(루트 디렉토리에 `.env` 파일을 만들고 자격 증명을 입력하세요.)
```env
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your_email@gmail.com
SENDER_PASSWORD=your_app_password
RECEIVER_EMAIL=your_email@gmail.com
FORWARD_EMAIL=other_email@example.com
```

### 3. Execution / 실행
Run the script to begin the 10-minute loop. It will execute an immediate fetch and send on startup.
(스크립트를 실행하면 즉시 메일을 한 번 보내고, 이후 10분마다 반복 실행됩니다.)
```bash
python main.py
```
