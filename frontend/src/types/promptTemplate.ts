/** 与后端 app/schemas/prompt_template.py 对齐 */

export interface PromptTemplateAdminOut {
  id: number;
  name: string;
  layer: string;
  template_text: string;
  applicable_mode: string;
  is_active: boolean;
  version: number;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface PromptTemplateLayerGroup {
  layer: string;
  by_mode: Record<string, PromptTemplateAdminOut[]>;
}

export interface PromptTemplatesGroupedResponse {
  layers: PromptTemplateLayerGroup[];
}

export interface PromptTemplateUpdate {
  name?: string | null;
  template_text?: string | null;
  applicable_mode?: string | null;
  is_active?: boolean | null;
  bump_version?: boolean;
}

export interface PromptTemplateCreate {
  name: string;
  layer: string;
  template_text: string;
  applicable_mode?: string;
  is_active?: boolean;
}
