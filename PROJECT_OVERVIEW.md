# 프로젝트 개요: 서울 당근마켓 게시글 기반 UMC 연결성 격차 분석

## 프로젝트 목적

서울시 당근마켓 커뮤니티 게시글을 분석하여, **UMC(Universal Meaningful Connectivity) 6개 차원**에 대한 지역별 격차를 파악한다. 최종적으로 각 자치구별 차원별 긍정/부정 빈도를 지도에 시각화하여 디지털 연결성 격차를 가시화한다.

## UMC 6개 차원

| 차원 키                | 설명                                 |
| ---------------------- | ------------------------------------ |
| `connection_quality`   | 인터넷 연결 품질 (속도, 안정성 등)   |
| `availability_for_use` | 사용 가능 여부 (커버리지, 인프라 등) |
| `affordability`        | 비용/경제성 (요금, 가격 부담 등)     |
| `devices`              | 기기/디바이스 (휴대폰, 컴퓨터 등)    |
| `digital_skills`       | 디지털 역량 (앱 사용, 리터러시 등)   |
| `safety_and_security`  | 안전/보안 (개인정보, 해킹, 사기 등)  |

## 데이터

- **출처**: 당근마켓 커뮤니티 게시글 (서울 전체)
- **형식**: CSV (`data/raw/`)
- **주요 컬럼**: `dbId`, `regionName`, `gu`, `title`, `content`, `status`, `createdAt` 등

---

## 전체 워크플로우

```
전체 데이터 (수백만 건)
│
├─ Phase 0: LLM 기반 키워드 발견 ─────────────────────────────
│    씨앗 키워드 (30~60개, 사람이 작성)
│      → 씨앗 키워드로 후보군 사전 필터링
│        → 후보군에서 구(gu)별 층화 랜덤 샘플링 (1,000건/라운드)
│          → LLM 분석: 차원별 정밀 키워드 + 변형 표현 추출
│            → 포화도 판단 (신규 키워드 발견율 < 5% → 중단)
│              → config/keywords.yaml 자동 저장
│
├─ Phase 1: 키워드 필터링 ─────────────────────────────────────
│    전체 데이터에서 정밀 키워드 포함 게시글만 추출
│      → data/processed/01_filtered.csv
│
├─ Phase 2: 텍스트 정규화 (전처리) ───────────────────────────
│    필터링된 글 → 이모지/자모음 제거 → Kiwi 형태소 분석
│      → 불필요한 품사(조사, 어미 등) 필터링 및 띄어쓰기 정규화
│        → data/processed/02_normalized.csv
│
├─ Phase 3: UMC 차원 분류 (Claude Code 오프라인) ──────────────
│    전처리된 글 → 배치 입력 마크다운 생성 (prepare)
│      → Claude Code가 umc_classification_prompt.md 기준으로 분류
│        → 마크다운 응답 파싱 CSV화 (parse)
│          → 원본 데이터와 병합 (merge)
│            → data/processed/03_umc_classified.csv
│              컬럼: dbId, gu, title, content, umc_related, umc_dimensions, problem_group
│
└─ Phase 4: 지역별 집계 + 지도 시각화 (미구현) ────────────────
     자치구(gu)별 차원별 긍/부정 건수 집계
       → 서울 지도 choropleth 시각화
         → UMC 격차 확인
```

---

## Phase 0 상세: LLM 기반 키워드 발견

### 배경

당근글 대부분("자전거 팝니다", "맛집 추천" 등)은 UMC와 무관하기 때문에
단순 랜덤 샘플링 시 관련 글이 극소수. 따라서 **2단계 전략**을 사용한다.

### 전략

```
[1단계] 씨앗 키워드 (사람이 작성, 넓게)
           → 후보군 추출 (UMC 관련 가능성 있는 글만)

[2단계] 후보군에서 층화 샘플 → LLM이 정밀 키워드 발견
           → 포화될 때까지 반복
```

### 포화도 판단 기준

| 라운드 | 신규 키워드 발견율 | 판단            |
| ------ | ------------------ | --------------- |
| 1차    | -                  | 기준선 생성     |
| 2차    | ≥ 20%              | 계속            |
| 3차    | 5~20%              | 계속            |
| 4차~   | < 5%               | **포화 → 종료** |

### 관련 파일

| 파일                        | 역할                           |
| --------------------------- | ------------------------------ |
| `config/seed_keywords.yaml` | 씨앗 키워드 (사람이 작성/수정) |
| `config/keywords.yaml`      | 정밀 키워드 (LLM이 생성)       |

### 실행 방법

```bash
# 실제 실행 (OpenAI API 키 필요)
export OPENAI_API_KEY="sk-..."
python -m src.phase00_keyword_discovery --input data/raw/seoul.csv --rounds 5

# 테스트 (LLM 호출 없이 샘플 파일만 저장)
python -m src.phase00_keyword_discovery --input data/raw/seoul.csv --dry-run
```

---

## Phase 2 상세: 텍스트 전처리 파이프라인

**현재 구현 완료.**

| 단계          | 파일                       | 설명                                              |
| ------------- | -------------------------- | ------------------------------------------------- |
| 키워드 필터링 | `src/phase01_keyword_filter.py` | 정밀 키워드로 게시글 선별                         |
| 텍스트 정규화 | `src/normalize.py`         | Kiwi 기반 띄어쓰기 교정, 불용어 제거, 형태소 분석 |
| 통합 실행     | `src/pipeline.py`          | CLI로 전체/단계별 실행                            |

```bash
python -m src.pipeline --input data/raw/seoul.csv
```

---

## Phase 3 상세: UMC 분류 (Claude Code 오프라인)

**현재 구현 완료.** `umc_classification_prompt.md`가 분류 에이전트 역할을 합니다.

| 단계 | 파일 | 입력 | 출력 |
|------|------|------|------|
| prepare | `src/phase03_llm_analysis.py` | `split_by_gu/{구명}.csv` | `phase03_batches/{구명}_batch{N}.md` |
| (수동) Claude Code | `umc_classification_prompt.md` | 배치 MD | `phase03_responses/{구명}_batch{N}.md` |
| parse | `src/phase03_llm_analysis.py` | 응답 MD | `phase03_parsed/{구명}_batch{N}.csv` |
| merge | `src/phase03_llm_analysis.py` | 파싱 CSV + 원본 | `03_umc_classified.csv` |

```bash
# 통합 실행
python main.py
python main.py --step parse merge   # 응답 저장 후

# 단계별 실행
python -m src.phase03_llm_analysis prepare --gu 종로구
python -m src.phase03_llm_analysis parse
python -m src.phase03_llm_analysis merge
```

## 기술 스택

- **언어**: Python 3.14+
- **패키지 관리**: `uv` (가상환경 `.venv`)
- **전처리**: `pandas`, `kiwipiepy`, `pyyaml`, `tqdm`
- **모델**: `transformers`, `torch`, `openai`
- **시각화**: 미정 (`folium`, `geopandas` 등)

## 팀 구성

| 이름 | 역할                                 |
| ---- | ------------------------------------ |
| 종윤 | 텍스트 분석 깃허브 관리, 전처리 개발 |
| 지윤 | UMC 차원별 키워드 검토, 전처리       |
| 윤지 | UMC 차원별 키워드 검토, 전처리       |
