# 당근마켓 텍스트 전처리 파이프라인

UMC(Universal Meaningful Connectivity) 차원 분류 전처리 프로젝트입니다.

## 에이전트 워크플로우 (Phase 3)

텍스트 분류 작업은 UMC Classifier Subagent를 통해 진행합니다. 

1. `python main.py --step prepare` 실행 → `data/processed/phase03_batches/` 에 입력 생성
2. `/agent umc_classifier` 로 에이전트 호출, 혹은 아래처럼 단일 명령 지시
   ```
   /agent umc_classifier data/processed/phase03_batches/종로구_batch001.md 파일을 읽고 분석한 뒤 응답을 data/processed/phase03_responses/종로구_batch001.md 에 저장해
   ```
3. `python main.py --step parse merge` 로 최종 CSV 병합
