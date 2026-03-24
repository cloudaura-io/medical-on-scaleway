/* ===================================================================
   Showcase 3 — Cross-domain Medical Research Agent
   Frontend controller — Scaleway Brand Redesign
   =================================================================== */

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let isRunning = false;
let timerInterval = null;
let startTime = null;
let totalChunksRetrieved = 0;
let findingIndex = 0;
let domainChunkCounts = { pharmacology: 0, cardiology: 0, clinical_trials: 0 };
let queriedDomains = new Set();

// ---------------------------------------------------------------------------
// DOM references
// ---------------------------------------------------------------------------

const queryTextarea   = document.getElementById('query-input');
const runBtn          = document.getElementById('btn-run');
const agentLog        = document.getElementById('agent-log');
const findingsList    = document.getElementById('findings-list');
const findingsEmpty   = document.getElementById('findings-empty');
const disclaimer      = document.getElementById('disclaimer');
const disclaimerText  = document.getElementById('disclaimer-text');
const statusDot       = document.getElementById('status-dot');
const statusLabel     = document.getElementById('status-label');
const sampleContainer = document.getElementById('sample-queries');

// Status bar elements
const statModel       = document.getElementById('stat-model');
const statDomains     = document.getElementById('stat-domains');
const statChunks      = document.getElementById('stat-chunks');
const statCove        = document.getElementById('stat-cove');
const timerDisplay    = document.getElementById('timer-value');

// Domain nodes
const domainNodes = {
    pharmacology:    document.getElementById('node-pharmacology'),
    cardiology:      document.getElementById('node-cardiology'),
    clinical_trials: document.getElementById('node-clinical_trials'),
};

// SVG elements
const brainCore   = document.getElementById('brain-core');
const brainRings  = [
    document.getElementById('brain-ring-1'),
    document.getElementById('brain-ring-2'),
    document.getElementById('brain-ring-3'),
];
const orbitDots = [
    document.getElementById('orbit-dot-1'),
    document.getElementById('orbit-dot-2'),
    document.getElementById('orbit-dot-3'),
];
const connLines = {
    left:  document.getElementById('conn-left'),
    right: document.getElementById('conn-right'),
};

// Domain positions in SVG coordinates
const domainPositions = {
    pharmacology:    { x: 225, y: 100 },
    cardiology:      { x: 450, y: 100 },
    clinical_trials: { x: 675, y: 100 },
};
const centerPos = { x: 450, y: 100 };

// ---------------------------------------------------------------------------
// Initialization
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {
    loadSampleQueries();
    loadDomains();

    runBtn.addEventListener('click', () => {
        const query = queryTextarea.value.trim();
        if (query) runResearch(query);
    });

    // Allow Ctrl+Enter to submit
    queryTextarea.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === 'Enter') {
            e.preventDefault();
            runBtn.click();
        }
    });
});

// ---------------------------------------------------------------------------
// Load sample queries
// ---------------------------------------------------------------------------

async function loadSampleQueries() {
    try {
        const res = await fetch('/api/sample-queries');
        const queries = await res.json();

        sampleContainer.innerHTML = '';
        queries.forEach((q) => {
            const btn = document.createElement('button');
            btn.className = 'sample-btn';
            btn.textContent = q;
            btn.title = q;
            btn.addEventListener('click', () => {
                queryTextarea.value = q;
                queryTextarea.focus();
            });
            sampleContainer.appendChild(btn);
        });

        // Pre-fill first query
        if (queries.length > 0) {
            queryTextarea.value = queries[0];
        }
    } catch (err) {
        console.warn('Could not load sample queries:', err);
    }
}

// ---------------------------------------------------------------------------
// Load domain stats
// ---------------------------------------------------------------------------

async function loadDomains() {
    try {
        const res = await fetch('/api/domains');
        const domains = await res.json();

        domains.forEach((d) => {
            const key = d.name.toLowerCase().replace(/\s+/g, '_');
            const chunksEl = document.getElementById('chunks-' + key);
            if (chunksEl) {
                chunksEl.textContent = d.chunks + ' chunks';
            }
        });

        statDomains.textContent = domains.length;
    } catch (err) {
        console.warn('Could not load domains:', err);
    }
}

// ---------------------------------------------------------------------------
// Main: Run Research
// ---------------------------------------------------------------------------

function runResearch(query) {
    if (isRunning) return;

    // Reset UI
    resetUI();
    setRunning(true);

    // POST to /api/research and read SSE stream
    fetch('/api/research', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
    }).then((res) => {
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        function readChunk() {
            reader.read().then(({ done, value }) => {
                if (done) {
                    setRunning(false);
                    triggerCompletion();
                    return;
                }

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop(); // Keep incomplete line in buffer

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const step = JSON.parse(line.slice(6));
                            handleStep(step);
                        } catch (e) {
                            // ignore parse errors
                        }
                    }
                }

                readChunk();
            });
        }
        readChunk();
    }).catch((err) => {
        addAgentLogEntry('Error: ' + err.message, 'error');
        setRunning(false);
    });
}

// ---------------------------------------------------------------------------
// Handle each SSE step
// ---------------------------------------------------------------------------

function handleStep(step) {
    const { type, data } = step;

    switch (type) {
        case 'thinking':
            activateBrain();
            addAgentLogEntry(typeof data === 'string' ? data : JSON.stringify(data), 'thinking');
            break;

        case 'tool_call':
            handleToolCall(data);
            break;

        case 'tool_result':
            handleToolResult(data);
            break;

        case 'synthesis':
            triggerSynthesisAnimation();
            addAgentLogEntry(typeof data === 'string' ? data : 'Synthesizing findings across domains...', 'synthesis');
            break;

        case 'verification':
            addAgentLogEntry('Running Chain-of-Verification (CoVe) on synthesized claims...', 'verification');
            if (data && data.findings) {
                data.findings.forEach((finding, i) => {
                    setTimeout(() => addFinding(finding), i * 400);
                });
            }
            break;

        case 'final':
            handleFinal(data);
            break;

        default:
            addAgentLogEntry(JSON.stringify(data), 'tool_result');
    }
}

// ---------------------------------------------------------------------------
// Tool call handling
// ---------------------------------------------------------------------------

function handleToolCall(data) {
    const { name, arguments: args } = data;

    let logText = `<span class="log-fn-name">${escapeHtml(name)}</span>`;
    if (args) {
        const argParts = Object.entries(args).map(([k, v]) => `${k}="${v}"`);
        logText += ` (${argParts.map(escapeHtml).join(', ')})`;
    }
    addAgentLogEntry(logText, 'tool_call', true);

    // Determine which domain to highlight
    let domain = null;
    if (args && args.domain) {
        domain = args.domain.toLowerCase().replace(/\s+/g, '_');
    } else if (name === 'check_drug_interactions') {
        domain = 'pharmacology';
    }

    if (domain) {
        activateDomainNode(domain);
        fireBeamToDomain(domain);
    }
}

function handleToolResult(data) {
    const { name, result, domain, chunks_retrieved } = data;

    // Update domain node with chunk count
    let domainKey = null;
    if (domain) {
        domainKey = domain.toLowerCase().replace(/\s+/g, '_');
        if (chunks_retrieved) {
            totalChunksRetrieved += chunks_retrieved;
            statChunks.textContent = totalChunksRetrieved;

            // Update badge
            domainChunkCounts[domainKey] = (domainChunkCounts[domainKey] || 0) + chunks_retrieved;
            updateDomainBadge(domainKey, domainChunkCounts[domainKey]);

            // Update chunks label
            const chunksEl = document.getElementById('chunks-' + domainKey);
            if (chunksEl) {
                const baseText = chunksEl.textContent.split('+')[0].trim();
                const baseNum = parseInt(baseText) || 0;
                chunksEl.textContent = baseNum + ' + ' + domainChunkCounts[domainKey] + ' retrieved';
            }
        }

        // Fire return beam (data coming back)
        fireReturnBeam(domainKey);
    }

    // Summarize result for log
    let summary;
    try {
        const parsed = typeof result === 'string' ? JSON.parse(result) : result;
        if (Array.isArray(parsed)) {
            summary = `Retrieved ${parsed.length} chunks from knowledge base`;
            if (parsed.length > 0 && parsed[0].source) {
                summary += ` [${parsed[0].source}]`;
            }
        } else if (parsed.severity) {
            summary = `Interaction severity: ${parsed.severity.toUpperCase()} - ${parsed.description?.slice(0, 100)}...`;
        } else {
            summary = `Result received (${name})`;
        }
    } catch {
        summary = `Result received (${name})`;
    }

    addAgentLogEntry(summary, 'tool_result');
}

// ---------------------------------------------------------------------------
// Final result
// ---------------------------------------------------------------------------

function handleFinal(data) {
    if (typeof data === 'string') {
        addAgentLogEntry(data, 'final');
    } else {
        if (data.error) {
            addAgentLogEntry('Error: ' + data.error, 'error');
            return;
        }

        addAgentLogEntry('Analysis complete.', 'final');

        if (data.disclaimer) {
            disclaimer.classList.add('disclaimer--visible');
            disclaimerText.textContent = data.disclaimer;
        }

        // Update status bar
        if (data.domains_queried) statDomains.textContent = data.domains_queried;
        if (data.chunks_retrieved) {
            totalChunksRetrieved = data.chunks_retrieved;
            statChunks.textContent = totalChunksRetrieved;
        }
        if (data.claims_verified !== undefined || data.claims_unverified !== undefined) {
            const verified = data.claims_verified || 0;
            const unverified = data.claims_unverified || 0;
            statCove.textContent = `${verified}V / ${unverified}U`;
            statCove.classList.add('status-item__value--highlight');
        }
    }
}

// ---------------------------------------------------------------------------
// =================== ANIMATION ENGINE ===================
// ---------------------------------------------------------------------------

// --- Brain Activation ---
function activateBrain() {
    brainCore.classList.add('brain-core--active');
    brainRings.forEach(r => r.classList.add('brain-ring--active'));
    orbitDots.forEach(d => d.classList.add('orbit-dot--active'));
}

function deactivateBrain() {
    brainCore.classList.remove('brain-core--active', 'brain-core--synthesis');
    brainRings.forEach(r => r.classList.remove('brain-ring--active'));
    orbitDots.forEach(d => d.classList.remove('orbit-dot--active'));
}

// --- Domain Node Activation ---
function activateDomainNode(domain) {
    const node = domainNodes[domain];
    if (!node) return;

    node.classList.remove('domain-node--complete');
    node.classList.add('domain-node--querying');
    queriedDomains.add(domain);

    // Activate connection lines
    updateConnectionLines();
}

function completeDomainNode(domain) {
    const node = domainNodes[domain];
    if (!node) return;

    node.classList.remove('domain-node--querying');
    node.classList.add('domain-node--complete');
}

function updateConnectionLines() {
    const hasPharm = queriedDomains.has('pharmacology');
    const hasCardio = queriedDomains.has('cardiology');
    const hasClinical = queriedDomains.has('clinical_trials');

    if (hasPharm || hasCardio) {
        connLines.left.classList.add('domain-connection--active');
    }
    if (hasCardio || hasClinical) {
        connLines.right.classList.add('domain-connection--active');
    }
}

// --- Domain Badge Update ---
function updateDomainBadge(domain, count) {
    const badge = document.getElementById('badge-' + domain);
    if (!badge) return;

    badge.textContent = count;
    badge.classList.add('domain-node__badge--visible');

    // Trigger tick animation
    badge.classList.remove('domain-node__badge--tick');
    // Force reflow
    void badge.offsetWidth;
    badge.classList.add('domain-node__badge--tick');
}

// --- Beam Animations ---
function fireBeamToDomain(domain) {
    const particlesLayer = document.getElementById('particles-layer');
    const target = domainPositions[domain];
    if (!target) return;

    // Create a beam line
    const beam = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    beam.setAttribute('x1', centerPos.x);
    beam.setAttribute('y1', centerPos.y);
    beam.setAttribute('x2', target.x);
    beam.setAttribute('y2', target.y);
    beam.setAttribute('stroke', '#b824f9');
    beam.setAttribute('stroke-width', '3');
    beam.setAttribute('stroke-linecap', 'round');
    beam.setAttribute('filter', 'url(#glow-purple)');
    beam.style.opacity = '0';

    particlesLayer.appendChild(beam);

    // Animate
    requestAnimationFrame(() => {
        beam.style.transition = 'opacity 0.15s ease-in';
        beam.style.opacity = '1';

        setTimeout(() => {
            beam.style.transition = 'opacity 0.5s ease-out';
            beam.style.opacity = '0';
            setTimeout(() => beam.remove(), 500);
        }, 300);
    });

    // Fire particles along the path
    fireParticles(centerPos, target, '#b824f9', 5);
}

function fireReturnBeam(domain) {
    const target = domainPositions[domain];
    if (!target) return;

    // Fire cyan particles from domain back to center
    fireParticles(target, centerPos, '#03cfda', 8);

    // Complete the domain node after return
    setTimeout(() => completeDomainNode(domain), 600);
}

function fireParticles(from, to, color, count) {
    const particlesLayer = document.getElementById('particles-layer');

    for (let i = 0; i < count; i++) {
        const particle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        const delay = i * 80;
        const size = 2 + Math.random() * 2;

        particle.setAttribute('cx', from.x);
        particle.setAttribute('cy', from.y);
        particle.setAttribute('r', size);
        particle.setAttribute('fill', color);
        particle.style.opacity = '0';

        particlesLayer.appendChild(particle);

        setTimeout(() => {
            const duration = 400 + Math.random() * 300;
            const startTime = performance.now();

            // Add slight wobble
            const wobbleAmplitude = 5 + Math.random() * 10;
            const wobbleFreq = 2 + Math.random() * 3;

            function animateParticle(now) {
                const elapsed = now - startTime;
                const progress = Math.min(elapsed / duration, 1);
                const eased = easeOutCubic(progress);

                const dx = to.x - from.x;
                const dy = to.y - from.y;
                const perpX = -dy / Math.sqrt(dx * dx + dy * dy);
                const perpY = dx / Math.sqrt(dx * dx + dy * dy);
                const wobble = Math.sin(progress * Math.PI * wobbleFreq) * wobbleAmplitude * (1 - progress);

                const x = from.x + dx * eased + perpX * wobble;
                const y = from.y + dy * eased + perpY * wobble;

                particle.setAttribute('cx', x);
                particle.setAttribute('cy', y);
                particle.style.opacity = progress < 0.1 ? progress * 10 : (1 - progress) * 1.2;

                if (progress < 1) {
                    requestAnimationFrame(animateParticle);
                } else {
                    particle.remove();
                }
            }

            requestAnimationFrame(animateParticle);
        }, delay);
    }
}

function easeOutCubic(t) {
    return 1 - Math.pow(1 - t, 3);
}

// --- Synthesis Animation ---
function triggerSynthesisAnimation() {
    // All domain nodes pulse
    Object.values(domainNodes).forEach(node => {
        node.classList.add('domain-node--synthesis');
    });

    // Brain enters synthesis mode
    brainCore.classList.remove('brain-core--active');
    brainCore.classList.add('brain-core--synthesis');

    // Fire converging streams from all domains to center
    Object.keys(domainPositions).forEach((domain, i) => {
        setTimeout(() => {
            fireParticles(domainPositions[domain], centerPos, '#b824f9', 6);
        }, i * 200);
    });

    // Remove synthesis state after a while
    setTimeout(() => {
        Object.values(domainNodes).forEach(node => {
            node.classList.remove('domain-node--synthesis');
        });
    }, 3000);
}

// --- Completion Animation ---
function triggerCompletion() {
    // All nodes glow steady cyan
    Object.keys(domainNodes).forEach(domain => {
        completeDomainNode(domain);
    });

    // Connection lines go solid cyan
    connLines.left.classList.remove('domain-connection--active');
    connLines.left.classList.add('domain-connection--complete');
    connLines.right.classList.remove('domain-connection--active');
    connLines.right.classList.add('domain-connection--complete');

    // Brain goes cyan
    brainCore.classList.remove('brain-core--active', 'brain-core--synthesis');
    brainCore.classList.add('brain-core--complete');

    // Stop orbit dots and brain rings
    brainRings.forEach(r => r.classList.remove('brain-ring--active'));
    orbitDots.forEach(d => {
        d.classList.remove('orbit-dot--active');
        d.style.fill = '#03cfda';
        d.style.opacity = '0.5';
    });

    // Sparkle burst on findings panel
    triggerSparkles();
}

function triggerSparkles() {
    const findingsPanel = document.querySelector('.panel--findings');
    if (!findingsPanel) return;

    const rect = findingsPanel.getBoundingClientRect();
    const overlay = document.createElement('div');
    overlay.className = 'sparkle-overlay';
    document.body.appendChild(overlay);

    const colors = ['#8c40ef', '#b824f9', '#03cfda', '#ffffff', '#792dd4'];

    for (let i = 0; i < 30; i++) {
        const sparkle = document.createElement('div');
        sparkle.className = 'sparkle';
        sparkle.style.left = (rect.left + Math.random() * rect.width) + 'px';
        sparkle.style.top = (rect.top + Math.random() * rect.height * 0.5) + 'px';
        sparkle.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
        sparkle.style.animationDelay = (Math.random() * 0.5) + 's';
        sparkle.style.animationDuration = (1 + Math.random() * 1) + 's';
        overlay.appendChild(sparkle);
    }

    setTimeout(() => overlay.remove(), 2500);
}

// ---------------------------------------------------------------------------
// Agent log entries
// ---------------------------------------------------------------------------

function addAgentLogEntry(text, type, isHtml) {
    // Remove cursor if present
    const cursor = agentLog.querySelector('.log-cursor');
    if (cursor) cursor.remove();

    // Remove welcome message if present
    const welcome = agentLog.querySelector('.log-welcome');
    if (welcome) welcome.remove();

    const entry = document.createElement('div');
    entry.className = `log-entry log-entry--${type || 'default'}`;

    const time = document.createElement('span');
    time.className = 'log-entry__time';
    time.textContent = getElapsed();

    const prefixes = {
        thinking:     '[THINK]',
        tool_call:    '[TOOL]',
        tool_result:  '[RESULT]',
        synthesis:    '[SYNTH]',
        verification: '[CoVe]',
        final:        '[DONE]',
        error:        '[ERROR]',
    };

    const prefix = document.createElement('span');
    prefix.className = 'log-entry__prefix';
    prefix.textContent = (prefixes[type] || '') + ' ';

    entry.appendChild(time);
    entry.appendChild(prefix);

    if (isHtml) {
        const contentSpan = document.createElement('span');
        contentSpan.innerHTML = text;
        entry.appendChild(contentSpan);
    } else {
        const content = document.createTextNode(text);
        entry.appendChild(content);
    }

    agentLog.appendChild(entry);

    // Add cursor
    const newCursor = document.createElement('span');
    newCursor.className = 'log-cursor';
    agentLog.appendChild(newCursor);

    // Auto-scroll
    const logBody = agentLog.closest('.panel__body');
    if (logBody) logBody.scrollTop = logBody.scrollHeight;
}

// ---------------------------------------------------------------------------
// Findings cards
// ---------------------------------------------------------------------------

function addFinding(finding) {
    if (findingsEmpty) findingsEmpty.style.display = 'none';

    const status = (finding.status || 'NO_EVIDENCE').toLowerCase();

    const card = document.createElement('div');
    card.className = `finding-card finding-card--${status}`;
    card.style.animationDelay = `${findingIndex * 0.15}s`;

    // Icons
    const iconsSVG = {
        verified:    '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>',
        unverified:  '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M12 9v2m0 4h.01"/></svg>',
        no_evidence: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><line x1="5" y1="12" x2="19" y2="12"/></svg>',
    };

    // Status label
    const statusLabels = {
        verified:    'VERIFIED',
        unverified:  'UNVERIFIED',
        no_evidence: 'NO EVIDENCE',
    };

    const hasExplanation = finding.explanation && finding.explanation.length > 0;

    card.innerHTML = `
        <div class="finding-card__header">
            <span class="finding-card__icon finding-card__icon--${status}">${iconsSVG[status] || ''}</span>
            <span class="finding-card__status finding-card__status--${status}">${statusLabels[status] || status}</span>
            <div class="finding-card__verify-ring">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    ${status === 'verified'
                        ? '<polyline points="20 6 9 17 4 12" stroke="#03cfda"/>'
                        : status === 'unverified'
                        ? '<path d="M12 9v2m0 4h.01M12 3a9 9 0 100 18 9 9 0 000-18z" stroke="#ff602e"/>'
                        : '<line x1="8" y1="12" x2="16" y2="12" stroke="#4a5270"/>'}
                </svg>
            </div>
        </div>
        <div class="finding-card__claim">${escapeHtml(finding.claim)}</div>
        ${hasExplanation ? `<div class="finding-card__explanation">${escapeHtml(finding.explanation)}</div>` : ''}
        ${finding.source ? `<span class="finding-card__source">${escapeHtml(finding.source)}</span>` : ''}
        ${hasExplanation ? '<div class="finding-card__expand-hint">click to expand</div>' : ''}
    `;

    // Click to expand evidence
    if (hasExplanation) {
        card.addEventListener('click', () => {
            card.classList.toggle('finding-card--expanded');
            const hint = card.querySelector('.finding-card__expand-hint');
            if (hint) {
                hint.textContent = card.classList.contains('finding-card--expanded') ? 'click to collapse' : 'click to expand';
            }
        });
    }

    findingsList.appendChild(card);
    findingIndex++;

    // Add verification shake for unverified
    if (status === 'unverified') {
        setTimeout(() => {
            card.style.animation = 'shakeReject 0.5s ease-in-out';
            setTimeout(() => {
                card.style.animation = '';
            }, 500);
        }, 500 + findingIndex * 150);
    }

    // Log the verification
    const logPrefix = status === 'verified' ? 'PASS' : status === 'unverified' ? 'WARN' : 'SKIP';
    addAgentLogEntry(
        `[${logPrefix}] ${finding.claim.slice(0, 80)}...`,
        'verification'
    );

    // Scroll findings panel
    const findingsBody = findingsList.closest('.panel__body');
    if (findingsBody) {
        setTimeout(() => { findingsBody.scrollTop = findingsBody.scrollHeight; }, 100);
    }
}

// ---------------------------------------------------------------------------
// UI state management
// ---------------------------------------------------------------------------

function setRunning(running) {
    isRunning = running;
    runBtn.disabled = running;

    const btnText = runBtn.querySelector('.btn-run__text');
    const btnIcon = runBtn.querySelector('.btn-run__icon');

    if (running) {
        btnText.textContent = 'Running...';
        btnIcon.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin-icon"><path d="M12 2v4m0 12v4m-7.07-3.93l2.83-2.83m8.48-8.48l2.83-2.83M2 12h4m12 0h4m-3.93 7.07l-2.83-2.83M7.76 7.76L4.93 4.93"/></svg>';
        runBtn.classList.add('btn-run--running');
    } else {
        btnText.textContent = 'Run Agent';
        btnIcon.innerHTML = '&#9889;';
        runBtn.classList.remove('btn-run--running');
    }

    statusDot.classList.toggle('header__status-dot--active', running);
    statusLabel.classList.toggle('header__status-label--active', running);
    statusLabel.textContent = running ? 'ACTIVE' : 'IDLE';

    if (running) {
        startTime = Date.now();
        timerInterval = setInterval(updateTimer, 100);
        activateBrain();
    } else {
        clearInterval(timerInterval);
        timerInterval = null;
    }
}

function resetUI() {
    // Clear agent log
    agentLog.innerHTML = '';

    // Clear findings
    findingsList.innerHTML = '';
    const emptyPlaceholder = document.createElement('div');
    emptyPlaceholder.className = 'findings-empty';
    emptyPlaceholder.id = 'findings-empty';
    emptyPlaceholder.innerHTML = `
        <div class="findings-empty__icon">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#30363d" stroke-width="1"><path d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/></svg>
        </div>
        <div class="findings-empty__text">Awaiting agent analysis...</div>
        <div class="findings-empty__sub">Run a query to see verified findings</div>
    `;
    findingsList.appendChild(emptyPlaceholder);
    findingIndex = 0;

    // Reset domain nodes
    Object.values(domainNodes).forEach(node => {
        node.classList.remove('domain-node--querying', 'domain-node--complete', 'domain-node--synthesis');
    });
    queriedDomains.clear();
    domainChunkCounts = { pharmacology: 0, cardiology: 0, clinical_trials: 0 };

    // Reset badges
    ['pharmacology', 'cardiology', 'clinical_trials'].forEach(d => {
        const badge = document.getElementById('badge-' + d);
        if (badge) {
            badge.classList.remove('domain-node__badge--visible', 'domain-node__badge--tick');
            badge.textContent = '0';
        }
    });

    // Reset SVG elements
    deactivateBrain();
    brainCore.classList.remove('brain-core--complete');

    connLines.left.classList.remove('domain-connection--active', 'domain-connection--complete');
    connLines.right.classList.remove('domain-connection--active', 'domain-connection--complete');

    // Reset orbit dot styles
    orbitDots.forEach(d => {
        d.style.fill = '';
        d.style.opacity = '';
    });

    // Clear any remaining particles
    const particlesLayer = document.getElementById('particles-layer');
    if (particlesLayer) particlesLayer.innerHTML = '';

    // Reset status bar
    totalChunksRetrieved = 0;
    statChunks.textContent = '0';
    statCove.textContent = 'Pending';
    statCove.classList.remove('status-item__value--highlight');
    statChunks.classList.remove('status-item__value--highlight');

    // Hide disclaimer
    disclaimer.classList.remove('disclaimer--visible');
}

function updateTimer() {
    if (!startTime) return;
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    timerDisplay.textContent = elapsed + 's';
}

function getElapsed() {
    if (!startTime) return '0.0s';
    return ((Date.now() - startTime) / 1000).toFixed(1) + 's';
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// Add spinning animation for the loading icon
const spinStyle = document.createElement('style');
spinStyle.textContent = `
    @keyframes spinIcon {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    .spin-icon {
        animation: spinIcon 1.5s linear infinite;
        display: inline-block;
    }
`;
document.head.appendChild(spinStyle);
