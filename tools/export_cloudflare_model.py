"""Export EXISTING, already-fitted sklearn classifiers to browser JSON.
This converter never calls .fit(), never alters the original joblib files.
Compatible with project.ipynb: word TF-IDF + multinomial Logistic Regression,
and char TF-IDF retrieval for principle evidence.
"""
import hashlib
import json
import os
from pathlib import Path
import tempfile
from zipfile import ZipFile

import joblib
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'cloudflare' / 'public'


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def locate_artifacts():
    # Prefer directory-based saved models. Ignore previous test/build outputs.
    paths = [p for p in ROOT.rglob('manifest.json') if '.git' not in p.parts and 'cloudflare' not in p.parts]
    paths = [p for p in paths if (p.parent / 'knowledge.json').is_file() and (p.parent / 'word_tfidf_logreg.joblib').is_file()]
    if paths:
        paths.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return paths[0].parent, None
    archives = sorted([p for p in ROOT.rglob('*.zip') if 'model' in p.stem.lower() and 'form13f' not in p.stem.lower()], key=lambda p: p.stat().st_mtime, reverse=True)
    for archive_path in archives:
        with ZipFile(archive_path) as z:
            names = z.namelist()
            matches = [name for name in names if name.endswith('/manifest.json') and '/models/' in '/' + name]
            for name in matches:
                prefix = name.rsplit('/', 1)[0]
                needed = [prefix + '/' + filename for filename in ('knowledge.json', 'word_tfidf_logreg.joblib', 'retriever.joblib')]
                if not all(n in names for n in needed):
                    continue
                temp = tempfile.TemporaryDirectory()
                dest = Path(temp.name)
                for n in names:
                    if n.startswith(prefix + '/') and not n.endswith('/'):
                        path = (dest / Path(n).name)
                        # Extract only members directly under model directory; no traversal.
                        if n.count('/') == prefix.count('/') + 1:
                            path.write_bytes(z.read(n))
                return dest, temp
    raise FileNotFoundError(
        '학습 모델을 찾지 못했습니다. GitHub 저장소에 manifest.json, knowledge.json, '
        'word_tfidf_logreg.joblib, retriever.joblib가 같은 models 폴더 안에 있거나 '
        'buffett_model_results*.zip 파일이 있어야 합니다. 기존 모델을 재학습하거나 대체하지 않습니다.'
    )


def verify(directory):
    manifest = read_json(directory / 'manifest.json')
    if manifest.get('training_complete') is not True:
        raise RuntimeError('학습 완료된 manifest가 아닙니다.')
    for filename, expected in manifest.get('artifact_sha256', {}).items():
        path = directory / filename
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError(f'모델 무결성 검증 실패: {filename}')
    return manifest


def export():
    directory, temporary = locate_artifacts()
    try:
        manifest = verify(directory)
        selected = manifest.get('selected_model', 'word_tfidf_logreg')
        if selected != 'word_tfidf_logreg':
            raise RuntimeError('이 배포 변환기는 최종 선택된 word_tfidf_logreg 모델만 지원합니다. 모델을 몰래 바꾸지 않습니다.')
        model_file = directory / (selected + '.joblib')
        model = joblib.load(model_file)
        vectorizer, classifier = model['tfidf'], model['classifier']
        if vectorizer.analyzer != 'word' or vectorizer.ngram_range != (1, 2):
            raise RuntimeError('원본 단어 TF-IDF 구성이 예상과 다릅니다.')
        if classifier.__class__.__name__ != 'LogisticRegression':
            raise RuntimeError('최종 모델이 LogisticRegression이 아닙니다.')
        classes = classifier.classes_.tolist()
        if len(classes) != 4 or classifier.coef_.shape != (4, len(vectorizer.vocabulary_)):
            raise RuntimeError('질문 분류기 출력 형식이 다릅니다.')
        features = {
            'model_name': selected, 'training_complete': True,
            'classes': classes,
            'vocabulary': vectorizer.vocabulary_,
            'idf': vectorizer.idf_.tolist(),
            'coef': classifier.coef_.tolist(), 'intercept': classifier.intercept_.tolist(),
            'ngram_range': list(vectorizer.ngram_range),
            'sublinear_tf': bool(vectorizer.sublinear_tf),
            'norm': vectorizer.norm, 'lowercase': bool(vectorizer.lowercase),
            'source_sha256': hashlib.sha256(model_file.read_bytes()).hexdigest(),
            'test_predictions': [
                {'question': q, 'expected': str(model.predict([q])[0])}
                for q in [
                    '워런 버핏은 장기투자를 어떻게 바라보나요?',
                    '2025년 1분기 애플 보유 수량은 얼마인가요?',
                    '그럼 2분기는요?',
                    '분기 사이 컨스텔레이션 보유량은 어떻게 변했나요?',
                    '왜 애플을 매수했나요?'
                ]
            ]
        }
        knowledge = read_json(directory / 'knowledge.json')
        retr = joblib.load(directory / 'retriever.joblib')
        rtvec, matrix = retr['vectorizer'], retr['matrix'].tocsr()
        if rtvec.analyzer != 'char' or rtvec.ngram_range != (2, 5):
            raise RuntimeError('근거 검색기 문자 TF-IDF 구성이 예상과 다릅니다.')
        principle_rows = []
        for i, r in enumerate(knowledge):
            if r['kind'] == 'INVESTMENT_PRINCIPLE':
                row = matrix.getrow(i)
                principle_rows.append({'knowledge_index': i,
                    'indices': row.indices.tolist(), 'values': row.data.tolist()})
        retrieval = {
            'vocabulary': rtvec.vocabulary_, 'idf': rtvec.idf_.tolist(),
            'ngram_range': [2, 5], 'rows': principle_rows,
            'source': 'saved retriever.joblib (not retrained)'
        }
        OUT.mkdir(parents=True, exist_ok=True)
        for name, obj in [('model.json', features), ('knowledge.json', knowledge), ('retriever.json', retrieval)]:
            p = OUT / name
            p.write_text(json.dumps(obj, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
            print(name, p.stat().st_size, 'bytes')
        print('Selected trained model:', selected, 'SHA256:', features['source_sha256'])
        print('Knowledge:', len(knowledge), 'entries; principles:', len(principle_rows))
    finally:
        if temporary is not None:
            temporary.cleanup()

if __name__ == '__main__':
    export()
