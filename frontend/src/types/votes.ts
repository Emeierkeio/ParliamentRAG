/**
 * TypeScript types for vote intelligence feature (Phase 14)
 */

export interface VoteExplorerEntry {
  vote_id: string;
  outcome: string;
  in_favor: number;
  against: number;
  abstained: number;
  margin: number;
  date: string;
  session_id: string;
  chamber: string;
  debate_id: string | null;
  label: string;
}

export interface VoteSearchResponse {
  votes: VoteExplorerEntry[];
  limit: number;
  offset: number;
  count: number;
}

export interface PartyCohesion {
  party: string;
  rice: number;
  votes_sampled: number;
}

export interface VoteCohesionData {
  available: boolean;
  reason?: string;
  chamber?: string;
  legislature?: number;
  parties?: PartyCohesion[];
}

export interface DeputyVoteStats {
  available: boolean;
  rebellion_rate: number | null;
  participation_rate: number | null;
  votes_cast: number;
  rebellions: number;
}

export interface IndividualVoteDeputy {
  id: string;
  name: string;
}

export interface PartyIndividualVotes {
  party: string;
  favor: IndividualVoteDeputy[];
  against: IndividualVoteDeputy[];
  abstained: IndividualVoteDeputy[];
}

export interface VoteIndividualResponse {
  available: boolean;
  vote_id: string;
  recorded: number;
  official_total: number;
  parties: PartyIndividualVotes[];
}

export interface VoteCompassParty {
  party: string;
  x: number;
  y: number;
}

export interface VoteCompassData {
  available: boolean;
  reason?: string;
  legislature?: number;
  chamber?: string;
  parties?: VoteCompassParty[];
  variance_explained?: number[];
}
