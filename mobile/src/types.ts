export type RiskProfile = "conservative" | "balanced" | "aggressive";

export interface Tokens {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  access_expires_at: string;
  refresh_expires_at: string;
}

export interface User {
  id: string;
  email: string;
  name: string;
  timezone: string;
  risk_profile: RiskProfile;
  role: string;
  is_active: boolean;
  subscription_status: string;
  has_app_access: boolean;
  checkout_url?: string | null;
  created_at: string;
}

export interface SubscriptionStatus {
  required: boolean;
  has_access: boolean;
  status: string;
  whop_user_id: string | null;
  checkout_url: string | null;
}

export interface Bankroll {
  id: string;
  balance: string;
  currency: string;
  max_stake_pct: string;
  max_daily_exposure_pct: string;
  max_thesis_exposure_pct: string;
  loss_pause_threshold: number;
  updated_at: string;
}

export interface CandidateInput {
  candidate_id: string;
  event_id: string;
  event_name: string;
  sport: string;
  league: string;
  start_time: string;
  market_type: string;
  market_period: string;
  selection: string;
  line: string | null;
  american_odds: number;
  estimated_probability: number;
  probability_source?: "model" | "manual_verified" | "market_implied" | "demo";
  source_urls?: string[];
  variance: number;
  data_quality: number;
  [key: string]: unknown;
}

export type Readiness = "DEMO" | "PARTIAL" | "VERIFIED";

export interface VerificationSummary {
  readiness: Readiness;
  candidate_count: number;
  verified_count: number;
  partial_count: number;
  demo_count: number;
  gaps_by_candidate: Record<string, string[]>;
}

export interface SlateResponse {
  sport: string;
  date: string;
  mode: "demo" | "live";
  readiness?: Readiness;
  notice: string;
  verification_summary?: VerificationSummary;
  candidates: CandidateInput[];
}

export interface Recommendation {
  id: string;
  analysis_id: string;
  candidate_id: string;
  event_id: string;
  event_name: string;
  sport: string;
  league: string;
  slate_date: string;
  market_type: string;
  market_period: string;
  selection: string;
  line: string | null;
  american_odds: number;
  estimated_probability: string;
  implied_probability: string;
  adjusted_probability: string;
  edge: string;
  expected_value: string;
  confidence_score: number;
  quality_score?: number | null;
  quality_score_max?: number;
  model_win_probability?: number | null;
  probability_available?: boolean;
  probability_unavailable_reason?: string | null;
  home_team?: string | null;
  away_team?: string | null;
  start_time?: string | null;
  bookmaker?: string | null;
  bookmaker_label?: string | null;
  price_timestamp?: string | null;
  market_scope_label?: string | null;
  verification_status?: string | null;
  ywp_rating: string;
  vision_score: string;
  miss_by_one_risk: string;
  reliability: string;
  stability: string;
  variance: string;
  data_quality: string;
  risk: string;
  risk_tier: string;
  variance_rating: string;
  edge_class: string;
  expected_value_label: string;
  suggested_stake_pct: string;
  decision: "PLAY" | "LEAN" | "WATCH" | "REVIEW" | "SKIP";
  recommendation_tier: string;
  rank: number;
  reason_codes: string[];
  reasoning_summary: string;
  warnings: string[];
  safer_alternative: string | null;
  higher_upside: string | null;
  invalidation_conditions: string[];
  live_trigger: string | null;
  hedge: string | null;
  quick_cash: boolean;
  chain_reaction_key: string | null;
  thesis_key: string;
  script_key: string;
  player_key: string | null;
  image_url?: string | null;
  team_image_url?: string | null;
  data_source: string;
  source_urls?: string[];
  source_timestamp: string;
  model_version: string;
  protocol_version: string;
  input_hash: string;
  outcome: string | null;
  created_at: string;
}

export interface AnalyzeResponse {
  engine: "YWP Sports Engine";
  model_version: string;
  analysis_id: string;
  status: "success";
  date: string;
  ranked_picks: Recommendation[];
  stay_away: Recommendation[];
  readiness?: Readiness;
  data_quality_summary: {
    protocol_status: string;
    protocol_run_id: string;
    average_data_quality: number;
    missing_field_count: number;
    unknown_source_labels: number;
    candidate_count: number;
    official_pass_count: number;
    official_skip_count?: number;
    official_pass?: boolean;
    verified_candidate_count?: number;
    readiness?: Readiness;
  };
}

export interface TicketCard {
  key: string;
  label: string;
  recommendation_ids: string[];
  legs: Recommendation[];
  risk: string;
  risk_explanation?: string | null;
  confidence_score: number;
  quality_score?: number | null;
  quality_score_max?: number;
  quality_score_note?: string;
  joint_win_probability?: number | null;
  joint_probability_status?: string;
  joint_probability_note?: string | null;
  weakest_leg_id: string | null;
  weakest_leg_criterion?: string | null;
  weakest_leg_explanation?: string | null;
  warnings: string[];
}

export interface BuildTicketResponse {
  analysis_id: string | null;
  official_pass?: boolean;
  cards: Record<string, TicketCard>;
  stay_away: Recommendation[];
  quarantined: Array<{
    recommendation_id: string;
    reason: string;
    selection?: string | null;
    analysis_rank?: number | null;
  }>;
}

export interface TicketLeg {
  id: string;
  recommendation_id: string;
  position: number;
  selection: string;
  american_odds: number;
  thesis_key: string;
  script_key: string;
  action: "follow" | "skip" | "replace";
  skip_reason: string | null;
  status: string;
  outcome: string | null;
  image_url?: string | null;
  team_image_url?: string | null;
}

export interface Ticket {
  id: string;
  ticket_type: string;
  label: string;
  sport: string;
  slate_date: string;
  status: string;
  stake: string;
  potential_payout: string;
  combined_decimal_odds: string;
  risk: string;
  confidence_score: number;
  intentional_correlation: boolean;
  intentional_thesis_exposure: boolean;
  override_acknowledged: boolean;
  last_lock_status: string | null;
  last_lock_expires_at: string | null;
  legs: TicketLeg[];
  created_at: string;
  updated_at: string;
}

export interface LockCheck {
  id: string;
  ticket_id: string;
  lock_status: "LOCKED" | "WARNING" | "CHANGE_REQUIRED" | "SKIP";
  ticket_confidence_score: number;
  recommended_action: string;
  overall_message: string;
  checks: Record<string, string>;
  warnings: string[];
  leg_results: Array<{
    recommendation_id: string;
    selection: string;
    status: string;
    changes_detected: string[];
  }>;
  expires_at: string;
  created_at: string;
}

export interface Performance {
  settled: number;
  wins: number;
  losses: number;
  pushes: number;
  win_rate: number | null;
  profit_loss: string;
  roi: number | null;
  by_sport: Array<Record<string, string | number | null>>;
  by_market: Array<Record<string, string | number | null>>;
  confidence_calibration: Array<Record<string, string | number | null>>;
}

export interface MissByOneReport {
  near_miss_results: number;
  tickets_killed_by_near_miss: number;
  last_leg_near_misses: number;
  by_sport: Array<Record<string, string | number>>;
  by_market: Array<Record<string, string | number>>;
  by_player: Array<Record<string, string | number>>;
  by_line: Array<Record<string, string | number>>;
  by_role: Array<Record<string, string | number>>;
  by_script: Array<Record<string, string | number>>;
  by_card_type: Array<Record<string, string | number>>;
  recurring_theses: Array<Record<string, string | number>>;
}

export interface LearningPulse {
  protocol_runs: number;
  graded_results: number;
  micro_updates: number;
  active_shifts: Array<{
    sport: string;
    market_type: string;
    feature_name: string;
    weight: number;
    version: number;
    sample_size: number;
  }>;
  latest_lesson: string | null;
  headline: string;
}

export interface ProtocolDefinition {
  name: string;
  version: string;
  status: string;
  constitutional_laws: string[];
  global_required_checks: string[];
  ain_seven_point_sweep: string[];
  strict_mode: Record<string, string[]>;
  miss_by_one_protocol: Record<string, string[]>;
  live_cashout_protocol: Record<string, string[]>;
  adaptive_learning: Record<string, string[]>;
  superseded_or_removed: string[];
}

export interface ResultRecord {
  id: string;
  recommendation_id: string;
  outcome: "WIN" | "LOSS" | "PUSH" | "VOID";
  final_score: string | null;
  stake: string;
  profit_loss: string;
  closing_odds: number | null;
  closing_line: string | null;
  clv_probability: string | null;
  line_value: string | null;
  actual_value: string | null;
  bet_line: string | null;
  miss_distance: string | null;
  killed_ticket: boolean;
  last_losing_leg: boolean;
  process_outcome_class: string;
  error_category: string | null;
  assumptions_review: string[];
  unexpected_events: string[];
  quick_cash_result: string | null;
  chain_reaction_result: string | null;
  live_trigger_result: string | null;
  cashout_action: string | null;
  cashout_offer: string | null;
  cashout_reason: string | null;
  cashout_time: string | null;
  process_grade: string;
  variance_grade: string;
  root_cause_tags: string[];
  lesson: string | null;
  result_time: string;
}
