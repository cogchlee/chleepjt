# Oracle Cloud Instance Setup & Management Guide
> **OC 인스턴스 설정 및 관리 가이드**

이 가이드는 클라우드 인스턴스(Oracle Cloud 등)에 Mailing System을 배포하고 24시간 안정적으로 운영하기 위한 절차를 설명합니다.

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

# 4. PM2 설치 (프로세스 관리를 위한 전역 설치)
sudo npm install -g pm2
```

---

## 3. Project Deployment & Setting (프로젝트 배포 및 세팅)

GitHub에서 코드를 가져오고 실행 환경을 구축합니다.

```bash
# 5. 코드 가져오기
git clone https://github.com/cogchlee/chleepjt.git
cd chleepjt/pythonMailing

# 6. 가상환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate

# 7. 라이브러리 설치
pip install -r requirements.txt

# 8. .env 파일 생성 및 설정 (보안 정보 직접 입력)
nano .env
```

---

## 4. Persistent Execution with PM2 (PM2를 이용한 무중단 실행 및 관리)

프로그램을 24시간 중단 없이 실행하고 관리하기 위한 핵심 명령어입니다.

```bash
# 9. 실시간 로그 출력을 위해 버퍼링 없이(-u) 프로세스 실행
pm2 start python3 --name "MailingSystem" -- -u main.py

# 10. 서버 재부팅 시 자동 시작 설정
pm2 startup
# (중요: 터미널에 출력된 'sudo env...' 문장을 그대로 복사해서 실행해야 합니다)

pm2 save
```

### 📋 PM2 Management Commands (관리 명령어)

| Command                              | Description                         |
| ------------------------------------ | ----------------------------------- |
| `pm2 status`                         | 현재 실행 중인 프로세스 상태 확인   |
| `pm2 logs MailingSystem`             | 실시간 로그 확인                    |
| `pm2 logs MailingSystem --lines 100` | 최근 로그 100줄 확인                |
| `pm2 stop MailingSystem`             | 프로세스 일시 중지                  |
| `pm2 restart MailingSystem`          | 프로세스 재시작 (소스 수정 후 반영) |
| `pm2 delete MailingSystem`           | PM2 목록에서 프로세스 삭제          |

---

## 5. Updating Code (코드 업데이트 시 반영 절차)

로컬에서 수정 후 GitHub에 푸시된 내용을 서버에 반영할 때 사용합니다.

```bash
# 11. 최신 코드 반영
git pull
pm2 restart MailingSystem
```

---

> [!TIP]
> **서버 재부팅 후 자동 실행 확인**
> 서버를 재부팅했을 때 프로그램이 자동으로 실행되지 않는다면, **Step 10 (`pm2 save`)**이 정상적으로 수행되었는지 다시 확인해 보세요!