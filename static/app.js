document.addEventListener('DOMContentLoaded', () => {
    const btnTrain = document.getElementById('btn-train');
    const btnTestA = document.getElementById('btn-test-a');
    const btnTestB = document.getElementById('btn-test-b');
    const trainStatus = document.getElementById('train-status');
    const consoleOutput = document.getElementById('console-output');

    function appendLog(text, className) {
        const div = document.createElement('div');
        div.className = `log-entry ${className}`;
        div.textContent = text;
        consoleOutput.appendChild(div);
        consoleOutput.scrollTop = consoleOutput.scrollHeight;
        return div;
    }

    function appendHTML(html, className) {
        const div = document.createElement('div');
        div.className = `log-entry ${className}`;
        div.innerHTML = html;
        consoleOutput.appendChild(div);
        consoleOutput.scrollTop = consoleOutput.scrollHeight;
        return div;
    }

    async function handleTrain() {
        btnTrain.disabled = true;
        const loader = appendHTML('<i class="ph-fill ph-circle-notch spinning"></i> Training ML Models (Isolation Forest & Baselines)...', 'loading-log');
        
        try {
            const res = await fetch('/api/train', { method: 'POST' });
            const data = await res.json();
            
            loader.remove();
            
            if(data.status === 'success') {
                appendLog(`✅ ${data.message}`, 'success');
                trainStatus.innerHTML = `<i class="ph ph-check-circle"></i> ${data.message}`;
                trainStatus.classList.remove('hidden');
                
                // Enable tests
                btnTestA.disabled = false;
                btnTestB.disabled = false;
            } else {
                appendLog(`❌ ${data.message}`, 'error');
                btnTrain.disabled = false;
            }
        } catch (e) {
            loader.remove();
            appendLog(`❌ Connection Error: ${e.message}`, 'error');
            btnTrain.disabled = false;
        }
    }

    async function runTest(endpoint, type) {
        // Disable buttons
        btnTestA.disabled = true;
        btnTestB.disabled = true;
        
        appendLog('------------------------------------------------------------', 'system');
        appendLog(`[*] Initializing Orchestration for Test ${type}...`, 'info');
        
        const loader = appendHTML('<i class="ph-fill ph-circle-notch spinning"></i> Awaiting Agent orchestration and Gateway validation...', 'loading-log');

        try {
            const res = await fetch(endpoint, { method: 'POST' });
            const data = await res.json();
            loader.remove();

            appendLog(`> USER QUERY: ${data.query}`, 'query');

            // Format logs from python print output to look beautiful
            const logs = data.logs.split('\n');
            let isError = false;

            for (let line of logs) {
                if(!line.trim()) continue;
                
                // Colorize based on content
                if (line.includes('ALLOW')) {
                    appendLog(line, 'success');
                } else if (line.includes('DENY') || line.includes('❌') || line.includes('ALERT')) {
                    appendLog(line, 'error');
                    isError = true;
                } else if (line.includes('✔') || line.includes('✅')) {
                    appendLog(line, 'success');
                } else if (line.includes('📨 REQUEST') || line.includes('Agent :')) {
                    appendLog(line, 'info');
                } else {
                    appendLog(line, 'system');
                }
                
                // Small artificial delay for visual effect
                await new Promise(r => setTimeout(r, 20));
            }

            appendLog(`Final Agent Response:`, 'info');
            appendLog(data.response, isError ? 'response-error' : 'response');

        } catch (e) {
            loader.remove();
            appendLog(`❌ Error: ${e.message}`, 'error');
        } finally {
            btnTestA.disabled = false;
            btnTestB.disabled = false;
        }
    }

    btnTrain.addEventListener('click', handleTrain);
    btnTestA.addEventListener('click', () => runTest('/api/test-a', 'A (Normal)'));
    btnTestB.addEventListener('click', () => runTest('/api/test-b', 'B (Quarantine)'));
});
