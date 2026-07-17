import type { TranscriptResponse, SpeechTextResponse, SuggestionsResponse, TranscriptSearchResponse } from '@/types/transcript';

function getLocale(): string {
  if (typeof document === 'undefined') return 'it';
  return (
    document.cookie
      .split('; ')
      .find(c => c.startsWith('NEXT_LOCALE='))
      ?.split('=')[1] || 'it'
  );
}

function buildHeaders(): HeadersInit {
  return { 'Accept-Language': getLocale() };
}

export async function getTranscriptSpeeches(debateId: string): Promise<TranscriptResponse> {
  const res = await fetch(
    `/api/transcript/${encodeURIComponent(debateId)}/speeches`,
    { headers: buildHeaders() },
  );
  if (!res.ok) throw new Error(`Transcript fetch failed: ${res.status}`);
  return res.json();
}

export async function getSpeechText(debateId: string, speechId: string): Promise<SpeechTextResponse> {
  const res = await fetch(
    `/api/transcript/${encodeURIComponent(debateId)}/speech/${encodeURIComponent(speechId)}`,
    { headers: buildHeaders() },
  );
  if (!res.ok) throw new Error(`Speech text fetch failed: ${res.status}`);
  return res.json();
}

export async function searchTranscript(debateId: string, query: string): Promise<TranscriptSearchResponse> {
  const res = await fetch(
    `/api/transcript/${encodeURIComponent(debateId)}/search?q=${encodeURIComponent(query)}`,
  );
  if (!res.ok) throw new Error(`Search failed: ${res.status}`);
  return res.json();
}

export async function getDebateSuggestions(debateId: string): Promise<SuggestionsResponse> {
  const res = await fetch(
    `/api/transcript/${encodeURIComponent(debateId)}/suggestions`,
    { headers: buildHeaders() },
  );
  if (!res.ok) throw new Error(`Suggestions fetch failed: ${res.status}`);
  return res.json();
}
