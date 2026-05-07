# 수기매체 자동화 (nonauto-media)

RTB House(APP/WEB), Buzzvil, BSA 데이터를 매일 오전 8시에 자동 수집하여 Google Sheets에 업로드합니다.

---

## 📁 파일 구조

```
nonauto-media/
├── .github/workflows/daily_crawl.yml  # 매일 08:00 KST 자동 실행
├── crawlers/
│   ├── rtbhouse.py    # RTB House APP/WEB 크롤러
│   └── buzzvil.py     # Buzzvil 크롤러
├── sheets/
│   └── uploader.py    # Google Sheets 업로드
├── config.json        # 정적 설정 (대시보드 URL, 시트 ID)
├── main.py            # 전체 실행 진입점
├── streamlit_app.py   # 수동 실행 / 설정 관리 UI
└── requirements.txt
```

---

## 🚀 초기 설정

### 1. GitHub Secrets 등록

레포 → Settings → Secrets and variables → Actions → New repository secret

| Secret 이름 | 값 |
|---|---|
| `RTBHOUSE_EMAIL` | RTB House 로그인 이메일 |
| `RTBHOUSE_PASSWORD` | RTB House 비밀번호 |
| `BUZZVIL_EMAIL` | Buzzvil 로그인 이메일 |
| `BUZZVIL_PASSWORD` | Buzzvil 비밀번호 |
| `GOOGLE_SERVICE_ACCOUNT` | service_account.json 파일 전체 내용 (텍스트) |

선택 환경변수:

| 이름 | 값 |
|---|---|
| `TARGET_DATE` | 수동 재처리 대상 날짜 (`YYYY-MM-DD`) |
| `ALLOW_PARTIAL_UPLOAD` | `1`이면 일부 매체 실패 시에도 Sheets 업로드 진행 |

### 2. Google Sheets 설정 시트 초기화

첫 실행 시 `설정` 시트가 자동 생성됩니다.  
초기값: BSA Mobile=920,000 / PC=460,000 / Buzzvil adgroup_id=55015

### 3. Streamlit Community Cloud 배포 (선택)

1. [share.streamlit.io](https://share.streamlit.io) → New app
2. 레포: `yjhwang-svg/nonauto-media` / Branch: `main` / File: `streamlit_app.py`
3. Advanced settings → Secrets 탭에 아래 추가:

```toml
GOOGLE_SERVICE_ACCOUNT = '{"type": "service_account", ...전체 JSON...}'
GITHUB_TOKEN = "ghp_xxxxxxxxxxxx"
GITHUB_REPO  = "yjhwang-svg/nonauto-media"
```

> `GITHUB_TOKEN`은 GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens에서 발급.  
> 권한: `Actions` (Read and write), `Contents` (Read)

---

## 📋 매월 해야 할 일

### Buzzvil adgroup_id 변경

**방법 A (Streamlit 앱에서)**  
앱 접속 → `⚙ 설정 관리` 탭 → Adgroup ID 수정 → 저장

**방법 B (config.json 직접 수정)**  
`config.json`을 열고 해당 값을 변경 후 커밋

---

## ⚙ 수동 실행 방법

**방법 A**: Streamlit 앱 → `▶ 수동 실행` 탭 → `🚀 지금 실행` 버튼

**방법 B**: GitHub → Actions 탭 → `Daily Media Crawl` → `Run workflow`

자동 실행은 GitHub Actions 서버 시간이 아니라 KST 기준 “전일”을 대상 날짜로 계산합니다.  
특정 날짜를 다시 넣어야 하면 workflow 환경변수로 `TARGET_DATE=YYYY-MM-DD`를 지정해 실행하세요.

크롤링 오류가 있으면 기본적으로 Sheets 업로드를 건너뛰고 Action을 실패 처리합니다.  
오류가 있는 상태에서도 BSA 등 일부 행을 올려야 하는 경우에만 `ALLOW_PARTIAL_UPLOAD=1`을 사용하세요.

---

## 🛠 BSA 비용 변경 방법

시트의 `설정` 탭 또는 Streamlit `⚙ 설정 관리` 탭에서 금액 수정.

---

## ⚠️ 크롤러 셀렉터 조정

RTB House / Buzzvil 대시보드 UI가 변경될 경우 크롤러가 작동하지 않을 수 있습니다.  
이 때는 `crawlers/rtbhouse.py` 또는 `crawlers/buzzvil.py`의 CSS 셀렉터를 수정하세요.

```python
# 예: 헤더 셀렉터 변경
header_cells = driver.find_elements(By.CSS_SELECTOR, "table thead th")
```
