'use strict';
const $ = id => document.getElementById(id);
let token = '', evidence = null, index = 0;
const explanations = [
  'A school page becomes a reviewed bank of questions. The blind probe is advisory: a lucky guess cannot veto a valid exercise.',
  'The application plans and delivers a short practice. Delivery is recorded only after the channel acknowledges it.',
  'The model is uncertain about one answer. The parent receives the question, expected answer and rubric; learning waits for a decision.',
  'The parent approves the answer. A final human verdict supersedes the provisional grade, without counting the response twice.',
  'SIMULATED TIME JUMP: two further days of complete practice. Persistent difficulty crosses the configured nine-answer threshold.',
  'The chosen button performs an action. The teacher note is delivered to the parent to share, or a seven-day load reduction is saved.',
  'SIMULATED TIME JUMP: the next practice follows the saved plan. Load reduction produces one question instead of three.'
];
function node(tag, text, className) { const el = document.createElement(tag); if (text != null) el.textContent = text; if (className) el.className = className; return el; }
async function api(path, body) {
  const response = await fetch('/judge/' + path, {method:'POST', headers:{'Content-Type':'application/json','X-Judge-Code':token}, body:JSON.stringify(body)});
  if (!response.ok) throw new Error(response.status === 403 ? 'The access code is incorrect.' : `The request could not finish (${response.status}). Please try again.`);
  return response.json();
}
$('login-form').addEventListener('submit', async event => {
  event.preventDefault(); $('status').textContent = '';
  try { const data = await api('login', {code:$('code').value}); token = data.token; $('code').value = ''; $('login').hidden = true; $('experience').hidden = false; $('run').focus(); }
  catch (error) { $('status').textContent = error.message; }
});
$('run').addEventListener('click', async () => {
  $('run').disabled = true; $('status').textContent = 'Executing the complete journey in isolated demo state…';
  try {
    evidence = await api('demo/run', {decision:$('decision').value}); index = 0;
    if (!evidence.passed) throw new Error('A journey assertion failed. Download the evidence before using this run.');
    $('verified').textContent = `${evidence.checks} checks passed`;
    $('journey').hidden = false; $('status').textContent = 'Complete run verified. Explore each stage below.';
    render(); $('journey').scrollIntoView({behavior:'smooth',block:'start'});
  } catch(error) { $('status').textContent = error.message; $('verified').textContent = 'Run incomplete'; }
  finally { $('run').disabled = false; }
});
$('previous').addEventListener('click', () => { index--; render(); });
$('next').addEventListener('click', () => { index++; render(); });
$('download').addEventListener('click', () => {
  if (!evidence) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(evidence,null,2)],{type:'application/json'}));
  const a = node('a'); a.href = url; a.download = `repaso-simulation-${evidence.decision}.json`; a.click(); URL.revokeObjectURL(url);
});
function render() {
  const c = evidence.checkpoints[index];
  const labels = ['School page','Practice arrives','Model asks for help','Human review','Persistent difficulty','Parent decides','Next practice'];
  const titles = ['The page becomes a practice bank','A short practice arrives','Uncertainty reaches the parent','One answer. One final decision.','A pattern needs attention','The decision changes what happens','The routine continues'];
  $('steps').replaceChildren(...evidence.checkpoints.map((_, i) => {
    const b = node('button',null); b.append(node('span',String(i+1).padStart(2,'0'),'step-number'),node('span',labels[i]));
    b.setAttribute('aria-current',i === index ? 'step' : 'false'); b.addEventListener('click',()=>{index=i;render();}); return b;
  }));
  $('previous').disabled = index === 0; $('next').disabled = index === evidence.checkpoints.length-1;
  $('stage-title').textContent = titles[index]; $('explanation').textContent = explanations[index];
  $('day').textContent = new Date(c.at).toLocaleString('en-GB',{dateStyle:'medium',timeStyle:'short',timeZone:'America/Caracas'}) + ' · simulated time';
  const reviewed = c.grades.filter(g=>g.correct !== null && !g.quarantined);
  $('attempts').textContent = reviewed.length;
  $('pending').textContent = c.reviews.filter(q=>q.status === 'pending').length + c.escalations.filter(e=>e.status === 'pending').length;
  $('completed').textContent = c.sessions.filter(s=>s.status === 'completed').length;
  const outcomes = [
    ['Less preparation for the parent','Seven questions survive review. The source remains linked to this family; another family cannot use its private material.'],
    ['An agreed routine, delivered','The parent receives a concept reminder, a recognition question and reasoning practice. Transport receipts make delivery recoverable.'],
    ['No invented certainty','The held answer does not update mastery. The parent may approve it, reject it, or keep it pending with “I do not know yet”.'],
    ['The adult has the final word','The provisional and final verdicts remain auditable. Only the final outcome contributes to the learning state.'],
    ['Evidence before another alert','The pattern spans nine answers. A deterministic threshold brings the parent concrete options and a drafted note.'],
    [evidence.decision === 'reduce_load' ? 'A lighter week is scheduled' : 'A note the parent can use',evidence.decision === 'reduce_load' ? 'One exercise per practice is saved for seven days. It will be applied by the next planning run.' : 'The drafted teacher note was delivered to the parent. Sharing it with the teacher remains the parent’s decision.'],
    [evidence.decision === 'reduce_load' ? 'One exercise. The change is visible.' : 'Practice continues after the note',evidence.decision === 'reduce_load' ? 'The next session contains one item, reflecting the parent’s decision. The adaptation has an explicit expiry.' : 'The next scheduled practice contains three items. The note decision is resolved and preserved in the record.']
  ];
  $('outcome-title').textContent = outcomes[index][0]; $('outcome').textContent = outcomes[index][1];
  $('adaptations').replaceChildren(...c.adaptations.map(a=>node('span',a.action.replaceAll('_',' ')+' · until '+a.expires_at.slice(0,10),'pill')));
  const material = c.materials.find(m=>m.parsed_text && m.status !== 'rejected' && m.status !== 'quarantined') || c.materials[0];
  $('material').replaceChildren(node('div',material?.parsed_text || 'No material yet','sheet'));
  const session = c.sessions.at(-1);
  $('practice').replaceChildren();
  if (!session?.capsule) $('practice').append(node('p','The next graph step will compose the practice.'));
  else {
    const count = session.capsule.item_ids.length;
    $('practice').append(node('p',`${count} question${count === 1 ? '' : 's'} · ${session.status.replaceAll('_',' ')}`));
    session.capsule.item_ids.forEach(id=>{const item=c.items.find(i=>i.id===id);if(!item)return;const q=node('div',null,'question');q.append(node('small',item.kind==='open'?'Explain your reasoning':'Choose an answer'),node('div',item.stem));$('practice').append(q);});
  }
  $('chat').replaceChildren(...c.transcript.map(e=>{
    if (e.type==='Reading') return node('div',e.label+' · '+e.values.map(v=>v.join(': ')).join(' / '),'reading');
    const b=node('div',null,'bubble'+(e.speaker==='Repaso'?'':' parent'));b.append(node('span',e.speaker,'speaker'),node('span',e.text));
    (e.buttons||[]).forEach(t=>b.append(node('span',t,'chat-button')));return b;
  }));
  requestAnimationFrame(()=>{$('chat').scrollTop=$('chat').scrollHeight;});
  $('trace').replaceChildren(...c.trace.map(t=>node('div',`${t.at.slice(11,19)}   ${t.kind}.${t.name}   ${t.status}`)));
  $('checks').replaceChildren(...evidence.beats.map(b=>node('li',(b.expected===b.actual?'✓ ':'✗ ')+b.name+' · '+b.actual)));
}
