/* =========================================================================
   Ambient Scribe — Frontend Controller
   Scaleway Medical AI Lab — Premium Scaleway Brand Edition
   ========================================================================= */

(function () {
  'use strict';

  // -----------------------------------------------------------------------
  // DOM references
  // -----------------------------------------------------------------------

  const $ = (sel) => document.querySelector(sel);
  const btnUploadLabel    = $('#btnUploadLabel');
  const audioFileInput    = $('#audioFileInput');
  const btnReset          = $('#btnReset');
  const recordingInd      = $('#recordingIndicator');
  const recordingLabel    = $('#recordingLabel');
  const transcriptBadge   = $('#transcriptBadge');
  const transcriptBody    = $('#transcriptBody');
  const transcriptText    = $('#transcriptText');
  const transcriptHolder  = $('#transcriptPlaceholder');
  const aiProcessing      = $('#aiProcessing');
  const clinicalBadge     = $('#clinicalBadge');
  const clinicalCards     = $('#clinicalCards');
  const clinicalHolder    = $('#clinicalPlaceholder');
  const sparkleContainer  = $('#sparkleContainer');
  const waveform          = $('#waveform');
  const waveformBars      = $('#waveformBars');
  const statusTranscript  = $('#statusTranscription');
  const statusExtraction  = $('#statusExtraction');
  const statusValidation  = $('#statusValidation');
  const statusValText     = $('#statusValidationText');
  const checkmarkIcon     = $('#checkmarkIcon');

  // -----------------------------------------------------------------------
  // State
  // -----------------------------------------------------------------------

  let timerStart    = null;
  let timerInterval = null;
  let isProcessing  = false;
  let sparkleInterval = null;

  // -----------------------------------------------------------------------
  // Waveform bars setup
  // -----------------------------------------------------------------------

  function initWaveform() {
    const barCount = 80;
    waveformBars.innerHTML = '';
    for (let i = 0; i < barCount; i++) {
      const bar = document.createElement('div');
      bar.className = 'waveform__bar';
      bar.style.setProperty('--bar-height', `${6 + Math.random() * 30}px`);
      bar.style.setProperty('--delay', `${Math.random() * 600}ms`);
      waveformBars.appendChild(bar);
    }
  }

  // -----------------------------------------------------------------------
  // Sparkle particle effects
  // -----------------------------------------------------------------------

  function startSparkles() {
    stopSparkles();
    sparkleInterval = setInterval(() => {
      const dot = document.createElement('div');
      dot.className = Math.random() > 0.5 ? 'sparkle-dot' : 'sparkle-dot sparkle-dot--cyan';
      dot.style.left = `${10 + Math.random() * 80}%`;
      dot.style.bottom = `${Math.random() * 30}%`;
      dot.style.animationDuration = `${1.2 + Math.random() * 1.2}s`;
      dot.style.width = dot.style.height = `${3 + Math.random() * 4}px`;
      sparkleContainer.appendChild(dot);
      setTimeout(() => dot.remove(), 2400);
    }, 100);
  }

  function stopSparkles() {
    if (sparkleInterval) {
      clearInterval(sparkleInterval);
      sparkleInterval = null;
    }
  }

  // -----------------------------------------------------------------------
  // Text glow effect for streaming words
  // -----------------------------------------------------------------------

  function applyTextGlow(wordElements) {
    wordElements.forEach((el, i) => {
      setTimeout(() => {
        el.classList.add('word-glow');
      }, i * 30);
    });
  }

  // -----------------------------------------------------------------------
  // Timer
  // -----------------------------------------------------------------------

  function startTimer() {
    timerStart = performance.now();
    timerInterval = setInterval(() => {
      const elapsed = ((performance.now() - timerStart) / 1000).toFixed(1);
      statusTranscript.textContent = `${elapsed}s`;
    }, 100);
  }

  function stopTimer() {
    if (timerInterval) {
      clearInterval(timerInterval);
      timerInterval = null;
    }
  }

  // -----------------------------------------------------------------------
  // State transitions
  // -----------------------------------------------------------------------

  function setIdle() {
    isProcessing = false;
    btnUploadLabel.classList.remove('is-disabled');
    audioFileInput.disabled = false;
    recordingInd.className = 'recording-indicator';
    recordingLabel.textContent = 'Idle';
    transcriptBadge.className = 'panel__badge';
    transcriptBadge.textContent = 'waiting';
    clinicalBadge.className = 'panel__badge';
    clinicalBadge.textContent = 'pending';
    statusValText.textContent = 'Ready';
    statusValidation.className = 'status-bar__value status-bar__value--status';
    waveform.classList.remove('is-active');
    aiProcessing.classList.remove('is-visible');
    stopSparkles();
  }

  function setTranscribing() {
    isProcessing = true;
    btnUploadLabel.classList.add('is-disabled');
    audioFileInput.disabled = true;
    recordingInd.className = 'recording-indicator is-active';
    recordingLabel.textContent = 'Transcribing';
    transcriptBadge.className = 'panel__badge is-active';
    transcriptBadge.textContent = 'processing';
    clinicalBadge.className = 'panel__badge';
    clinicalBadge.textContent = 'pending';
    statusValText.textContent = 'Transcribing';
    statusValidation.className = 'status-bar__value status-bar__value--status is-active';
    waveform.classList.add('is-active');

    transcriptHolder.style.display = 'none';
    aiProcessing.classList.add('is-visible');
    transcriptText.classList.remove('is-visible');
    transcriptText.innerHTML = '';
    clinicalHolder.style.display = '';
    clinicalCards.innerHTML = '';
  }

  function setTranscriptReady() {
    aiProcessing.classList.remove('is-visible');
    transcriptText.classList.add('is-visible');
  }

  function setExtracting() {
    recordingInd.className = 'recording-indicator is-active';
    recordingLabel.textContent = 'Extracting';
    transcriptBadge.className = 'panel__badge is-complete';
    transcriptBadge.textContent = 'complete';
    clinicalBadge.className = 'panel__badge is-active';
    clinicalBadge.textContent = 'processing';
    statusValText.textContent = 'Extracting';
    waveform.classList.remove('is-active');

    clinicalHolder.style.display = 'none';
    showLoadingCards();
    startSparkles();
  }

  function setComplete(processingTime) {
    isProcessing = false;
    btnUploadLabel.classList.remove('is-disabled');
    audioFileInput.disabled = false;
    recordingInd.className = 'recording-indicator is-complete';
    recordingLabel.textContent = 'Complete';
    clinicalBadge.className = 'panel__badge is-complete';
    clinicalBadge.textContent = 'extracted';
    statusValText.textContent = 'Validated';
    statusValidation.className = 'status-bar__value status-bar__value--status is-complete';
    stopSparkles();
    if (processingTime) {
      statusExtraction.textContent = `${processingTime}s`;
    }
  }

  function setError(message) {
    isProcessing = false;
    btnUploadLabel.classList.remove('is-disabled');
    audioFileInput.disabled = false;
    recordingInd.className = 'recording-indicator';
    recordingLabel.textContent = 'Error';
    statusValText.textContent = message || 'Error';
    statusValidation.className = 'status-bar__value status-bar__value--status is-error';
    waveform.classList.remove('is-active');
    aiProcessing.classList.remove('is-visible');
    stopSparkles();
  }

  // -----------------------------------------------------------------------
  // Loading placeholder cards
  // -----------------------------------------------------------------------

  function showLoadingCards() {
    clinicalCards.innerHTML = '';
    const sections = ['Patient', 'Symptoms', 'Medications', 'Vitals', 'Assessment', 'Plan'];
    sections.forEach((label, i) => {
      const card = document.createElement('div');
      card.className = 'clinical-card clinical-card--loading';
      card.style.animationDelay = `${i * 120}ms`;
      card.innerHTML = `
        <div class="clinical-card__header">
          <span class="clinical-card__label">${label}</span>
        </div>
        <div class="clinical-card__content">
          <div class="shimmer-line" style="width: ${70 + Math.random() * 30}%"></div>
          <div class="shimmer-line" style="width: ${50 + Math.random() * 40}%"></div>
          <div class="shimmer-line" style="width: ${40 + Math.random() * 30}%"></div>
        </div>
      `;
      clinicalCards.appendChild(card);
    });
  }

  // -----------------------------------------------------------------------
  // Render clinical note
  // -----------------------------------------------------------------------

  const SECTION_ICONS = {
    patient: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
    symptoms: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>',
    medications: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg>',
    vitals: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>',
    assessment: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>',
    plan: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>',
  };

  const VITAL_LABELS = {
    blood_pressure:    'Blood Pressure',
    heart_rate:        'Heart Rate',
    temperature:       'Temperature',
    respiratory_rate:  'Respiratory Rate',
    oxygen_saturation: 'SpO\u2082',
  };

  function formatVitalValue(key, val) {
    if (val === null || val === undefined) return '--';
    if (key === 'heart_rate')        return `${val} bpm`;
    if (key === 'temperature')       return `${val} \u00B0F`;
    if (key === 'respiratory_rate')  return `${val} /min`;
    if (key === 'oxygen_saturation') return `${val}%`;
    return String(val);
  }

  function renderClinicalNote(data) {
    clinicalCards.innerHTML = '';
    const sections = [];

    // Patient
    const patientLines = [];
    if (data.patient_name) patientLines.push(`<strong>${esc(data.patient_name)}</strong>`);
    if (data.age) patientLines.push(`Age ${data.age}`);
    if (data.sex) patientLines.push(capitalize(data.sex));
    if (data.chief_complaint) patientLines.push(`<br/><em>&ldquo;${esc(data.chief_complaint)}&rdquo;</em>`);
    sections.push({ key: 'patient', label: 'Patient', html: patientLines.join(' &middot; ') });

    // Symptoms
    if (data.symptoms && data.symptoms.length) {
      const items = data.symptoms.map((s) => `<li>${esc(s)}</li>`).join('');
      sections.push({ key: 'symptoms', label: 'Symptoms', html: `<ul>${items}</ul>` });
    }

    // Medications
    if (data.medications && data.medications.length) {
      const items = data.medications.map((m) => `<li>${esc(m)}</li>`).join('');
      sections.push({ key: 'medications', label: 'Medications', html: `<ul>${items}</ul>` });
    }

    // Vitals
    if (data.vitals) {
      const items = Object.entries(data.vitals)
        .filter(([, v]) => v !== null && v !== undefined)
        .map(([k, v]) => `
          <div class="vital-item">
            <span class="vital-item__label">${VITAL_LABELS[k] || k}</span>
            <span class="vital-item__value">${formatVitalValue(k, v)}</span>
          </div>
        `)
        .join('');
      if (items) {
        sections.push({ key: 'vitals', label: 'Vitals', html: `<div class="vital-grid">${items}</div>` });
      }
    }

    // Assessment
    if (data.assessment) {
      sections.push({ key: 'assessment', label: 'Assessment', html: `<p>${esc(data.assessment)}</p>` });
    }

    // Plan
    if (data.plan && data.plan.length) {
      const items = data.plan.map((p, i) => `<li><strong>${i + 1}.</strong> ${esc(p)}</li>`).join('');
      sections.push({ key: 'plan', label: 'Plan', html: `<ul>${items}</ul>` });
    }

    sections.forEach((section, i) => {
      const card = document.createElement('div');
      card.className = 'clinical-card';
      card.style.animationDelay = `${i * 200}ms`;
      card.innerHTML = `
        <div class="clinical-card__header">
          <span class="clinical-card__icon">${SECTION_ICONS[section.key] || ''}</span>
          <span class="clinical-card__label">${section.label}</span>
        </div>
        <div class="clinical-card__content">${section.html}</div>
      `;
      clinicalCards.appendChild(card);
    });

    // Stop sparkles shortly after cards render
    setTimeout(() => stopSparkles(), 1500);
  }

  // -----------------------------------------------------------------------
  // Upload and process audio file
  // -----------------------------------------------------------------------

  async function handleFileUpload(file) {
    if (isProcessing) return;

    resetUI();
    setTranscribing();
    startTimer();

    try {
      // Step 1 — Transcribe
      const formData = new FormData();
      formData.append('file', file);

      const transcribeRes = await fetch('/api/transcribe', {
        method: 'POST',
        body: formData,
      });

      if (!transcribeRes.ok) {
        const err = await transcribeRes.json().catch(() => ({}));
        throw new Error(err.detail || err.error || `Transcription failed (${transcribeRes.status})`);
      }

      const transcribeData = await transcribeRes.json();
      const transcript = transcribeData.transcript;

      stopTimer();

      // Display the transcript with glow effect
      setTranscriptReady();
      transcriptText.innerHTML = '';
      const words = transcript.split(/\s+/);
      const wordElements = [];
      words.forEach((word, i) => {
        const span = document.createElement('span');
        span.className = 'word';
        span.textContent = word + ' ';
        span.dataset.index = i;
        transcriptText.appendChild(span);
        wordElements.push(span);
      });

      // Apply the purple text glow animation to each word
      applyTextGlow(wordElements);

      // Step 2 — Extract clinical note
      setExtracting();

      const extractRes = await fetch('/api/extract', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transcript }),
      });

      if (!extractRes.ok) {
        const err = await extractRes.json().catch(() => ({}));
        throw new Error(err.detail || err.error || `Extraction failed (${extractRes.status})`);
      }

      const extractData = await extractRes.json();
      renderClinicalNote(extractData.clinical_note);
      setComplete(extractData.processing_time_s);
    } catch (err) {
      stopTimer();
      setError(err.message || 'Processing failed');
      console.error('Pipeline error:', err);
    }
  }

  // -----------------------------------------------------------------------
  // Reset
  // -----------------------------------------------------------------------

  function resetUI() {
    stopTimer();
    setIdle();
    transcriptHolder.style.display = '';
    transcriptText.classList.remove('is-visible');
    transcriptText.innerHTML = '';
    clinicalHolder.style.display = '';
    clinicalCards.innerHTML = '';
    statusTranscript.textContent = '--';
    statusExtraction.textContent = '--';
    // Reset the file input so the same file can be re-uploaded
    audioFileInput.value = '';
  }

  // -----------------------------------------------------------------------
  // Helpers
  // -----------------------------------------------------------------------

  function esc(str) {
    const el = document.createElement('span');
    el.textContent = str;
    return el.innerHTML;
  }

  function capitalize(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
  }

  // -----------------------------------------------------------------------
  // Init
  // -----------------------------------------------------------------------

  function init() {
    initWaveform();
    audioFileInput.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (file) handleFileUpload(file);
    });
    btnReset.addEventListener('click', resetUI);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
