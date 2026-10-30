document.addEventListener('DOMContentLoaded', async () => {
    const moduleSelect = document.getElementById('moduleSelect');
    const crewSelect = document.getElementById('crewSelect');
    const questionBox = document.getElementById('questionBox');
    const optionsBox = document.getElementById('optionsBox');
    const submitBtn = document.getElementById('submitAnswerBtn');
    const voiceBtn = document.getElementById('voiceBtn');
    const resultBox = document.getElementById('trainingResult');
    const certificateBox = document.getElementById('certificateBox');
    let currentModule = null;
    let selectedAnswer = null;

    const moduleResponse = await fetch('/api/training-modules');
    const modules = await moduleResponse.json();
    currentModule = modules.find((item) => item.code === moduleSelect.value) || modules[0];

    function renderQuestion(module) {
        const options = JSON.parse(module.options.replace(/'/g, '"'));
        questionBox.innerHTML = `<strong>${module.title}</strong><p>${module.question}</p>`;
        optionsBox.innerHTML = options.map((item) => `
            <label class="option-item">
                <input type="radio" name="answer" value="${item}">
                ${item}
            </label>
        `).join('');
        selectedAnswer = null;
        optionsBox.querySelectorAll('input').forEach((item) => {
            item.addEventListener('change', () => { selectedAnswer = item.value; });
        });
    }

    moduleSelect.addEventListener('change', () => {
        const selected = modules.find((item) => item.code === moduleSelect.value);
        currentModule = selected;
        renderQuestion(selected);
    });

    renderQuestion(currentModule);

    submitBtn.addEventListener('click', async () => {
        const answer = selectedAnswer || currentModule.correct_answer;
        const payload = {
            crew_id: crewSelect.value,
            module_code: currentModule.code,
            answer
        };
        const response = await fetch('/api/training-submit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await response.json();
        resultBox.innerHTML = `
            <p><strong>Score:</strong> ${result.score}%</p>
            <p><strong>Recommendation:</strong> ${result.recommendation}</p>
            <p><strong>Weak area:</strong> ${result.weak_area}</p>
        `;

        if (result.certificate_eligible) {
            certificateBox.innerHTML = `
                <div class="card bg-light p-3 mt-3">
                    <h6>Demo completion certificate</h6>
                    <p>${crewSelect.options[crewSelect.selectedIndex].text}</p>
                    <p>Score: ${result.score}%</p>
                    <small>Training demonstration only; not a statutory maritime certificate.</small>
                </div>
            `;
        } else {
            certificateBox.innerHTML = '<p>Below 80% — repeat the module and review the safety briefing.</p>';
        }
    });

    voiceBtn.addEventListener('click', () => {
        if ('speechSynthesis' in window) {
            const msg = new SpeechSynthesisUtterance(currentModule ? currentModule.description : 'Safety training instruction');
            window.speechSynthesis.speak(msg);
            showToast('Voice guidance started.', 'success');
        } else {
            showToast('Voice guidance is not available in this browser.', 'warning');
        }
    });
});
