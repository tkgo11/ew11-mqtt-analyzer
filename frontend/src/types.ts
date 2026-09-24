export interface PacketDto {
  seq: number;
  ts: number;
  topic: string;
  hex: string;
  len: number;
  fmt: string;
  raw: string;
}

export interface StatusDto {
  mode: "demo" | "live";
  source: string | null;
  status: string;
  broker: string;
  topic: string;
  uptime_s: number;
  total_packets: number;
  rate_per_s: number;
  markers: number;
  topics: string[];
  demo_events?: Record<string, string> | null;
}

export interface MarkerDto {
  id: number;
  ts: number;
  label: string;
}

export interface ByteStatDto {
  idx: number;
  distinct: number;
  entropy: number;
  top: [string, number][];
  role: string;
  const: number | null;
  is_counter: boolean;
}

export interface ChecksumDto {
  algo: string;
  pos: number;
  size: number;
  covered: [number, number];
  rate: number;
  verified: boolean;
  endian: string;
}

export interface VerdictDto {
  sig: string;
  count: number;
  rate_per_min: number;
  mean_interval: number | null;
  cv: number | null;
  periodicity: number;
  baseline_count: number;
  event_count: number;
  event_lift: number | null;
  marker_ids: number[];
  verdict: "IDLE" | "EVENT" | "MIXED" | "UNKNOWN";
  verdict_ko: string;
  confidence: number;
  topics: string[];
  first_ts: number;
  last_ts: number;
}

export interface FamilyDto {
  sig: string;
  verdict: VerdictDto;
  bytemap: ByteStatDto[];
  checksum: ChecksumDto | null;
  checksum_candidates: ChecksumDto[];
  samples: string[];
}

export interface DiffHitDto {
  sig: string;
  count_in: number;
  novel: boolean;
  changed_positions: number[];
  samples_in: string[];
  samples_out: string[];
}

export interface MarkerDiffDto {
  marker: MarkerDto;
  hits: DiffHitDto[];
}

export interface AnalysisDto {
  started_at: number;
  ended_at: number;
  duration_s: number;
  total_packets: number;
  total_families: number;
  markers: MarkerDto[];
  families: FamilyDto[];
  diffs: MarkerDiffDto[];
  notes: string[];
  params: { prefix_len: number; event_pre: number; event_post: number };
}

export interface ConfigDto {
  mqtt: {
    host: string;
    port: number;
    username: string;
    has_password: boolean;
    topic: string;
    tls: boolean;
    client_id: string;
  };
  analysis: {
    prefix_len: number;
    event_pre: number;
    event_post: number;
    max_packets: number;
    demo_speed: number;
  };
  ai: {
    provider: string;
    base_url: string;
    api_key: string;
    has_key: boolean;
    model: string;
    max_tokens: number;
  };
  demo: boolean;
}

export type WsMsg =
  | { type: "packet"; data: PacketDto }
  | { type: "status"; data: { status: string } }
  | { type: "marker"; data: MarkerDto };
