"""
Phase 0: Claude 기반 키워드 발견 — 샘플링 & 병합 도구

워크플로우:
  1. sample: 씨앗 키워드로 후보군 필터링 → 구별 층화 랜덤 샘플링 → Claude용 프롬프트 생성
  2. merge:  Claude 응답 JSON을 keywords.yaml에 병합 + 포화도 체크
  3. status: 현재 진행 상태 확인

실행:
  python -m src.sample_for_claude sample --round 1
  python -m src.sample_for_claude merge --round 1 --input data/processed/claude_response_round1.json
  python -m src.sample_for_claude status
"""

import argparse
import json
import re
import sys
import yaml  # type: ignore
import pandas as pd  # type: ignore
from pathlib import Path
from typing import Dict, List, Tuple

# ── 상수 ────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent

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

# 기본 경로
DEFAULT_INPUT = "data/processed/01_filtered_merged.csv"
DEFAULT_SEED_KEYWORDS = "config/seed_keywords.yaml"
DEFAULT_KEYWORDS_OUTPUT = "config/keywords.yaml"
SAMPLED_IDS_PATH = "data/processed/sampled_ids.json"
DISCOVERY_LOG_PATH = "data/processed/discovery_log.json"

# ── 유틸 ────────────────────────────────────────────────────────────────────


def _resolve(rel: str) -> Path:
    """프로젝트 루트 기준 상대 경로를 절대 경로로 변환합니다."""
    return PROJECT_ROOT / rel


def _load_json(path: Path, default=None):
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default if default is not None else {}


def _save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Step 1: 씨앗 키워드로 후보군 필터링 ──────────────────────────────────────


def load_seed_keywords(seed_path: Path) -> List[str]:
    """씨앗 키워드를 로드합니다."""
    with open(seed_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    keywords = data.get("seed_keywords", [])
    print(f"  씨앗 키워드 수: {len(keywords)}개")
    return keywords


def filter_candidates(df: pd.DataFrame, seed_keywords: List[str]) -> pd.DataFrame:
    """씨앗 키워드를 포함하는 후보 게시글을 추출합니다."""
    # title + content 합쳐서 검색
    search_text = (
        df.get("title", pd.Series([""] * len(df))).fillna("")
        + " "
        + df.get("content", pd.Series([""] * len(df))).fillna("")
    ).str.lower()

    pattern = "|".join(re.escape(kw.lower()) for kw in seed_keywords)
    mask = search_text.str.contains(pattern, regex=True, na=False)
    candidates = df[mask].reset_index(drop=True)

    print(f"  전체 게시글: {len(df):,}건")
    print(f"  후보군 (씨앗 키워드 포함): {len(candidates):,}건 ({len(candidates)/max(len(df),1)*100:.1f}%)")
    return candidates


# ── Step 2: 층화 랜덤 샘플링 ─────────────────────────────────────────────────


def stratified_sample(
    df: pd.DataFrame,
    n_total: int = 1000,
    gu_col: str = "gu",
    exclude_ids: set | None = None,
    id_col: str = "dbId",
    random_state: int = 42,
) -> pd.DataFrame:
    """구(gu)별 층화 랜덤 샘플링. 이미 샘플링된 ID는 제외합니다."""
    # 중복 제외
    if exclude_ids and id_col in df.columns:
        before = len(df)
        df = df[~df[id_col].astype(str).isin(exclude_ids)]
        print(f"  이전 라운드 중복 제외: {before - len(df):,}건 제외 → {len(df):,}건 남음")

    if len(df) == 0:
        print("  ⚠️  남은 후보군이 없습니다.")
        return pd.DataFrame()

    if gu_col not in df.columns:
        print(f"  ⚠️  '{gu_col}' 컬럼 없음 → 단순 랜덤 샘플링")
        n = min(n_total, len(df))
        return df.sample(n=n, random_state=random_state).reset_index(drop=True)

    groups = df[gu_col].value_counts()
    n_groups = len(groups)
    n_per_group = max(1, n_total // n_groups)

    samples = []
    for gu, count in groups.items():
        group_df = df[df[gu_col] == gu]
        n = min(n_per_group, len(group_df))
        samples.append(group_df.sample(n=n, random_state=random_state))

    result = pd.concat(samples).sample(frac=1, random_state=random_state).reset_index(drop=True)
    result = result.head(n_total)
    print(f"  층화 샘플: {len(result)}건 ({n_groups}개 구에서 구당 ~{n_per_group}건)")
    return result


# ── Step 3: Claude용 프롬프트 생성 ───────────────────────────────────────────


def build_prompt(sample_df: pd.DataFrame, round_num: int, max_posts: int = 50) -> str:
    """Claude에 전달할 프롬프트를 마크다운으로 생성합니다.

    Args:
        sample_df: 샘플 데이터프레임
        round_num: 라운드 번호
        max_posts: 프롬프트에 포함할 최대 게시글 수 (기본 50, 나머지는 CSV 참조)
    """
    dimensions_desc = "\n".join(
        f"- **{dim}**: {label}" for dim, label in UMC_DIMENSION_LABELS.items()
    )

    display_df = sample_df.head(max_posts)

    # 샘플 텍스트 포맷
    text_lines = []
    for i, (_, row) in enumerate(display_df.iterrows()):
        title = str(row.get("title", "")).strip() if pd.notna(row.get("title")) else ""
        content = str(row.get("content", "")).strip() if pd.notna(row.get("content")) else ""
        combined = f"{title} {content}".strip()
        # 300자로 잘라서 표시
        truncated = combined[:300] + ("..." if len(combined) > 300 else "")
        gu = row.get("gu", "?")
        text_lines.append(f"[{i+1}] ({gu}) {truncated}")

    texts_formatted = "\n".join(text_lines)

    extra_note = ""
    if len(sample_df) > max_posts:
        extra_note = f"\n> **참고**: 전체 샘플은 {len(sample_df)}건이며, 위에는 {max_posts}건만 표시됩니다. 전체 샘플은 CSV 파일을 참조하세요.\n"

    prompt = f"""# 키워드 발견 분석 요청 (라운드 {round_num})

당신은 한국어 텍스트 분석 전문가입니다.
아래는 당근마켓 커뮤니티 게시글에서 **씨앗 키워드로 사전 필터링된 후보군** 중 무작위 추출한 샘플입니다.

## 분석 목적

이 글들에서 **UMC(Universal Meaningful Connectivity) 6개 차원**과 관련된 키워드 및 표현을 발견하는 것이 목적입니다.
당근마켓 특유의 **구어체, 은어, 축약어, 변형 표현**까지 포착해 주세요.

## UMC 6개 차원

{dimensions_desc}

## 게시글 샘플 ({len(display_df)}건 / 전체 {len(sample_df)}건)
{extra_note}
{texts_formatted}

## 요청사항

각 차원별로:
1. 해당 차원과 관련된 **모든 키워드/표현/단어** 추출 (위 샘플에서 등장한 것 위주)
2. **변형 표현 포함** (예: "좋다", "굿", "나이스", "짱" 등 같은 의미의 다양한 표현)
3. **부정적 표현도 포함** (예: "느려", "안터져", "먹통", "쓸모없음")
4. 각 차원과 **무관한 글의 대략적 비율**도 알려주세요

## 출력 형식 (반드시 아래 JSON 형식으로)

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

> **중요**: 반드시 위 JSON 형식으로만 답변해 주세요. 각 차원의 값은 문자열 리스트입니다.
"""
    return prompt


# ── Step 4: 키워드 병합 & 포화도 ─────────────────────────────────────────────


def load_keywords(path: Path) -> Dict[str, List[str]]:
    """현재 keywords.yaml을 로드합니다."""
    if not path.exists():
        return {dim: [] for dim in UMC_DIMENSIONS}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return {dim: list(data.get(dim, []) or []) for dim in UMC_DIMENSIONS}


def merge_keywords(
    existing: Dict[str, List[str]],
    new_round: Dict[str, List[str]],
) -> Tuple[Dict[str, List[str]], int, int]:
    """기존 키워드에 신규 키워드를 병합합니다.

    Returns:
        (병합된 키워드, 신규 키워드 수, 기존 전체 수)
    """
    merged: Dict[str, List[str]] = {dim: list(existing.get(dim, [])) for dim in UMC_DIMENSIONS}
    prev_total = sum(len(v) for v in merged.values())
    new_count = 0

    for dim in UMC_DIMENSIONS:
        new_keywords = new_round.get(dim, [])
        existing_set = set(kw.lower() for kw in merged[dim])

        for kw in new_keywords:
            if isinstance(kw, str) and kw.lower() not in existing_set:
                merged[dim].append(kw)
                existing_set.add(kw.lower())
                new_count += 1

    return merged, new_count, prev_total


def save_keywords(keywords: Dict[str, List[str]], path: Path):
    """keywords.yaml에 저장합니다."""
    output = {dim: sorted(set(keywords.get(dim, []))) for dim in UMC_DIMENSIONS}
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        f.write("# =============================================================================\n")
        f.write("# UMC 차원별 키워드 (LLM 분석으로 자동 생성됨)\n")
        f.write("# =============================================================================\n\n")
        yaml.dump(output, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"  키워드 저장 완료: {path}")
    for dim, kws in output.items():
        print(f"    {dim}: {len(kws)}개")


def check_saturation(new_count: int, prev_total: int, threshold: float = 0.05) -> bool:
    """포화 여부를 판단합니다."""
    if prev_total == 0:
        print(f"  포화도 체크: 첫 라운드 (기준선) → 계속")
        return False
    rate = new_count / prev_total
    saturated = rate < threshold
    status = "✅ 포화!" if saturated else "계속"
    print(f"  포화도 체크: 신규 {new_count}개 / 기존 {prev_total}개 = {rate:.1%} (임계값: {threshold:.0%}) → {status}")
    return saturated


# ── 서브커맨드 구현 ──────────────────────────────────────────────────────────


def cmd_sample(args):
    """sample 서브커맨드: 랜덤 샘플 추출 + Claude 프롬프트 생성"""
    round_num = args.round
    n_per_round = args.n_per_round
    input_path = _resolve(args.input)
    seed_path = _resolve(args.seed_keywords)

    print("=" * 60)
    print(f"Phase 0: 키워드 발견 샘플링 — 라운드 {round_num}")
    print("=" * 60)

    # 1. 데이터 로드
    print(f"\n[1/4] 데이터 로드: {input_path}")
    df = pd.read_csv(input_path, encoding="utf-8")
    print(f"  로드 완료: {len(df):,}건")

    # 2. 씨앗 키워드로 후보군 필터링
    print("\n[2/4] 씨앗 키워드로 후보군 필터링...")
    seed_keywords = load_seed_keywords(seed_path)
    candidates = filter_candidates(df, seed_keywords)

    if len(candidates) == 0:
        print("⚠️  씨앗 키워드로 추출된 후보군이 없습니다.")
        return

    # 3. 이전 샘플 ID 로드 (중복 방지)
    print("\n[3/4] 층화 랜덤 샘플링...")
    sampled_ids_path = _resolve(SAMPLED_IDS_PATH)
    sampled_ids_data = _load_json(sampled_ids_path, default={"ids": []})
    exclude_ids = set(str(x) for x in sampled_ids_data.get("ids", []))
    print(f"  이전 라운드까지 누적 샘플: {len(exclude_ids):,}건")

    sample = stratified_sample(
        candidates,
        n_total=n_per_round,
        exclude_ids=exclude_ids,
        random_state=round_num * 42,
    )

    if len(sample) == 0:
        print("⚠️  샘플링할 수 있는 후보가 없습니다.")
        return

    # 샘플 ID 기록
    id_col = "dbId" if "dbId" in sample.columns else sample.columns[0]
    new_ids = sample[id_col].astype(str).tolist()
    sampled_ids_data["ids"] = sorted(exclude_ids | set(new_ids))
    _save_json(sampled_ids_path, sampled_ids_data)

    # 4. 샘플 CSV + 프롬프트 저장
    print("\n[4/4] 샘플 및 프롬프트 저장...")
    sample_csv_path = _resolve(f"data/processed/sample_round{round_num}.csv")
    prompt_md_path = _resolve(f"data/processed/prompt_round{round_num}.md")

    sample.to_csv(sample_csv_path, index=False, encoding="utf-8-sig")
    print(f"  샘플 CSV: {sample_csv_path}")

    prompt = build_prompt(sample, round_num)
    prompt_md_path.parent.mkdir(parents=True, exist_ok=True)
    with open(prompt_md_path, "w", encoding="utf-8") as f:
        f.write(prompt)
    print(f"  프롬프트 MD: {prompt_md_path}")

    print(f"\n{'=' * 60}")
    print(f"✅ 라운드 {round_num} 샘플 추출 완료!")
    print(f"   다음 단계: prompt_round{round_num}.md 를 Claude에 전달하세요.")
    print(f"   Claude 응답을 data/processed/claude_response_round{round_num}.json 으로 저장한 뒤:")
    print(f"   python -m src.sample_for_claude merge --round {round_num} --input data/processed/claude_response_round{round_num}.json")
    print(f"{'=' * 60}")


def cmd_merge(args):
    """merge 서브커맨드: Claude 응답을 keywords.yaml에 병합"""
    round_num = args.round
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = _resolve(args.input)
    keywords_path = _resolve(args.output)
    log_path = _resolve(DISCOVERY_LOG_PATH)

    print("=" * 60)
    print(f"키워드 병합 — 라운드 {round_num}")
    print("=" * 60)

    # 1. Claude 응답 로드
    print(f"\n[1/3] Claude 응답 로드: {input_path}")
    if not input_path.exists():
        print(f"⚠️  파일을 찾을 수 없습니다: {input_path}")
        return

    with open(input_path, "r", encoding="utf-8") as f:
        content = f.read()

    # JSON 파싱 (```json ... ``` 블록도 처리)
    json_match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_str = content.strip()

    try:
        response_data = json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"⚠️  JSON 파싱 실패: {e}")
        print("  Claude 응답이 올바른 JSON 형식인지 확인하세요.")
        return

    # 2. 기존 키워드 로드 + 병합
    print(f"\n[2/3] 키워드 병합 중...")
    existing = load_keywords(keywords_path)
    merged, new_count, prev_total = merge_keywords(existing, response_data)

    total_after = sum(len(v) for v in merged.values())
    print(f"  신규 키워드: {new_count}개")
    print(f"  병합 후 총 키워드: {total_after}개")

    # 포화도 체크
    saturated = check_saturation(new_count, prev_total)

    # 3. 저장
    print(f"\n[3/3] 저장...")
    save_keywords(merged, keywords_path)

    # 로그 기록
    log = _load_json(log_path, default={"rounds": []})
    log["rounds"].append({
        "round": round_num,
        "new_keywords": new_count,
        "total_keywords": total_after,
        "prev_total": prev_total,
        "saturation_rate": round(new_count / prev_total, 4) if prev_total > 0 else None,
        "saturated": saturated,
    })
    _save_json(log_path, log)

    # LLM 메타 정보 출력
    if "notes" in response_data:
        print(f"\n  📝 Claude 메모: {response_data['notes']}")
    if "unrelated_ratio" in response_data:
        ratio = response_data["unrelated_ratio"]
        print(f"  📊 무관 글 비율: {ratio:.0%}" if isinstance(ratio, (int, float)) else f"  📊 무관 글 비율: {ratio}")

    print(f"\n{'=' * 60}")
    if saturated:
        print(f"✅ 포화 도달! 키워드 발견 단계가 완료되었습니다.")
        print(f"   최종 키워드: {keywords_path}")
    else:
        next_round = round_num + 1
        print(f"🔄 아직 포화되지 않았습니다. 다음 라운드를 진행하세요:")
        print(f"   python -m src.sample_for_claude sample --round {next_round}")
    print(f"{'=' * 60}")


def cmd_status(args):
    """status 서브커맨드: 현재 진행 상태 출력"""
    keywords_path = _resolve(args.output)
    log_path = _resolve(DISCOVERY_LOG_PATH)
    sampled_ids_path = _resolve(SAMPLED_IDS_PATH)

    print("=" * 60)
    print("키워드 발견 진행 상태")
    print("=" * 60)

    # 키워드 현황
    keywords = load_keywords(keywords_path)
    total = sum(len(v) for v in keywords.values())
    print(f"\n📋 키워드 현황 ({keywords_path}):")
    print(f"   총 키워드 수: {total}개")
    for dim in UMC_DIMENSIONS:
        kws = keywords.get(dim, [])
        count = len(kws)
        preview = ", ".join(kws[:5])
        if len(kws) > 5:
            preview += f", ... (+{len(kws) - 5}개)"
        print(f"   - {dim}: {count}개{' — ' + preview if preview else ''}")

    # 샘플링 현황
    sampled_data = _load_json(sampled_ids_path, default={"ids": []})
    print(f"\n📊 샘플링 현황:")
    print(f"   누적 샘플 수: {len(sampled_data.get('ids', []))}건")

    # 라운드 이력
    log = _load_json(log_path, default={"rounds": []})
    rounds = log.get("rounds", [])
    if rounds:
        print(f"\n📈 라운드 이력:")
        print(f"   {'라운드':>6} | {'신규':>6} | {'누적':>6} | {'발견율':>8} | 상태")
        print(f"   {'─'*6:>6} | {'─'*6:>6} | {'─'*6:>6} | {'─'*8:>8} | {'─'*8}")
        for r in rounds:
            rate = f"{r['saturation_rate']:.1%}" if r.get("saturation_rate") is not None else "-"
            status = "✅ 포화" if r.get("saturated") else "계속"
            print(f"   {r['round']:>6} | {r['new_keywords']:>6} | {r['total_keywords']:>6} | {rate:>8} | {status}")
    else:
        print(f"\n📈 아직 진행된 라운드가 없습니다.")

    # 다음 단계 안내
    last_round = rounds[-1] if rounds else None
    if last_round and last_round.get("saturated"):
        print(f"\n✅ 포화 도달 완료! Phase 1 (키워드 필터링)으로 넘어갈 수 있습니다.")
    else:
        next_round = (last_round["round"] + 1) if last_round else 1
        print(f"\n🔜 다음 단계: python -m src.sample_for_claude sample --round {next_round}")

    print("=" * 60)


# ── CLI ──────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Claude 기반 UMC 키워드 발견 도구",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예:
  python -m src.sample_for_claude sample --round 1
  python -m src.sample_for_claude merge --round 1 --input data/processed/claude_response_round1.json
  python -m src.sample_for_claude status
        """,
    )
    subparsers = parser.add_subparsers(dest="command", help="서브커맨드")

    # sample
    sp_sample = subparsers.add_parser("sample", help="샘플 추출 + Claude 프롬프트 생성")
    sp_sample.add_argument("--round", type=int, required=True, help="라운드 번호")
    sp_sample.add_argument("--n-per-round", type=int, default=1000, help="라운드당 샘플 수 (기본: 1000)")
    sp_sample.add_argument("--input", default=DEFAULT_INPUT, help="입력 CSV 파일")
    sp_sample.add_argument("--seed-keywords", default=DEFAULT_SEED_KEYWORDS, help="씨앗 키워드 파일")

    # merge
    sp_merge = subparsers.add_parser("merge", help="Claude 응답 병합 + 포화도 체크")
    sp_merge.add_argument("--round", type=int, required=True, help="라운드 번호")
    sp_merge.add_argument("--input", required=True, help="Claude 응답 JSON 파일 경로")
    sp_merge.add_argument("--output", default=DEFAULT_KEYWORDS_OUTPUT, help="키워드 출력 파일")

    # status
    sp_status = subparsers.add_parser("status", help="진행 상태 확인")
    sp_status.add_argument("--output", default=DEFAULT_KEYWORDS_OUTPUT, help="키워드 파일 경로")

    args = parser.parse_args()

    if args.command == "sample":
        cmd_sample(args)
    elif args.command == "merge":
        cmd_merge(args)
    elif args.command == "status":
        cmd_status(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
