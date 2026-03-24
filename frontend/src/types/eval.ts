/** 与后端 app/schemas/eval.py 对齐 */

export interface EvalRunCreate {
  rag_config_id: number;
  story_version_id: number;
  generate_cases?: boolean;
  case_ids?: number[] | null;
}

export interface EvalSampleSessionsRequest {
  session_id: number;
  max_turns?: number;
}

export interface EvalRunOut {
  id: number;
  rag_config_id: number;
  story_version_id: number;
  status: string;
  total_cases: number;
  avg_faithfulness: number | null;
  avg_story_quality: number | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface EvalRunsListResponse {
  items: EvalRunOut[];
  total: number;
}

export interface EvalCaseBrief {
  id: number;
  story_version_id: number;
  case_type: string;
  question: string;
  evidence_spans: unknown[];
  rubric: string | null;
  created_at: string;
}

export interface EvalResultOut {
  id: number;
  eval_run_id: number;
  eval_case_id: number;
  generated_answer: string;
  retrieved_context: unknown[];
  structured_facts_used: unknown[];
  faithfulness_score: number | null;
  story_quality_score: number | null;
  judge_reasoning: string | null;
  created_at: string;
  case: EvalCaseBrief | null;
}

export interface EvalResultsListResponse {
  items: EvalResultOut[];
  total: number;
}

export interface EvalRunTriggerResponse {
  run_id: number;
  message?: string;
}
