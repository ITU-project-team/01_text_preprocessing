"""
Phase 3: LLM 기반 UMC 차원 분류 및 감성 분석

이 스크립트는 `sample_for_claude.py`와 동일한 아키텍처를 사용하여
Phase 3 분석용 프롬프트 파일(MarkDown)과 정제된 데이터 파일(CSV)을 생성하고 결과를 병합합니다.

명령어:
  python -m src.phase03_llm_analysis prepare --input data/processed/split_by_gu/종로구.csv
  python -m src.phase03_llm_analysis merge --input data/processed/split_by_gu/종로구.csv --response prompts/phase03_responses/종로구.json
"""

import argparse
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import pandas as pd  # type: ignore

PROJECT_ROOT = Path(__file__).resolve().parent.parent

UMC_DIMENSION_LABELS = {
    "connection_quality": "통신 인프라 수준 (4G/5G, 다운로드 속도 등)",
    "availability_for_use": "디지털 서비스 접근 가능성 (WiFi, 데이터 사용량 등)",
    "affordability": "경제적 부담 수준 (요금, 통신비 등)",
    "devices": "기기 접근성 (스마트폰, PC 보유 등)",
    "digital_skills": "디지털 역량 (앱 조작, 사이버 활동 숙련도 등)",
    "safety_and_security": "안전/보안 인식 (해킹, 사기, 개인정보 등)"
}

def _resolve(rel: str) -> Path:
    return PROJECT_ROOT / rel

def build_prompt(sample_df: pd.DataFrame, gu_name: str, max_posts: int = 50) -> str:
    """Claude Sonnet에 전달할 프롬프트를 마크다운으로 생성합니다."""
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
        truncated = combined[:300] + ("..." if len(combined) > 300 else "")  # type: ignore
        text_lines.append(f"[{i+1}] ({gu_name}) {truncated}")

    texts_formatted = "\n".join(text_lines)

    extra_note = ""
    if len(sample_df) > max_posts:
        extra_note = (
            f"\n> **참고**: 전체 샘플은 {len(sample_df)}건이며, 위에는 {max_posts}건만 표시됩니다.\n"
            "전체 분석 대상은 함께 제공되는 CSV 파일을 참조하세요.\n"
        )

    prompt = f"""# 분석 대상: {gu_name} 게시글 (Phase 3)

당신은 한국어 텍스트 분석 및 UMC 연결형 격차 분석 전문가입니다.
동봉된 CSV 파일의 **모든 행**을 읽고, 다음 6개의 UMC 차원에 해당하는지 식별한 뒤 감성(Positive/Negative)을 판단하세요.

---

## UMC 6개 차원

{dimensions_desc}

---

## 분석 규칙

1. 각 게시물의 내용(title, content)을 보고 어떠한 차원들에 접점이 있는지 파악하세요. (한 게시물에 여러 차원이 해당될 수 있습니다.)
2. 각 차원에 대해, 내용이 긍정적 측면을 띄면 "Positive", 불편/부정적 측면이면 "Negative"로 평가하세요.
3. 어떠한 차원에도 관련된 내용이 없다면, 차원에 "해당없음"을 지정하고 감성은 `null`로 출력하세요.
4. 반드시 제공된 샘플 형식처럼 JSON Array 형식으로만 답변을 출력하세요. 처리한 모든 행에 대해 누락 없이 결과 JSON 파일 하나를 반환해 주세요.

---

## 게시글 프리뷰 ({len(display_df)}건 / 전체 {len(sample_df)}건)
{extra_note}
{texts_formatted}

---

## 출력 스키마 (Few-shot 예시)

```json
[
  {{
    "dbId": "sample_1",
    "classifications": [
      {{"dimension": "connection_quality", "sentiment": "Negative"}},
      {{"dimension": "devices", "sentiment": "Positive"}}
    ]
  }},
  {{
    "dbId": "sample_2",
    "classifications": [
      {{"dimension": "해당없음", "sentiment": null}}
    ]
  }}
]
```
"""
    return prompt


def run_prepare(
    input_path: Path, 
    output_prompt_dir: Path, 
    sample_size: Optional[int] = None
) -> None:
    if not input_path.exists():
        print(f"❌ 파일을 찾을 수 없습니다: {input_path}")
        return

    df = pd.read_csv(input_path, encoding="utf-8")
    gu_name = input_path.stem

    if 'dbId' not in df.columns:
        print("⚠️ 'dbId' 컬럼이 없어 임시 id를 부여합니다.")
        df['dbId'] = [f"{gu_name}_{i}" for i in range(len(df))]

    output_prompt_dir.mkdir(parents=True, exist_ok=True)

    if sample_size is not None:
        # 테스트 추출 모드: 개수 제한 및 새로운 샘플 CSV 파일 생성
        export_df = df.sample(n=min(sample_size, len(df)), random_state=42)
        keep_cols = ['dbId', 'title', 'content']
        for col in keep_cols:
            if col not in export_df.columns:
                export_df[col] = ""
        export_df = export_df[keep_cols]
        
        sample_dir = _resolve("data/processed/phase03_test_samples")
        sample_dir.mkdir(parents=True, exist_ok=True)
        target_csv_path = sample_dir / f"{gu_name}.csv"
        export_df.to_csv(target_csv_path, index=False, encoding="utf-8-sig")
        target_csv_rel = f"data/processed/phase03_test_samples/{gu_name}.csv"
        df_for_prompt = export_df
    else:
        # 전체 실행 모드: 원본 그대로 참조
        target_csv_rel = f"data/processed/split_by_gu/{gu_name}.csv"
        df_for_prompt = df

    print(f"\n[1/1] {gu_name} 전용 프롬프트 생성...")
    prompt_str = build_prompt(df_for_prompt, gu_name=gu_name, max_posts=50)
    
    # 편향 방지를 위해 프롬프트 내에 메타데이터 무시 지시문 추가
    instruction_addon = f"""
> **데이터 읽기 주의사항 (중요)**:
> 제공된 파일(`{target_csv_rel}`)을 기반으로 분석하되, 
> LLM 평가의 편향을 방지하기 위해 파일 내에 존재하는 `title`과 `content` 컬럼의 게시글 본문만 읽고 진행하세요. 
> 분석할 때 기존에 존재하는 차원이나 기타 메타데이터 컬럼은 철저히 무시/제외해야 합니다.
"""
    prompt_str = prompt_str.replace("---", instruction_addon + "\n---", 1)

    prompt_md_path = output_prompt_dir / f"prompt_{gu_name}.md"
    
    with open(prompt_md_path, "w", encoding="utf-8") as f:
        f.write(prompt_str)
    print(f"  ✅ 프롬프트 MD 저장: {prompt_md_path}\n")


def run_merge(input_path: Path, response_path: Path, output_path: Path) -> None:
    if not input_path.exists():
        print(f"❌ 원본 파일을 찾을 수 없습니다: {input_path}")
        return

    if not response_path.exists():
        print(f"❌ 응답 JSON 파일을 찾을 수 없습니다: {response_path}")
        return

    gu_name = input_path.stem
    print(f"\n[1/3] 원본 데이터({gu_name}) 로딩 및 준비...")
    df = pd.read_csv(input_path, encoding='utf-8')
    if 'dbId' not in df.columns:
        df['dbId'] = [f"{gu_name}_{i}" for i in range(len(df))]
    df['dbId'] = df['dbId'].astype(str)

    print(f"\n[2/3] Claude JSON 응답 로딩 및 파싱: {response_path.name}")
    with open(response_path, "r", encoding="utf-8") as f:
        content = f.read()

    json_match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_str = content.strip()

    try:
        parsed_results = json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"❌ JSON 파싱 실패: {e}")
        return

    results_map = {}
    for item in parsed_results:
        dbid = str(item.get("dbId", ""))
        cls_list = item.get("classifications", [])
        if dbid:
            results_map[dbid] = cls_list

    def map_classifications(row_id):
        return json.dumps(results_map.get(row_id, []), ensure_ascii=False)

    df['umc_classifications'] = df['dbId'].apply(map_classifications)
    valid_count = len(df[df['umc_classifications'] != "[]"])
    print(f"  매핑 성공 건수: {valid_count:,} / 전체 {len(df):,}건")

    print(f"\n[3/3] 최종 CSV 저장: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding='utf-8-sig')


def cmd_prepare(args):
    input_path = _resolve(args.input)
    output_prompt_dir = _resolve(args.output_prompt_dir)
    run_prepare(input_path, output_prompt_dir, sample_size=args.sample_size)

def cmd_merge(args):
    input_path = _resolve(args.input)
    response_path = _resolve(args.response)
    
    if args.output:
        out_path = _resolve(args.output)
    else:
        out_path = _resolve(f"data/processed/phase03_analyzed/{input_path.stem}.csv")

    run_merge(input_path, response_path, out_path)

def main():
    parser = argparse.ArgumentParser(description="Phase 3 데이터 준비 및 LLM 응답 병합")
    subparsers = parser.add_subparsers(dest="command")

    sp_prep = subparsers.add_parser("prepare", help="MD 프롬프트 생성")
    sp_prep.add_argument("--input", required=True, help="원본 구(gu) 단위 CSV 파일 경로")
    sp_prep.add_argument("--output-prompt-dir", default="prompts/phase03", help="프롬프트 마크다운 저장 경로")
    sp_prep.add_argument("--sample-size", type=int, default=None, help="테스트용 샘플 개수 제한 (기본값: 전체)")

    sp_merge = subparsers.add_parser("merge", help="Claude 응답 병합")
    sp_merge.add_argument("--input", required=True, help="원본 구(gu) 단위 CSV 파일 경로")
    sp_merge.add_argument("--response", required=True, help="응답 JSON 경로 (예: prompts/phase03_responses/종로구.json)")
    sp_merge.add_argument("--output", help="최종 저장 경로 (기본값: phase03_analyzed 내 자동 할당)")

    args = parser.parse_args()

    if args.command == "prepare":
        cmd_prepare(args)
    elif args.command == "merge":
        cmd_merge(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
