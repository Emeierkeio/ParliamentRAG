import type {
  TimelineResponse,
  DebateDetailResponse,
  SpeakerSummaryResponse,
  VoteActTextResponse,
  VoteDetailResponse,
  VoteInfo,
} from '@/types/timeline';

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

export async function getTimelineSessions(params: {
  before?: string | null;
  limit?: number;
  chamber?: string;
  search?: string;
  fromDate?: string;
  toDate?: string;
}): Promise<TimelineResponse> {
  const searchParams = new URLSearchParams();
  if (params.before) searchParams.set('before', params.before);
  if (params.limit) searchParams.set('limit', String(params.limit));
  if (params.chamber && params.chamber !== 'both') searchParams.set('chamber', params.chamber);
  if (params.search) searchParams.set('search', params.search);
  if (params.fromDate) searchParams.set('from_date', params.fromDate);
  if (params.toDate) searchParams.set('to_date', params.toDate);

  const qs = searchParams.toString();
  const url = `/api/timeline${qs ? `?${qs}` : ''}`;
  const res = await fetch(url, { headers: buildHeaders() });
  if (!res.ok) throw new Error(`Timeline fetch failed: ${res.status}`);
  return res.json();
}

export async function getDebateDetail(debateId: string): Promise<DebateDetailResponse> {
  const res = await fetch(`/api/timeline/debates/${encodeURIComponent(debateId)}`, {
    headers: buildHeaders(),
  });
  if (!res.ok) throw new Error(`Debate detail fetch failed: ${res.status}`);
  return res.json();
}

export async function getSessionVotes(sessionId: string): Promise<VoteInfo[]> {
  const res = await fetch(
    `/api/timeline/sessions/${encodeURIComponent(sessionId)}/votes`,
    { headers: buildHeaders() },
  );
  if (!res.ok) throw new Error(`Session votes fetch failed: ${res.status}`);
  return res.json();
}

export async function getVoteDetail(voteId: string): Promise<VoteDetailResponse> {
  const res = await fetch(`/api/timeline/votes/${encodeURIComponent(voteId)}`, {
    headers: buildHeaders(),
  });
  if (!res.ok) throw new Error(`Vote detail fetch failed: ${res.status}`);
  return res.json();
}

/** Testo dell'emendamento/articolo votato, estratto dall'Allegato A.
 *  null quando non estraibile (404): il chiamante nasconde la sezione. */
export async function getVoteActText(
  voteId: string,
): Promise<VoteActTextResponse | null> {
  const res = await fetch(
    `/api/timeline/votes/${encodeURIComponent(voteId)}/act-text`,
    { headers: buildHeaders() },
  );
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`Vote act text fetch failed: ${res.status}`);
  return res.json();
}

export async function getSpeakerSummary(
  debateId: string,
  speakerId: string,
): Promise<SpeakerSummaryResponse> {
  const res = await fetch(
    // speakerId is a full URI (http://dati.camera.it/... or dati.senato.it/...):
    // without encoding, the Next proxy 308-redirects and collapses "//" → "/",
    // mangling the id before it reaches the backend.
    `/api/timeline/speakers/${encodeURIComponent(debateId)}/${encodeURIComponent(speakerId)}`,
    { headers: buildHeaders() },
  );
  if (!res.ok) throw new Error(`Speaker summary fetch failed: ${res.status}`);
  return res.json();
}
