# Oracle Cloud Instance Setup & Management Guide
> **OC 인스턴스 24시간 자동화 봇 배포 및 운영 가이드**

이 가이드는 클라우드 인스턴스(Oracle Cloud, AWS 등)에 **Mailing System** 및 **Upbit Auto Trading Bot**을 한 번에 배포하고, 서버 재부팅에도 무관하게 24시간 안정적으로 구동하기 위한 통합 절차입니다.

---

## 1. Accessing Instance from Local (로컬 PC에서 인스턴스 접속)

서버에 접속하기 위한 첫 번째 단계입니다.

```bash
# 1. SSH 키 파일 권한 수정 (보안상 필수)
chmod 400 your_key_name.key

# 2. 서버 접속
ssh -i your_key_name.key ubuntu@<인스턴스_공용_IP_주소>
```

---

## 2. Server Environment Setup (서버 환경 설정 - 최초 1회)

서버 운영에 필요한 필수 프로그램들을 설치합니다.

```bash
# 3. 패키지 목록 업데이트 및 필수 도구 설치
sudo apt update && sudo apt upgrade -y
sudo apt install python3-pip python3-venv git nodejs npm -y

# 4. PM2 설치 (프로세스 관리를 위한 전域 설치)
sudo npm install -g pm2
```

---

## 3. Project Deployment & Setting (프로젝트 통합 배포 및 세팅)

GitHub에서 코드를 가져오고 두 프로젝트(메일링, 자동매매)를 위한 공통 실행 환경(Virtual Environment)을 구축합니다.

```bash
# 5. 코드 가져오기
git clone https://github.com/cogchlee/chleepjt.git
cd chleepjt

# 6. 최상위 디렉토리에서 통합 가상환경(venv) 생성 및 활성화
python3 -m venv venv
source venv/bin/activate

# 7. 프로젝트별 라이브러리 정상 설치
# 7-1. pythonMailing 패키지 설치
pip install -r pythonMailing/requirements.txt
# 7-2. tradeProject 패키지 설치
pip install -r tradeProject/requirements.txt

# 8. .env 파일 생성 및 설정 (보안 정보 직접 입력)
# (1) 메일링 봇용 환경 변수 세팅
nano pythonMailing/.env

# (2) 자동 매매 봇용 환경 변수 세팅
nano tradeProject/.env
```
*(nano 에디터에서는 단축키 `Ctrl+O` 후 `Enter`로 저장, `Ctrl+X`로 종료합니다)*

---

## 4. Persistent Execution with PM2 (프로젝트별 분리 무중단 실행)

서버의 전역(Global) 파이썬이 아닌 **가상환경(venv)에 설치된 파이썬**을 명시적으로 지정하여 실행해야 `ModuleNotFoundError`를 방지할 수 있습니다.

```bash
# ---------- 필수: chleepjt 폴더 경로에서 실행 ----------

# 9-1. Mailing System 실행 등록 (-u: 실시간 로그 버퍼링 방지용)
pm2 start ./venv/bin/python --name "MailingSystem" -- -u pythonMailing/main.py

# 9-2. Upbit Auto Trading Bot 실행 등록
pm2 start ./venv/bin/python --name "TradeSys" -- -u tradeProject/main.py
```

### [중요] 03. YouTube Personal Agent (autoComment)
이 시스템은 Gemini Pro를 활용하여 타겟 유튜브 채널의 콘텐츠를 분석하고, 사용자의 정체성이 담긴 댓글 초안을 생성한 뒤 텔레그램을 통해 승인을 받아 자동 게시하는 에이전트입니다.

`chleepjt` 디렉토리 최상위 경로에서 동일한 가상환경(`venv`)을 사용하여 동작 기반을 세팅할 예정입니다 (개발 진행에 따라 안내 업데이트).
```bash
# 추후 봇 백그라운드 구동 명령어 배치 예정
# pm2 start ./venv/bin/python --name "AutoComment" -- autoComment/main.py
```

---

## 5. PM2 관리 명령어 요약시 자동 시작 시스템(Startup Hook) 설정
pm2 startup
# (중요: 위 명령어 입력 시 터미널에 출력되는 'sudo env ...' 로 시작하는 문장을 복사 후 그대로 다시 실행해야 합니다)

# 11. 현재 PM2에 등록된 프로세스 목록 영구 저장
pm2 save

### 📋 PM2 Management Commands (유용한 관리 명령어)

| Command                              | Description                         |
| ------------------------------------ | ----------------------------------- |
| `pm2 status`                         | 현재 실행 중인 모든 프로세스 상태 확인   |
| `pm2 logs MailingSystem`             | 메일링 봇 실시간 로그 확인                    |
| `pm2 logs TradeSys`                  | 거래 봇 실시간 로그 확인 (매수/매도 내역 등)  |
| `pm2 logs --lines 100`               | 전체 앱의 최근 100줄 로그 보기                 |
| `pm2 stop TradeSys`                  | 특정 프로세스 일시 중지                  |
| `pm2 restart all`                    | 등록된 모든 프로세스 재시작 (소스 업데이트 시) |
| `pm2 delete TradeSys`                | PM2 실행 목록에서 프로세스 완전 삭제          |

---

## 5. Updating Code (코드 업데이트 시 반영 절차)

로컬에서 수정한 내용을 GitHub에 푸시한 뒤 서버에 반영하는 절차입니다. `chleepjt` 루트 경로에서 다시 진행하세요.

```bash
# 12. 최신 코드 가져오기 (만약 꼬였을 경우 git stash 후 pull)
cd ~/chleepjt
git pull

# 13. 만약 requirements가 변경되었다면 패키지 재설치
source venv/bin/activate
pip install -r tradeProject/requirements.txt  # (예시)

# 14. 프로세스 재시작으로 수정 내용 반영
pm2 restart all
```

---

> [!TIP]
> **서버 재부팅 튜토리얼 점검**
> 서버를 처음 설정 후 테스트 삼아 `sudo reboot`을 한 번 실행해 보세요.
> 서버 재접속 후 `pm2 status`를 쳤을 때 두 봇이 모두 **'online'** 상태라면 세팅이 완벽히 성공한 것입니다! (Step 10, 11번의 자동화 설정)
