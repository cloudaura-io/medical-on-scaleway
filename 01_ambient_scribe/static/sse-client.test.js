/**
 * Tests for sse-client.js SSE parser utility.
 *
 * Run: node --test 01_ambient_scribe/static/sse-client.test.js
 */

import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';

// sse-client.js is designed as a browser script that attaches to `window`.
// We simulate the browser global and import the module.
globalThis.window = globalThis.window || {};

// Dynamic import so the module attaches to our simulated window
await import('./sse-client.js');

const { parseSSELines } = window.SSEClient;

// ---------------------------------------------------------------------------
// Helper: create a ReadableStream from an array of string chunks
// ---------------------------------------------------------------------------
function makeStream(chunks) {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
}

// ---------------------------------------------------------------------------
// Tests for parseSSELines (the core line-level parser)
// ---------------------------------------------------------------------------

describe('parseSSELines', () => {
  it('parses a single SSE data line into a JSON object', () => {
    const lines = ['data: {"event":"transcript_chunk","text":"hello"}', ''];
    const events = parseSSELines(lines);
    assert.equal(events.length, 1);
    assert.deepEqual(events[0], { event: 'transcript_chunk', text: 'hello' });
  });

  it('parses multiple SSE events from a set of lines', () => {
    const lines = [
      'data: {"event":"transcript_chunk","text":"hello"}',
      '',
      'data: {"event":"transcript_chunk","text":"world"}',
      '',
    ];
    const events = parseSSELines(lines);
    assert.equal(events.length, 2);
    assert.equal(events[0].text, 'hello');
    assert.equal(events[1].text, 'world');
  });

  it('skips malformed JSON lines gracefully', () => {
    const lines = [
      'data: {"event":"transcript_chunk","text":"good"}',
      '',
      'data: NOT_VALID_JSON',
      '',
      'data: {"event":"transcript_done"}',
      '',
    ];
    const events = parseSSELines(lines);
    assert.equal(events.length, 2);
    assert.equal(events[0].text, 'good');
    assert.equal(events[1].event, 'transcript_done');
  });

  it('skips empty lines and non-data lines', () => {
    const lines = [
      '',
      ': this is a comment',
      'event: some_event',
      'data: {"event":"transcript_chunk","text":"only"}',
      '',
      '',
    ];
    const events = parseSSELines(lines);
    assert.equal(events.length, 1);
    assert.equal(events[0].text, 'only');
  });
});

// ---------------------------------------------------------------------------
// Tests for streamSSE (full stream consumption via fetch + ReadableStream)
// ---------------------------------------------------------------------------

describe('streamSSE - stream consumption', () => {
  it('handles incomplete lines across chunk boundaries (buffer management)', async () => {
    // Split a single SSE event across two chunks, mid-JSON
    const chunk1 = 'data: {"event":"transcript_ch';
    const chunk2 = 'unk","text":"split"}\n\n';

    const stream = makeStream([chunk1, chunk2]);
    const collected = [];

    await window.SSEClient.streamSSE(stream, (evt) => {
      collected.push(evt);
    });

    assert.equal(collected.length, 1);
    assert.equal(collected[0].text, 'split');
  });

  it('handles multiple events across many chunks', async () => {
    const stream = makeStream([
      'data: {"event":"transcript_chunk","text":"a"}\n\ndata: {"ev',
      'ent":"transcript_chunk","text":"b"}\n\ndata: {"event":"tra',
      'nscript_done"}\n\n',
    ]);
    const collected = [];

    await window.SSEClient.streamSSE(stream, (evt) => {
      collected.push(evt);
    });

    assert.equal(collected.length, 3);
    assert.equal(collected[0].text, 'a');
    assert.equal(collected[1].text, 'b');
    assert.equal(collected[2].event, 'transcript_done');
  });

  it('skips malformed JSON in stream gracefully', async () => {
    const stream = makeStream([
      'data: INVALID\n\ndata: {"event":"ok"}\n\n',
    ]);
    const collected = [];

    await window.SSEClient.streamSSE(stream, (evt) => {
      collected.push(evt);
    });

    assert.equal(collected.length, 1);
    assert.equal(collected[0].event, 'ok');
  });
});
