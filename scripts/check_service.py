"""실행 중인 Gradio HTTP API에서 저장 모델 표시·출처·후속 질문·입력 오류를 확인한다."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path


def check(url):
    from gradio_client import Client

    client = Client(url, verbose=False)
    schema = client.view_api(return_format="dict")
    endpoints = schema.get("named_endpoints", {})
    names = sorted(name for name in endpoints if name.startswith("/reply"))
    if not names:
        raise RuntimeError("질의응답 API를 찾지 못했습니다. 서비스의 API 목록을 확인합니다.")
    endpoint = names[0]
    if len(endpoints[endpoint].get("parameters", [])) != 2:
        raise RuntimeError("API 입력 형식이 예상과 다릅니다. message와 history 입력을 확인합니다.")
    questions = ["워런 버핏은 장기투자를 어떻게 바라보나요?", "2025년 1분기 애플 보유 수량은 얼마인가요?",
                 "그럼 2분기는요?", "분기 사이 컨스텔레이션 보유량은 어떻게 변했나요?", "왜 애플을 매수했나요?"]
    history, records = [], []
    for question in questions:
        result = client.predict(question, history, api_name=endpoint)
        if not isinstance(result, (tuple, list)) or len(result) != 3:
            raise RuntimeError("API 출력 형식이 예상과 다릅니다.")
        _, history, sources = result
        answer = history[-1]["content"]
        if not isinstance(answer, str):
            raise RuntimeError("답변 텍스트 형식을 확인할 수 없습니다.")
        if "word_tfidf_logreg" not in sources:
            raise AssertionError("기존 최종 모델의 표시를 확인할 수 없습니다.")
        records.append({"question": question, "answer": answer, "sources": sources})
    assert "P2020_1" in records[0]["sources"]
    assert "300,000,000" in records[1]["answer"]
    assert "280,000,000" in records[2]["answer"]
    assert "+1,391,000" in records[3]["answer"] and "UNKNOWN" in records[3]["answer"]
    assert "확인할 수 없습니다" in records[4]["answer"] and "SCOPE_13F" in records[4]["sources"]
    invalid = client.predict("", history, api_name=endpoint)
    assert "입력 오류" in invalid[-1]
    return {"service_url": url, "checked_at_utc": datetime.now(timezone.utc).isoformat(),
            "endpoint": endpoint, "question_cases_passed": len(records), "input_error_passed": True,
            "retrained": False, "test_metrics_recomputed": False, "records": records}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="실제로 실행 중인 로컬 또는 workers.dev 주소")
    parser.add_argument("--output", type=Path, help="실제 검사 결과를 새 JSON 파일로 저장")
    args = parser.parse_args()
    if not args.url.startswith(("http://", "https://")):
        parser.error("HTTP(S) 주소를 입력합니다.")
    result = check(args.url.rstrip("/"))
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(text)
    print(text)
