/* A view of observed evidence. Animations only follow actual new data. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  let code = '', current = null, previous = null, selectedTab = 'turns';
  let timer = null, generation = 0, changes = [], freshEvents = new Set();
  let snapshotQueue = Promise.resolve();
  let knownEvents = new Set(), knownNotes = new Set(), rehearsalBusy = false;
  const esc = s => String(s ?? '').replace(/[&<>"']/g, x => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));
  const human = s => String(s || '').replace(/[_.]/g, ' ');
  const time = s => s ? new Date(s).toLocaleTimeString('en-GB', {hour:'2-digit',minute:'2-digit',second:'2-digit'}) : '—';
  const date = s => s ? new Date(s).toLocaleDateString('en-GB', {day:'numeric',month:'short'}) : '—';
  const empty = s => `<p class="empty">${esc(s)}</p>`;
  const labels = {explanation:'Asked for help',answer:'Answer evaluated',another_question:'Requested another question',stop:'Chose to stop',distress:'Adult attention requested',something_else:'Conversation',about_the_practice:'About the practice'};
  async function api(path, options = {}) {
    const response = await fetch(path, {...options, headers:{'X-Judge-Code':code,'Content-Type':'application/json',...(options.headers || {})},cache:'no-store',signal:AbortSignal.timeout(25000)});
    if (!response.ok) throw new Error(response.status === 403 ? 'Access code rejected.' : response.status === 404 ? 'This family is no longer available to this observer.' : 'The memory source could not be reached. Displayed data may be out of date.');
    return response.json();
  }
  function readSnapshot(family) {
    const read = snapshotQueue.catch(() => {}).then(() => api('/judge/memory/snapshot/'+encodeURIComponent(family)));
    snapshotQueue = read;
    return read;
  }
  function status(text, live = false) {
    $('connection').textContent = text;
    $('connection-dot').className = live ? 'live' : 'error';
  }
  function proof(label,title,detail,index='↗') {
    $('proof-label').textContent=label; $('proof-title').textContent=title;
    $('proof-detail').textContent=detail; $('proof-index').textContent=index;
  }
  function addChange(kind,title,before,after,detail) {
    changes.unshift({kind,title,before,after,detail,at:new Date().toISOString()});
    changes = changes.slice(0,9);
  }
  function compare(a,b) {
    const newNotes = b.notes.filter(n => !a.notes.some(o=>o.id===n.id));
    const help = newNotes.filter(n=>n.intent==='explanation' && n.explained);
    const unansweredHelp = newNotes.filter(n=>n.intent==='explanation' && !n.explained);
    if(unansweredHelp.length) {
      addChange('Help request','A request was saved without an explanation','Requested','No approach retained','Inspect the model event for the outcome. This is not counted as a remembered explanation.');
      proof('HELP REQUEST / EXPLANATION NOT RETAINED','The request arrived. No explanation was remembered.',`Assessed answers: ${a.counts.assessed} → ${b.counts.assessed}. Inspect the activity stream for the call outcome.`,'!');
    }
    if (help.length) {
      const same = a.counts.assessed === b.counts.assessed;
      addChange('Conversation memory','An explanation was remembered',a.counts.explanations,b.counts.explanations,same?'Assessed answers stayed at '+b.counts.assessed+'.':'Other answers were also observed in this interval.');
      proof('MOMENT 01 / HELP KEEPS ITS MEANING',same?'Asking for help did not cost an attempt.':'A new explanation is in memory.',same?`Assessed answers: ${a.counts.assessed} → ${b.counts.assessed}. Remembered approach: ${help.at(-1).explained || 'available in the conversation'}.`:'Open the conversation memory to inspect the new approach.','01');
      if(a.notes.some(n=>n.explained) && help.some(n=>n.explained)) proof('MOMENT 01 / THE NEXT EXPLANATION HAS A PAST','The conversation now remembers both approaches.',`Before: ${a.notes.filter(n=>n.explained).at(-1).explained}. Now also: ${help.at(-1).explained}. Inspect the context-loaded event to verify retrieval.`,'01');
    }
    if (b.counts.assessed !== a.counts.assessed) {
      addChange('Learning record','Assessed answers changed',a.counts.assessed,b.counts.assessed,'Read from effective stored assessments.');
      proof('MOMENT 02 / EVIDENCE PERSISTS','The answer became part of the learning record.',`${a.counts.assessed} → ${b.counts.assessed} assessed answers. The next decision can use this evidence.`,'02');
    }
    const resolved=b.decisions.filter(d=>d.status==='resolved' && a.decisions.find(o=>o.id===d.id)?.status!=='resolved');
    if(resolved.length) {
      addChange('Human decision','A decision was recorded','Pending',human(resolved.at(-1).choice),'The decision and its resolution time are stored.');
      proof('MOMENT 03 / THE ADULT CHANGES THE PLAN','A human decision now shapes the next step.',`Recorded choice: ${human(resolved.at(-1).choice)}. Inspect the active adaptation and next practice.`,'03');
    }
    const aa=a.adaptations.find(x=>x.item_limit===1), bb=b.adaptations.find(x=>x.item_limit===1);
    if(bb && !aa) {addChange('Active plan','Practice load is now limited','Previous plan','1 question',`Active until ${date(bb.expires_at)}; source: an explicit stored adaptation.`);proof('MOMENT 03 / FOLLOW-THROUGH','Less practice is now a saved plan.',`One question per scheduled practice. Active until ${date(bb.expires_at)}. This is read from storage.`,'03');}
    const next=b.sessions.at(-1), old=a.sessions.at(-1);
    if(next && (next.id!==old?.id || next.questions!==old?.questions)) addChange('Scheduled practice','A practice plan changed',old?.questions ?? '—',next.questions,`${next.date} · ${human(next.status)}. A prepared or simulated date is not a real clock wait.`);
    const ack=x=>x.deliveries.reduce((n,d)=>n+d.acknowledged,0);
    if(ack(b)>ack(a)) addChange('Transport','More messages acknowledged',ack(a),ack(b),'Transport receipt; not a read receipt.');
  }
  let evolutionStudent='', evolutionTopic='', evolutionDay='', evolutionMode='daily';
  const calendarDate = value => value ? new Date(value+'T12:00:00').toLocaleDateString('en-GB',{day:'numeric',month:'short'}) : '—';
  function selectedEvolution() {
    const rows=current?.evolution?.series || [];
    return rows.find(r=>(r.student_ref || '')===evolutionStudent && (r.competency_id || '')===evolutionTopic) || rows.find(r=>!r.student_ref && !r.competency_id);
  }
  function resetEvolution() {evolutionStudent='';evolutionTopic='';evolutionDay='';evolutionMode='daily';}
  function renderEvolution() {
    const evolution=current?.evolution, rows=evolution?.series || [];
    if(!rows.length){$('evolution-dashboard').hidden=true;return;}
    $('evolution-dashboard').hidden=false;
    const learners=rows.filter(r=>r.student_ref && !r.competency_id);
    if(evolutionStudent && !learners.some(s=>s.student_ref===evolutionStudent)){evolutionStudent='';evolutionTopic='';evolutionDay='';}
    $('evolution-students').innerHTML=`<button class="learner-tab ${!evolutionStudent?'selected':''}" data-student="" aria-pressed="${!evolutionStudent}"><span class="learner-mini all">⌂</span><span>Whole family<small>${current.students.length} ${current.students.length===1?'learner':'learners'}</small></span></button>`+learners.map(s=>`<button class="learner-tab ${s.student_ref===evolutionStudent?'selected':''}" data-student="${esc(s.student_ref)}" aria-pressed="${s.student_ref===evolutionStudent}"><span class="learner-mini">${esc(s.student?.charAt(0)||'S')}</span><span>${esc(s.student)}<small>${(current.students || []).find(p=>p.student_ref===s.student_ref)?.grade?`Grade ${esc(current.students.find(p=>p.student_ref===s.student_ref).grade)}`:'Learner evidence'}</small></span></button>`).join('');
    const topics=rows.filter(r=>(r.student_ref || '')===evolutionStudent && r.competency_id);
    if(evolutionTopic && !topics.some(t=>t.competency_id===evolutionTopic))evolutionTopic='';
    $('evolution-topic').innerHTML='<option value="">All topics</option>'+topics.map(t=>`<option value="${esc(t.competency_id)}">${esc(t.label)}</option>`).join('');
    $('evolution-topic').value=evolutionTopic;$('evolution-topic').disabled=!topics.length;
    const series=selectedEvolution(), summary=series.summary || {}, assessed=summary.assessed || 0, correct=summary.correct || 0;
    const days=(series.days || []).slice(-Number($('evolution-period').value || 30));
    if(!days.some(d=>d.date===evolutionDay))evolutionDay=days.filter(d=>d.active).at(-1)?.date || days.at(-1)?.date || '';
    $('evolution-summary').innerHTML=[
      ['Evaluated answers',assessed,`${correct} correct · recorded assessment history`,'↗'],
      ['Distinct question content',summary.distinct_contents || 0,assessed>(summary.distinct_contents || 0)?`${assessed-(summary.distinct_contents || 0)} repeated-content attempts`:'Coverage beyond repeating one question','◇'],
      ['Retained requests for help',summary.help_requests || 0,`${summary.explanations || 0} approaches remembered · retained notes`,'↺'],
      ['Days with evidence',summary.active_days || 0,summary.first_activity?`First record · ${calendarDate(String(summary.first_activity).slice(0,10))}`:'Waiting for the first recorded activity','▤']
    ].map(([label,value,detail,icon],i)=>`<article class="evolution-stat"><div><span>${label}</span><i aria-hidden="true">${icon}</i></div><strong class="${i===1?'accent':''}">${value}</strong><p>${esc(detail)}</p></article>`).join('');
    $('evolution-heading').textContent=evolutionTopic?series.label:!evolutionStudent?'One family. A connected learning record.':`${series.student}’s learning record`;
    $('evolution-zone').textContent=evolution.timezone || '';
    document.querySelectorAll('[data-evolution-mode]').forEach(b=>{const active=b.dataset.evolutionMode===evolutionMode;b.classList.toggle('selected',active);b.setAttribute('aria-pressed',active);});
    const cumulative=evolutionMode==='cumulative';
    $('evolution-legend').innerHTML=cumulative?'<span><i class="legend-answer"></i>Cumulative evaluated answers</span><span><i class="legend-help"></i>Distinct question content</span>':'<span><i class="legend-answer"></i>Evaluated answers</span><span><i class="legend-help"></i>Retained help requests</span>';
    if(!cumulative && days.some(d=>d.held))$('evolution-legend').innerHTML+='<span><i class="legend-held"></i>Held for review</span>';
    const amount=d=>cumulative?Math.max(d.cumulative_assessed || 0,d.cumulative_distinct_contents || 0):(d.assessed || 0)+(d.help_requests || 0)+(d.held || 0);
    const maximum=Math.max(1,...days.map(amount));
    document.querySelector('.chart-guides').innerHTML=[maximum,maximum/2,0].map(value=>`<span><b>${value}</b></span>`).join('');
    $('evolution-chart').innerHTML=days.map(d=>{
      const a=cumulative?d.cumulative_assessed || 0:d.assessed || 0,b=cumulative?d.cumulative_distinct_contents || 0:d.help_requests || 0,h=cumulative?0:d.held || 0;
      const description=cumulative?`${a} cumulative answers, ${b} distinct questions`:`${a} evaluated answers, ${b} retained help requests, ${h} held`;
      return `<button class="day-column ${d.date===evolutionDay?'selected':''} ${d.active?'active':''} ${cumulative?'cumulative':''}" data-day="${esc(d.date)}" aria-pressed="${d.date===evolutionDay}" aria-label="${esc(calendarDate(d.date))}: ${description}" title="${esc(calendarDate(d.date))}: ${description}"><span class="day-bars"><i class="answer-bar" style="height:${a/maximum*100}%"></i><i class="help-bar" style="height:${b/maximum*100}%"></i>${h?`<i class="held-bar" style="height:${h/maximum*100}%"></i>`:''}</span><span class="day-tick"></span></button>`;
    }).join('');
    $('evolution-dates').innerHTML=`<span>${calendarDate(days[0]?.date)}</span><span>${calendarDate(days[Math.floor(days.length/2)]?.date)}</span><span>${calendarDate(days.at(-1)?.date)}</span>`;
    const observedDays=days.filter(d=>d.active).length;
    const headline=observedDays===0?'No activity recorded in this window.':observedDays===1?'One day of evidence. A starting point.':`${observedDays} days with recorded activity in this window.`;
    $('evolution-history-note').innerHTML=`<span class="history-note-icon">${observedDays>1?'↗':'○'}</span><div><strong>${headline}</strong><p>${cumulative?'Cumulative counts show the growth of the record, not a historical mastery score.':'Select a day to inspect its evidence. An empty day means no activity was recorded.'} Help notes are retained for ${evolution.help_history_retention_days || 7} days.</p></div>`;
    renderEvolutionDay(series,days.find(d=>d.date===evolutionDay));
    const reviewGroups=new Map();
    for(const review of series.next_reviews || []) {
      const key=JSON.stringify([review.competency_id,review.question,review.due_date]);
      const grouped=reviewGroups.get(key);
      if(grouped)grouped.records++;else reviewGroups.set(key,{...review,records:1});
    }
    const reviews=[...reviewGroups.values()];
    $('evolution-reviews').innerHTML=reviews.slice(0,4).map(r=>`<article class="review-row"><div class="review-date"><strong>${calendarDate(r.due_date)}</strong><span>${r.overdue?'PAST DUE DATE':'DUE DATE'}</span></div><div><p>${esc(r.question)}</p><span>${r.records>1?`${r.records} review entries · same question and date`:`${r.interval_days} day interval · ${r.repetitions} ${r.repetitions===1?'repetition':'repetitions'}`} · ${esc(human(r.competency_id))}</span></div></article>`).join('') || '<p class="dashboard-empty">No spaced review date is stored for this selection yet. An evaluated answer can establish the next review.</p>';
    if(reviews.length)$('evolution-reviews').innerHTML+='<p class="review-source">Dates come from the stored spaced review schedule. They do not confirm that a message has been scheduled or sent.</p>';
    const decisions=series.adult_decisions || [];
    $('evolution-decisions').innerHTML=decisions.slice(-4).reverse().map(d=>`<article class="decision-row"><span class="decision-indicator ${d.status==='resolved'?'resolved':''}">${d.status==='resolved'?'✓':'○'}</span><div><strong>${esc(human(d.kind))}</strong><p>${d.choice?`Recorded choice · ${esc(human(d.choice))}`:esc(human(d.status))}</p><small>${calendarDate(String(d.resolved_at || d.created_at).slice(0,10))} · ${d.status==='resolved'?'Decision retained':d.status==='pending'?'Human review pending':human(d.status)}</small></div></article>`).join('') || '<p class="dashboard-empty">No adult decision is recorded for this selection. When a decision is saved, it will appear here.</p>';
  }
  function renderEvolutionDay(series,day) {
    if(!day){$('evolution-detail').innerHTML=empty('No day is available yet.');return;}
    const eps=(current.episodes || []).filter(e=>(!evolutionStudent || e.student_ref===evolutionStudent) && (!evolutionTopic || e.competency_id===evolutionTopic) && new Intl.DateTimeFormat('en-CA',{timeZone:current.evolution.timezone,year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(e.at))===day.date);
    const latest=eps.at(-1), help=day.help_requests || 0, assessed=day.assessed || 0;
    $('evolution-detail').innerHTML=`<p class="eyebrow">SELECTED DAY</p><h3>${calendarDate(day.date)}</h3><span class="day-evidence-badge">${day.active?'RECORDED EVIDENCE':'NO RECORDED ACTIVITY'}</span><div class="day-summary"><div><strong>${assessed}</strong><span>evaluated ${assessed===1?'answer':'answers'}</span></div><div><strong>${help}</strong><span>retained ${help===1?'help request':'help requests'}</span></div></div><div class="day-description"><span class="kind">What happened</span><p>${assessed?`${day.correct || 0} of ${assessed} answers were correct across ${day.distinct_contents || 0} distinct question ${day.distinct_contents===1?'content':'contents'}.`:help?'The retained evidence is a request for help, without an evaluated answer on this day.':'No assessed answers or retained help requests are available for this date.'}</p>${day.explanations?`<p>${day.explanations} explanation ${day.explanations===1?'approach was':'approaches were'} saved for later turns.</p>`:''}${day.held?`<p>${day.held} assessments held for review; excluded from correctness totals.</p>`:''}</div><div class="day-running"><span>Cumulative record by this date</span><strong>${day.cumulative_assessed || 0} answers <i>·</i> ${day.cumulative_distinct_contents || 0} distinct questions</strong></div>${latest?`<button class="day-open" data-evolution-open="${esc(latest.id)}"><span>Follow this day’s episode</span><span>↗</span></button>`:'<p class="day-no-transcript">A day can have stored learning evidence without a retained conversation transcript.</p>'}`;
  }
  $('evolution-students').addEventListener('click',e=>{const button=e.target.closest('[data-student]');if(!button)return;evolutionStudent=button.dataset.student;evolutionTopic='';evolutionDay='';renderEvolution();renderMap();});
  $('evolution-topic').addEventListener('change',e=>{evolutionTopic=e.target.value;evolutionDay='';renderEvolution();renderMap();});
  $('evolution-period').addEventListener('change',()=>{evolutionDay='';renderEvolution();});
  $('evolution-chart').addEventListener('click',e=>{const button=e.target.closest('[data-day]');if(button){evolutionDay=button.dataset.day;renderEvolution();}});
  document.querySelectorAll('[data-evolution-mode]').forEach(button=>button.addEventListener('click',()=>{evolutionMode=button.dataset.evolutionMode;renderEvolution();}));
  $('evolution-detail').addEventListener('click',e=>{const button=e.target.closest('[data-evolution-open]');if(!button)return;const episode=(current.episodes || []).find(v=>v.id===button.dataset.evolutionOpen);if(episode){openTopic(`${episode.student_ref}:${episode.competency_id}`);setMode('replay');selectEpisode(episode.id,true);}});

  let selectedTopic = '', selectedEpisode = '', viewMode = 'live', replayTimer = null, lastRenderedEpisode = '';
  const topicKey = t => `${t.student_ref}:${t.competency_id}`;
  const topicEpisodes = () => (current?.episodes || []).filter(e=>`${e.student_ref}:${e.competency_id}`===selectedTopic);
  const activeTopic = () => (current?.learning_topics || []).find(t=>topicKey(t)===selectedTopic);
  const episodeLabel = e => e.outcome==='explained'?'New explanation':e.outcome==='help_unavailable'?'Help requested':e.outcome==='held'?'Review pending':e.outcome==='assessed'?(e.correct?'Correct answer':'Answer evaluated'):(labels[e.intent] || 'Recorded turn');
  function stopReplay() { clearInterval(replayTimer);replayTimer=null;$('replay-play').textContent='▶';$('replay-play').setAttribute('aria-label','Play stored episodes'); }
  function renderMap() {
    $('topic-map').innerHTML=(current.learning_topics || []).filter(t=>(!evolutionStudent || t.student_ref===evolutionStudent) && (!evolutionTopic || t.competency_id===evolutionTopic)).map(t=>{
      const eps=(current.episodes || []).filter(e=>e.student_ref===t.student_ref && e.competency_id===t.competency_id);
      const latest=eps.at(-1), student=current.students.find(s=>s.alias===t.student);
      const next=t.repeated_attempts?'Assess a different question to check transfer.':t.assessed?'Keep building evidence across distinct questions.':'An evaluated answer will add learning evidence.';
      return `<article class="map-card"><div class="map-card-top"><span class="avatar">${esc(t.student?.charAt(0)||'S')}</span><div><strong>${esc(t.student)}</strong><small>${student?`Grade ${esc(student.grade)} · `:''}Mathematics</small></div><span class="pill subdued">${eps.length} retained turns</span></div><p class="eyebrow">${esc(human(t.competency_id))}</p><h3>${esc(t.label)}</h3><p class="map-summary">${esc(t.summary || `${t.correct} correct answers across ${t.distinct_contents} distinct questions. ${t.explanations} explanation approaches remembered.`)}</p><div class="map-stats"><div><b>${t.distinct_contents}</b><span>distinct questions</span></div><div><b>${t.assessed}</b><span>assessed answers</span></div><div><b>${t.explanations}</b><span>remembered approaches</span></div></div><div class="map-next"><span class="kind">${latest?'Latest recorded moment':'Next evidence to look for'}</span>${latest?`${esc(episodeLabel(latest))} · ${date(latest.at)} ${time(latest.at)}`:esc(next)}</div><button class="map-open" data-topic="${esc(topicKey(t))}" ${eps.length?'':'disabled'}><span>${eps.length?'Open learning episode':'Waiting for a retained conversation'}</span><span aria-hidden="true">↗</span></button></article>`;
    }).join('') || empty('No topic evidence yet. Open a practice in Telegram; retained learning episodes will appear here.');
  }
  function focusChat(id) {
    const chat=$('episode-chat'), turn=chat.querySelector(`[data-chat-turn="${CSS.escape(id)}"]`);
    if(turn)chat.scrollTo({top:Math.max(0,chat.scrollTop+turn.getBoundingClientRect().top-chat.getBoundingClientRect().top-12),behavior:'smooth'});
  }
  function openTopic(key) {
    selectedTopic=key;selectedEpisode=topicEpisodes().at(-1)?.id || '';viewMode='live';stopReplay();
    $('learning-map').hidden=true;$('episode-workspace').hidden=false;document.body.classList.add('episode-open');renderEpisode();focusChat(selectedEpisode);window.scrollTo({top:0,behavior:'smooth'});
  }
  function closeTopic() {
    stopReplay();selectedTopic='';selectedEpisode='';lastRenderedEpisode='';viewMode='live';$('learning-map').hidden=false;$('episode-workspace').hidden=true;document.body.classList.remove('episode-open');
  }
  function setMode(mode) {
    stopReplay();viewMode=mode;
    if(mode==='live')selectedEpisode=topicEpisodes().at(-1)?.id || '';
    renderEpisode();focusChat(selectedEpisode);
  }
  function selectEpisode(id, scroll=false) {
    selectedEpisode=id;renderEpisode();
    if(scroll)focusChat(id);
  }
  function renderEpisode() {
    if(!selectedTopic || !current)return;
    const topic=activeTopic(), episodes=topicEpisodes();
    if(!topic){closeTopic();return;}
    if(!episodes.some(e=>e.id===selectedEpisode))selectedEpisode=episodes.at(-1)?.id || '';
    const index=episodes.findIndex(e=>e.id===selectedEpisode), episode=episodes[index];
    $('episode-student').textContent=topic.student;$('episode-topic').textContent=topic.label;$('chat-student').textContent=topic.student;$('chat-avatar').textContent=topic.student?.charAt(0)||'S';
    $('mode-live').classList.toggle('selected',viewMode==='live');$('mode-replay').classList.toggle('selected',viewMode==='replay');
    $('mode-live').setAttribute('aria-pressed',viewMode==='live');$('mode-replay').setAttribute('aria-pressed',viewMode==='replay');$('replay-bar').hidden=viewMode!=='replay';
    $('episode-state').textContent=viewMode==='replay'?'REPLAY · stored turns':current.source==='aws'?'LIVE · AWS evidence':'LOCAL · synthetic rehearsal';
    $('episode-headline').textContent=episode?.memory?.approaches_loaded>0?'The next explanation has a past.':episode?.outcome==='assessed'?'An answer becomes learning evidence.':'Help that remembers.';
    $('episode-subtitle').textContent=viewMode==='replay'?'Replay retained turns. The evidence panel shows the latest stored topic totals.':'Select any message. Follow what was recalled, changed and saved.';
    $('replay-range').max=Math.max(0,episodes.length-1);$('replay-range').value=Math.max(0,index);$('replay-range').disabled=episodes.length<2;$('replay-play').disabled=episodes.length<2;
    $('replay-position').textContent=`${index+1} / ${episodes.length}`;$('replay-time').textContent=time(episode?.at);
    $('episode-timeline').innerHTML=episodes.map((e,i)=>`<button class="timeline-turn ${e.id===selectedEpisode?'selected':''}" data-turn="${esc(e.id)}" aria-pressed="${e.id===selectedEpisode}">${String(i+1).padStart(2,'0')} · ${esc(episodeLabel(e))}<small>${time(e.at)}</small></button>`).join('');
    $('timeline-caption').textContent=viewMode==='replay'?'Historical turns · current topic totals':'Select a recorded turn';
    renderConversation(viewMode==='replay'?episodes.slice(0,index+1):episodes);
    renderProcess(episode);renderTopicEvidence(topic,episode);
    if(lastRenderedEpisode!==selectedEpisode){$('episode-process').scrollTop=0;$('episode-learning').scrollTop=0;}
    lastRenderedEpisode=selectedEpisode;
  }
  function renderConversation(episodes) {
    const chat=$('episode-chat'), oldScroll=chat.scrollTop;
    chat.innerHTML=episodes.map((e,i)=>{
      const conversation=e.conversation || [];
      return `<article class="chat-turn ${e.id===selectedEpisode?'selected':''}" data-chat-turn="${esc(e.id)}"><div class="turn-date"><span class="turn-index">TURN ${String(i+1).padStart(2,'0')}</span> · <time>${date(e.at)} ${time(e.at)}</time></div>${conversation.map(m=>`<button class="chat-message ${m.role==='student'?'student':'agent'}" data-episode="${esc(e.id)}" aria-label="Inspect ${esc(episodeLabel(e))}" aria-pressed="${e.id===selectedEpisode}"><span class="speaker">${m.role==='student'?esc(activeTopic().student):'Repaso'}</span><span class="message-text">${esc(m.text)}</span><span class="message-meta"><span>${m.role==='student'?'Retained excerpt':m.status==='acknowledged'?'Transport acknowledged':'Stored reply'}</span><time>${time(m.at)}</time>${m.role==='agent' && m.status==='acknowledged'?'<span aria-label="Transport acknowledged">✓✓</span>':''}</span></button>`).join('')}${!conversation.some(m=>m.role==='student')?'<div class="record-gap">Response text is not retained for this turn. The recorded evidence remains available.</div>':''}${!conversation.some(m=>m.role==='agent') && episodeLabel(e)!=='Correct answer' && e.outcome!=='assessed'?'<div class="record-gap">A full reply is not available in the linked retained records.</div>':''}${e.outcome==='assessed'?`<div class="assessment-badge"><span>${e.correct===true?'✓':'○'}</span><div><strong>${e.correct===true?'Correct answer recorded':'Answer evaluated'}</strong><p>${esc(e.question || 'Assessment retained')}</p></div></div>`:''}<button class="turn-focus" data-episode="${esc(e.id)}">${e.id===selectedEpisode?'Evidence selected →':'Follow this turn →'}</button></article>`;
    }).join('') || empty('No retained messages for this topic yet.');
    chat.scrollTop=oldScroll;
  }
  function renderProcess(episode) {
    if(!episode){$('episode-process').innerHTML=empty('Select a recorded conversation.');return;}
    const memory=episode.memory || {}, events=episode.events || [];
    const model=events.find(e=>e.kind==='llm' && e.extra?.output==='Explanation' && e.status==='ok');
    const failed=events.find(e=>e.kind==='llm' && e.status==='failed');
    const delivered=events.some(e=>e.kind==='delivery' && e.name==='acknowledged');
    const saved=memory.saved_approach, previous=memory.previous_approaches || [];
    const hasRecall=memory.approaches_loaded!==null && memory.approaches_loaded!==undefined;
    const step=(label,title,body,observed,detail='')=>`<div class="process-step ${observed?'':'waiting'}"><div class="step-label"><span>${label}</span><small>${observed?'OBSERVED':'NO LINKED EVIDENCE'}</small></div><h4>${esc(title)}</h4>${body?`<p>${esc(body)}</p>`:''}${detail}</div>`;
    let html=`<div class="process-selection"><span>${esc(episodeLabel(episode))}</span><time>${time(episode.at)}</time></div>`;
    const selectionHtml=html;
    html='';
    html+=step('01 / Understand the turn',episode.outcome==='held'?'Assessment awaiting review':episode.assessment_source?'Practice answer evaluated':labels[episode.intent] || human(episode.intent),episode.question || 'A conversation note was retained.',true);
    html+=step('02 / Retrieve context',hasRecall?`${memory.approaches_loaded} prior ${memory.approaches_loaded===1?'approach':'approaches'} loaded`:'Retrieval event not available',hasRecall?`${memory.notes_loaded ?? 0} retained notes supplied to this explanation.`:'The observer does not infer retrieval from timing alone.',hasRecall,previous.map(p=>`<div class="approach-box"><span class="kind">Prior approach · retained context window</span><p>${esc(p.approach)}</p></div>`).join(''));
    if(episode.intent==='explanation') {
      html+=step('03 / Adapt the explanation',model?'A new explanation was generated':failed?'The explanation call did not complete':'Generation event not available',model?'The linked model call completed successfully.':failed?`Recorded outcome: ${human(failed.extra?.stop_reason || failed.status)}.`:'A saved approach can exist outside the current log window.',Boolean(model || failed));
      html+=step('04 / Remember for next time',saved?'New approach saved':'No explanation approach retained',saved?'This approach is now available to a later turn.':'A help request alone is not counted as a remembered explanation.',Boolean(saved),saved?`<div class="approach-box new"><span class="kind">Saved in learning memory</span><p>${esc(saved)}</p></div>${previous.length?'<div class="memory-delta"><span>Previous context</span><span>→</span><strong>New saved approach</strong></div>':''}`:'');
    } else if(episode.outcome==='assessed') {
      html+=step('03 / Evaluate the answer',episode.correct===true?'Correct answer recorded':episode.correct===false?'Incorrect answer recorded':'Assessment retained','This turn adds an evaluated answer to the learning record.',true);
    } else if(episode.outcome==='held') html+=step('03 / Hold for review','Assessment awaiting review','This result is held and excluded from the assessed topic totals.',true);
    else html+=step('03 / Retain the turn','Conversation note saved','The recorded intent remains available in the retained window.',true);
    html+=step('05 / Return to the learner',delivered?'Reply transport acknowledged':'Delivery evidence not available',delivered?'The transport accepted the reply. This is not a read receipt.':'No acknowledgement linked to this turn is visible in the current event window.',delivered);
    if(saved) {
      const previousCard=previous.length?previous.map(p=>`<div class="comparison-before"><span class="kind">Before · retained context window</span><p>${esc(p.approach)}</p></div>`).join(''):`<div class="comparison-before"><span class="kind">Previous context</span><p>${hasRecall && memory.approaches_loaded===0?'No previous explanation approach was loaded.':'No prior approach text is available in the verified retained window.'}</p></div>`;
      const comparison=`<div class="memory-comparison"><div class="recall-count"><strong>${hasRecall?memory.approaches_loaded:'—'}</strong><span>prior ${memory.approaches_loaded===1?'approach':'approaches'} loaded<br><small>${hasRecall?'From the linked retrieval event':'Retrieval event unavailable'}</small></span></div>${previousCard}<div class="comparison-arrow">↓ <span>${model?'New explanation generated':'Saved explanation approach'}</span></div><div class="comparison-after"><span class="kind">Now · saved for the next turn</span><p>${esc(saved)}</p></div><div class="memory-outcome"><span>✓ Approach retained</span><span>${delivered?'✓ Transport acknowledged':'Delivery evidence pending'}</span></div></div>`;
      html=selectionHtml+comparison+`<details class="trace-link action-details"><summary>Follow the recorded agent actions</summary>${html}</details>`;
    } else html=selectionHtml+html;
    html+=`<details class="trace-link"><summary>${events.length} linked instrumented events · inspect</summary>${events.map(e=>`<div class="trace-row ${esc(e.status)}"><span>${esc(human(e.kind))} / ${esc(human(e.name))}<br>${esc(e.status)}${e.extra?.stop_reason?' · '+esc(human(e.extra.stop_reason)):''}</span><small>${time(e.at)}${e.duration_ms!=null?'<br>'+(e.duration_ms/1000).toFixed(2)+' s':''}</small></div>`).join('') || '<p class="trace-empty">Logs may arrive later or fall outside the retained event window. Stored state remains visible.</p>'}</details>`;
    const process=$('episode-process'), priorScroll=process.scrollTop, traceOpen=Boolean(process.querySelector('.action-details[open]'));
    process.innerHTML=html;process.scrollTop=priorScroll;if(traceOpen)process.querySelector('.action-details')?.setAttribute('open','');
  }
  function renderTopicEvidence(topic,episode) {
    const m=topic.mastery, difficulties=topic.difficulties || [], contents=topic.contents || [];
    $('evidence-period').textContent='Latest stored topic totals';
    $('episode-learning').innerHTML=`${viewMode==='replay'?'<p class="replay-caveat">Replay follows recorded turns. These totals are the latest stored state, not a historical snapshot.</p>':''}<div class="topic-overline"><span>MATHEMATICS</span><span>${esc(topic.student)}</span></div><h3 class="topic-evidence-title">${esc(topic.label)}</h3><div class="evidence-score"><div><strong>${topic.correct}<small> / ${topic.assessed}</small></strong><span>answers correct</span></div><div><strong class="accent">${topic.distinct_contents}</strong><span>distinct assessed questions</span></div><div><strong>${topic.explanations}</strong><span>remembered explanations</span></div><div><strong>${difficulties.length}</strong><span>assessed difficulty levels</span></div></div><div class="evidence-insight"><span class="kind">What the evidence says</span><p>${esc(topic.summary || `${topic.assessed} answers assessed across ${topic.distinct_contents} distinct questions.`)}</p></div>${topic.repeated_attempts?`<div class="evidence-caution">${topic.repeated_attempts} repeated-content ${topic.repeated_attempts===1?'attempt':'attempts'}. Success on the same question does not establish transfer to new questions.</div>`:''}${episode?`<div class="content-evidence selected-content"><p class="kind">Selected turn</p><p>${episode.outcome==='held'?'This result is held for review and excluded from assessed totals.':episode.outcome==='assessed'?`An answer was evaluated: ${episode.correct===true?'correct':episode.correct===false?'incorrect':'result retained'}.`:episode.intent==='explanation'?'A request for help. This turn does not add an assessed answer.':'A conversation turn was retained.'}</p><span>${esc(episodeLabel(episode))}</span><span>${time(episode.at)}</span></div>`:''}<p class="section-label">DIFFICULTY COVERAGE</p>${difficulties.map(d=>`<div class="difficulty-row"><span><i class="difficulty-dot"></i>Level ${esc(human(d.level))}</span><strong>${d.correct} / ${d.assessed} correct</strong><span>${d.distinct_contents} distinct</span></div>`).join('') || '<p class="topic-note">No evaluated difficulty evidence yet.</p>'}${m?`<div class="mastery-evidence"><p class="section-label">STORED MASTERY ESTIMATE</p><div class="mastery-line"><span>${esc(human(m.level))} · ${m.attempts} attempts</span><span>${Math.round(m.ema_accuracy*100)}% weighted accuracy</span></div><meter min="0" max="1" value="${m.ema_accuracy}" aria-label="Stored weighted accuracy estimate"></meter><p>An application estimate from observed practice. ${topic.distinct_contents<2?'Evidence is limited to one or fewer distinct questions.':'This alone does not demonstrate learning gains.'}</p></div>`:''}<p class="section-label">ASSESSED CONTENT</p>${contents.map(c=>`<div class="content-evidence ${(c.content_refs || [c.content_ref]).includes(episode?.content_ref)?'selected-content':''}"><p>${esc(c.question)}</p><span>${c.correct} / ${c.assessed} correct</span><span>${esc(human(c.difficulty || 'Difficulty not retained'))}</span></div>`).join('') || '<p class="topic-note">An evaluated answer will add content evidence here.</p>'}${topic.held?`<p class="topic-note">${topic.held} held or unresolved assessments are excluded from these results.</p>`:''}<div class="evidence-insight"><span class="kind">Suggested next evidence</span><p>${topic.repeated_attempts?'A correct answer on a different question would add evidence of transfer.':topic.assessed?'Continue across distinct questions and difficulty levels to strengthen the evidence.':'An answer to the open question will provide the first assessment evidence.'}</p></div>`;
  }
  $('topic-map').addEventListener('click',e=>{const b=e.target.closest('[data-topic]');if(b && !b.disabled)openTopic(b.dataset.topic);});
  $('back-map').addEventListener('click',closeTopic);
  $('mode-live').addEventListener('click',()=>setMode('live'));$('mode-replay').addEventListener('click',()=>setMode('replay'));
  $('episode-chat').addEventListener('click',e=>{const b=e.target.closest('[data-episode]');if(b){stopReplay();selectEpisode(b.dataset.episode);}});
  $('episode-timeline').addEventListener('click',e=>{const b=e.target.closest('[data-turn]');if(b){stopReplay();selectEpisode(b.dataset.turn,true);}});
  $('replay-range').addEventListener('input',e=>{stopReplay();const episode=topicEpisodes()[Number(e.target.value)];if(episode)selectEpisode(episode.id,true);});
  $('replay-play').addEventListener('click',()=>{
    if(replayTimer){stopReplay();return;}
    const episodes=topicEpisodes();if(episodes.length<2)return;
    if(selectedEpisode===episodes.at(-1).id)selectEpisode(episodes[0].id,true);
    $('replay-play').textContent='Ⅱ';$('replay-play').setAttribute('aria-label','Pause stored episodes');
    replayTimer=setInterval(()=>{const eps=topicEpisodes(), index=eps.findIndex(e=>e.id===selectedEpisode);if(index>=eps.length-1){stopReplay();return;}selectEpisode(eps[index+1].id,true);},3200);
  });

  function renderMemory() {
    if(!current)return;
    let html='';
    if(selectedTab==='turns') html=[...current.notes].reverse().map(n=>`<article class="memory-card ${!knownNotes.has(n.id)?'fresh':''}"><div class="row-head"><span class="kind">${esc(labels[n.intent] || human(n.intent))}</span><time class="time">${time(n.at)}</time></div><h3>${esc(n.said || (n.intent==='answer'?'Attempt recorded · message text cleared':'Conversation note'))}</h3>${n.question?`<p>${esc(n.question)}</p>`:''}${n.explained?`<span class="fact">Remembered approach · ${esc(n.explained)}</span>`:''}${n.intent==='explanation' && !n.explained?'<span class="fact">No explanation approach retained · inspect the call outcome</span>':''}${n.correct!==null?`<span class="fact">Recorded result · ${n.correct?'correct':'incorrect'}</span>`:''}</article>`).join('') || empty('No retained conversation notes yet. Ask for an explanation during an open practice to see what is remembered.');
    if(selectedTab==='decisions') html=current.adaptations.map(a=>`<article class="memory-card"><div class="row-head"><span class="kind">Active adaptation</span><span class="time">Until ${date(a.expires_at)}</span></div><h3>${a.item_limit===1?'One question per practice':esc(human(a.action))}</h3><p>${esc(human(a.competency_id))}</p><span class="fact">Persisted plan · ${esc(a.source?.startsWith('escalation:')?'adult decision':'application policy')}</span></article>`).join('')+[...current.decisions].reverse().map(d=>`<article class="memory-card"><div class="row-head"><span class="kind">${esc(human(d.kind))}</span><span class="pill subdued">${esc(d.status)}</span></div><h3>${esc(d.summary)}</h3>${d.choice?`<span class="fact">Chosen · ${esc(human(d.choice))}</span>`:''}${d.note?`<p>${esc(d.note)}</p>`:''}</article>`).join('') || empty('No adult decisions recorded yet. Pending reviews and saved choices will appear here.');
    if(selectedTab==='practice') html=[...current.studies].reverse().map(s=>`<article class="memory-card"><div class="row-head"><span class="kind">Study sitting</span><span class="pill subdued">${esc(s.status)}</span></div><h3>${esc(s.goal.label || human(s.goal.competency_id) || 'Mathematics practice')}</h3><p>${s.progress.correct+s.progress.wrong} answered · ${s.budget.questions} question budget</p><span class="fact">Opened ${date(s.opened_at)} · ${time(s.opened_at)}</span></article>`).join('')+[...current.sessions].reverse().map(s=>`<article class="memory-card"><div class="row-head"><span class="kind">Scheduled practice</span><time class="time">${esc(s.date)}</time></div><h3>${s.questions} ${s.questions===1?'question':'questions'} · ${esc(human(s.status))}</h3><p>${s.answered} answers processed</p></article>`).join('') || empty('No practice is stored yet. Send supported material and start a session in Telegram.');
    $('memory-content').innerHTML=html;
  }
  function renderLearning() {
    const note=[...current.notes].reverse().find(n=>n.explained);
    const saved=note && current.events.find(e=>e.kind==='memory' && e.name==='turn.saved' && e.extra.record_ref===note.id);
    const correlation=saved?.extra.correlation_id;
    const context=correlation && current.events.find(e=>e.name==='explanation.context_loaded' && e.extra.correlation_id===correlation);
    const model=correlation && current.events.find(e=>e.kind==='llm' && e.extra.output==='Explanation' && e.status==='ok' && e.extra.correlation_id===correlation);
    const delivered=correlation && current.events.some(e=>e.kind==='delivery' && e.name==='acknowledged' && e.extra.parent_correlation_id===correlation);
    const stages=[
      ['01 / Telegram',note?.said || 'Waiting for a help request',Boolean(note)],
      ['02 / Recall',context?`${context.extra.approaches_loaded} previous approaches loaded`:'Awaiting matching retrieval event',Boolean(context)],
      ['03 / Adapt',model?'Explanation generated':'Awaiting matching model event',Boolean(model)],
      ['04 / Remember',note?.explained || 'No approach retained',Boolean(note)],
      ['05 / Deliver',delivered?'Transport confirmed':'Awaiting matching delivery event',Boolean(delivered)]
    ];
    $('learning-loop').innerHTML=stages.map(([label,text,ok])=>`<div class="loop-stage ${ok?'observed':''}"><span class="kind">${esc(label)}</span><p>${esc(text)}</p><small>${ok?'Observed':'Pending evidence'}</small></div>`).join('');
    $('learning-topics').innerHTML=(current.learning_topics || []).map(t=>{
      const m=t.mastery;
      return `<article class="topic-card"><div class="row-head"><h3>${esc(t.label)}</h3><span class="kind">${esc(t.student)}</span></div><div class="topic-facts"><span><b>${t.explanations}</b> explanations remembered</span><span><b>${t.correct} / ${t.assessed}</b> correct answers</span><span><b>${t.distinct_contents}</b> distinct assessed questions</span></div>${m?`<div class="mastery-line"><span>Stored mastery estimate · ${esc(human(m.level))}</span><strong>${Math.round(m.ema_accuracy*100)}%</strong></div><meter min="0" max="1" value="${m.ema_accuracy}" aria-label="Stored accuracy estimate"></meter><p class="topic-note">Weighted accuracy from ${m.attempts} attempts. A new explanation does not raise this estimate.</p>`:'<p class="topic-note">Awaiting evaluated answers for a mastery estimate.</p>'}${t.repeated_attempts?`<p class="topic-caution">${t.repeated_attempts} repeated-content attempts. These results do not establish improvement on new questions.</p>`:''}${t.held?`<p class="topic-note">${t.held} assessments held or unresolved; excluded from these results.</p>`:''}<details><summary>Inspect assessed content</summary>${t.contents.map(c=>`<p>${esc(c.question)} <span class="fact">${c.correct} / ${c.assessed} correct</span></p>`).join('') || '<p>No assessed content yet.</p>'}</details></article>`;
    }).join('') || empty('Learning evidence will be grouped here by student and topic.');
  }
  function renderEvents() {
    const e=current.events;
    const opened=new Set([...$('events').querySelectorAll('details[open]')].map(d=>d.dataset.event));
    $('events-status').textContent=current.events_status==='connected'?'Connected':current.events_status==='unavailable'?'Logs unavailable':'Not configured';
    $('events').innerHTML=[...e].reverse().map(v=>{
      const title=v.kind==='llm'?`${human(v.name)} · model call`:v.kind==='delivery'?`Message ${human(v.name)}`:v.kind==='study_turn'||v.kind==='turn'?(labels[v.name]||human(v.name)):human(v.name);
      return `<article class="event ${esc(v.status)} ${freshEvents.has(v.id)?'fresh':''}"><span class="event-mark">${v.status==='failed'?'!':v.status==='started'?'↗':'✓'}</span><div><h3>${esc(title)}</h3><p>${esc(v.kind)} · ${esc(v.status)}${v.duration_ms!=null?' · '+(v.duration_ms/1000).toFixed(2)+'s':''}${v.extra.evidence_origin?' · '+esc(v.extra.evidence_origin):''}</p>${v.extra.correlation_id||v.extra.model_id?`<details data-event="${esc(v.id)}" ${opened.has(v.id)?'open':''}><summary>Inspect event</summary>${v.extra.model_id?`<p>Model · ${esc(v.extra.model_id)}</p>`:''}${v.extra.correlation_id?`<p>Correlation · ${esc(v.extra.correlation_id)}</p>`:''}${v.extra.stop_reason?`<p>Call outcome · ${esc(human(v.extra.stop_reason))}</p>`:''}${v.extra.parent_correlation_id?`<p>Triggered by · ${esc(v.extra.parent_correlation_id)}</p>`:''}${v.extra.approaches_loaded!==undefined?`<p>Memory supplied · ${esc(v.extra.notes_loaded)} notes / ${esc(v.extra.approaches_loaded)} previous approaches</p>`:''}${v.extra.usage_available==='True'?`<p>Reported tokens · ${esc(v.extra.input_tokens || '0')} in / ${esc(v.extra.output_tokens || '0')} out</p>`:''}</details>`:''}</div><time class="time">${time(v.at)}</time></article>`;
    }).join('') || empty(current.events_status==='unavailable'?'The state is available, but the log source could not be read. Retrying automatically.':'Waiting for matching instrumented events. Older state can exist without events in the current log window.');
  }
  function renderChanges() {
    $('changes').innerHTML=changes.map(c=>`<article class="change"><span class="kind">${esc(c.kind)}</span><h3>${esc(c.title)}</h3><p class="delta">${esc(c.before)} → ${esc(c.after)}</p><p>${esc(c.detail)}</p></article>`).join('') || empty('The first snapshot is your baseline. New changes will appear here.');
  }
  function rehearsalControls() {
    const completed=current?.rehearsal_completed || [];
    const next=['help','another','answer','reduce'].find(step=>!completed.includes(step));
    document.querySelectorAll('[data-step]').forEach(b=>{b.disabled=rehearsalBusy || b.dataset.step!==next;});
  }
  function render(data) {
    const priorEpisodeIds = new Set(current?.episodes?.map(e=>e.id) || []);
    current=data;
    if(selectedTopic && viewMode==='live') {
      const latest=topicEpisodes().at(-1);
      if(latest && !priorEpisodeIds.has(latest.id)) selectedEpisode=latest.id;
    }
    if(previous)compare(previous,data);
    freshEvents=new Set(previous?data.events.filter(e=>!knownEvents.has(e.id)).map(e=>e.id):[]);
    if(!previous)knownNotes=new Set(data.notes.map(n=>n.id));
    $('assessed').textContent=data.counts.assessed;
    $('explanations').textContent=data.counts.explanations;
    $('pending').textContent=data.decisions.filter(d=>d.status==='pending').length+data.counts.held;
    const last=data.sessions.at(-1);
    $('questions').textContent=last?.questions ?? '—';
    $('practice-date').textContent=last?`${last.date} · ${human(last.status)}`:'No scheduled practice observed';
    $('source').textContent=data.source==='aws'?'AWS · observed state':'LOCAL REHEARSAL';
    $('updated').textContent='Read '+time(data.observed_at);
    $('rehearsal').hidden=!data.rehearsal;
    if(!previous && data.rehearsal) proof('LOCAL REHEARSAL / STORED STATE',data.rehearsal_completed.length?'Your rehearsal memory is here.':'Start with a request for help.',data.rehearsal_completed.length===4?'All four steps are saved. Inspect the conversation, decisions and practice, or verify the saved memory.':'Use the controls in order. The family, model responses and next-day clock are simulated; stored changes come from the application.');
    rehearsalControls();
    renderEvolution();renderMap();renderEpisode();renderMemory();renderLearning();renderEvents();renderChanges();
    if(selectedTopic && viewMode==='live' && !priorEpisodeIds.has(selectedEpisode))focusChat(selectedEpisode);
    knownEvents=new Set(data.events.map(e=>e.id));knownNotes=new Set(data.notes.map(n=>n.id));
    previous=data;
  }
  async function poll(epoch=generation) {
    clearTimeout(timer);
    const family=$('family').value;
    if(!family || !code)return;
    try {
      const data=await readSnapshot(family);
      if(epoch!==generation)return;
      render(data);$('error').hidden=true;status('Observing memory',true);
    }catch(e){if(epoch!==generation)return;status('Connection interrupted');$('error').textContent=e.message;$('error').hidden=false;}
    if(epoch===generation && code)timer=setTimeout(()=>poll(epoch),3000);
  }
  $('connect-form').addEventListener('submit',async e=>{
    e.preventDefault();code=$('access-code').value;const button=e.target.querySelector('button');button.disabled=true;$('login-error').textContent='';
    try{const students=await api('/judge/students');if(!students.length)throw new Error('No families are shared with this observer yet. Configure an explicit family allowlist.');const groups=new Map();for(const student of students){const members=groups.get(student.family_id)||[];members.push(student);groups.set(student.family_id,members);}const rows=[...groups].map(([family_id,members])=>({family_id,label:members.length===1?`${members[0].alias} · Grade ${members[0].grade}`:`${members[0].alias} + ${members.length-1} ${members.length===2?'learner':'learners'}`}));$('family').innerHTML=rows.map(s=>`<option value="${esc(s.family_id)}">${esc(s.label)}</option>`).join('');$('gate').hidden=true;$('observer').hidden=false;$('disconnect').hidden=false;$('access-code').value='';generation++;await poll();}catch(err){$('login-error').textContent=err.message;code='';}finally{button.disabled=false;}
  });
  $('disconnect').addEventListener('click',()=>{resetEvolution();closeTopic();$('topic-map').innerHTML='';$('episode-chat').innerHTML='';$('episode-process').innerHTML='';$('episode-learning').innerHTML='';code='';generation++;clearTimeout(timer);current=previous=null;changes=[];knownEvents.clear();knownNotes.clear();$('observer').hidden=true;$('gate').hidden=false;$('disconnect').hidden=true;$('family').innerHTML='';$('memory-content').innerHTML='';$('events').innerHTML='';$('changes').innerHTML='';$('learning-loop').innerHTML='';$('learning-topics').innerHTML='';$('reply').textContent='';$('chat-preview').hidden=true;status('Not connected');proof('WATCH A CONVERSATION LEAVE A TRACE','Memory is ready. Your next message starts the story.','Send a message in Telegram. Changes appear here when they are read from storage.');});
  $('family').addEventListener('change',()=>{resetEvolution();closeTopic();$('topic-map').innerHTML=empty('Loading this learning circle…');generation++;previous=current=null;changes=[];knownEvents.clear();knownNotes.clear();['assessed','explanations','pending','questions'].forEach(id=>$(id).textContent='—');$('source').textContent='Connecting';$('updated').textContent='Waiting for state';$('practice-date').textContent='Reading selected family';$('reply').textContent='';$('chat-preview').hidden=true;$('memory-content').innerHTML=empty('Loading this family…');$('events').innerHTML='';$('changes').innerHTML='';$('learning-loop').innerHTML='';$('learning-topics').innerHTML='';proof('FOLLOWING A NEW FAMILY','Reading this family’s memory.','Each family has its own observation baseline.');poll();});
  document.querySelectorAll('[data-tab]').forEach(b=>b.addEventListener('click',()=>{selectedTab=b.dataset.tab;document.querySelectorAll('[data-tab]').forEach(x=>x.classList.toggle('selected',x===b));renderMemory();}));
  $('verify').addEventListener('click',async()=>{const before=current;if(!before)return;const epoch=generation;$('verify').disabled=true;try{const data=await readSnapshot(before.family_id);if(epoch!==generation)return;render(data);const same=JSON.stringify({notes:before.notes,decisions:before.decisions,adaptations:before.adaptations})===JSON.stringify({notes:data.notes,decisions:data.decisions,adaptations:data.adaptations});proof('MOMENT 04 / MEMORY OUTLIVES THE SCREEN',same?'Read again. The memory is still there.':'Fresh evidence arrived during verification.',same?'Conversation notes and decisions matched a new read from storage.':'The observer has updated to the latest stored state.','04');}catch(e){$('error').textContent=e.message;$('error').hidden=false;}finally{$('verify').disabled=false;}});
  document.querySelectorAll('[data-step]').forEach(b=>b.addEventListener('click',async()=>{if(rehearsalBusy)return;rehearsalBusy=true;document.querySelectorAll('[data-step]').forEach(x=>x.disabled=true);try{const reply=await api('/judge/memory/rehearsal/'+b.dataset.step,{method:'POST',body:'{}'});$('chat-preview').hidden=false;$('reply').textContent=reply.messages.join('\n\n');await poll();}catch(e){$('error').textContent=e.message;$('error').hidden=false;}finally{rehearsalBusy=false;rehearsalControls();}}));
})();
