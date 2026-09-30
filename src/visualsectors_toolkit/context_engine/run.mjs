// MIT. Bounded stdin/stdout adapter; no network, credentials, model call or warehouse access.
import { isDeepStrictEqual } from 'node:util';
import { buildComputedScreenerContext, buildScreenerContextAnalystRequest,
  parseScreenerContextAnalystOutput } from './engine.mjs';

const maxBytes = 64 * 1024 * 1024;
try {
  let size = 0;
  const chunks = [];
  for await (const chunk of process.stdin) {
    size += chunk.length;
    if (size > maxBytes) throw new Error('context_input_too_large');
    chunks.push(chunk);
  }
  const payload = JSON.parse(Buffer.concat(chunks).toString('utf8'));
  const context = buildComputedScreenerContext(payload.spec, payload.packet);
  if (payload.mode === 'computed') {
    process.stdout.write(JSON.stringify(context));
  } else {
    if (!['request', 'decision'].includes(payload.mode)) throw new Error('context_mode_invalid');
    const metadata = payload.analysis_input;
    const allowed = ['schema_version', 'analysis_release', 'retrieval_spec_hash', 'decision_time',
      'as_of_session', 'screen', 'performance_12m', 'candidates'];
    if (!metadata || typeof metadata !== 'object' || Array.isArray(metadata)
        || Object.keys(metadata).some(key => !allowed.includes(key))) {
      throw new Error('context_analysis_metadata_invalid');
    }
    const input = { ...metadata, context };
    const request = buildScreenerContextAnalystRequest(input);
    if (payload.mode === 'request') {
      process.stdout.write(JSON.stringify(request));
    } else {
      if (!payload.request) throw new Error('context_dispatched_request_required');
      // The released parser verifies the exact request hash, prompt, schema and all atoms.
      const output = parseScreenerContextAnalystOutput(payload.model_output, input, payload.request);
      // Returned membership and order remain the frozen screen's; no foreign row is displayed.
      if (!isDeepStrictEqual(output.decisions.map(row => row.candidate_id),
          payload.spec.candidates.map(row => row.candidate_id))) throw new Error('context_population_changed');
      process.stdout.write(JSON.stringify(output));
    }
  }
} catch (error) {
  const message = error instanceof Error ? error.message : 'context_failed';
  // Emit released error codes only, not arbitrary evidence strings or stack traces.
  process.stderr.write(/^(screener_context_|context_)[a-zA-Z0-9_: +,.-]+$/.test(message)
    ? message.slice(0, 500) : 'context_input_invalid');
  process.exitCode = 2;
}
