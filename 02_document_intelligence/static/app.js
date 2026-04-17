/* ============================================================
   Document Intelligence - Frontend Controller
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
        previewTabs:      $('#preview-tabs'),
        pdfCanvasHost:    $('#pdf-canvas-host'),
        processStatus:    $('#process-status'),
    };

    // Active tab in the document preview panel ('pdf' | 'text')
    state.previewTab = 'pdf';

    // PDF.js (window.pdfjsLib) and its worker are loaded as an ES module
    // from index.html so that v4.x's .mjs-only cdnjs build resolves.
    const PDF_PREVIEW_MAX_PAGES = 10;

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

    // ---- Inline process status (replaces the old full-screen overlay) ----

    let processStatusFadeTimer = null;

    function setProcessStatus(text, kind) {
        // kind: 'active' | 'done' | 'idle'
        if (!dom.processStatus) return;
        if (processStatusFadeTimer) {
            clearTimeout(processStatusFadeTimer);
            processStatusFadeTimer = null;
        }
        if (kind === 'idle' || !text) {
            dom.processStatus.classList.add('hidden');
            dom.processStatus.textContent = '';
            return;
        }
        dom.processStatus.classList.remove('hidden', 'is-done', 'is-active');
        dom.processStatus.classList.add(kind === 'done' ? 'is-done' : 'is-active');
        dom.processStatus.textContent = text;
        if (kind === 'done') {
            processStatusFadeTimer = setTimeout(() => {
                if (dom.processStatus) dom.processStatus.classList.add('hidden');
            }, 4000);
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
            buffer: null,   // raw PDF bytes - kept so the QUERY phase can re-render
        };
        state.files.push(entry);
        renderFileList();

        let buffer;
        try {
            buffer = await file.arrayBuffer();
            entry.buffer = buffer;
        } catch (err) {
            entry.status = 'error';
            renderFileList();
            console.error('File read error:', err);
            return;
        }

        try {
            const formData = new FormData();
            formData.append('file', new Blob([buffer], { type: 'application/pdf' }), file.name);
            const res = await fetch('api/upload', { method: 'POST', body: formData });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Upload failed');
            }

            const data = await res.json();
            entry.docId = data.doc_id;
            entry.status = 'queued';
            renderFileList();

            processDocument(entry);
        } catch (err) {
            entry.status = 'error';
            renderFileList();
            console.error('Upload error:', err);
        }
    }

    // Render a PDF (from cached ArrayBuffer) into the QUERY-phase left panel.
    async function renderPdfIntoCanvasHost(file) {
        const host = dom.pdfCanvasHost;
        if (!host) return;
        host.innerHTML = '';

        if (!file || !file.buffer) {
            host.innerHTML = '<div class="preview-empty">PDF preview unavailable for this document.</div>';
            return;
        }
        if (!window.pdfjsLib) {
            host.innerHTML = '<div class="preview-empty">PDF.js not loaded.</div>';
            return;
        }

        try {
            // pdf.js consumes the buffer; clone so the cached one stays usable.
            const pdf = await window.pdfjsLib.getDocument({ data: file.buffer.slice(0) }).promise;
            const total = pdf.numPages;
            const renderCount = Math.min(total, PDF_PREVIEW_MAX_PAGES);

            for (let pageNum = 1; pageNum <= renderCount; pageNum++) {
                const page = await pdf.getPage(pageNum);
                const viewport = page.getViewport({ scale: 1.3 });
                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');
                canvas.width = viewport.width;
                canvas.height = viewport.height;
                host.appendChild(canvas);
                await page.render({ canvasContext: ctx, viewport }).promise;
            }

            if (total > renderCount) {
                const more = document.createElement('div');
                more.className = 'preview-more';
                more.textContent = '+' + (total - renderCount) + ' more page(s)';
                host.appendChild(more);
            }
        } catch (err) {
            console.error('PDF preview error:', err);
            host.innerHTML = '<div class="preview-empty">Preview failed: ' + escapeHtml(err.message || String(err)) + '</div>';
        }
    }

    // ---- Document Processing (SSE) ----

    async function processDocument(entry) {
        if (!entry.docId) return;

        entry.status = 'processing';
        state.processing = true;
        setPhase('process');
        renderFileList();
        setProcessStatus('📄 Starting…', 'active');

        try {
            const res = await fetch(`api/process/${entry.docId}`, { method: 'POST' });
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
            setProcessStatus('⚠ Processing error: ' + (err.message || err), 'done');
            console.error('Process error:', err);
        }

        state.processing = false;
        renderFileList();
        updateStatus();
        checkAllDone();
    }

    function handleProcessEvent(entry, evt) {
        switch (evt.event) {
            case 'processing_started':
                setProcessStatus('📄 ' + (evt.filename || 'document') + ' — starting…', 'active');
                break;

            case 'page_processed':
                entry.pages = evt.total;
                entry.pageTexts = entry.pageTexts || [];
                entry.pageTexts.push({
                    page: evt.page,
                    text: evt.text,
                });
                setProcessStatus(`🔍 Vision model: page ${evt.page} of ${evt.total} scanned`, 'active');
                renderFileList();
                break;

            case 'indexing_started':
                setProcessStatus('🧩 Chunking text + 📐 generating embeddings…', 'active');
                break;

            case 'indexing_complete':
                entry.chunks = evt.chunks;
                state.chunksIndexed += evt.chunks;
                setProcessStatus(`✅ Indexed ${evt.chunks} chunks`, 'active');
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
                setProcessStatus(
                    `Last processed: ${evt.filename} · ${evt.pages}p · ${evt.chunks}ch`,
                    'done'
                );
                break;

            case 'error':
                entry.status = 'error';
                renderFileList();
                setProcessStatus('⚠ ' + (evt.detail || 'processing error'), 'done');
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

        try {
            const res = await fetch('api/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query }),
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Query failed');
            }

            const data = await res.json();
            removeTypingIndicator();
            addChatMessage('assistant', data.answer, data.sources);
        } catch (err) {
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

    // The currently displayed file in the preview panel — kept in module
    // scope so tab clicks can re-render without needing the dropdown event.
    let currentPreviewFile = null;

    function showDocumentPreview(file) {
        currentPreviewFile = file || null;

        // Always render the OCR text into the text pane (ready when user toggles).
        if (file && file.pageTexts && file.pageTexts.length > 0) {
            const text = file.pageTexts.map(p =>
                `--- Page ${p.page} ---\n${p.text}`
            ).join('\n\n');
            dom.extractedText.textContent = text;
        } else {
            dom.extractedText.textContent = 'No extracted text available.';
        }

        // Render or clear the PDF pane based on whichever tab is active.
        applyPreviewTab(state.previewTab);
    }

    function applyPreviewTab(tab) {
        state.previewTab = tab === 'text' ? 'text' : 'pdf';
        // Toggle button active states
        if (dom.previewTabs) {
            dom.previewTabs.querySelectorAll('.preview-tab').forEach(btn => {
                const isActive = btn.dataset.tab === state.previewTab;
                btn.classList.toggle('is-active', isActive);
                btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
            });
        }
        // Toggle pane visibility
        if (dom.pdfCanvasHost) {
            dom.pdfCanvasHost.classList.toggle('hidden', state.previewTab !== 'pdf');
        }
        if (dom.extractedText) {
            dom.extractedText.classList.toggle('hidden', state.previewTab !== 'text');
        }
        // Render PDF only when the PDF tab is the visible one (saves work).
        if (state.previewTab === 'pdf' && currentPreviewFile) {
            renderPdfIntoCanvasHost(currentPreviewFile);
        }
    }

    function initPreviewTabs() {
        if (!dom.previewTabs) return;
        dom.previewTabs.querySelectorAll('.preview-tab').forEach(btn => {
            btn.addEventListener('click', () => applyPreviewTab(btn.dataset.tab));
        });
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
        initPreviewTabs();
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
