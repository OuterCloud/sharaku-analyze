// Settings API client

export interface SettingsData {
  llm_api_key: string;
  llm_api_key_set: boolean;
  llm_base_url: string;
  llm_model: string;
  llm_max_tokens: string;
  llm_temperature: string;
  knowledge_dir: string;
}

export interface SettingsResponse {
  success: boolean;
  settings: SettingsData;
  error?: string;
}

export interface SaveSettingsResponse {
  success: boolean;
  configured: boolean;
  message: string;
  error?: string;
}

export async function getSettings(): Promise<SettingsResponse> {
  const resp = await fetch("/api/settings");
  if (!resp.ok) throw new Error(`Failed to fetch settings: ${resp.status}`);
  return resp.json();
}

export async function saveSettings(data: {
  llm_api_key?: string;
  llm_base_url: string;
  llm_model: string;
  llm_max_tokens: string;
  llm_temperature: string;
  knowledge_dir: string;
}): Promise<SaveSettingsResponse> {
  const formData = new FormData();
  if (data.llm_api_key !== undefined) {
    formData.append("llm_api_key", data.llm_api_key);
  }
  formData.append("llm_base_url", data.llm_base_url);
  formData.append("llm_model", data.llm_model);
  formData.append("llm_max_tokens", data.llm_max_tokens);
  formData.append("llm_temperature", data.llm_temperature);
  formData.append("knowledge_dir", data.knowledge_dir);

  const resp = await fetch("/api/settings", {
    method: "POST",
    body: formData,
  });
  if (!resp.ok) throw new Error(`Failed to save settings: ${resp.status}`);
  return resp.json();
}
