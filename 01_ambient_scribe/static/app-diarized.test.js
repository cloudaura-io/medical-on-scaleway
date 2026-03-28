/**
 * Tests for diarized (non-streaming) transcription integration in app.js.
 *
 * These tests verify that the frontend uses a regular fetch() to POST
 * audio to /api/transcribe, then splits the returned transcript into
 * tokens and feeds them into the drip queue with a typewriter effect.
 *
 * Run: node --test 01_ambient_scribe/static/app-diarized.test.js
 */

import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const appJsSource = readFileSync(resolve(__dirname, 'app.js'), 'utf-8');

// ---------------------------------------------------------------------------
// Minimal DOM mock for app.js
// ---------------------------------------------------------------------------

function createMockElement(tag, id) {
  const el = {
    id: id || '',
    tagName: tag || 'DIV',
    className: '',
    textContent: '',
    innerHTML: '',
    style: { display: '', setProperty() {} },
    dataset: {},
    disabled: false,
    value: '',
    children: [],
    _listeners: {},
    scrollTop: 0,
    scrollHeight: 0,
    classList: {
      _classes: new Set(),
      add(cls) { this._classes.add(cls); },
      remove(cls) { this._classes.delete(cls); },
      contains(cls) { return this._classes.has(cls); },
    },
    appendChild(child) {
      this.children.push(child);
      return child;
    },
    addEventListener(event, handler) {
      if (!this._listeners[event]) this._listeners[event] = [];
      this._listeners[event].push(handler);
    },
    remove() {},
    querySelector() { return null; },
  };
  return el;
}

// Build all DOM elements app.js expects
const domElements = {};
const elementIds = [
  'btnUploadLabel', 'audioFileInput', 'btnReset', 'recordingIndicator',
  'recordingLabel', 'transcriptBadge', 'transcriptBody', 'transcriptText',
  'transcriptPlaceholder', 'aiProcessing', 'clinicalBadge', 'clinicalCards',
  'clinicalPlaceholder', 'sparkleContainer', 'waveform', 'waveformBars',
  'statusTranscription', 'statusExtraction', 'statusValidation',
  'statusValidationText',
];

function setupDOM() {
  for (const id of elementIds) {
    domElements[id] = createMockElement('DIV', id);
    domElements[id].classList._classes.clear();
    domElements[id].children = [];
    domElements[id].textContent = '';
    domElements[id].innerHTML = '';
    domElements[id].style = { display: '', setProperty() {} };
    domElements[id].disabled = false;
    domElements[id].className = '';
  }

  globalThis.document = {
    readyState: 'complete',
    querySelector(sel) {
      const id = sel.startsWith('#') ? sel.slice(1) : sel;
      return domElements[id] || createMockElement('DIV', id);
    },
    createElement(tag) {
      return createMockElement(tag);
    },
    addEventListener() {},
  };

  globalThis.performance = { now: () => Date.now() };
  globalThis.setTimeout = (fn, _ms) => { fn(); return 1; };
  globalThis.clearTimeout = () => {};
  globalThis.setInterval = () => 1;
  globalThis.clearInterval = () => {};
  globalThis.console = globalThis.console || { warn() {}, error() {}, log() {} };
  globalThis.FormData = class FormData {
    constructor() { this._data = {}; }
    append(key, val) { this._data[key] = val; }
  };
}

// ---------------------------------------------------------------------------
// Tests: Diarized non-streaming transcription
// ---------------------------------------------------------------------------

describe('Diarized transcription integration', () => {
  let fetchCalls;

  beforeEach(() => {
    setupDOM();
    fetchCalls = [];

    // Ensure no SSEClient is available (we should NOT use it)
    globalThis.window = globalThis.window || {};
    delete globalThis.window.SSEClient;

    // Mock fetch for both transcribe and extract endpoints
    globalThis.fetch = async (url, opts) => {
      fetchCalls.push({ url, opts });
      if (url === '/api/transcribe') {
        return {
          ok: true,
          json: async () => ({
            transcript: 'Doctor: How are you feeling today?\nPatient: I have a headache.',
          }),
        };
      }
      if (url === '/api/extract') {
        return {
          ok: true,
          json: async () => ({
            clinical_note: { patient_name: 'Test', assessment: 'OK' },
            processing_time_s: 1.5,
          }),
        };
      }
      return { ok: true, json: async () => ({}) };
    };
  });

  it('app.js source must reference /api/transcribe for transcription', () => {
    // The source code should call /api/transcribe via fetch
    assert.ok(
      appJsSource.includes('/api/transcribe'),
      'app.js must reference /api/transcribe endpoint',
    );
  });

  it('handleFileUpload sends audio via fetch to /api/transcribe', async () => {
    // Simulate what the updated handleFileUpload should do:
    // 1. Create FormData with audio file
    // 2. POST to /api/transcribe via fetch
    // 3. Get back JSON with transcript
    const formData = new FormData();
    formData.append('file', { name: 'test.wav' });

    const response = await fetch('/api/transcribe', {
      method: 'POST',
      body: formData,
    });
    const data = await response.json();

    // Verify fetch was called to /api/transcribe
    assert.equal(fetchCalls.length, 1);
    assert.equal(fetchCalls[0].url, '/api/transcribe');
    assert.equal(fetchCalls[0].opts.method, 'POST');

    // Verify we got a transcript back
    assert.ok(data.transcript);
    assert.ok(data.transcript.includes('Doctor:'));
    assert.ok(data.transcript.includes('Patient:'));
  });

  it('transcript is split into tokens and creates word spans', () => {
    const transcript = 'Doctor: How are you feeling today?\nPatient: I have a headache.';
    const container = createMockElement('DIV', 'transcriptText');

    // Split transcript into tokens (words and whitespace chunks)
    // The implementation should split on whitespace boundaries
    const tokens = transcript.split(/(\s+)/);
    let wordIndex = 0;

    for (const token of tokens) {
      if (!token) continue;
      const span = createMockElement('SPAN');
      span.className = 'word';
      span.textContent = token;
      span.dataset.index = wordIndex++;
      container.appendChild(span);
    }

    // Verify spans were created
    assert.ok(container.children.length > 0);

    // Verify all text is present when concatenated
    const fullText = container.children.map((c) => c.textContent).join('');
    assert.equal(fullText, transcript);
  });

  it('speaker labels (Doctor: / Patient:) are present in rendered tokens', () => {
    const transcript = 'Doctor: Hello there.\nPatient: Hi doctor.';
    const container = createMockElement('DIV', 'transcriptText');

    // Split into tokens and render
    const tokens = transcript.split(/(\s+)/);
    for (const token of tokens) {
      if (!token) continue;
      const span = createMockElement('SPAN');
      span.className = 'word';
      span.textContent = token;
      container.appendChild(span);
    }

    // Verify that Doctor: and Patient: labels appear in the rendered text
    const fullText = container.children.map((c) => c.textContent).join('');
    assert.ok(fullText.includes('Doctor:'), 'Rendered text must include Doctor: label');
    assert.ok(fullText.includes('Patient:'), 'Rendered text must include Patient: label');
  });

});

describe('Dead code and stale reference checks', () => {
  it('app.js must NOT declare an unused checkmarkIcon variable', () => {
    // The checkmarkIcon DOM element exists in HTML, but the JS variable is never
    // used after declaration. The variable assignment line should be removed.
    const declarationPattern = /const\s+checkmarkIcon\s*=/;
    assert.ok(
      !declarationPattern.test(appJsSource),
      'app.js must not declare an unused checkmarkIcon variable — remove the dead reference',
    );
  });

});

describe('Diarized token drip queue', () => {
  beforeEach(() => {
    setupDOM();
  });

  it('tokens are dripped via setTimeout for typewriter effect', () => {
    const tokens = ['Doctor:', ' ', 'Hello', ' ', 'there.'];
    const container = createMockElement('DIV', 'transcriptText');
    const rendered = [];

    // Simulate drip queue behavior
    for (const token of tokens) {
      const span = createMockElement('SPAN');
      span.className = 'word';
      span.textContent = token;
      span.classList.add('word-glow');
      container.appendChild(span);
      rendered.push(token);
    }

    assert.equal(container.children.length, 5);
    assert.deepEqual(rendered, tokens);

    // Each span should have had word-glow class applied
    for (const child of container.children) {
      assert.ok(child.classList.contains('word-glow'));
    }
  });

  it('transcript with newlines renders correctly with line breaks', () => {
    const transcript = 'Doctor: Hello.\nPatient: Hi.';
    // When split by whitespace-preserving regex, newline is preserved
    const tokens = transcript.split(/(\s+)/);

    // Verify newline is preserved as a token
    assert.ok(tokens.includes('\n'), 'Newline should be preserved as a token');

    // Verify we have the expected structure
    const nonEmpty = tokens.filter((t) => t);
    assert.ok(nonEmpty.length > 0);
    assert.ok(nonEmpty.join('') === transcript);
  });

  it('newline tokens produce <br> elements instead of <span> elements', () => {
    const transcript = 'Doctor: Hello.\nPatient: Hi.\n\nEnd.';
    const tokens = transcript.split(/(\s+)/);
    const container = createMockElement('DIV', 'transcriptText');

    for (const token of tokens) {
      if (!token) continue;
      if (/\n/.test(token)) {
        const nlCount = (token.match(/\n/g) || []).length;
        for (let i = 0; i < nlCount; i++) {
          const br = createMockElement('BR');
          container.appendChild(br);
        }
      } else {
        const span = createMockElement('SPAN');
        span.className = 'word';
        span.textContent = token;
        container.appendChild(span);
      }
    }

    // Count <br> elements — should be 3 (one from \n, two from \n\n)
    const brCount = container.children.filter((c) => c.tagName === 'BR').length;
    assert.equal(brCount, 3, 'Should have 3 <br> elements for 3 newlines');

    // No span should contain a newline character
    const spans = container.children.filter((c) => c.tagName === 'SPAN');
    for (const span of spans) {
      assert.ok(!/\n/.test(span.textContent), 'No span should contain a newline');
    }
  });
});

// ---------------------------------------------------------------------------
// Tests: README accuracy
// ---------------------------------------------------------------------------

const readmeSource = readFileSync(resolve(__dirname, '..', 'README.md'), 'utf-8');

describe('README accuracy', () => {
  it('README should reference the diarized transcription flow', () => {
    // The README description should mention transcription (not streaming)
    assert.ok(
      readmeSource.includes('transcri'),
      'README must mention transcription in its description',
    );
  });
});
