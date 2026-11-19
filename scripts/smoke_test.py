"""저장 가중치로 질의응답 기능, 대화 맥락, 입력 예외 처리를 검증한다."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from unittest.mock import patch

from check_package import inspect_package

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    readiness = inspect_package()
    if not readiness["local_inference_ready"]:
        raise RuntimeError("실제 모델 또는 실행 환경이 준비되지 않았습니다: " + "; ".join(readiness["failures"] + readiness["pending"]))
    from persona_runtime import EvidenceChat, create_gradio
    with patch("sklearn.pipeline.Pipeline.fit", side_effect=AssertionError("배포 중 재학습 호출 금지")):
        engine = EvidenceChat(ROOT / "models")
        records, state = [], {}
        questions = ["워런 버핏은 장기투자를 어떻게 바라보나요?", "2025년 1분기 애플 보유 수량은 얼마인가요?",
                     "그럼 2분기는요?", "분기 사이 컨스텔레이션 보유량은 어떻게 변했나요?", "왜 애플을 매수했나요?"]
        for question in questions:
            result = engine.ask(question, state)
            records.append(result)
            state = result["state"]
        assert records[0]["evidence_ids"]
        assert "300,000,000" in records[1]["answer"]
        assert "280,000,000" in records[2]["answer"] and records[2]["state"].get("cusip") == "037833100"
        assert "+1,391,000" in records[3]["answer"] and "UNKNOWN" in records[3]["answer"]
        assert records[4]["response_intent"] == "UNSUPPORTED" and records[4]["evidence_ids"] == ["SCOPE_13F"]
        for invalid in ("", " " * 4, "가" * 801):
            try:
                engine.ask(invalid)
            except ValueError:
                pass
            else:
                raise AssertionError("입력 오류 처리가 없습니다.")
        fresh = engine.ask(questions[0])
        assert "cusip" not in fresh["state"]
        demo = create_gradio(ROOT / "models")
        demo.close()
    output = ROOT / "reports" / ("deployment_smoke_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".json")
    record = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "records": records,
              "training_called": False, "test_metrics_recomputed": False, "external_prediction_verified": False}
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("저장 가중치 추론·후속 질문·입력 오류·Gradio 생성 검사 통과:", output)


if __name__ == "__main__":
    main()
