/* =========================================================================
   Drug Interactions - Scaleway Medical AI Lab
   Frontend JavaScript
   ========================================================================= */

(function () {
  'use strict';

  // -----------------------------------------------------------------------
  // DOM refs
  // -----------------------------------------------------------------------

  var medInput          = document.getElementById('medInput');
  var populationSelect  = document.getElementById('populationSelect');
  var btnAnalyze        = document.getElementById('btnAnalyze');
  var sampleQueries     = document.getElementById('sampleQueries');
  var traceLog          = document.getElementById('traceLog');
  var traceCounter      = document.getElementById('traceCounter');
  var findingsContainer = document.getElementById('findingsContainer');
  var findingsCounter   = document.getElementById('findingsCounter');
  var reportPanel       = document.getElementById('reportPanel');
  var reportContent     = document.getElementById('reportContent');
  var statusDot         = document.getElementById('statusDot');
  var statusLabel       = document.getElementById('statusLabel');
  var homeLink          = document.getElementById('homeLink');

  // -----------------------------------------------------------------------
  // State
  // -----------------------------------------------------------------------

  var stepCount    = 0;
  var isAnalyzing  = false;
  var statusInterval = null;
  var dotInterval   = null;

  // Rotating status messages shown before first SSE event arrives
  var loadingMessages = [
    'Connecting to Mistral Small 3.2',
    'Searching drug database',
    'Querying FDA label index',
    'Looking up drug interactions',
    'Checking population warnings',
    'Analyzing pharmacokinetics',
    'Cross-referencing contraindications',
    'Evaluating adverse reactions',
    'Classifying severity levels',
    'Synthesizing findings'
  ];
  var loadingMsgIndex = 0;
  var firstEventReceived = false;

  // -----------------------------------------------------------------------
  // Home link - works under any path prefix
  // -----------------------------------------------------------------------

  if (homeLink) {
    var base = location.pathname.replace(/\/[^/]*\/?$/, '');
    homeLink.href = base ? base + '/' : '/';
  }

  // -----------------------------------------------------------------------
  // Fetch and render sample queries
  // -----------------------------------------------------------------------

  function loadSampleQueries() {
    fetch('api/sample-queries')
      .then(function (r) { return r.json(); })
      .then(function (samples) {
        sampleQueries.innerHTML = '';
        samples.forEach(function (sample) {
          var btn = document.createElement('button');
          btn.className = 'btn btn--ghost btn--sm sample-btn';
          btn.textContent = sample.label;
          btn.addEventListener('click', function () {
            medInput.value = sample.medications.join(', ');
            if (sample.population) {
              populationSelect.value = sample.population;
            } else {
              populationSelect.value = '';
            }
          });
          sampleQueries.appendChild(btn);
        });
      })
      .catch(function (err) {
        console.error('Failed to load sample queries:', err);
      });
  }

  loadSampleQueries();

  // -----------------------------------------------------------------------
  // Status helpers
  // -----------------------------------------------------------------------

  function setStatus(label, active) {
    statusLabel.textContent = label;
    if (active) {
      statusDot.classList.add('is-active');
    } else {
      statusDot.classList.remove('is-active');
    }
  }

  function startLoadingIndicator() {
    firstEventReceived = false;
    loadingMsgIndex = 0;

    // Show initial loading message in trace panel
    var placeholder = traceLog.querySelector('.trace-placeholder');
    if (placeholder) {
      placeholder.className = 'trace-loading';
      placeholder.innerHTML = '<span class="loading-text">' + loadingMessages[0] + '</span><span class="loading-dots"></span>';
    }

    // Animate dots
    var dotCount = 0;
    dotInterval = setInterval(function () {
      var dotsEl = traceLog.querySelector('.loading-dots');
      if (!dotsEl) return;
      dotCount = (dotCount + 1) % 4;
      dotsEl.textContent = '.'.repeat(dotCount);
    }, 400);

    // Rotate status messages every 3s
    statusInterval = setInterval(function () {
      if (firstEventReceived) {
        stopLoadingIndicator();
        return;
      }
      loadingMsgIndex = (loadingMsgIndex + 1) % loadingMessages.length;
      var textEl = traceLog.querySelector('.loading-text');
      if (textEl) {
        textEl.textContent = loadingMessages[loadingMsgIndex];
      }
      setStatus(loadingMessages[loadingMsgIndex], true);
    }, 3000);

    setStatus(loadingMessages[0], true);
  }

  function stopLoadingIndicator() {
    if (statusInterval) { clearInterval(statusInterval); statusInterval = null; }
    if (dotInterval) { clearInterval(dotInterval); dotInterval = null; }
    var loadingEl = traceLog.querySelector('.trace-loading');
    if (loadingEl) loadingEl.remove();
  }

  // -----------------------------------------------------------------------
  // Reset UI
  // -----------------------------------------------------------------------

  function resetUI() {
    stepCount = 0;
    traceLog.innerHTML = '<div class="trace-placeholder">Agent trace will appear here as the ReAct loop runs...</div>';
    traceCounter.textContent = '0 steps';
    findingsContainer.innerHTML = '<div class="findings-placeholder">Severity-classified findings will appear after analysis completes.</div>';
    findingsCounter.textContent = '--';
    reportPanel.style.display = 'none';
    reportContent.textContent = '';
    setStatus('IDLE', false);
  }

  // -----------------------------------------------------------------------
  // Render a trace entry (THINK / ACT / OBSERVE)
  // -----------------------------------------------------------------------

  function renderTraceEntry(traceData) {
    // Remove placeholder on first entry
    var placeholder = traceLog.querySelector('.trace-placeholder');
    if (placeholder) placeholder.remove();

    var entry = document.createElement('div');
    entry.className = 'trace-entry';

    // Think
    if (traceData.think) {
      var thinkLabel = document.createElement('div');
      thinkLabel.className = 'trace-label trace-label--think';
      thinkLabel.textContent = 'THINK';
      entry.appendChild(thinkLabel);

      var thinkText = document.createElement('div');
      thinkText.className = 'trace-text';
      thinkText.textContent = traceData.think;
      entry.appendChild(thinkText);
    }

    // Act
    if (traceData.act) {
      var actLabel = document.createElement('div');
      actLabel.className = 'trace-label trace-label--act';
      actLabel.textContent = 'ACT';
      entry.appendChild(actLabel);

      var actText = document.createElement('div');
      actText.className = 'trace-text';
      actText.textContent = traceData.act;
      entry.appendChild(actText);
    }

    // Observe
    if (traceData.observe) {
      var obsLabel = document.createElement('div');
      obsLabel.className = 'trace-label trace-label--observe';
      obsLabel.textContent = 'OBSERVE';
      entry.appendChild(obsLabel);

      var obsText = document.createElement('div');
      obsText.className = 'trace-text trace-text--truncated';
      obsText.textContent = traceData.observe;
      entry.appendChild(obsText);
    }

    traceLog.appendChild(entry);
    traceLog.scrollTop = traceLog.scrollHeight;

    stepCount++;
    traceCounter.textContent = stepCount + ' step' + (stepCount !== 1 ? 's' : '');
  }

  // -----------------------------------------------------------------------
  // Render findings
  // -----------------------------------------------------------------------

  function renderFindings(findings) {
    if (!Array.isArray(findings) || findings.length === 0) return;

    findingsContainer.innerHTML = '';
    findingsCounter.textContent = findings.length + ' finding' + (findings.length !== 1 ? 's' : '');

    findings.forEach(function (finding) {
      var severity = (finding.severity || 'moderate').toLowerCase();
      var card = document.createElement('div');
      card.className = 'finding-card finding-card--' + severity;

      var sevLabel = document.createElement('div');
      sevLabel.className = 'finding-card__severity finding-card__severity--' + severity;
      sevLabel.textContent = (finding.severity || 'MODERATE').toUpperCase();
      card.appendChild(sevLabel);

      var claim = document.createElement('div');
      claim.className = 'finding-card__claim';
      claim.textContent = finding.claim || '';
      card.appendChild(claim);

      if (finding.evidence_snippet) {
        var evidence = document.createElement('div');
        evidence.className = 'finding-card__evidence';
        evidence.textContent = '"' + finding.evidence_snippet + '"';
        card.appendChild(evidence);
      }

      if (finding.verified === false) {
        var warn = document.createElement('div');
        warn.className = 'finding-card__warn';
        warn.textContent = 'Snippet substituted with verbatim text from the cited FDA section (model paraphrase detected).';
        card.appendChild(warn);
      }

      if (finding.source_id) {
        var source = document.createElement('div');
        source.className = 'finding-card__source';

        if (finding.label_url) {
          var link = document.createElement('a');
          link.href = finding.label_url;
          link.target = '_blank';
          link.rel = 'noopener';
          link.textContent = finding.source_id;
          source.appendChild(link);
        } else {
          source.textContent = finding.source_id;
        }
        card.appendChild(source);
      }

      findingsContainer.appendChild(card);
    });
  }

  function showFinalReport(finalText) {
    reportPanel.style.display = 'block';
    reportContent.textContent = finalText;
  }

  // -----------------------------------------------------------------------
  // Analyze - SSE stream
  // -----------------------------------------------------------------------

  function runAnalysis() {
    var rawInput = medInput.value.trim();
    if (!rawInput) return;

    var medications = rawInput.split(',').map(function (s) { return s.trim(); }).filter(Boolean);
    if (medications.length === 0) return;

    var population = populationSelect.value || null;

    resetUI();
    isAnalyzing = true;
    btnAnalyze.disabled = true;
    startLoadingIndicator();

    var body = JSON.stringify({
      medications: medications,
      population: population
    });

    fetch('api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body
    })
    .then(function (response) {
      if (!response.ok) {
        throw new Error('Server error: ' + response.status);
      }

      var reader = response.body.getReader();
      var decoder = new TextDecoder();
      var buffer = '';

      function processChunk(result) {
        if (result.done) {
          finishAnalysis();
          return;
        }

        buffer += decoder.decode(result.value, { stream: true });

        // Process complete SSE events
        var events = buffer.split('\n\n');
        buffer = events.pop(); // Keep incomplete event in buffer

        events.forEach(function (eventBlock) {
          if (!eventBlock.trim()) return;

          var lines = eventBlock.split('\n');
          var eventType = '';
          var dataLines = [];

          lines.forEach(function (line) {
            if (line.startsWith('event: ')) {
              eventType = line.substring(7).trim();
            } else if (line.startsWith('data: ')) {
              dataLines.push(line.substring(6));
            }
          });

          if (dataLines.length === 0) return;

          var dataStr = dataLines.join('\n');
          try {
            var data = JSON.parse(dataStr);
            handleSSEEvent(eventType, data);
          } catch (e) {
            console.warn('Failed to parse SSE data:', dataStr);
          }
        });

        return reader.read().then(processChunk);
      }

      return reader.read().then(processChunk);
    })
    .catch(function (err) {
      console.error('Analysis failed:', err);
      setStatus('ERROR', false);

      // Show error in trace
      var errDiv = document.createElement('div');
      errDiv.className = 'trace-entry';
      errDiv.innerHTML = '<div class="trace-label" style="color:var(--color-error)">ERROR</div>' +
                         '<div class="trace-text">' + escapeHtml(err.message) + '</div>';
      traceLog.appendChild(errDiv);

      finishAnalysis();
    });
  }

  function handleSSEEvent(eventType, data) {
    if (!firstEventReceived) {
      firstEventReceived = true;
      stopLoadingIndicator();
      setStatus('ANALYZING', true);
    }
    if (data.type === 'trace' && data.data) {
      renderTraceEntry(data.data);
    } else if (data.type === 'findings' && Array.isArray(data.data)) {
      renderFindings(data.data);
    } else if (data.type === 'final' && data.data) {
      showFinalReport(data.data);
    } else if (data.type === 'error' && data.data) {
      var errDiv = document.createElement('div');
      errDiv.className = 'trace-entry';
      errDiv.innerHTML = '<div class="trace-label" style="color:var(--color-error)">ERROR</div>' +
                         '<div class="trace-text">' + escapeHtml(data.data.error || 'Unknown error') + '</div>';
      traceLog.appendChild(errDiv);
    }
  }

  function finishAnalysis() {
    isAnalyzing = false;
    btnAnalyze.disabled = false;
    stopLoadingIndicator();
    setStatus('COMPLETE', false);
  }

  function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // -----------------------------------------------------------------------
  // Event listeners
  // -----------------------------------------------------------------------

  btnAnalyze.addEventListener('click', runAnalysis);

  medInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !isAnalyzing) {
      runAnalysis();
    }
  });

})();
