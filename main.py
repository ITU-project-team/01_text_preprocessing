"""
UMC 분석 파이프라인 — 통합 실행 진입점

전체 분석 파이프라인을 한 번에 또는 단계별로 실행합니다.

전체 실행 (Phase 1→2→3 prepare까지):
  python main.py

단계별 실행:
  python main.py --step filter    # Phase 1: 키워드 필터링
  python main.py --step split     # Phase 2: 구별 분할
  python main.py --step prepare   # Phase 3a: 배치 입력 생성
  python main.py --step parse     # Phase 3b: Claude 응답 파싱
  python main.py --step merge     # Phase 3c: 최종 병합

여러 단계 연속 실행:
  python main.py --step filter split prepare

Phase 3 옵션:
  python main.py --step prepare --gu 종로구 강남구
  python main.py --step prepare --batch-size 30

파이프라인 흐름:
  data/raw/*.csv
    └─ [전처리: phase00_data_cleaning.ipynb]
         └─ data/processed/01_cleaned_merged.csv
              └─ [filter] data/processed/02_keyword_filtered.csv
                   └─ [split] data/processed/split_by_gu/{구명}.csv
                        └─ [prepare] data/processed/phase03_batches/{구명}_batch{N}.md
                             └─ [Claude Code 수동 분석] → data/processed/phase03_responses/
                                  └─ [parse] data/processed/phase03_parsed/{구명}_batch{N}.csv
                                       └─ [merge] data/processed/03_umc_classified.csv
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

# 단계 정의 (순서 고정)
PIPELINE_STEPS = ["filter", "split", "prepare", "parse", "merge"]

# 기본 경로
DEFAULT_SOURCE = "data/processed/01_cleaned_merged.csv"
DEFAULT_KEYWORDS = "config/keywords.yaml"
FILTERED_CSV = "data/processed/02_keyword_filtered.csv"
FINAL_CSV = "data/processed/03_umc_classified.csv"


def _resolve(rel: str) -> Path:
    return PROJECT_ROOT / rel


# ─────────────────────────────────────────────────────────────────────────────

def run_filter(source: str, keywords: str) -> None:
    """Phase 1: 키워드 기반 게시글 필터링"""
    from src.phase01_keyword_filter import run as fb_run  # type: ignore

    print("=" * 60)
    print("Phase 1: 키워드 필터링")
    print("=" * 60)

    in_path = str(_resolve(source))
    out_path = str(_resolve(FILTERED_CSV))
    kw_path = str(_resolve(keywords))

    fb_run(input_path=in_path, output_path=out_path, keywords_path=kw_path)
    print(f"\n  출력: {FILTERED_CSV}")


def run_split(source: str) -> None:
    """Phase 2: 구(gu)별 CSV 분할"""
    from src.phase02_split_by_gu import run as sg_run  # type: ignore

    print("=" * 60)
    print("Phase 2: 구별 분할")
    print("=" * 60)

    in_path = str(_resolve(source))
    sg_run(input_path=in_path)
    print(f"\n  출력: data/processed/split_by_gu/")


def run_prepare(gu_list: list[str] | None, batch_size: int) -> None:
    """Phase 3a: Claude Code용 배치 입력 마크다운 생성"""
    from src.phase03_llm_analysis import run_prepare as p3_prepare  # type: ignore

    print("=" * 60)
    print("Phase 3a: 배치 입력 생성 (prepare)")
    print("=" * 60)

    p3_prepare(gu_list=gu_list, batch_size=batch_size)


def run_parse(gu_list: list[str] | None) -> None:
    """Phase 3b: Claude 응답 파싱"""
    from src.phase03_llm_analysis import run_parse as p3_parse  # type: ignore

    print("=" * 60)
    print("Phase 3b: Claude 응답 파싱 (parse)")
    print("=" * 60)

    p3_parse(gu_list=gu_list)


def run_merge() -> None:
    """Phase 3c: 최종 CSV 병합"""
    from src.phase03_llm_analysis import run_merge as p3_merge  # type: ignore

    print("=" * 60)
    print("Phase 3c: 최종 병합 (merge)")
    print("=" * 60)

    p3_merge(
        source_csv=FILTERED_CSV,
        output_csv=FINAL_CSV,
    )
    print(f"\n  출력: {FINAL_CSV}")


# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="UMC 분석 파이프라인 통합 실행",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
단계 설명:
  filter  Phase 1 — 키워드 필터링
  split   Phase 2 — 구별 CSV 분할
  prepare Phase 3a — Claude Code용 배치 입력 생성
  parse   Phase 3b — Claude 응답 파싱
  merge   Phase 3c — 최종 CSV 병합

사용 예:
  python main.py                            # 전체 (filter→split→prepare)
  python main.py --step filter split        # filter + split만
  python main.py --step prepare --batch-size 30
  python main.py --step prepare --gu 종로구
  python main.py --step parse merge         # 응답 파싱 후 병합
        """,
    )

    parser.add_argument(
        "--step",
        nargs="+",
        choices=PIPELINE_STEPS,
        default=None,
        metavar="STEP",
        help=(
            "실행할 단계 (기본: filter split prepare). "
            f"선택 가능: {', '.join(PIPELINE_STEPS)}"
        ),
    )
    parser.add_argument(
        "--source",
        default=DEFAULT_SOURCE,
        help=f"filter 단계 입력 CSV (기본: {DEFAULT_SOURCE})",
    )
    parser.add_argument(
        "--keywords",
        default=DEFAULT_KEYWORDS,
        help=f"키워드 YAML 파일 (기본: {DEFAULT_KEYWORDS})",
    )
    parser.add_argument(
        "--gu",
        nargs="+",
        default=None,
        metavar="구명",
        help="prepare/parse에서 처리할 구 목록 (기본: 전체). 예: --gu 종로구 강남구",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="prepare 배치 크기 — 건수/배치 (기본: 50)",
    )

    args = parser.parse_args()

    # 기본값: filter → split → prepare
    steps: list[str] = args.step if args.step else ["filter", "split", "prepare"]

    # 순서 보장 (사용자가 역순으로 입력해도 파이프라인 순서 유지)
    ordered_steps = [s for s in PIPELINE_STEPS if s in steps]

    print("=" * 60)
    print("🥕 UMC 분석 파이프라인")
    print(f"   실행 단계: {' → '.join(ordered_steps)}")
    print("=" * 60)

    for step in ordered_steps:
        print()

        if step == "filter":
            src = args.source
            # filter 단계는 01_cleaned_merged.csv가 없으면 02를 직접 입력 가능
            if not _resolve(src).exists():
                # 이미 필터링된 파일이 있으면 split부터 시작 가능
                if _resolve(FILTERED_CSV).exists():
                    print(f"⚠️  {src} 없음, 이미 {FILTERED_CSV} 존재 → filter 건너뜀")
                    continue
                else:
                    print(f"❌ 입력 파일 없음: {src}")
                    sys.exit(1)
            run_filter(src, args.keywords)

        elif step == "split":
            # split 입력: 필터링된 CSV
            split_src = FILTERED_CSV
            if not _resolve(split_src).exists():
                print(f"❌ {split_src} 없음. 먼저 filter 단계를 실행하세요.")
                sys.exit(1)
            run_split(split_src)

        elif step == "prepare":
            run_prepare(gu_list=args.gu, batch_size=args.batch_size)

        elif step == "parse":
            run_parse(gu_list=args.gu)

        elif step == "merge":
            run_merge()

    print()
    print("=" * 60)

    if "prepare" in ordered_steps and "parse" not in ordered_steps:
        print("✅ prepare 완료!")
        print()
        print("  다음 단계 (수동):")
        print("  1. data/processed/phase03_batches/*.md 를 확인하세요.")
        print("  2. Claude Code에서 CLAUDE.md 를 시스템 프롬프트로 설정한 후")
        print("     각 배치 파일을 분석하세요.")
        print("  3. 응답을 data/processed/phase03_responses/ 에")
        print("     동일한 파일명으로 저장하세요.")
        print("  4. python main.py --step parse merge")
    elif "merge" in ordered_steps:
        print(f"✅ 파이프라인 완료! 최종 결과: {FINAL_CSV}")
    else:
        print(f"✅ 단계 완료: {' → '.join(ordered_steps)}")

    print("=" * 60)


if __name__ == "__main__":
    main()
