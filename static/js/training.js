document.addEventListener('DOMContentLoaded', async () => {
    const moduleSelect = document.getElementById('moduleSelect');
    const languageSelect = document.getElementById('langSelect');
    const questionBox = document.getElementById('questionBox');
    const optionsBox = document.getElementById('optionsBox');
    const actionList = document.getElementById('actionList');
    const answerInput = document.getElementById('voiceAnswer');
    let modules = [];
    let current = null;
    let sessionId = null;
    let selectedAnswer = '';
    let actions = [];
    let startedAt = Date.now();
    let muted = false;
    let assessment = [];
    let questionIndex = 0;
    let answers = {};
    let recognition = null;
    let submitted = false;

    let lastSpokenText = '';
    const speak = text => {
        if (!text) return;
        lastSpokenText = text;
        if (muted) { document.getElementById('voiceStatus').textContent = 'Voice output is muted.'; return; }
        if (!('speechSynthesis' in window)) { document.getElementById('voiceStatus').textContent = 'Speech output is unavailable; text remains visible.'; return; }
        speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = languageSelect.value;
        const preferred = speechSynthesis.getVoices().find(v => v.lang.toLowerCase().startsWith(languageSelect.value.split('-')[0]));
        if (preferred) utterance.voice = preferred;
        speechSynthesis.speak(utterance);
        document.getElementById('voiceStatus').textContent = 'Speaking: ' + text;
    };
    async function refreshDashboard() {
        const response = await fetch('/api/training-dashboard');
        if (!response.ok) return;
        const data = await response.json();
        document.getElementById('progressSummary').innerHTML = `<div class="progress mb-2"><div class="progress-bar" style="width:${data.progress}%"></div></div><strong>${data.progress}% complete</strong>`;
        document.getElementById('recommendations').innerHTML = data.recommendations.length ? data.recommendations.map(x => `<div class="recommendation">${x}</div>`).join('') : '<span class="text-muted">No weak areas recorded.</span>';
    }
    async function startModule(module) {
        const response = await fetch('/api/training-sessions', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({module_code:module.code})});
        const data = await response.json();
        if (!response.ok) { showToast(data.error, 'error'); return false; }
        sessionId = data.sessionId || data.session_id;
        startedAt = Date.now(); actions = []; selectedAnswer = '';
        answerInput.value = '';
        return true;
    }
    async function renderModule(module) {
        current = module;
        if (window.ARTraining) window.ARTraining.setScenario(module.code);
        document.getElementById('moduleTitle').textContent = module.title;
        document.getElementById('moduleDescription').textContent = module.description;
        assessment = [];
        questionIndex = 0;
        answers = {};
        submitted = false;
        const assessmentResponse = await fetch(`/api/training-assessment/${module.code}`);
        if (assessmentResponse.ok) {
            assessment = (await assessmentResponse.json()).questions;
            renderAssessmentQuestion();
        } else {
            questionBox.textContent = 'Assessment scenarios could not be loaded.';
        }
        document.getElementById('objectiveList').innerHTML = `<ul><li>${module.description}</li><li>Protect personnel and communicate clearly.</li><li>Use the correct equipment and follow the vessel response.</li></ul>`;
        const choices = module.code.includes('fire') ? ['Fire blanket', 'CO2 extinguisher', 'Water hose'] : module.code.includes('gas') ? ['SCBA', 'Standard dust mask', 'Gas detector'] : module.code.includes('ppe') ? ['Chemical gloves', 'Approved SCBA', 'Cotton apron'] : ['Raise alarm', 'Isolate source', 'Call muster control'];
        actionList.innerHTML = choices.map(choice => `<button type="button" class="action-choice">${choice}</button>`).join('');
        actionList.querySelectorAll('button').forEach(button => button.addEventListener('click', () => {
            const isCorrect = button.textContent === module.correct_answer || /CO2|SCBA|Raise alarm|Isolate|muster/i.test(button.textContent) && module.code !== 'alternative-fuels';
            actions.push({key:'equipment', value:button.textContent, correct:isCorrect, expected:module.recommended_equipment || module.correct_answer});
            const feedback = isCorrect ? 'Correct choice. Verify procedure and maintain communication.' : 'Unsafe choice for this scenario. Review the equipment briefing.';
            document.getElementById('sceneFeedback').textContent = feedback;
            showToast(feedback, isCorrect ? 'success' : 'warning'); speak(feedback);
        }));
        speak(`${module.title}. ${module.description}`);
    }

    function renderAssessmentQuestion() {
        if (!assessment.length) return;
        const question = assessment[questionIndex];
        document.getElementById('assessmentInstructions').textContent = `${question.stage}. Choose the safest procedure; this answer is saved when you continue.`;
        document.getElementById('assessmentProgress').textContent = `${questionIndex + 1} / ${assessment.length}`;
        document.getElementById('assessmentProgressBar').style.width = `${((questionIndex + 1) / assessment.length) * 100}%`;
        questionBox.innerHTML = `<strong>${question.prompt}</strong><div class="assessment-feedback" aria-live="polite"></div>`;
        optionsBox.innerHTML = question.options.map(option => `<label class="option-item"><input type="radio" name="assessment-answer" value="${option.id}"> ${option.text}</label>`).join('');
        optionsBox.querySelectorAll('input').forEach(input => {
            input.checked = answers[question.id] === input.value;
            input.addEventListener('change', () => {
                answers[question.id] = input.value;
                selectedAnswer = input.value;
                answerInput.value = input.closest('label').textContent.trim();
                document.getElementById('submitAnswerBtn').disabled = Object.keys(answers).length !== assessment.length || submitted;
            });
        });
        document.getElementById('previousQuestionBtn').disabled = questionIndex === 0;
        speak(`${question.stage}. ${question.prompt}`);
    }

    const moduleResponse = await fetch('/api/training-modules');
    const moduleCodes = ['engine-fire','gas-toxic','ship-flooding','emergency-muster','marine-ppe','alternative-fuels'];
    modules = (await moduleResponse.json()).filter(module => moduleCodes.includes(module.code));
    moduleSelect.innerHTML = modules.map(module => `<option value="${module.code}">${module.title}</option>`).join('');
    const cards = document.createElement('div'); cards.className = 'training-module-cards';
    cards.innerHTML = modules.map(module => `<article class="training-module-card"><strong>${module.title}</strong><span>${module.description}</span><button type="button" data-module="${module.code}">Open module</button></article>`).join('');
    document.querySelector('.training-workspace > .row').before(cards);
    cards.querySelectorAll('button').forEach(button => button.addEventListener('click', async () => { moduleSelect.value = button.dataset.module; moduleSelect.dispatchEvent(new Event('change')); cards.scrollIntoView({behavior:'smooth', block:'center'}); }));
    await startModule(modules[0]); await renderModule(modules[0]); await refreshDashboard();
    moduleSelect.addEventListener('change', async () => { const module = modules.find(item => item.code === moduleSelect.value); if (await startModule(module)) renderModule(module); });
    document.getElementById('muteBtn').addEventListener('click', event => { muted = !muted; event.target.textContent = muted ? 'Unmute' : 'Mute'; });
    document.getElementById('voiceBtn').addEventListener('click', () => speak(lastSpokenText || `${current.title}. ${current.description}`));
    document.getElementById('previousQuestionBtn').addEventListener('click', () => { if (questionIndex > 0) { questionIndex--; renderAssessmentQuestion(); } });
    document.getElementById('nextQuestionBtn').addEventListener('click', () => {
        if (!assessment.length) return;
        if (!answers[assessment[questionIndex].id]) { showToast('Select a safety response before continuing.', 'warning'); return; }
        if (questionIndex < assessment.length - 1) { questionIndex++; renderAssessmentQuestion(); }
        else showToast('All decisions recorded. Review answers, then submit once.', 'success');
    });
    document.getElementById('reviewAnswersBtn').addEventListener('click', () => {
        if (!assessment.length) return;
        questionBox.innerHTML = `<strong>Review decisions</strong>`;
        optionsBox.innerHTML = assessment.map(q => { const chosen = q.options.find(o => o.id === answers[q.id]); return `<div class="review-answer"><span>${q.stage}</span><strong>${chosen ? chosen.text : 'Not answered'}</strong></div>`; }).join('');
        document.getElementById('assessmentProgress').textContent = 'Review';
    });

    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    document.getElementById('micBtn').addEventListener('click', () => {
        if (!Recognition) { document.getElementById('voiceStatus').textContent = 'Speech recognition is not supported here. Type your answer below.'; answerInput.focus(); return; }
        if (recognition) recognition.stop();
        recognition = new Recognition();
        recognition.lang = languageSelect.value;
        recognition.interimResults = true;
        recognition.continuous = false;
        document.getElementById('voiceStatus').textContent = 'Listening…';
        document.getElementById('micBtn').classList.add('is-listening');
        recognition.onresult = event => {
            const transcript = Array.from(event.results).map(result => result[0].transcript).join(' ').trim();
            answerInput.value = transcript;
            selectedAnswer = transcript;
            const q = assessment[questionIndex];
            if (q) {
                const normalized = transcript.toLowerCase();
                const match = q.options.find(option => normalized.includes(option.text.toLowerCase().slice(0, 12)) || option.text.toLowerCase().split(/\s+/).filter(word => word.length > 5).some(word => normalized.includes(word)));
                if (match) {
                    answers[q.id] = match.id;
                    q.options.forEach(option => { const input = [...optionsBox.querySelectorAll('input')].find(item => item.value === option.id); if (input) input.checked = option.id === match.id; });
                    document.getElementById('submitAnswerBtn').disabled = Object.keys(answers).length !== assessment.length || submitted;
                }
            }
            document.getElementById('voiceStatus').textContent = 'Recognized: ' + transcript;
        };
        recognition.onend = () => { document.getElementById('micBtn').classList.remove('is-listening'); if (document.getElementById('voiceStatus').textContent === 'Listening…') document.getElementById('voiceStatus').textContent = 'Listening stopped. Type your answer if needed.'; };
        recognition.onerror = event => { document.getElementById('voiceStatus').textContent = event.error === 'not-allowed' ? 'Microphone permission denied. Allow microphone access or type your answer.' : `Speech recognition error: ${event.error}. Text input is available.`; };
        try { recognition.start(); } catch (_) { document.getElementById('voiceStatus').textContent = 'Recognition is already active or unavailable. Use text input.'; }
    });
    document.getElementById('micStopBtn').addEventListener('click', () => { if (recognition) recognition.stop(); document.getElementById('voiceStatus').textContent = 'Listening stopped.'; });
    document.getElementById('voicePauseBtn').addEventListener('click', () => { if ('speechSynthesis' in window) speechSynthesis.pause(); });
    document.getElementById('voiceResumeBtn').addEventListener('click', () => { if ('speechSynthesis' in window) speechSynthesis.resume(); });
    document.getElementById('voiceStopBtn').addEventListener('click', () => { if ('speechSynthesis' in window) speechSynthesis.cancel(); });
    document.querySelectorAll('.scene-hazard').forEach(button => button.addEventListener('click', () => {
        const action = button.dataset.action;
        const feedback = action === 'hazard' ? 'Risk identified: inspect activation point, fuel source and nearby ignition. Raise the alarm.' : action === 'equipment' ? 'Equipment inspected. Select task-specific PPE and suppression equipment from Actions.' : 'Muster route identified. Keep route clear and report at the muster station.';
        document.getElementById('sceneFeedback').textContent = feedback; speak(feedback);
        actions.push({key:'hazard_scan', value:action, correct:action !== 'none', expected:'hazard/equipment/route'});
    }));
    // Camera, WebXR and Three.js rendering are initialized by ar-training.js.

    document.getElementById('submitAnswerBtn').addEventListener('click', async () => {
        if (submitted) return;
        if (Object.keys(answers).length !== assessment.length) { showToast('Review and answer every scenario before submitting.', 'warning'); return; }
        submitted = true;
        const elapsed = Math.round((Date.now() - startedAt) / 1000);
        const submitButton = document.getElementById('submitAnswerBtn');
        submitButton.disabled = true;
        submitButton.textContent = 'Submitting…';
        const response = await fetch('/api/training-submit', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({session_id:sessionId, answers:assessment.map(q => ({key:q.id, answer:answers[q.id]})), actions, elapsed_seconds:elapsed})});
        const result = await response.json();
        submitButton.textContent = response.ok ? 'Assessment submitted' : 'Submission unavailable';
        if (!response.ok) { submitted = false; submitButton.disabled = false; submitButton.textContent = 'Submit assessment once'; showToast(result.error || 'Submission failed.', 'error'); return; }
        const resultBox = document.getElementById('trainingResult'); resultBox.hidden = false;
        const mistakes = result.mistakes && result.mistakes.length ? `<h6>Review decisions</h6>${result.mistakes.map(item => `<article><strong>${item.stage || item.key}</strong><p>${item.feedback || ''}</p><small>Selected: ${item.selected}</small><br><small>Correct procedure: ${item.correct}</small></article>`).join('')}` : '<p>No incorrect decisions recorded.</p>';
        const certificate = result.certificate ? `
            <section class="completed-certificate-preview" aria-label="Training completion certificate">
                <div class="completed-certificate-heading"><span>✓ Training completed</span><strong>MARINVA prototype certificate</strong></div>
                <iframe title="Certificate preview" src="/certificate/verify/${result.certificate.verification_id}"></iframe>
                <div class="completed-certificate-actions">
                    <a class="btn btn-outline-primary" href="/certificate/verify/${result.certificate.verification_id}" target="_blank" rel="noopener">Open full certificate</a>
                    <a class="btn btn-success" href="/certificate/${result.certificate.verification_id}.pdf">Download prototype certificate PDF</a>
                </div>
            </section>` : '';
        resultBox.innerHTML = `<h4>${result.passed ? 'Module passed' : 'Review required'}</h4><p>Score: <strong>${result.score}%</strong>. Correct decisions: ${assessment.length - result.mistakes.length} / ${assessment.length}. Passing requires more than 80%.</p>${mistakes}<p>${result.recommendation}</p>${certificate}${result.passed ? '' : '<button class="btn btn-outline-primary" id="retryTrainingBtn">Repeat training</button>'}`;
        document.getElementById('retryTrainingBtn')?.addEventListener('click', () => location.reload());
        speak(result.passed ? `Module passed with ${result.score} percent.` : `Score ${result.score} percent. Review the safety feedback and repeat the training.`);
        await refreshDashboard();
    });

    async function loadPersonalizedAssessments() {
        const response = await fetch('/api/personalized-assessment');
        const container = document.getElementById('personalizedAssessment');
        if (!response.ok) { container.innerHTML = '<p>Sign in with a crew profile to load personalized assessments.</p>'; return; }
        const data = await response.json();
        document.getElementById('personalizedRole').textContent = `${data.role} · ${data.role_key}`;
        container.innerHTML = ['individual', 'common'].map(category => {
            const questions = data[category];
            return `<article class="personalized-assessment"><h6>${category === 'individual' ? 'Role-based individual assessment' : 'Common maritime emergency assessment'}</h6>${questions.map((q, index) => `<fieldset data-question="${q.code}"><legend>${index + 1}. ${q.prompt}</legend>${q.options.map(option => `<label class="option-item"><input type="radio" name="${category}-${q.code}" value="${option}"> ${option}</label>`).join('')}</fieldset>`).join('')}<button type="button" class="btn btn-primary" data-submit-category="${category}">Submit ${category} assessment</button></article>`;
        }).join('');
        container.querySelectorAll('[data-submit-category]').forEach(button => button.addEventListener('click', () => submitPersonalizedAssessment(button.dataset.submitCategory, button)));
    }

    async function submitPersonalizedAssessment(category, button) {
        const article = button.closest('article');
        const answers = [...article.querySelectorAll('fieldset')].map(fieldset => ({code: fieldset.dataset.question, option: fieldset.querySelector('input:checked')?.value}));
        if (answers.some(answer => !answer.option)) { showToast('Answer every question in this assessment.', 'warning'); return; }
        button.disabled = true;
        const response = await fetch('/api/personalized-assessment/submit', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({category, answers})});
        const result = await response.json();
        if (!response.ok) { button.disabled = false; showToast(result.error || 'Assessment submission failed.', 'error'); return; }
        button.textContent = `Score ${result.score}% · ${result.passed ? 'Passed' : 'Retry available'}`;
        button.insertAdjacentHTML('afterend', `<div class="personalized-result">${result.mistakes.length ? result.mistakes.map(m => `<p>${m.feedback}<br><small>Weak area: ${m.weak_area}</small></p>`).join('') : '<p>All decisions were correct.</p>'}<strong>${result.recommendation}</strong></div>`);
        speak(`Assessment score ${result.score} percent. ${result.passed ? 'Passed.' : 'Review the recommendations and retry.'}`);
    }

    await loadPersonalizedAssessments();
});
