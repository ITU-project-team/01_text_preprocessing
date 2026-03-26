"""
Phase 00: 데이터 필터링 및 병합 (Data Cleaning)

원본 청크 파일들(daangn_chunk_*.csv)을 불러와
DELETED, BLOCKED 및 빈 게시글을 필터링한 후 하나의 파일로 병합합니다.
"""

import os
import glob
import pandas as pd  # type: ignore
import io
from pathlib import Path
from src.phase01_keyword_filter import filter_deleted_posts  # type: ignore

def run(input_dir: str = "data/raw", output_path: str = "data/processed/01_cleaned_merged.csv") -> None:
    """원시 청크 파일들을 병합하고 필터링을 수행합니다."""
    
    all_files = sorted(glob.glob(os.path.join(input_dir, "daangn_chunk_*.csv")))
    
    if not all_files:
        print(f"❌ {input_dir} 에 'daangn_chunk_*.csv' 파일이 없습니다. 크롤링 데이터를 확인하세요.")
        return

    print(f"📌 [시작] 총 {len(all_files)}개의 CSV 파일을 순차적으로 필터링합니다.\n")

    df_list = []
    total_initial_rows = 0
    total_filtered_rows = 0

    for file in all_files:
        file_name = os.path.basename(file)
        try:
            try:
                # 1. 정상적인 파일 로드
                df_chunk = pd.read_csv(file, encoding="utf-8", low_memory=False)
            except Exception as e:
                # 1-1. EOF inside string 에러 발생 시 (크롤링 중단 등으로 파일 끝부분이 짤린 경우)
                if 'EOF inside string' in str(e):
                    print(f"   ⚠️ {file_name}: 맨 앞/끝 줄 짤림 감지됨. 손상된 데이터 제외 후 복구 중...")
                    with open(file, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    
                    # 마지막 줄(짤린 줄) 버리고 읽기
                    clean_text = "".join(lines[:-1])  # type: ignore[index]
                    df_chunk = pd.read_csv(io.StringIO(clean_text), low_memory=False)
                else:
                    raise e

            initial_len = len(df_chunk)
            total_initial_rows += initial_len
            
            # 행 번호 및 출처 파일 추적을 위한 컬럼 추가
            df_chunk['origin_file'] = file_name
            df_chunk['origin_row'] = range(2, len(df_chunk) + 2)
            
            # 2. DELETED, BLOCKED 및 빈 내용 게시글 필터링 수행
            df_filtered = filter_deleted_posts(df_chunk)
            filtered_len = len(df_filtered)
            total_filtered_rows += filtered_len
            
            # 3. 정제된 데이터만 리스트에 보관
            if filtered_len > 0:
                df_list.append(df_filtered)
                
            print(f"✔ {file_name} 처리 완료: {initial_len:,}행 -> {filtered_len:,}행")
            
        except Exception as e:
            print(f"❌ {file_name} 처리 불가: {e}")

    print("\n" + "=" * 50)
    print(f"📊 [필터링 누적 결과] 총 원본: {total_initial_rows:,}행 -> 총 정제됨: {total_filtered_rows:,}행")
    print("=" * 50 + "\n")

    # 4. 정제된 데이터들만 모아서 최종 병합
    if df_list:
        print("🔄 정제된 데이터를 하나로 병합 중입니다...")
        merged_df = pd.concat(df_list, ignore_index=True)
        
        if 'dbId' in merged_df.columns:
            # 중복 의심 데이터 상세 분석
            duplicate_mask = merged_df.duplicated(subset=['dbId'], keep=False)
            duplicates_df = merged_df[duplicate_mask]
            
            if not duplicates_df.empty:
                print(f"\n🚨 중복된 데이터가 감지되었습니다. 원본 기준 {len(duplicates_df['dbId'].unique())}개의 게시물이 중복 저장되었습니다.")
                
                # 실제 중복 제거 (가장 처음 마주친 데이터만 남김)
                before_dedup = len(merged_df)
                merged_df = merged_df.drop_duplicates(subset=['dbId'])
                print(f"\n정보: {before_dedup - len(merged_df):,}건의 중복 데이터를 성공적으로 제거했습니다.")
            else:
                print("\n정보: 발견된 중복 데이터가 없습니다.")

        # 저장 시 분석용으로 썼던 위치 칼럼 제거
        if 'origin_file' in merged_df.columns:
            merged_df = merged_df.drop(columns=['origin_file', 'origin_row'])

        # 결과물 저장
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        merged_df.to_csv(output_path, index=False, encoding="utf-8-sig")
        print(f"\n✅ 최종 데이터 병합 및 저장 완료!")
        print(f"   - 최종 게시물 수: {len(merged_df):,}개")
        print(f"   - 저장 경로: {output_path}")
    else:
        print("병합할 데이터가 존재하지 않습니다.")

if __name__ == "__main__":
    run()
