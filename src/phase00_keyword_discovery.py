"""
Phase 0: LLM 기반 키워드 발견 파이프라인

흐름:
  1. 씨앗 키워드로 전체 데이터에서 후보군(UMC 관련 가능성 있는 글) 추출
  2. 후보군에서 구(gu)별 층화 랜덤 샘플링 (라운드별 1,000건)
  3. 샘플을 LLM에 전달하여 차원별 정밀 키워드 + 변형 표현 발견
  4. 신규 키워드 발견율이 포화될 때까지 반복
  5. 결과를 config/keywords.yaml에 저장

실행:
  python -m src.phase00_keyword_discovery --input data/raw/seoul.csv --rounds 3
"""

import argparse
import json
import random
import re
import yaml  # type: ignore
import pandas as pd  # type: ignore
from pathlib import Path
from tqdm import tqdm  # type: ignore
from typing import Dict, List, Tuple

# UMC 6개 차원
UMC_DIMENSIONS = [
    "connection_quality",
    "availability_for_use",
    "affordability",
    "devices",
    "digital_skills",
    "safety_and_security",
]

UMC_DIMENSION_LABELS = {
    "connection_quality": "연결 품질 (인터넷 속도, 안정성 등)",
    "availability_for_use": "사용 가능성 (커버리지, 인프라 접근 등)",
    "affordability": "경제성 (요금, 비용 부담 등)",
    "devices": "기기 (스마트폰, 컴퓨터, 공유기 등)",
    "digital_skills": "디지털 역량 (앱 사용법, 디지털 활용 등)",
    "safety_and_security": "안전과 보안 (개인정보, 사기, 해킹 등)",
}


# =============================================================================
# Step 1: 씨앗 키워드로 후보군 추출
# =============================================================================

def load_seed_keywords(seed_path: str = "config/seed_keywords.yaml") -> List[str]:
    """씨앗 키워드를 로드합니다."""
    with open(seed_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    keywords = data.get("seed_keywords", [])
    print(f"  씨앗 키워드 수: {len(keywords)}")
    return keywords


def filter_candidate_posts(
    df: pd.DataFrame,
    seed_keywords: List[str],
) -> pd.DataFrame:
    """씨앗 키워드를 포함하는 후보 게시글을 추출합니다.

    Args:
        df: 전체 데이터프레임
        seed_keywords: 씨앗 키워드 리스트

    Returns:
        후보 게시글 데이터프레임
    """
    # 삭제된 글, 빈 글 제거
    if "status" in df.columns:
        df = df[df["status"] != "DELETED"]
    if "content" in df.columns:
        df = df[df["content"].notna() & (df["content"].str.strip() != "")]

    # title + content 합쳐서 검색
    search_text = (
        df.get("title", pd.Series([""] * len(df))).fillna("") + " " +
        df.get("content", pd.Series([""] * len(df))).fillna("")
    ).str.lower()

    # 씨앗 키워드 중 하나라도 포함된 글
    pattern = "|".join(re.escape(kw.lower()) for kw in seed_keywords)
    mask = search_text.str.contains(pattern, regex=True, na=False)
    candidates = df[mask].reset_index(drop=True)

    print(f"  전체 게시글: {len(df):,}건")
    print(f"  후보군 (씨앗 키워드 포함): {len(candidates):,}건 ({len(candidates)/len(df)*100:.1f}%)")
    return candidates


# =============================================================================
# Step 2: 층화 랜덤 샘플링
# =============================================================================

def stratified_sample(
    df: pd.DataFrame,
    n_per_round: int = 1000,
    gu_col: str = "gu",
    random_state: int | None = None,
) -> pd.DataFrame:
    """구(gu)별 층화 랜덤 샘플링을 수행합니다.

    서울 25개 구에서 균등하게 샘플을 추출하여 지역 편향을 방지합니다.
    글 수가 적은 구는 해당 구 전체를 사용합니다.

    Args:
        df: 후보 데이터프레임
        n_per_round: 라운드당 총 샘플 수
        gu_col: 구 컬럼명
        random_state: 랜덤 시드

    Returns:
        샘플 데이터프레임
    """
    if gu_col not in df.columns:
        print(f"  ⚠️  '{gu_col}' 컬럼 없음 → 단순 랜덤 샘플링")
        n = min(n_per_round, len(df))
        return df.sample(n=n, random_state=random_state)

    groups = df[gu_col].value_counts()
    n_groups = len(groups)
    n_per_group = max(1, n_per_round // n_groups)

    samples = []
    for gu, count in groups.items():
        group_df = df[df[gu_col] == gu]
        n = min(n_per_group, len(group_df))
        samples.append(group_df.sample(n=n, random_state=random_state))

    result = pd.concat(samples).sample(frac=1, random_state=random_state).reset_index(drop=True)
    result = result.head(n_per_round)  # 총 수 맞추기
    print(f"  층화 샘플: {len(result)}건 ({n_groups}개 구에서 구당 ~{n_per_group}건)")
    return result


# =============================================================================
# Step 3: LLM 분석으로 키워드 발견
# =============================================================================

def build_llm_prompt(sample_texts: List[str]) -> str:
    """LLM에 전달할 프롬프트를 생성합니다."""
    formatted_lines = []
    for i, t in enumerate(sample_texts):
        if i >= 50:
            break
        
        # Bypass Pyre string slicing bug
        text_str = str(t)
        truncated = "".join(text_str[j] for j in range(min(300, len(text_str))))
        formatted_lines.append(f"[{i+1}] {truncated}")
        
    texts_formatted = "\n".join(formatted_lines)

    dimensions_desc = "\n".join(
        f"- {dim}: {label}"
        for dim, label in UMC_DIMENSION_LABELS.items()
    )

    prompt = f"""당신은 한국어 텍스트 분석 전문가입니다.
아래는 당근마켓 커뮤니티 게시글 샘플입니다.

이 글들을 분석하여, UMC(Universal Meaningful Connectivity)의 6개 차원과 관련된
키워드와 표현들을 추출해 주세요.

## UMC 6개 차원
{dimensions_desc}

## 게시글 샘플 ({len(sample_texts)}건)
{texts_formatted}

## 요청사항
각 차원별로:
1. 해당 차원과 관련된 **모든 표현/단어** 추출 (위 샘플에서 등장한 것 위주)
2. **변형 표현 포함** (예: "좋다", "굿", "나이스", "짱", "개좋음" 등 같은 의미의 다양한 표현)
3. **부정적 표현도 포함** (예: "느려", "안터져", "먹통", "쓸모없음")
4. 해당 차원과 **무관한 글**이 섞여있다면 그 비율도 알려주세요

## 출력 형식 (반드시 JSON으로)
```json
{{
  "connection_quality": ["키워드1", "키워드2", ...],
  "availability_for_use": ["키워드1", ...],
  "affordability": ["키워드1", ...],
  "devices": ["키워드1", ...],
  "digital_skills": ["키워드1", ...],
  "safety_and_security": ["키워드1", ...],
  "unrelated_ratio": 0.3,
  "notes": "기타 관찰 사항"
}}
```
"""
    return prompt


def parse_llm_response(response_text: str) -> Dict[str, List[str]]:
    """LLM 응답에서 JSON을 추출합니다."""
    # ```json ... ``` 블록 추출
    json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        # 그냥 { } 전체 추출 시도
        json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
        else:
            print("  ⚠️  LLM 응답에서 JSON을 찾을 수 없습니다.")
            return {}

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"  ⚠️  JSON 파싱 실패: {e}")
        return {}


def call_llm(prompt: str, api_key: str | None = None, model: str = "gpt-4o-mini") -> str:
    """OpenAI API로 LLM을 호출합니다.

    Args:
        prompt: 입력 프롬프트
        api_key: OpenAI API 키 (없으면 환경변수 OPENAI_API_KEY 사용)
        model: 사용할 모델명

    Returns:
        LLM 응답 텍스트
    """
    try:
        from openai import OpenAI  # type: ignore
        import os

        client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return response.choices[0].message.content
    except ImportError:
        print("  ⚠️  openai 패키지가 없습니다. uv pip install openai")
        raise
    except Exception as e:
        print(f"  ⚠️  LLM 호출 실패: {e}")
        raise


# =============================================================================
# Step 4: 포화도 계산 및 키워드 병합
# =============================================================================

def _combine_lists(a: List[str], b: List[str]) -> List[str]:
    return [x for x in a] + [x for x in b]

def merge_keywords(
    existing: Dict[str, List[str]],
    new_round: Dict[str, List[str]],
) -> Tuple[Dict[str, List[str]], int]:
    """기존 키워드에 신규 키워드를 병합하고 신규 발견 수를 반환합니다.

    Returns:
        (병합된 키워드 dict, 신규 키워드 수)
    """
    merged: Dict[str, List[str]] = {dim: list(existing.get(dim, [])) for dim in UMC_DIMENSIONS}
    new_added_kws: List[str] = []

    for dim in UMC_DIMENSIONS:
        new_keywords = new_round.get(dim, [])
        existing_list: List[str] = merged[dim]
        existing_set = set(kw.lower() for kw in existing_list)
        
        valid_news: List[str] = []
        for kw in new_keywords:
            if kw.lower() not in existing_set:
                valid_news.append(kw)
                existing_set.add(kw.lower())
        new_merged: Dict[str, List[str]] = {}
        for k in UMC_DIMENSIONS:
            new_merged[k] = merged[k] if k in merged else []
        new_merged[dim] = _combine_lists(existing_list, valid_news)
        merged = new_merged

    return merged, len(new_added_kws)


def is_saturated(new_count: int, total_count: int, threshold: float = 0.05) -> bool:
    """신규 키워드 발견율이 임계값 미만이면 포화로 판단합니다."""
    if total_count == 0:
        return False
    rate = new_count / total_count
    print(f"  포화도 체크: 신규 {new_count}개 / 전체 {total_count}개 = {rate:.1%} (임계값: {threshold:.0%})")
    return rate < threshold


# =============================================================================
# Step 5: 최종 저장
# =============================================================================

def save_keywords(keywords: Dict[str, List[str]], output_path: str = "config/keywords.yaml"):
    """발견된 키워드를 keywords.yaml에 저장합니다."""
    # 빈 리스트인 차원은 빈 리스트로 유지
    output = {dim: sorted(set(keywords.get(dim, []))) for dim in UMC_DIMENSIONS}

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# =============================================================================\n")
        f.write("# UMC 차원별 키워드 (LLM 분석으로 자동 생성됨)\n")
        f.write("# =============================================================================\n\n")
        yaml.dump(output, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"  키워드 저장 완료: {output_path}")
    for dim, kws in output.items():
        print(f"    {dim}: {len(kws)}개")


# =============================================================================
# 메인 파이프라인
# =============================================================================

def run(
    input_path: str,
    n_per_round: int = 1000,
    max_rounds: int = 5,
    saturation_threshold: float = 0.05,
    seed_path: str = "config/seed_keywords.yaml",
    output_keywords: str = "config/keywords.yaml",
    llm_model: str = "gpt-4o-mini",
    dry_run: bool = False,
):
    """키워드 발견 파이프라인을 실행합니다.

    Args:
        input_path: 원본 CSV 파일 경로
        n_per_round: 라운드당 샘플 수 (기본 1,000)
        max_rounds: 최대 반복 라운드 수 (기본 5)
        saturation_threshold: 포화 판단 임계값 (신규 키워드 비율, 기본 5%)
        seed_path: 씨앗 키워드 YAML 경로
        output_keywords: 결과 저장 경로
        llm_model: 사용할 LLM 모델명
        dry_run: True이면 LLM 호출 없이 프롬프트만 출력 (테스트용)
    """
    print("=" * 60)
    print("Phase 0: LLM 기반 키워드 발견")
    print("=" * 60)

    # 1. 전체 데이터 로드
    print("\n[1/4] 데이터 로드 중...")
    df = pd.read_csv(input_path, encoding="utf-8")

    # 2. 씨앗 키워드로 후보군 추출
    print("\n[2/4] 씨앗 키워드로 후보군 추출...")
    seed_keywords = load_seed_keywords(seed_path)
    candidates = filter_candidate_posts(df, seed_keywords)

    if len(candidates) == 0:
        print("⚠️  씨앗 키워드로 추출된 후보군이 없습니다. seed_keywords.yaml을 확인하세요.")
        return

    # 이미 샘플링된 인덱스 추적 (중복 방지)
    sampled_indices: set = set()
    accumulated_keywords: Dict[str, List[str]] = {dim: [] for dim in UMC_DIMENSIONS}

    # 3. 라운드별 반복
    print("\n[3/4] 라운드별 LLM 분석...")
    for round_num in range(1, max_rounds + 1):
        print(f"\n--- Round {round_num} / {max_rounds} ---")

        # 이미 샘플링된 글 제외
        remaining = candidates[~candidates.index.isin(sampled_indices)]
        if len(remaining) == 0:
            print("  남은 후보군 없음 → 종료")
            break

        # 층화 샘플링
        sample = stratified_sample(
            remaining,
            n_per_round=min(n_per_round, len(remaining)),
            random_state=round_num * 42,
        )
        sampled_indices.update(sample.index.tolist())

        # 텍스트 추출
        sample_texts = (
            sample.get("title", pd.Series([""] * len(sample))).fillna("") + " " +
            sample.get("content", pd.Series([""] * len(sample))).fillna("")
        ).str.strip().tolist()

        # 프롬프트 생성
        prompt = build_llm_prompt(sample_texts)

        if dry_run:
            # dry-run: 프롬프트만 출력
            prompt_str = str(prompt)
            print("".join(prompt_str[j] for j in range(min(1000, len(prompt_str)))))
            print("...(이하 생략)...")
            sample.to_csv(f"data/processed/sample_round{round_num}.csv",
                          index=False, encoding="utf-8-sig")
            print(f"  샘플 저장: data/processed/sample_round{round_num}.csv")
            continue

        # LLM 호출
        print("  LLM 호출 중...")
        try:
            response = call_llm(prompt, model=llm_model)
        except Exception:
            print("  LLM 호출 실패 → 라운드 건너뜀")
            continue

        # 응답 파싱
        round_keywords = parse_llm_response(response)
        if not round_keywords:
            continue

        prev_total: int = 0
        for dim in UMC_DIMENSIONS:
            if dim in accumulated_keywords:  # type: ignore
                prev_total = prev_total + len(accumulated_keywords[dim])  # type: ignore
        
        parsed_keywords: Dict[str, List[str]] = {}
        for dim in UMC_DIMENSIONS:
            if dim in round_keywords:  # type: ignore
                parsed_keywords[dim] = list(round_keywords[dim])  # type: ignore
                
        accumulated_keywords, new_count = merge_keywords(accumulated_keywords, parsed_keywords)
        
        total_count = 0
        for dim in UMC_DIMENSIONS:
            if dim in accumulated_keywords:  # type: ignore
                total_count = total_count + len(accumulated_keywords[dim])  # type: ignore

        print(f"  이번 라운드 신규 키워드: {new_count}개 (누적: {total_count}개)")

        # LLM 노트 출력
        if "notes" in round_keywords:
            print(f"  LLM 메모: {round_keywords['notes']}")
        if "unrelated_ratio" in round_keywords:
            print(f"  무관 글 비율: {round_keywords['unrelated_ratio']:.0%}")

        # 포화 판단
        if round_num > 1 and is_saturated(new_count, prev_total, saturation_threshold):
            print(f"\n✅ 포화 도달! (라운드 {round_num}에서 중단)")
            break

    # 4. 저장
    print("\n[4/4] 키워드 저장...")
    if not dry_run:
        save_keywords(accumulated_keywords, output_keywords)
    else:
        print("  [DRY RUN] 실제 실행 시 keywords.yaml에 저장됩니다.")

    print("\n" + "=" * 60)
    print("✅ Phase 0 완료!")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="LLM 기반 UMC 키워드 발견 파이프라인"
    )
    parser.add_argument("--input", required=True, help="입력 CSV 파일 (예: data/raw/seoul.csv)")
    parser.add_argument("--rounds", type=int, default=5, help="최대 라운드 수 (기본: 5)")
    parser.add_argument("--n-per-round", type=int, default=1000, help="라운드당 샘플 수 (기본: 1000)")
    parser.add_argument("--threshold", type=float, default=0.05, help="포화 임계값 (기본: 0.05 = 5%%)")
    parser.add_argument("--model", default="gpt-4o-mini", help="LLM 모델명 (기본: gpt-4o-mini)")
    parser.add_argument("--seed-keywords", default="config/seed_keywords.yaml",
                        help="씨앗 키워드 파일 경로")
    parser.add_argument("--output", default="config/keywords.yaml", help="키워드 출력 경로")
    parser.add_argument("--dry-run", action="store_true",
                        help="LLM 호출 없이 샘플만 저장 (테스트용)")

    args = parser.parse_args()

    run(
        input_path=args.input,
        n_per_round=args.n_per_round,
        max_rounds=args.rounds,
        saturation_threshold=args.threshold,
        seed_path=args.seed_keywords,
        output_keywords=args.output,
        llm_model=args.model,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
