# EW11 MQTT 패킷 분석기

EW11(RS485↔Wi-Fi 변환기)을 통해 월패드에 연결된 상태에서 흐르는 MQTT 패킷을 수집·분석하는 도구입니다.

- **자동 신호 vs 버튼 신호 구분**: 아무것도 안 해도 주기적으로 오는 상태 패킷과, 버튼을 눌렀을 때만 나타나는 이벤트 패킷을 자동 분류합니다.
- **이벤트 마킹**: 버튼을 누르기 직전에 "마커"를 찍으면, 그 전후 시간대 패킷을 집중 분석해 어떤 패킷이 그 버튼과 연관됐는지 보여줍니다.
- **패킷 구조 분석**: 바이트별 역할(헤더/체크섬/카운터/상태값) 추정, XOR·Sum·CRC 체크섬 자동 감지, 패밀리별 바이트 맵.
- **AI 연동**: 분석 리포트를 마크다운 파일로 저장해 ChatGPT/Claude에 직접 붙여넣거나, OpenAI 호환/Anthropic API로 앱에서 바로 전송할 수 있습니다.
- **GUI 포함**: 브라우저에서 실시간 모니터링, 마킹, 분석, 리포트, 설정을 모두 다룹니다.

## 빠른 시작 (데모 모드)

월패드 없이 시뮬레이터로 전체 기능을 체험할 수 있습니다.

```bash
./run.sh --demo
# 브라우저에서 http://localhost:8321 열기
```

데모 모드에서는 월패드 시뮬레이터가 주기 상태 패킷을 생성하고, "이벤트 표시" 탭의 데모 버튼으로 버튼 누름을 흉내 낼 수 있습니다.

## 실제 월패드(EW11)에 연결

1. EW11을 월패드 RS485 배선에 연결하고, EW11의 MQTT 브로커를 확인합니다 (EW11 자체 브로커 또는 중계 브로커).
2. 실행:

```bash
./run.sh --host <MQTT 브로커 IP> --port 1883 --topic "ew11/#"
```

또는 설정 탭에서 브로커 주소를 입력 후 저장하면 됩니다.

## 버튼 신호 분석 워크플로우

1. **실시간 모니터** 탭에서 패킷이 들어오는지 확인합니다.
2. **이벤트 표시** 탭에서 버튼을 누르기 **직전**에 `마커 찍기`를 누릅니다.
3. 월패드에서 버튼을 누릅니다.
4. 같은 버튼을 2~3회 반복하면 신뢰도가 올라갑니다.
5. **패킷 분석** 탭에서 `분석 실행`을 누릅니다.
6. `이벤트` 배지가 붙은 패밀리가 버튼 관련 신호입니다. 카드를 열어 바이트 맵과 체크섬을 확인하세요.

## AI 분석

- **파일로 보내기**: `AI 리포트` 탭 → `리포트 생성` → `파일 다운로드`로 `.md` 저장 후 ChatGPT/Claude에 첨부. 리포트 안에 AI용 분석 지침이 포함되어 있습니다.
- **API로 보내기**: `설정` 탭에서 AI provider(openai/anthropic), API 키, 모델을 입력 후 `AI 리포트` 탭에서 `API로 분석` 클릭. API 키는 로컬 `config.json`에만 저장됩니다(권한 600).

## 수동 설치·실행

```bash
# 백엔드
python -m venv .venv && .venv/bin/pip install -e '.[dev]'

# 프론트엔드
cd frontend && npm ci && npm run build && cd ..

# 실행 (데모)
.venv/bin/python -m ew11_analyzer --demo

# 실행 (실제 MQTT)
.venv/bin/python -m ew11_analyzer --host 192.168.x.x --topic "ew11/#"
```

## 테스트

```bash
# 백엔드 단위 테스트 + 린트 + 타입체크
.venv/bin/pytest tests -q
.venv/bin/ruff check src tests
.venv/bin/mypy src

# 프론트엔드
cd frontend && npm test && npm run typecheck && npm run lint && npm run build

# E2E (Playwright — 데모 서버 자동 구동)
cd e2e && npm ci && npx playwright install chromium && npx playwright test
```

## CI/CD

- `.github/workflows/ci.yml`: push/PR마다 백엔드 테스트·린트·타입체크, 프론트엔드 테스트·빌드, Playwright E2E를 실행합니다.
- `.github/workflows/release.yml`: `v*` 태그 push 시 PyInstaller로 Linux/Windows/macOS 단일 바이너리를 빌드해 GitHub Release에 첨부합니다.

## 프로젝트 구조

```
src/ew11_analyzer/   백엔드 (FastAPI + 분석 엔진)
  packets.py         MQTT 페이로드 정규화 (hex/JSON/바이너리)
  families.py        패킷 패밀리 그룹화 (3바이트 프리픽스 서명)
  checksums.py       XOR/Sum/CRC 체크섬 자동 감지
  bytemap.py         바이트별 역할 추정 (헤더/상태/카운터/체크섬)
  classify.py        IDLE/EVENT/MIXED 분류 (주기성 + 이벤트 윈도우 lift)
  diffing.py         마커 전후 신규 패밀리·변경 바이트 분석
  analysis.py        분석 오케스트레이션
  report.py          AI용 마크다운/JSON/CSV 리포트
  ai.py              OpenAI 호환/Anthropic API 클라이언트
  storage.py         SQLite 저장 (패킷/마커, 자동 정리)
  sources/mqtt.py    Paho MQTT 라이브 소스
  sources/simulator.py  월패드 시뮬레이터 (데모/E2E용)
  pipeline.py        수집→저장→분석 파이프라인 + WS 브로드캐스트
  api.py             REST/WebSocket + SPA 서빙
frontend/            React+TS+Vite GUI (한국어)
tests/               백엔드 pytest (76개)
e2e/                 Playwright E2E (5개)
```

## 보안 참고

- 이 도구는 **수동 분석 전용**입니다. 월패드로 패킷을 송신하는 기능은 없습니다.
- API 키는 로컬 데이터 디렉터리의 `config.json`에만 저장되며 외부로 나가지 않습니다.
- MQTT 브로커는 기본적으로 읽기 구독만 합니다.
