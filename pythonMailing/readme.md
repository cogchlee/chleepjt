# 🚀 프로젝트명: AI News Automated Mailing System

## 1. 프로젝트 목적 및 주요 기능
### 1.1 개발 목적
* **다중 카테고리 정보 집약**: AI 기술 동향(CAT1)과 유아 교육/문해력(CAT2) 뉴스를 자동 수집하여 정보 습득 효율성 극대화.
* **지능형 큐레이션**: 정보 과잉 시대에 중요도 기반 스코어링을 통해 고품질의 뉴스만 선별하여 개인 이메일로 전달.

### 1.2 주요 기능
* **독립적 다중 파이프라인**: CAT1(AI/ML)과 CAT2(Education)를 각각 독립적인 발송자/수신자 및 스케줄로 관리.
* **지능형 뉴스 랭킹**: 맞춤형 키워드 기반 스코어링 시스템을 통해 최상위 중요도 기사 우선 추출.
* **글로벌 뉴스 번역**: 영문 기사를 자동으로 감지하여 한글로 번역(Google Translate) 후 병기 발송.
* **세련된 UI/UX**: Toss 스타일의 다크 모드 HTML 포맷팅과 시그니처 블루 액센트를 적용한 고품질 메일 본문.

---

## 2. 뉴스 수집 소스 

### 2.1 Category 1: AI & ML
CAT1은 다음의 전문 매체 및 커뮤니티를 우선적으로 탐색하여 뉴스를 수집합니다.

1.  **[AI 타임스](https://www.aitimes.com/)**: 국내외 AI 전문 뉴스
2.  **[로봇신문](https://www.irobotnews.com/)**: 로봇 및 Physical AI 동향
3.  **[테크M](https://www.techm.kr/)**: IT 산업 및 빅테크 전략
4.  **[디지털데일리](https://www.ddaily.co.kr/)**: IT 인프라 및 엔터프라이즈 소식
5.  **[GeekNews (Hada)](https://news.hada.io/)**: 개발자 중심 기술 큐레이션
6.  **[PyTorch KR](https://pytorch.kr/)**: 파이토치 생태계 및 라이브러리 소식
7.  **[OKKY](https://okky.kr/)**: 국내 최대 개발자 커뮤니티
8.  **[TensorFlow Blog](https://tensorflow.blog/)**: 텐서플로우 관련 기술 포스트
9.  **그 외 Google 검색**: 위 소스 외 보완을 위한 키워드 기반 검색

### 2.2 Category 2: Education & Literacy
CAT2는 다음의 전문 매체 및 커뮤니티를 우선적으로 탐색하여 뉴스를 수집합니다.

1.  **[교육부](https://www.moe.go.kr/)**: 교육 정책 및 뉴스
2.  **[한국교육학술정보원](https://www.keris.or.kr/)**: 교육 정보 및 연구 자료
3.  **[EBS 교육뉴스](https://news.ebs.co.kr/)**: 교육 관련 뉴스
4.  **[한국교원단체총연합회](https://www.ktwu.or.kr/)**: 교원 관련 소식
5.  **[학부모뉴스24](https://www.parentsnews.co.kr/)**: 학부모 대상 교육 정보
6.  **[교육과정평가원](https://www.kice.re.kr/)**: 교육 과정 및 평가 정보
7.  **[한국교육개발원](https://www.kedi.re.kr/)**: 교육 연구 및 정책
8.  **[그 외 Google 검색**: 위 소스 외 보완을 위한 키워드 기반 검색

---

## 3. 설정 및 환경 구축 (Configuration)

### 3.1 상세 설정 모듈 (`config.py` & `.env`)
민감한 정보는 환경 변수로 관리하며, 시스템 시작 시 자동 검증을 수행합니다. 필수 설정값 누락 시 import 시점에 경고 메시지를 출력합니다.

| 카테고리         | 변수명                 | 설명                                                        |
| :--------------- | :--------------------- | :---------------------------------------------------------- |
| **공통**         | `LOG_LEVEL`            | "DEBUG", "INFO", "WARNING", "ERROR" (기본값: INFO)          |
| **CAT1 (AI/ML)** | `SENDER_EMAIL`         | 발송자 이메일 주소                                          |
|                  | `SENDER_PASSWORD`      | 발송자 비밀번호 (Gmail 앱 비밀번호)                         |
|                  | `RECEIVER_EMAIL`       | 수신자 이메일 주소                                          |
|                  | `FORWARD_EMAIL`        | (선택) 전달 주소 ("NONE" 혹은 한국 시간 주말에는 발송 생략) |
|                  | `SCHEDULE_TYPE`        | CAT1 실행 주기 (예: `once_daily`, `10m`, `30m`)             |
| **CAT2 (Edu)**   | `CAT2_SENDER_EMAIL`    | CAT2 전용 발송자 이메일 주소 (CAT1과 독립적으로 동작)       |
|                  | `CAT2_SENDER_PASSWORD` | CAT2 전용 발송자 비밀번호                           |
|                  | `CAT2_RECEIVER_EMAIL`  | CAT2 전용 수신자 이메일                             |
|                  | `CAT2_FORWARD_EMAIL`   | CAT2 전용 전달 주소                                 |
|                  | `CAT2_SCHEDULE_TYPE`   | CAT2 실행 주기 (기본값: `once_daily`)               |

### 3.2 환경 설정 (`.env` 파일 생성)
프로젝트 루트 디렉토리에 `.env` 파일을 생성하고 아래 내용을 입력합니다.

```env
# Gmail SMTP 설정 (Gmail App Password 필요)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your_email@gmail.com
SENDER_PASSWORD=your_app_password_16_digits

# 수신자 설정
RECEIVER_EMAIL=receiver@gmail.com
FORWARD_EMAIL=optional_forwarding@example.com

# 스케줄 타입 (once_daily, twice_daily, 또는 "10m", "30m" 등)
SCHEDULE_TYPE=once_daily
CAT2_SCHEDULE_TYPE=once_daily

# 로깅 레벨 (선택사항: DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO
```

### 3.3 Gmail 앱 비밀번호 생성 방법
1. **Google 계정 보안 설정** 접속
2. **"앱 비밀번호"** 검색 및 활성화 (2단계 인증 필요)
3. 앱 이름을 지정하고 생성된 **16자리 비밀번호**를 복사
4. `.env` 파일의 `SENDER_PASSWORD` (필요 시 `CAT2_SENDER_PASSWORD`)에 입력

---

## 4. 기술 스택 및 개발 환경
* **언어**: Python 3.8+
* **News Engine**: `feedparser`, `newspaper3k`, `googlenewsdecoder`
* **Translation**: `googletrans` (4.0.0-rc1)
* **Automation**: `schedule`
* **Mailing**: `smtplib`, `email.mime` (SMTP 기반)
* **Formatting**: `beautifulsoup4`, `lxml_html_clean`
* **Configuration**: `python-dotenv`

---

## 5. 구현 로직 (Implementation Logic)

### 5.1 뉴스 수집 및 스코어링 (News Fetching)
* **주제별 수집**: 주제당 설정된 최대 풀에서 키워드 가중치를 계산하여 기사 추출.
* **유효성 검사**: HTTPS 연결 확인 및 403 에러 발생 시 RSS 요약본으로 대체하는 Fallback 메커니즘.

### 5.2 중복 방지 시스템 (Deduplication)
* **트래커 운용**: `sent_links.json` 파일을 통해 이미 발송된 URL 기록.
* **주간 초기화**: 매주 일요일 자정에 트래커를 자동 초기화하여 신선도 유지.

### 5.3 이메일 렌더링 및 발송 (Email Rendering)
* **다크 모드 HTML**: 모서리가 둥근 컨테이너와 가독성 높은 폰트 설정.
* **이중 언어 지원**: 한/영 이중 제목 제공 및 원문 링크 직접 이동 기능 (본문 요약 제외로 피로도 최소화).
* **전달 로직**: 설정된 수신자 외에 전달 주소(`FORWARD_EMAIL`) 지원 (단, 주말 발송은 제외).

### 5.4 로깅 및 모니터링 (Logging)
* **상태 기록**: `ai_news_mailing.log`에 작업 시작, 완료, 처리 결과 및 에러 스택 트레이스 상세 기록.
* **레벨 제어**: 환경 변수(`LOG_LEVEL`)를 통해 DEBUG부터 ERROR까지 로깅 강도 조절 가능.

---

## 6. 운영 및 예외 처리 (Operations & Error Handling)

### 6.1 상세 스케줄링 및 자동화 정책
* **자유로운 실행 주기**: `once_daily`, `twice_daily` 또는 세밀한 분 단위(`10m`, `30m`) 스케줄링을 완벽하게 지원합니다.
* **주말 발송 스마트 제어**: 한국 시간(KST) 기준 주말(토/일)에는 설정된 전달 이메일(`FORWARD_EMAIL`) 발송을 자동으로 생략하여 주말 업무 방해를 줄입니다.
* **시작 전 자동 검증**: 시스템 구동 시 `config.py`에서 필수 환경 변수 누락 여부를 즉시 검사하여 오작동을 미연에 방지합니다.

### 6.2 안정성 및 보안 (Security & Resilience)
* **보안 강화**: SMTP App Password 규격을 강제하며 `.env`를 통해 민감 정보를 격리하여 소스 코드 유출 시에도 안전하게 보호합니다.
* **무중단 시스템(Fault Tolerance)**: 네트워크 타임아웃, 커넥션 에러, JSON 파싱 오류나 SMTP 인증 실패 등 외부 요인에 의한 에러 발생 시 시스템이 멈추지 않습니다. 상세 에러 로그만 기록한 뒤 다음 스케줄을 안정적으로 대기합니다.
* **투명한 로깅 시스템**: `ai_news_mailing.log` 파일에 작업 시작 및 완료 시간, 뉴스 수집 결과, 에러 스택 트레이스 등 모든 운영 과정이 투명하게 기록되어 손쉬운 디버깅을 제공합니다.

---

> **🔖 버전 정보 (Version Info)**  
> **버전**: 2.1.0  
> **마지막 업데이트**: 2026-03-31
