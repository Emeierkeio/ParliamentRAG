import { config } from '@/config';
import type {
  VoteSearchResponse,
  VoteCohesionData,
  DeputyVoteStats,
  VoteCompassData,
  VoteIndividualResponse,
} from '@/types/votes';

const BASE = config.api.baseUrl;

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

export async function searchVotes(params: {
  chamber: string;
  legislature: number;
  from_date?: string;
  to_date?: string;
  outcome?: string;
  min_margin?: number;
  limit?: number;
  offset?: number;
}): Promise<VoteSearchResponse> {
  const qs = new URLSearchParams();
  qs.set('chamber', params.chamber);
  qs.set('legislature', String(params.legislature));
  if (params.from_date) qs.set('from_date', params.from_date);
  if (params.to_date) qs.set('to_date', params.to_date);
  if (params.outcome) qs.set('outcome', params.outcome);
  if (params.min_margin !== undefined) qs.set('min_margin', String(params.min_margin));
  if (params.limit !== undefined) qs.set('limit', String(params.limit));
  if (params.offset !== undefined) qs.set('offset', String(params.offset));

  const res = await fetch(`${BASE}/votes?${qs.toString()}`, {
    headers: buildHeaders(),
  });
  if (!res.ok) throw new Error(`Votes fetch failed: ${res.status}`);
  return res.json();
}

export async function getVoteCohesion(
  chamber: string,
  legislature: number,
  deputyId?: string,
): Promise<VoteCohesionData | DeputyVoteStats> {
  const qs = new URLSearchParams();
  qs.set('chamber', chamber);
  qs.set('legislature', String(legislature));
  if (deputyId) qs.set('deputy_id', deputyId);

  const res = await fetch(`${BASE}/rankings/votes?${qs.toString()}`, {
    headers: buildHeaders(),
  });
  if (!res.ok) throw new Error(`Vote cohesion fetch failed: ${res.status}`);
  return res.json();
}

export async function getVoteIndividual(voteId: string): Promise<VoteIndividualResponse> {
  const res = await fetch(
    `${BASE}/votes/${encodeURIComponent(voteId)}/individual`,
    { headers: buildHeaders() },
  );
  if (!res.ok) throw new Error(`Individual votes fetch failed: ${res.status}`);
  return res.json();
}

export async function getVoteCompass(
  legislature: number,
  chamber: string,
): Promise<VoteCompassData> {
  const qs = new URLSearchParams();
  qs.set('legislature', String(legislature));
  qs.set('chamber', chamber);

  const res = await fetch(`${BASE}/compass/votes?${qs.toString()}`, {
    headers: buildHeaders(),
  });
  if (!res.ok) throw new Error(`Vote compass fetch failed: ${res.status}`);
  return res.json();
}
