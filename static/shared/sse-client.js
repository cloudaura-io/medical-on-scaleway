/**
 * SSE Client Utility for POST-based Server-Sent Events.
 *
 * Standard EventSource only supports GET requests. This utility uses
 * fetch() + ReadableStream to consume SSE from a POST endpoint.
 *
 * Pattern adapted from 03_research_agent/static/app.js (lines 160-199).
 *
 * @module SSEClient
 */

(function (exports) {
  'use strict';

  /**
   * Parse an array of raw SSE lines and extract parsed JSON events.
   *
   * Only lines starting with "data: " are processed. Each such line's
   * payload is parsed as JSON. Malformed JSON is logged and skipped.
   * Empty lines, comments (":"), and other field types are ignored.
   *
   * @param {string[]} lines - Array of raw SSE lines.
   * @returns {Object[]} Array of parsed event objects.
   */
  function parseSSELines(lines) {
    const events = [];
    for (const line of lines) {
      if (!line.startsWith('data: ')) {
        continue;
      }
      const payload = line.slice(6);
      try {
        events.push(JSON.parse(payload));
      } catch (e) {
        console.warn('[SSEClient] Skipping malformed JSON:', payload);
      }
    }
    return events;
  }

  /**
   * Consume a ReadableStream of SSE data, invoking a callback for each
   * parsed event object.
   *
   * Handles incomplete lines that are split across read boundaries by
   * maintaining an internal buffer.
   *
   * @param {ReadableStream} stream - The readable body stream from fetch().
   * @param {function(Object): void} onEvent - Callback invoked for each parsed event.
   * @returns {Promise<void>} Resolves when the stream is fully consumed.
   */
  async function streamSSE(stream, onEvent) {
    const reader = stream.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        // Process any remaining buffered data
        if (buffer.trim()) {
          const remaining = buffer.split('\n');
          const events = parseSSELines(remaining);
          for (const evt of events) {
            onEvent(evt);
          }
        }
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      // Keep the last element (potentially incomplete line) in the buffer
      buffer = lines.pop();

      const events = parseSSELines(lines);
      for (const evt of events) {
        onEvent(evt);
      }
    }
  }

  /**
   * Send a POST request and consume the SSE response stream.
   *
   * @param {string} url - The endpoint URL.
   * @param {FormData|Object} body - The request body (FormData for file uploads).
   * @param {function(Object): void} onEvent - Callback invoked for each SSE event.
   * @param {Object} [options] - Additional fetch options.
   * @returns {Promise<void>} Resolves when the stream completes.
   * @throws {Error} If the HTTP response is not ok.
   */
  async function postSSE(url, body, onEvent, options) {
    const fetchOptions = {
      method: 'POST',
      body: body,
      ...options,
    };

    const response = await fetch(url, fetchOptions);

    if (!response.ok) {
      let detail;
      try {
        const err = await response.json();
        detail = err.detail || err.error || `Request failed (${response.status})`;
      } catch (e) {
        detail = `Request failed (${response.status})`;
      }
      throw new Error(detail);
    }

    await streamSSE(response.body, onEvent);
  }

  // Export for both browser (window.SSEClient) and module environments
  exports.SSEClient = {
    parseSSELines: parseSSELines,
    streamSSE: streamSSE,
    postSSE: postSSE,
  };

})(typeof window !== 'undefined' ? window : globalThis);
