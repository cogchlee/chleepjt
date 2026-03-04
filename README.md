# Project Practice Page with AI Agent

> 🤖 A personal project practice repository using AI Agent.
> (AI Agent를 활용한 개인 프로젝트 실습 저장소입니다.)

---

## 📋 Project Lists

| No. | Project                               | Language / Stack | Status           | Description                                                                                                                          |
| --- | ------------------------------------- | ---------------- | ---------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| 01  | [Mailing System](./pythonMailing/)    | Python           | ✅ Active         | AI, ML, Education & Literacy News Auto Collection and Auth Mailing System (AI, ML, 교육/문해력 뉴스 자동 수집 및 이메일 발송 시스템) |
| 02  | [Upbit Auto Trading](./tradeProject/) | Python           | ✅ Active         | Upbit API Auto Trading Bot with Simulation Mode (업비트 가상자산 자동매매 및 모의투자 봇)                                            |
| 03  | —                                     | —                | 🔜 Planned (예정) | —                                                                                                                                    |

---

## 📁 Repository Structure (저장소 구조)

```
Project/
├── pythonMailing/          # 01. AI News Auto Mailing System
│   ├── main.py             #   Entry point with scheduler (진입점 / 스케줄러)
│   ├── config.py           #   Env vars & RSS feed settings (환경 변수 및 RSS 피드 설정)
│   ├── news_fetcher.py     #   News fetching & importance ranking (뉴스 수집 및 중요도 랭킹)
│   ├── email_sender.py     #   HTML email builder & sender (HTML 이메일 생성 및 발송)
│   ├── requirements.txt    #   Python package list (Python 패키지 목록)
│   ├── OC_guidance.md      #   Deployment & management guide (배포 및 관리 가이드)
│   └── readme.md           #   Project detail docs (프로젝트 상세 설명)
├── tradeProject/           # 02. Upbit Auto Trading System
│   ├── main.py             #   Trading bot main loop (자동매매 봇 메인 루프)
│   ├── test_simulate.py    #   Simulation logic test script (모의투자 테스트 스크립트)
│   ├── .env.example        #   Environment variables template (환경변수 템플릿)
│   └── README.md           #   Project detail docs (프로젝트 상세 설명)
├── README.md               # Repository overview (전체 저장소 소개 / 현재 파일)
└── .gitignore
```

---

## 🚀 Quick Start (빠른 시작)

For detailed instructions per project, refer to the `readme.md` in each folder.
(각 프로젝트의 상세 실행 방법은 해당 폴더의 `readme.md`를 참고하세요.)

### 01. Mailing System
```bash
cd pythonMailing
pip install -r requirements.txt
# Set up .env file before running (실행 전 .env 파일 설정 필요)
python main.py
```

### 02. Upbit Trading Bot
```bash
cd tradeProject
pip install pyupbit python-dotenv
# Set up .env file before running (실행 전 .env 파일 확인)
python main.py
```

---

## 🛠 Tech Stack (기술 스택)

### 01. Mailing System

| Category (분류)         | Tools                                |
| ----------------------- | ------------------------------------ |
| Language (언어)         | Python 3.8+                          |
| News Source (뉴스 소스) | Google News RSS                      |
| Translation (번역)      | Google Translate API (`googletrans`) |
| Scheduling (스케줄링)   | `schedule` library                   |
| Email (이메일)          | SMTP (Gmail)                         |
| AI Agent Tool           | Google Gemini (Antigravity)          |

### 02. Upbit Trading Bot

| Category (분류)       | Tools                                |
| --------------------- | ------------------------------------ |
| Language (언어)       | Python 3.8+                          |
| Exchange API (거래소) | Upbit Open API (`pyupbit`)           |
| Strategy (전략)       | Volatility Breakout + Moving Average |
| Configuration (설정)  | `python-dotenv`                      |

### 03. — *(TBD)*

---

## 📝 Convention (프로젝트 규칙)

- Project numbers are assigned sequentially in `01`, `02` format.
  (프로젝트 번호는 `01`, `02` 형식으로 순차 부여)
- Each project is managed in an independent folder.
  (각 프로젝트는 독립된 폴더로 관리)
- A `readme.md` is required in every project folder.
  (각 폴더 내 `readme.md` 필수 작성)
- Sensitive information is managed via `.env` files, excluded from Git.
  (민감 정보는 `.env` 파일로 관리하며 `.gitignore` 처리)