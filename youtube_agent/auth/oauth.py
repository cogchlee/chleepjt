"""
auth/oauth.py
=============
YouTube Data API v3 - OAuth 2.0 인증 모듈
- token.json 자동 로드/저장
- Access Token 만료 시 자동 Refresh
- 최초 인증: 헤드리스 서버(Oracle Cloud)에 최적화된 OOB(Out-Of-Band) 플로우
- Scope: youtube.force-ssl (댓글 게시 + 읽기 포함)
"""

import json
import sys
import time
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# 필요한 OAuth 스코프 (댓글 게시를 위해 force-ssl 필요)
SCOPES = [
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtube.readonly",
]

_MAX_RETRY = 3
_RETRY_DELAY = 2  # seconds


class YouTubeAuthManager:
    """
    YouTube OAuth 2.0 인증 및 token.json 생명주기 관리.

    사용 예:
        auth_mgr = YouTubeAuthManager(
            client_id="...",
            client_secret="...",
            token_path="./data/token.json",
            redirect_uri="urn:ietf:wg:oauth:2.0:oob",
        )
        youtube_client = auth_mgr.get_youtube_client()
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        token_path: str | Path,
        redirect_uri: str = "urn:ietf:wg:oauth:2.0:oob",
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_path = Path(token_path)
        self.redirect_uri = redirect_uri
        self._credentials: Optional[Credentials] = None

    # ──────────────────────────────────────────────
    # 공개 인터페이스
    # ──────────────────────────────────────────────

    def get_credentials(self) -> Credentials:
        """
        유효한 Credentials 객체를 반환한다.
        - token.json 존재 시: 로드 후 만료면 자동 refresh
        - token.json 없을 시: OOB 인증 플로우 진행
        """
        if self._credentials and self._credentials.valid:
            return self._credentials

        creds = self._load_token()

        if creds and creds.expired and creds.refresh_token:
            creds = self._refresh_token(creds)
        elif not creds or not creds.valid:
            creds = self._run_oob_flow()

        self._credentials = creds
        self._save_token(creds)
        return creds

    def get_youtube_client(self, version: str = "v3"):
        """
        인증된 YouTube API 클라이언트를 반환한다.
        네트워크 오류 시 최대 3회 재시도.
        """
        creds = self.get_credentials()
        for attempt in range(1, _MAX_RETRY + 1):
            try:
                client = build("youtube", version, credentials=creds, cache_discovery=False)
                return client
            except HttpError as e:
                if e.resp.status in (401, 403):
                    # 토큰 문제: 강제 재인증
                    print(f"[AUTH] HTTP {e.resp.status} — 토큰 재인증 시도...")
                    self._credentials = None
                    self.token_path.unlink(missing_ok=True)
                    creds = self.get_credentials()
                else:
                    if attempt == _MAX_RETRY:
                        raise
                    print(f"[AUTH] HTTP {e.resp.status} — {attempt}회 재시도 중...")
                    time.sleep(_RETRY_DELAY * attempt)
            except Exception as e:
                if attempt == _MAX_RETRY:
                    raise
                print(f"[AUTH] 연결 오류({e}) — {attempt}회 재시도 중...")
                time.sleep(_RETRY_DELAY * attempt)

    def revoke_and_delete_token(self) -> None:
        """토큰을 취소하고 token.json을 삭제한다 (재인증 강제)."""
        creds = self._load_token()
        if creds and creds.token:
            try:
                import requests
                requests.post(
                    "https://oauth2.googleapis.com/revoke",
                    params={"token": creds.token},
                    timeout=10,
                )
                print("[AUTH] 토큰 취소 완료.")
            except Exception as e:
                print(f"[AUTH] 토큰 취소 중 오류 (무시): {e}")
        self.token_path.unlink(missing_ok=True)
        self._credentials = None
        print("[AUTH] token.json 삭제 완료.")

    # ──────────────────────────────────────────────
    # 내부 메서드
    # ──────────────────────────────────────────────

    def _load_token(self) -> Optional[Credentials]:
        """token.json에서 Credentials를 로드한다."""
        if not self.token_path.exists():
            return None
        try:
            data = json.loads(self.token_path.read_text(encoding="utf-8"))
            creds = Credentials(
                token=data.get("token"),
                refresh_token=data.get("refresh_token"),
                token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
                client_id=self.client_id,
                client_secret=self.client_secret,
                scopes=data.get("scopes", SCOPES),
            )
            return creds
        except (json.JSONDecodeError, KeyError) as e:
            print(f"[AUTH] token.json 로드 실패 ({e}). 재인증이 필요합니다.")
            return None

    def _save_token(self, creds: Credentials) -> None:
        """Credentials를 token.json에 저장한다."""
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        token_data = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": list(creds.scopes) if creds.scopes else SCOPES,
        }
        self.token_path.write_text(
            json.dumps(token_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        # 보안: 파일 권한 설정 (Linux/Oracle Cloud)
        try:
            import stat
            self.token_path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 600
        except (AttributeError, NotImplementedError):
            pass  # Windows에서는 무시

    def _refresh_token(self, creds: Credentials) -> Credentials:
        """만료된 Access Token을 Refresh Token으로 갱신한다."""
        print("[AUTH] Access Token 갱신 중...")
        for attempt in range(1, _MAX_RETRY + 1):
            try:
                creds.refresh(Request())
                print("[AUTH] ✅ Token 갱신 완료.")
                return creds
            except Exception as e:
                if attempt == _MAX_RETRY:
                    print(f"[AUTH] ❌ Token 갱신 최종 실패: {e}")
                    print("[AUTH] Refresh Token이 만료됐을 수 있습니다. 재인증을 진행합니다.")
                    return self._run_oob_flow()
                print(f"[AUTH] Token 갱신 실패 ({e}). {attempt}회 재시도...")
                time.sleep(_RETRY_DELAY * attempt)

    def _run_oob_flow(self) -> Credentials:
        """
        OOB(Out-Of-Band) 인증 플로우 - 헤드리스 서버(Oracle Cloud) 환경 지원.
        사용자가 URL에 접속해 코드를 복사 후 터미널에 붙여넣는 방식.
        """
        client_config = {
            "installed": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uris": [self.redirect_uri],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }

        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        flow.redirect_uri = self.redirect_uri

        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",  # Refresh Token 재발급 보장
        )

        print("\n" + "=" * 60)
        print("  YouTube OAuth 2.0 인증이 필요합니다.")
        print("=" * 60)
        print("  아래 URL을 브라우저에서 열고 Google 계정으로 로그인 후,")
        print("  표시되는 인증 코드를 복사하여 아래에 붙여넣으세요.\n")
        print(f"  {auth_url}\n")
        print("=" * 60)

        code = input("  인증 코드 입력: ").strip()
        flow.fetch_token(code=code)
        print("[AUTH] ✅ 인증 완료. token.json에 저장됩니다.")
        return flow.credentials


# ── 직접 실행 시 인증 테스트 ──
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import config

    print("YouTube OAuth 2.0 인증 테스트 시작...\n")
    auth_mgr = YouTubeAuthManager(
        client_id=config.GOOGLE_CLIENT_ID,
        client_secret=config.GOOGLE_CLIENT_SECRET,
        token_path=config.TOKEN_PATH,
        redirect_uri=config.GOOGLE_REDIRECT_URI,
    )

    try:
        yt = auth_mgr.get_youtube_client()
        # 인증 확인: 내 채널 정보 조회
        response = yt.channels().list(part="snippet", mine=True).execute()
        channel = response["items"][0]["snippet"]
        print(f"✅ 인증 성공!")
        print(f"   채널명: {channel['title']}")
        print(f"   채널 ID: {response['items'][0]['id']}")
        print(f"   token.json 저장 경로: {config.TOKEN_PATH.resolve()}")
    except HttpError as e:
        print(f"❌ API 오류: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 예외 발생: {e}")
        sys.exit(1)
