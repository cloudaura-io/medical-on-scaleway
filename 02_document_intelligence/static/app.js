/* ============================================================
   Document Intelligence — Frontend Controller
   Scaleway Brand Design
   ============================================================ */

(function () {
    'use strict';

    // ---- State ----
    const state = {
        phase: 'upload',          // 'upload' | 'process' | 'query'
        files: [],                // {id, docId, name, status, pages, chunks, pageTexts}
        chunksIndexed: 0,
        documentsReady: 0,
        processing: false,
        querying: false,
    };

    // ---- DOM refs ----
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    const dom = {
        phaseSteps:       $$('.phase-step'),
        phaseConnectors:  $$('.phase-connector'),
        uploadSection:    $('#upload-section'),
        splitView:        $('#split-view'),
        uploadZone:       $('#upload-zone'),
        fileInput:        $('#file-input'),
        fileList:         $('#file-list'),
        docSelect:        $('#doc-select'),
        extractedText:    $('#extracted-text'),
        chatMessages:     $('#chat-messages'),
        queryInput:       $('#query-input'),
        queryBtn:         $('#query-btn'),
        sampleQuestions:  $('#sample-questions'),
        statusChunks:     $('#status-chunks'),
        statusDocs:       $('#status-docs'),
        statusDot:        $('#status-dot'),
        aiOverlay:        $('#ai-overlay'),
        aiScanner:        $('#ai-scanner'),
        aiEmbeddings:     $('#ai-embeddings'),
        aiRadar:          $('#ai-radar'),
        embeddingsCanvas: $('#embeddings-canvas'),
    };

    // ---- Phase Management ----

    function setPhase(phase) {
        state.phase = phase;
        const phases = ['upload', 'process', 'query'];
        const idx = phases.indexOf(phase);

        dom.phaseSteps.forEach((step, i) => {
            step.classList.remove('active', 'completed');
            if (i < idx) step.classList.add('completed');
            else if (i === idx) step.classList.add('active');
        });

        dom.phaseConnectors.forEach((conn, i) => {
            conn.classList.remove('active', 'completed');
            if (i < idx) conn.classList.add('completed');
            else if (i === idx) conn.classList.add('active');
        });

        // Show/hide sections
        dom.uploadSection.classList.toggle('hidden', phase === 'query');
        dom.splitView.classList.toggle('hidden', phase === 'upload');

        if (phase === 'query') {
            dom.queryInput.focus();
        }
    }

    // ---- AI Animation System ----

    function showAiAnimation(type) {
        dom.aiOverlay.classList.remove('hidden');
        dom.aiScanner.classList.add('hidden');
        dom.aiEmbeddings.classList.add('hidden');
        dom.aiRadar.classList.add('hidden');

        switch (type) {
            case 'ocr':
                dom.aiScanner.classList.remove('hidden');
                break;
            case 'embedding':
                dom.aiEmbeddings.classList.remove('hidden');
                startEmbeddingAnimation();
                break;
            case 'search':
                dom.aiRadar.classList.remove('hidden');
                break;
        }
    }

    function hideAiAnimation() {
        dom.aiOverlay.classList.add('hidden');
        stopEmbeddingAnimation();
    }

    // ---- Embedding Constellation Animation ----
    let embeddingAnimFrame = null;

    function startEmbeddingAnimation() {
        const canvas = dom.embeddingsCanvas;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const w = canvas.width;
        const h = canvas.height;

        const particles = [];
        const numParticles = 30;
        const connectionDist = 60;

        for (let i = 0; i < numParticles; i++) {
            particles.push({
                x: Math.random() * w,
                y: Math.random() * h,
                vx: (Math.random() - 0.5) * 0.8,
                vy: (Math.random() - 0.5) * 0.8,
                radius: Math.random() * 2.5 + 1,
                alpha: Math.random() * 0.5 + 0.3,
            });
        }

        function animate() {
            ctx.clearRect(0, 0, w, h);

            // Update positions
            for (const p of particles) {
                p.x += p.vx;
                p.y += p.vy;
                if (p.x < 0 || p.x > w) p.vx *= -1;
                if (p.y < 0 || p.y > h) p.vy *= -1;
            }

            // Draw connections
            for (let i = 0; i < particles.length; i++) {
                for (let j = i + 1; j < particles.length; j++) {
                    const dx = particles[i].x - particles[j].x;
                    const dy = particles[i].y - particles[j].y;
                    const dist = Math.sqrt(dx * dx + dy * dy);
                    if (dist < connectionDist) {
                        const alpha = (1 - dist / connectionDist) * 0.4;
                        ctx.beginPath();
                        ctx.moveTo(particles[i].x, particles[i].y);
                        ctx.lineTo(particles[j].x, particles[j].y);
                        ctx.strokeStyle = `rgba(140, 64, 239, ${alpha})`;
                        ctx.lineWidth = 1;
                        ctx.stroke();
                    }
                }
            }

            // Draw particles
            for (const p of particles) {
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(140, 64, 239, ${p.alpha})`;
                ctx.fill();

                // Glow
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.radius * 3, 0, Math.PI * 2);
                const gradient = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.radius * 3);
                gradient.addColorStop(0, `rgba(140, 64, 239, ${p.alpha * 0.3})`);
                gradient.addColorStop(1, 'rgba(140, 64, 239, 0)');
                ctx.fillStyle = gradient;
                ctx.fill();
            }

            embeddingAnimFrame = requestAnimationFrame(animate);
        }

        animate();
    }

    function stopEmbeddingAnimation() {
        if (embeddingAnimFrame) {
            cancelAnimationFrame(embeddingAnimFrame);
            embeddingAnimFrame = null;
        }
    }

    // ---- Typing Indicator ----

    function showTypingIndicator() {
        const indicator = document.createElement('div');
        indicator.className = 'typing-indicator';
        indicator.id = 'typing-indicator';
        indicator.innerHTML = `
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
        `;
        dom.chatMessages.appendChild(indicator);
        dom.chatMessages.scrollTop = dom.chatMessages.scrollHeight;
    }

    function removeTypingIndicator() {
        const indicator = $('#typing-indicator');
        if (indicator) indicator.remove();
    }

    // ---- File Upload ----

    function initUpload() {
        const zone = dom.uploadZone;

        zone.addEventListener('dragover', (e) => {
            e.preventDefault();
            zone.classList.add('drag-over');
        });

        zone.addEventListener('dragleave', () => {
            zone.classList.remove('drag-over');
        });

        zone.addEventListener('drop', (e) => {
            e.preventDefault();
            zone.classList.remove('drag-over');
            const files = Array.from(e.dataTransfer.files).filter(
                f => f.type === 'application/pdf'
            );
            files.forEach(uploadFile);
        });

        dom.fileInput.addEventListener('change', (e) => {
            Array.from(e.target.files).forEach(uploadFile);
            e.target.value = '';
        });
    }

    async function uploadFile(file) {
        const localId = crypto.randomUUID ? crypto.randomUUID() : Date.now().toString();
        const entry = {
            id: localId,
            docId: null,
            name: file.name,
            status: 'uploading',
            pages: 0,
            chunks: 0,
            pageTexts: [],
        };
        state.files.push(entry);
        renderFileList();

        try {
            const formData = new FormData();
            formData.append('file', file);
            const res = await fetch('/api/upload', { method: 'POST', body: formData });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Upload failed');
            }

            const data = await res.json();
            entry.docId = data.doc_id;
            entry.status = 'queued';
            renderFileList();

            // Auto-process
            processDocument(entry);
        } catch (err) {
            entry.status = 'error';
            renderFileList();
            console.error('Upload error:', err);
        }
    }

    // ---- Document Processing (SSE) ----

    async function processDocument(entry) {
        if (!entry.docId) return;

        entry.status = 'processing';
        state.processing = true;
        setPhase('process');
        renderFileList();

        // Show OCR animation
        showAiAnimation('ocr');

        try {
            const res = await fetch(`/api/process/${entry.docId}`, { method: 'POST' });
            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;
                    try {
                        const evt = JSON.parse(line.slice(6));
                        handleProcessEvent(entry, evt);
                    } catch (_) { /* skip malformed */ }
                }
            }
        } catch (err) {
            entry.status = 'error';
            console.error('Process error:', err);
        }

        hideAiAnimation();
        state.processing = false;
        renderFileList();
        updateStatus();
        checkAllDone();
    }

    function handleProcessEvent(entry, evt) {
        switch (evt.event) {
            case 'page_processed':
                entry.pages = evt.total;
                entry.pageTexts = entry.pageTexts || [];
                entry.pageTexts.push({
                    page: evt.page,
                    preview: evt.text_preview,
                });
                renderFileList();
                break;

            case 'indexing_complete':
                // Switch to embedding animation
                showAiAnimation('embedding');
                entry.chunks = evt.chunks;
                state.chunksIndexed += evt.chunks;
                updateStatus();
                break;

            case 'complete':
                entry.status = 'done';
                entry.pages = evt.pages;
                entry.chunks = evt.chunks;
                state.documentsReady++;
                renderFileList();
                updateDocSelector();
                updateStatus();
                break;

            case 'error':
                entry.status = 'error';
                renderFileList();
                break;
        }
    }

    // ---- Query ----

    function initQuery() {
        dom.queryBtn.addEventListener('click', sendQuery);
        dom.queryInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendQuery();
            }
        });
    }

    async function sendQuery() {
        const query = dom.queryInput.value.trim();
        if (!query || state.querying) return;

        state.querying = true;
        dom.queryBtn.disabled = true;
        dom.queryInput.value = '';

        addChatMessage('user', query);
        showTypingIndicator();

        // Show radar search animation briefly
        showAiAnimation('search');

        try {
            const res = await fetch('/api/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query }),
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Query failed');
            }

            const data = await res.json();
            hideAiAnimation();
            removeTypingIndicator();
            addChatMessage('assistant', data.answer, data.sources);
        } catch (err) {
            hideAiAnimation();
            removeTypingIndicator();
            addChatMessage('assistant', `Error: ${err.message}`);
        }

        state.querying = false;
        dom.queryBtn.disabled = false;
        dom.queryInput.focus();
    }

    // ---- Rendering ----

    function renderFileList() {
        dom.fileList.innerHTML = state.files.map((f, i) => {
            const statusClass = f.status;
            const statusLabel = {
                uploading: 'Uploading...',
                queued: 'Queued',
                processing: 'Processing...',
                done: `${f.pages}p / ${f.chunks}ch`,
                error: 'Error',
            }[f.status] || f.status;

            const iconSvg = f.status === 'done'
                ? '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><polyline points="16 13 10.5 18 8 15.5"/></svg>'
                : '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>';

            return `
                <li class="file-item" style="animation-delay: ${i * 0.08}s">
                    <span class="file-icon">${iconSvg}</span>
                    <span class="file-name">${escapeHtml(f.name)}</span>
                    <span class="file-status ${statusClass}">${statusLabel}</span>
                </li>`;
        }).join('');
    }

    function updateDocSelector() {
        const ready = state.files.filter(f => f.status === 'done');
        dom.docSelect.innerHTML = '<option value="">Select a document...</option>' +
            ready.map(f =>
                `<option value="${f.docId}">${escapeHtml(f.name)} (${f.pages} pages)</option>`
            ).join('');

        dom.docSelect.onchange = () => {
            const docId = dom.docSelect.value;
            const file = state.files.find(f => f.docId === docId);
            showDocumentPreview(file);
        };

        // Auto-select first
        if (ready.length > 0 && !dom.docSelect.value) {
            dom.docSelect.value = ready[0].docId;
            showDocumentPreview(ready[0]);
        }
    }

    function showDocumentPreview(file) {
        if (!file || !file.pageTexts || file.pageTexts.length === 0) {
            dom.extractedText.textContent = 'No extracted text available.';
            return;
        }

        const text = file.pageTexts.map(p =>
            `--- Page ${p.page} ---\n${p.preview}`
        ).join('\n\n');
        dom.extractedText.textContent = text;
    }

    function addChatMessage(role, text, sources) {
        const msg = document.createElement('div');
        msg.className = `chat-msg ${role}`;

        if (role === 'assistant') {
            // Render citations inline as cyan pills
            let html = escapeHtml(text).replace(
                /\[Source:\s*([^\]]+)\]/g,
                '<span class="citation" data-source="$1">$1</span>'
            );
            html = html.replace(/\n/g, '<br>');
            msg.innerHTML = html;

            // Add sources panel if available
            if (sources && sources.length > 0) {
                const panel = document.createElement('details');
                panel.className = 'sources-panel';
                panel.innerHTML = `
                    <summary>${sources.length} source${sources.length > 1 ? 's' : ''} referenced</summary>
                    ${sources.map(s => `
                        <div class="source-item">
                            <span class="source-score">${(s.score * 100).toFixed(0)}%</span>
                            <div class="source-name">${escapeHtml(s.source)}</div>
                            <div class="source-content">${escapeHtml(s.content.slice(0, 200))}...</div>
                        </div>
                    `).join('')}
                `;
                msg.appendChild(panel);
            }
        } else {
            msg.textContent = text;
        }

        dom.chatMessages.appendChild(msg);
        dom.chatMessages.scrollTop = dom.chatMessages.scrollHeight;

        // Add citation click handlers
        msg.querySelectorAll('.citation').forEach(pill => {
            pill.addEventListener('click', () => {
                highlightSource(pill.dataset.source);
            });
        });
    }

    function highlightSource(sourceName) {
        // Find the document in the selector and switch to it
        const file = state.files.find(f => f.name === sourceName);
        if (file) {
            dom.docSelect.value = file.docId;
            showDocumentPreview(file);
        }

        // Flash the extracted text panel with purple glow
        dom.extractedText.style.transition = 'box-shadow 0.3s ease';
        dom.extractedText.style.boxShadow = '0 0 0 3px rgba(140, 64, 239, 0.4), 0 0 20px rgba(140, 64, 239, 0.15)';
        setTimeout(() => {
            dom.extractedText.style.boxShadow = '';
        }, 1500);
    }

    function updateStatus() {
        dom.statusChunks.textContent = state.chunksIndexed;
        dom.statusDocs.textContent = state.documentsReady;
        dom.statusDot.classList.toggle('inactive', state.documentsReady === 0);
    }

    function checkAllDone() {
        const allDone = state.files.length > 0 &&
            state.files.every(f => f.status === 'done' || f.status === 'error');
        if (allDone && state.files.some(f => f.status === 'done')) {
            setPhase('query');
        }
    }

    // ---- Sample Questions ----

    function initSampleQuestions() {
        dom.sampleQuestions.addEventListener('click', (e) => {
            if (e.target.classList.contains('sample-q')) {
                dom.queryInput.value = e.target.textContent;
                dom.queryInput.focus();
            }
        });
    }

    // ---- Utility ----

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // ---- Init ----

    function init() {
        initUpload();
        initQuery();
        initSampleQuestions();
        setPhase('upload');
        updateStatus();
    }

    // Run on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
