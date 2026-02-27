# Project Practice Page with AI Agent

> 🤖 AI Agent를 활용한 개인 프로젝트 실습 저장소입니다.

---

## 📋 Project Lists

| No. | Project                            | Language / Stack | Status   | Description                                  |
| --- | ---------------------------------- | ---------------- | -------- | -------------------------------------------- |
| 01  | [Mailing System](./pythonMailing/) | Python           | ✅ Active | AI & ML 뉴스 자동 수집 및 이메일 발송 시스템 |
| 02  | —                                  | —                | 🔜 예정   | —                                            |
| 03  | —                                  | —                | 🔜 예정   | —                                            |

---

## 📁 Repository Structure

```
AntiGravityPjt_01/
├── pythonMailing/          # 01. AI News Auto Mailing System
│   ├── main.py             #   진입점 (스케줄러)
│   ├── config.py           #   환경 변수 및 RSS 피드 설정
│   ├── news_fetcher.py     #   뉴스 수집 및 중요도 랭킹
│   ├── email_sender.py     #   HTML 이메일 생성 및 발송
│   ├── requirements.txt    #   Python 패키지 목록
│   └── readme.md           #   프로젝트 상세 설명
├── README.md               # 전체 저장소 소개 (현재 파일)
└── .gitignore
```

---

## 🚀 Quick Start

각 프로젝트의 상세 실행 방법은 해당 폴더의 `readme.md`를 참고하세요.

### 01. Mailing System
```bash
cd pythonMailing
pip install -r requirements.txt
# .env 파일 설정 후 실행
python main.py
```

---

## 🛠 Tech Stack

| Category      | Tools                                |
| ------------- | ------------------------------------ |
| Language      | Python 3.8+                          |
| News Source   | Google News RSS                      |
| Translation   | Google Translate API (`googletrans`) |
| Scheduling    | `schedule` library                   |
| Email         | SMTP (Gmail)                         |
| AI Agent Tool | Google Gemini (Antigravity)          |

---

## 📝 Convention

- 프로젝트 번호는 `01`, `02` 형식으로 순차 부여
- 각 프로젝트는 독립된 폴더로 관리
- 각 폴더 내 `readme.md` 필수 작성
- 민감 정보는 `.env` 파일로 관리 (`.gitignore` 처리)

---

## 📅 History

| Date       | Update                                    |
| ---------- | ----------------------------------------- |
| 2026-02-27 | 01. AI News Mailing System 초기 구현 완료 |
| 2026-02-27 | 저장소 초기 구성 및 README 작성           |