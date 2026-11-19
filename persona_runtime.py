"""학습한 질문 분류기와 공식 근거를 연결하는 질의응답 및 Gradio 인터페이스."""
from pathlib import Path
import hashlib
import json
import re
import time
import joblib

PERIODS = ("2025-03-31", "2025-06-30")

LABELS = ["INVESTMENT_PRINCIPLE", "HOLDING_FACT", "HOLDING_CHANGE", "UNSUPPORTED"]

def digest(path):
    hasher = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(part)
    return hasher.hexdigest()

def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

ALIASES = {
    "037833100": ["애플", "AAPL"], "025816109": ["아메리칸 익스프레스", "아메리칸익스프레스", "AXP"],
    "060505104": ["뱅크오브아메리카", "뱅크 오브 아메리카", "BAC"], "191216100": ["코카콜라", "코카 콜라", "KO"],
    "166764100": ["셰브론", "쉐브론", "CVX"], "21036P108": ["컨스텔레이션", "콘스텔레이션", "STZ"],
    "670346105": ["누코", "뉴코", "NUCOR", "NUE"], "23331A109": ["디알호튼", "D R HORTON", "DHI"],
    "872590104": ["티모바일", "티 모바일", "T-MOBILE", "TMUS"], "91324P102": ["유나이티드헬스", "유나이티드 헬스", "UNH"],
    "674599105": ["옥시덴탈", "OXY"], "023135106": ["아마존", "AMZN"],
}

class EvidenceChat:
    """학습 모델은 질문 유형을 예측합니다. 답변 문장은 공식 근거에 템플릿을 적용합니다."""
    def __init__(self, model_dir, model_key=None):
        folder = Path(model_dir)
        if not (folder / "manifest.json").is_file():
            raise RuntimeError("학습 모델이 없습니다. project.ipynb의 두 모델 학습 셀을 실행합니다.")
        manifest = read_json(folder / "manifest.json")
        if manifest.get("training_complete") is not True:
            raise RuntimeError("학습 완료 모델이 아닙니다.")
        for name, expected in manifest["artifact_sha256"].items():
            if Path(name).name != name or not (folder / name).is_file() or digest(folder / name) != expected:
                raise RuntimeError("학습 파일이 없거나 변경됐습니다: " + name)
        import sklearn
        if sklearn.__version__ != manifest["sklearn_version"]:
            raise RuntimeError("학습 당시 scikit-learn 버전 " + manifest["sklearn_version"] + "을 설치하거나 현재 환경에서 재학습합니다.")
        self.key = model_key or manifest["selected_model"]
        if self.key not in manifest["models"]:
            raise ValueError("지원하지 않는 학습 모델")
        self.model = joblib.load(folder / (self.key + ".joblib"))
        self.retriever = joblib.load(folder / "retriever.joblib")
        self.knowledge = read_json(folder / "knowledge.json")
        self.by_id = {r["evidence_id"]: r for r in self.knowledge}
        self.manifest = manifest

    def entity(self, question, state):
        found = []
        for item in self.knowledge:
            payload = item["payload"]
            cusip = payload.get("cusip")
            if not cusip:
                continue
            aliases = [cusip, payload["issuer_name"], *ALIASES.get(cusip, [])]
            if any((len(alias) > 4 and alias.lower() in question.lower()) or re.search(r"(?<![A-Za-z0-9])" + re.escape(alias) + r"(?![A-Za-z0-9])", question, re.I) for alias in aliases):
                found.append(cusip)
        found = sorted(set(found))
        if len(found) > 1:
            raise ValueError("한 번에 한 증권의 이름 또는 CUSIP을 입력합니다.")
        return found[0] if found else state.get("cusip") if re.search(r"그|해당|그러면", question) else None

    def ask(self, question, state=None):
        if not isinstance(question, str) or not question.strip() or len(question) > 800:
            raise ValueError("질문은 1~800자로 입력합니다.")
        state = dict(state or {})
        started = time.perf_counter()
        followup = bool(state.get("last_question") and re.search(r"^(그|그러면|그럼|해당)", question.strip()))
        contextual = state["last_question"] + " 후속 질문: " + question if followup else question
        predicted = str(self.model.predict([contextual])[0])
        intent = predicted
        guard = None
        if re.search(r"왜.*(?:매수|매도|샀|팔)|(?:매수|매도|매매).*이유|매수한.*이유|(?:진짜|투자|매매|선택한).*동기|개인\s*계좌|비공개|목표\s*주가|수익.*보장|내일|다음\s*달|202[6-9]", question):
            intent, guard = "UNSUPPORTED", "범위·미확인 동기 보호 규칙"
        if re.search(r"[34]\s*분기|202[0-4]년.*보유", question):
            intent, guard = "UNSUPPORTED", "포함된 보고 기간 밖의 보유 질문"
        matches = re.findall(r"([12])\s*분기|Q([12])|2025-(03-31|06-30)", question, re.I)
        if matches and intent == "HOLDING_FACT":
            a, b, date = matches[-1]
            period = PERIODS[int(a or b) - 1] if a or b else "2025-" + date
        else:
            period = state.get("period", PERIODS[1]) if followup else PERIODS[1]
        cusip = self.entity(question, state) if intent in {"HOLDING_FACT", "HOLDING_CHANGE"} else None
        candidates = [i for i, item in enumerate(self.knowledge) if item["kind"] == intent]
        if intent == "HOLDING_FACT":
            candidates = [i for i in candidates if self.knowledge[i]["payload"].get("period_end") == period]
            if cusip:
                candidates = [i for i in candidates if self.knowledge[i]["payload"].get("cusip") == cusip]
            else:
                candidates = [i for i in candidates if self.knowledge[i]["payload"].get("cusip")]
        elif intent == "HOLDING_CHANGE" and cusip:
            candidates = [i for i in candidates if self.knowledge[i]["payload"].get("cusip") == cusip]
        chosen = []
        if intent == "UNSUPPORTED":
            chosen = [self.by_id["SCOPE_13F"]]
            answer = "확인할 수 없습니다. 이 프로젝트의 13F는 버크셔 기관의 공개 보유 기록이며 버핏 개인의 특정 매매 이유·체결 시점·개인 계좌·미래 주가를 입증하지 않습니다. 일반 원칙을 특정 거래의 동기로 연결하지 않습니다."
        elif intent in {"HOLDING_FACT", "HOLDING_CHANGE"} and not cusip and not re.search(r"어떤|목록|종목|증가|감소|변화|현황|보유.*회사|상위", question):
            answer = "조회할 증권의 회사명 또는 CUSIP을 입력해 주세요. 이름이 확인되지 않아 임의의 기업 자료로 대신 답하지 않았습니다."
        elif not candidates:
            if intent == "HOLDING_FACT" and cusip:
                chosen = [self.by_id["FILING_" + period]]
                answer = f"{period}의 포함된 공개 공시에서 해당 증권을 찾지 못했습니다. 기관 전체 보유가 0이거나 개인이 전량 매도했다는 뜻은 아닙니다."
            else:
                answer = "연결할 공식 근거를 찾지 못했습니다. 질문을 투자 원칙·2025년 1/2분기 보유·분기 변화 중 하나로 구체화해 주세요."
        else:
            if intent == "INVESTMENT_PRINCIPLE":
                scores = (self.retriever["matrix"] @ self.retriever["vectorizer"].transform([contextual]).T).toarray().ravel()
                ranked = sorted(candidates, key=lambda i: -scores[i])
                chosen = [self.knowledge[i] for i in ranked[:3] if scores[i] > 0]
                answer = "공식 주주서한의 원칙을 한국어로 요약합니다. 실제 인물의 새로운 발언을 생성하는 방식은 아닙니다.\n\n" + "\n\n".join(f'[{r["evidence_id"]}] {r["text"]}\n적용 조건: {r["payload"]["condition"]}' for r in chosen)
                if not chosen:
                    answer = "질문과 연결할 투자 원칙 근거를 찾지 못했습니다."
            else:
                if not cusip and intent == "HOLDING_CHANGE":
                    requested = "POSITION_INCREASED" if re.search(r"증가|늘|늘어난", question) else "POSITION_DECREASED" if re.search(r"감소|줄|줄어", question) else None
                    if requested:
                        candidates = [i for i in candidates if self.knowledge[i]["payload"]["change_label"] == requested]
                ranking = lambda i: self.knowledge[i]["payload"].get("market_value", abs(self.knowledge[i]["payload"].get("delta_shares", 0)))
                chosen = [self.knowledge[i] for i in sorted(candidates, key=ranking, reverse=True)[:3]]
                answer = "Berkshire Hathaway의 공개 신고 자료를 기준으로 설명합니다.\n\n" + "\n\n".join(f'[{r["evidence_id"]}] {r["text"]}' for r in chosen)
                if not cusip:
                    answer += f"\n\n해당 조건 {len(candidates)}건 중 최대 3건을 표시했습니다. 전체 조회는 정형화 데이터 파일을 확인합니다."
                if intent == "HOLDING_CHANGE":
                    answer += "\n\n보유 변화는 체결 기록이 아닙니다. 미신고는 비교 계산에서 0으로 두었고, 분할·합병·식별자 변경은 별도 확인하지 못했습니다. 매매 동기는 UNKNOWN입니다."
                else:
                    answer += f"\n\n보고 기준일은 {period}이며 제출일과 구분합니다. 수정 공시까지 포함한 사후 공개 자료 기준입니다."
        next_state = {"last_question": contextual[-1600:], "intent": intent, "period": period}
        if cusip:
            next_state["cusip"] = cusip
        return {"question": question, "model": self.key, "predicted_intent": predicted, "response_intent": intent, "guard_override": guard,
                "answer": answer, "evidence_ids": [r["evidence_id"] for r in chosen], "sources": [{"evidence_id": r["evidence_id"], "evidence_type": r["evidence_type"], "urls": r["source_urls"], "location": r["payload"].get("source_location")} for r in chosen],
                "state": next_state, "elapsed_seconds": time.perf_counter() - started}

def create_gradio(model_dir):
    try:
        import gradio as gr
    except ImportError as error:
        raise RuntimeError("Gradio가 없습니다. requirements.txt를 설치합니다.") from error
    engine = EvidenceChat(model_dir)
    def reply(message, history, state):
        try:
            result = engine.ask(message, state)
        except ValueError as error:
            return message, history or [], state or {}, "입력 오류: " + str(error)
        except Exception:
            return message, history or [], state or {}, "모델 추론 또는 근거 조회에 실패했습니다. 실행 로그와 학습 파일을 확인해 주세요."
        history = (history or []) + [{"role": "user", "content": message}, {"role": "assistant", "content": result["answer"]}]
        source_text = f'학습 모델: **{result["model"]}** · 예측 유형: `{result["predicted_intent"]}` · 응답 유형: `{result["response_intent"]}`\n\n'
        if result["guard_override"]:
            source_text += "근거 범위 보호 규칙 적용: " + result["guard_override"] + "\n\n"
        for source in result["sources"]:
            source_text += f'- `{source["evidence_id"]}` · {source["evidence_type"]} · {source["location"] or "SEC 공시/자료 범위"}\n'
            source_text += "\n".join("  - [공식 출처](" + url + ")" for url in source["urls"]) + "\n"
        return "", history, result["state"], source_text
    with gr.Blocks(title="워런 버핏 투자 원칙 분석 챗봇") as demo:
        gr.Markdown("# 워런 버핏 투자 원칙 분석 챗봇\n직접 학습한 **질문 유형 분류기**와 공식 근거로 답변을 구성합니다. 버핏 본인의 새 발언·매매 조언을 생성하지 않습니다.")
        state = gr.State({})
        history = gr.Chatbot(height=430)
        message = gr.Textbox(label="질문", placeholder="버핏은 장기투자를 어떻게 바라보나요?", max_lines=4)
        with gr.Row():
            send, reset = gr.Button("질문하기", variant="primary"), gr.Button("대화 초기화")
        sources = gr.Markdown("공식 출처와 모델의 예측 유형이 여기에 표시됩니다.")
        gr.Examples(["워런 버핏은 장기투자를 어떻게 바라보나요?", "2025년 1분기 애플 보유 수량은 얼마인가요?", "그럼 2분기는요?", "분기 사이 컨스텔레이션 보유량은 어떻게 변했나요?", "왜 애플을 매수했나요?"], inputs=message)
        send.click(reply, [message, history, state], [message, history, state, sources], concurrency_limit=1)
        message.submit(reply, [message, history, state], [message, history, state, sources], concurrency_limit=1)
        reset.click(lambda: ("", [], {}, "새 대화를 시작합니다."), outputs=[message, history, state, sources], queue=False)
    return demo.queue()
