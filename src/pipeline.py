"""
텍스트 전처리 통합 파이프라인

2단계 전처리를 순차적으로 실행합니다:
  1. 키워드 필터링 (filter_by_keyword)
  2. Kiwi 텍스트 정규화 (normalize) — 띄어쓰기 교정 + 형태소 분석 + 품사 기반 필터링
"""

import argparse
from pathlib import Path

from src import filter_by_keyword, normalize  # type: ignore



def run_pipeline(
    input_path: str,
    output_dir: str = "data/processed",
    keywords_path: str = "config/keywords.yaml",
    steps: list[str] | None = None,
):
    """전체 전처리 파이프라인을 실행합니다.

    Args:
        input_path: 원본 CSV 파일 경로
        output_dir: 출력 디렉토리
        keywords_path: 키워드 YAML 파일 경로
        steps: 실행할 단계 리스트 (None이면 전체 실행)
                가능한 값: ["filter", "normalize"]
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    all_steps = ["filter", "normalize"]
    if steps is None:
        steps = all_steps

    current_input = input_path

    print("=" * 60)
    print("텍스트 전처리 파이프라인 시작")
    print(f"  입력: {input_path}")
    print(f"  출력: {output_dir}")
    print(f"  실행 단계: {', '.join(steps)}")
    print("=" * 60)

    # Step 1: 키워드 필터링
    if "filter" in steps:
        filtered_path = str(output_path / "01_filtered.csv")
        filter_by_keyword.run(
            input_path=current_input,
            output_path=filtered_path,
            keywords_path=keywords_path,
        )
        current_input = filtered_path
        print()

    # Step 2: Kiwi 텍스트 정규화 (띄어쓰기 + 형태소 + 품사 필터링)
    if "normalize" in steps:
        normalized_path = str(output_path / "02_normalized.csv")
        normalize.run(
            input_path=current_input,
            output_path=normalized_path,
        )
        print()

    print("=" * 60)
    print("✅ 전처리 파이프라인 완료!")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="당근마켓 텍스트 전처리 파이프라인",
    )
    parser.add_argument(
        "--input",
        required=True,
        help="입력 CSV 파일 경로 (예: data/raw/seoul.csv)",
    )
    parser.add_argument(
        "--output-dir",
        default="data/processed",
        help="출력 디렉토리 (기본: data/processed)",
    )
    parser.add_argument(
        "--keywords",
        default="config/keywords.yaml",
        help="키워드 YAML 파일 경로 (기본: config/keywords.yaml)",
    )
    parser.add_argument(
        "--step",
        nargs="+",
        choices=["filter", "normalize"],
        default=None,
        help="특정 단계만 실행 (기본: 전체). 예: --step filter",
    )

    args = parser.parse_args()

    run_pipeline(
        input_path=args.input,
        output_dir=args.output_dir,
        keywords_path=args.keywords,
        steps=args.step,
    )


if __name__ == "__main__":
    main()
