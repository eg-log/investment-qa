'use strict';
// Browser-only deployment adapter for the ALREADY FITTED sklearn model.
// No model training, no external LLM API, no paid Cloudflare container.
const PERIODS=['2025-03-31','2025-06-30'];
const ALIASES={
  '037833100':['애플','AAPL'],'025816109':['아메리칸 익스프레스','아메리칸익스프레스','AXP'],
  '060505104':['뱅크오브아메리카','뱅크 오브 아메리카','BAC'],'191216100':['코카콜라','코카 콜라','KO'],
  '166764100':['셰브론','쉐브론','CVX'],'21036P108':['컨스텔레이션','콘스텔레이션','STZ'],
  '670346105':['누코','뉴코','NUCOR','NUE'],'23331A109':['디알호튼','D R HORTON','DHI'],
  '872590104':['티모바일','티 모바일','T-MOBILE','TMUS'],'91324P102':['유나이티드헬스','유나이티드 헬스','UNH'],
  '674599105':['옥시덴탈','OXY'],'023135106':['아마존','AMZN']};
let model=null, knowledge=null, retriever=null, state={};
const $=id=>document.getElementById(id);
function tfidf(text,conf){
  // Matches Python TfidfVectorizer(analyzer='word', token_pattern=r'(?u)\b\w+\b', ngram_range=(1,2), sublinear_tf=True)
  const words=(String(text).toLowerCase().match(/[\p{L}\p{N}\p{M}_]+/gu)||[]);
  const counts=new Map(); const add=x=>counts.set(x,(counts.get(x)||0)+1);
  for(let i=0;i<words.length;i++){add(words[i]);if(i+1<words.length)add(words[i]+' '+words[i+1]);}
  const pairs=[];let sum=0;
  for(const [feature,count] of counts){const idx=conf.vocabulary[feature];if(idx===undefined)continue;
    const tf=conf.sublinear_tf?1+Math.log(count):count;const v=tf*conf.idf[idx];pairs.push([idx,v]);sum+=v*v;}
  if(sum>0){const norm=Math.sqrt(sum);for(const row of pairs)row[1]/=norm;}
  return pairs;
}
function predict(question){
  const vector=tfidf(question,model);
  const scores=model.intercept.map((intercept,i)=>{
    let result=intercept;const coef=model.coef[i];for(const [idx,val] of vector)result+=coef[idx]*val;return result;});
  let index=0;for(let i=1;i<scores.length;i++)if(scores[i]>scores[index])index=i;
  return model.classes[index];
}
function retrievePrinciples(query){
  const text=query.toLowerCase().replace(/\s{2,}/g,' ');const ngrams=new Map();
  for(let n=2;n<=5;n++)for(let i=0;i+n<=text.length;i++){const g=text.slice(i,i+n);ngrams.set(g,(ngrams.get(g)||0)+1);}
  const vector=new Map();let norm=0;
  for(const [g,count] of ngrams){const idx=retriever.vocabulary[g];if(idx===undefined)continue;
    const v=count*retriever.idf[idx];vector.set(idx,v);norm+=v*v;}
  norm=Math.sqrt(norm);if(norm===0)return [];
  for(const [k,v] of vector)vector.set(k,v/norm);
  return retriever.rows.map(row=>({i:row.knowledge_index,score:row.indices.reduce((s,idx,j)=>s+(vector.get(idx)||0)*row.values[j],0)}))
    .filter(row=>row.score>0).sort((a,b)=>b.score-a.score).slice(0,3).map(row=>knowledge[row.i]);
}
function matchAlias(text,alias){
  const lower=String(text).toLowerCase(), a=String(alias).toLowerCase();
  if(a.length>4 && lower.includes(a))return true;
  const start=lower.indexOf(a);if(start<0)return false;
  // Respect ASCII ticker/CUSIP boundaries, avoid 'KO' inside an English word.
  const ascii=/^[a-z0-9]+$/i.test(a);if(!ascii)return true;
  const before=lower[start-1]||'',after=lower[start+a.length]||'';
  return !/[a-z0-9]/.test(before)&&!/[a-z0-9]/.test(after);
}
function entity(question,prev){
  const found=new Set();
  for(const r of knowledge){const p=r.payload||{};if(!p.cusip)continue;
    const aliases=[p.cusip,p.issuer_name||'',...(ALIASES[p.cusip]||[])].filter(Boolean);
    if(aliases.some(a=>matchAlias(question,a)))found.add(p.cusip);
  }
  if(found.size>1)throw Error('한 번에 한 증권의 이름 또는 CUSIP을 입력합니다.');
  return found.size?[...found][0]:/(그|해당|그러면)/.test(question)?prev.cusip||null:null;
}
function ask(question,prev={}){
  if(!question||!question.trim()||question.length>800)throw Error('질문은 1~800자로 입력합니다.');
  const followup=!!(prev.last_question&&/^(그|그러면|그럼|해당)/.test(question.trim()));
  const contextual=followup?prev.last_question+' 후속 질문: '+question:question;
  const predicted=predict(contextual);let intent=predicted,guard=null;
  if(/왜.*(?:매수|매도|샀|팔)|(?:매수|매도|매매).*이유|매수한.*이유|(?:진짜|투자|매매|선택한).*동기|개인\s*계좌|비공개|목표\s*주가|수익.*보장|내일|다음\s*달|202[6-9]/.test(question)){
    intent='UNSUPPORTED';guard='범위·미확인 동기 보호 규칙';}
  if(/[34]\s*분기|202[0-4]년.*보유/.test(question)){
    intent='UNSUPPORTED';guard='포함된 보고 기간 밖의 보유 질문';}
  const periods=[...question.matchAll(/([12])\s*분기|Q([12])|2025-(03-31|06-30)/gi)];
  let period=followup?(prev.period||PERIODS[1]):PERIODS[1];
  if(periods.length&&intent==='HOLDING_FACT'){
    const m=periods[periods.length-1];period=m[1]||m[2]?PERIODS[Number(m[1]||m[2])-1]:'2025-'+m[3];}
  const cusip=['HOLDING_FACT','HOLDING_CHANGE'].includes(intent)?entity(question,prev):null;
  let candidates=knowledge.filter(r=>r.kind===intent),chosen=[],answer='';
  const byId=id=>knowledge.find(r=>r.evidence_id===id);
  if(intent==='HOLDING_FACT'){
    candidates=candidates.filter(r=>(r.payload||{}).period_end===period);
    if(cusip)candidates=candidates.filter(r=>(r.payload||{}).cusip===cusip);
    else candidates=candidates.filter(r=>!!(r.payload||{}).cusip);
  }else if(intent==='HOLDING_CHANGE'&&cusip)candidates=candidates.filter(r=>(r.payload||{}).cusip===cusip);
  if(intent==='UNSUPPORTED'){
    chosen=[byId('SCOPE_13F')].filter(Boolean);
    answer='확인할 수 없습니다. 이 프로젝트의 13F는 버크셔 기관의 공개 보유 기록이며 버핏 개인의 특정 매매 이유·체결 시점·개인 계좌·미래 주가를 입증하지 않습니다. 일반 원칙을 특정 거래의 동기로 연결하지 않습니다.';
  }else if(['HOLDING_FACT','HOLDING_CHANGE'].includes(intent)&&!cusip&&!/(어떤|목록|종목|증가|감소|변화|현황|보유.*회사|상위)/.test(question)){
    answer='조회할 증권의 회사명 또는 CUSIP을 입력해 주세요. 이름이 확인되지 않아 임의의 기업 자료로 대신 답하지 않았습니다.';
  }else if(!candidates.length){
    if(intent==='HOLDING_FACT'&&cusip){chosen=[byId('FILING_'+period)].filter(Boolean);
      answer=period+'의 포함된 공개 공시에서 해당 증권을 찾지 못했습니다. 기관 전체 보유가 0이거나 개인이 전량 매도했다는 뜻은 아닙니다.';
    }else answer='연결할 공식 근거를 찾지 못했습니다. 질문을 투자 원칙·2025년 1/2분기 보유·분기 변화 중 하나로 구체화해 주세요.';
  }else if(intent==='INVESTMENT_PRINCIPLE'){
    chosen=retrievePrinciples(contextual);
    answer='공식 주주서한의 원칙을 한국어로 요약합니다. 실제 인물의 새로운 발언을 생성하는 방식은 아닙니다.\n\n'
      +chosen.map(r=>'['+r.evidence_id+'] '+r.text+'\n적용 조건: '+r.payload.condition).join('\n\n');
    if(!chosen.length)answer='질문과 연결할 투자 원칙 근거를 찾지 못했습니다.';
  }else{
    if(!cusip&&intent==='HOLDING_CHANGE'){
      const requested=/(증가|늘|늘어난)/.test(question)?'POSITION_INCREASED':/(감소|줄|줄어)/.test(question)?'POSITION_DECREASED':null;
      if(requested)candidates=candidates.filter(r=>r.payload.change_label===requested);
    }
    const ranking=r=>r.payload.market_value!==undefined?r.payload.market_value:Math.abs(r.payload.delta_shares||0);
    chosen=[...candidates].sort((a,b)=>ranking(b)-ranking(a)).slice(0,3);
    answer='Berkshire Hathaway의 공개 신고 자료를 기준으로 설명합니다.\n\n'+chosen.map(r=>'['+r.evidence_id+'] '+r.text).join('\n\n');
    if(!cusip)answer+='\n\n해당 조건 '+candidates.length+'건 중 최대 3건을 표시했습니다. 전체 조회는 정형화 데이터 파일을 확인합니다.';
    if(intent==='HOLDING_CHANGE')answer+='\n\n보유 변화는 체결 기록이 아닙니다. 미신고는 비교 계산에서 0으로 두었고, 분할·합병·식별자 변경은 별도 확인하지 못했습니다. 매매 동기는 UNKNOWN입니다.';
    else answer+='\n\n보고 기준일은 '+period+'이며 제출일과 구분합니다. 수정 공시까지 포함한 사후 공개 자료 기준입니다.';
  }
  const next={last_question:contextual.slice(-1600),intent,period};if(cusip)next.cusip=cusip;
  return {question,model:model.model_name,predicted_intent:predicted,response_intent:intent,guard_override:guard,answer,
    sources:chosen.map(r=>({id:r.evidence_id,type:r.evidence_type,urls:r.source_urls||[],location:r.payload?.source_location||null})),state:next};
}
function addMessage(kind,text){const d=document.createElement('div');d.className='message '+kind;d.textContent=text;$('messages').append(d);$('messages').scrollTop=$('messages').scrollHeight;}
function showEvidence(result){const el=$('evidence');el.replaceChildren();
  const head=document.createElement('div');head.className='datum';head.textContent='학습 모델: '+result.model;el.append(head);
  const meta=document.createElement('div');meta.textContent='예측: '+result.predicted_intent+' / 응답: '+result.response_intent;el.append(meta);
  if(result.guard_override){const guard=document.createElement('div');guard.textContent='보호 규칙: '+result.guard_override;el.append(guard);}
  const ul=document.createElement('ul');for(const item of result.sources){const li=document.createElement('li');li.textContent=item.id+' · '+item.type+' · '+(item.location||'SEC 공시/자료 범위');
    for(const url of item.urls){if(!/^https:\/\//.test(url))continue;const a=document.createElement('a');a.href=url;a.rel='noopener noreferrer';a.target='_blank';a.textContent=' 공식 출처';li.append(' · ',a);}ul.append(li);}el.append(ul);
}
async function submit(question){if(!model)return;addMessage('user',question);$('question').value='';try{
  const result=ask(question,state);state=result.state;addMessage('assistant',result.answer);showEvidence(result);
}catch(e){addMessage('assistant','입력 오류: '+e.message);}}
async function init(){
  try{
    const resources=await Promise.all(['model.json','knowledge.json','retriever.json'].map(async file=>{const r=await fetch('./'+file,{cache:'no-store'});if(!r.ok)throw Error(file+' 파일을 찾을 수 없습니다 ('+r.status+'). GitHub Actions에서 기존 학습 모델 변환을 먼저 완료해야 합니다.');return r.json();}));
    [model,knowledge,retriever]=resources;
    if(!model.training_complete||!model.source_sha256)throw Error('학습 완료 모델의 검증 정보가 누락되었습니다.');
    // Compare the JS decision rule with predictions recorded from the original sklearn pipeline.
    const wrong=model.test_predictions.filter(t=>predict(t.question)!==t.expected);
    if(wrong.length)throw Error('원본 분류기와 브라우저 추론 결과가 다릅니다: '+wrong.map(x=>x.question).join(', '));
    $('send').disabled=false;$('status').textContent='학습 모델 검증 완료 · '+model.model_name+' · 공식 근거 '+knowledge.length+'건';$('status').classList.add('ready');
  }catch(e){$('status').textContent='배포 파일 확인 필요: '+e.message;$('status').classList.add('error');console.error(e);}
}
$('ask-form').addEventListener('submit',e=>{e.preventDefault();submit($('question').value);});
$('reset').addEventListener('click',()=>{state={};$('messages').replaceChildren();addMessage('assistant','새 대화를 시작합니다.');$('evidence').textContent='질문 후 예측된 유형과 근거를 표시합니다.';});
$('examples').querySelectorAll('button').forEach(button=>button.addEventListener('click',()=>{$('question').value=button.textContent;$('question').focus();}));
init();
