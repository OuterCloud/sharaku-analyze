import { useEffect, useState } from "react";
import { getSettings, saveSettings, SettingsData } from "../api/settings";
import { useI18n } from "../i18n/context";

export default function SettingsTab() {
  const { t } = useI18n();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [settings, setSettings] = useState<SettingsData | null>(null);
  const [form, setForm] = useState({
    llm_api_key: "",
    llm_base_url: "https://api.openai.com/v1",
    llm_model: "claude-opus-5",
    llm_max_tokens: "8000",
    llm_temperature: "",
    knowledge_dir: "knowledge",
  });
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [keyEditing, setKeyEditing] = useState(false);

  useEffect(() => {
    loadSettings();
  }, []);

  async function loadSettings() {
    try {
      setLoading(true);
      const res = await getSettings();
      if (res.success) {
        setSettings(res.settings);
        setForm({
          llm_api_key: "",
          llm_base_url: res.settings.llm_base_url,
          llm_model: res.settings.llm_model,
          llm_max_tokens: res.settings.llm_max_tokens,
          llm_temperature: res.settings.llm_temperature,
          knowledge_dir: res.settings.knowledge_dir,
        });
      }
    } catch {
      setMessage({ type: "error", text: t("common.error.requestFailed") });
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    setMessage(null);
    try {
      const payload = {
        llm_api_key: keyEditing ? form.llm_api_key : undefined,
        llm_base_url: form.llm_base_url,
        llm_model: form.llm_model,
        llm_max_tokens: form.llm_max_tokens,
        llm_temperature: form.llm_temperature,
        knowledge_dir: form.knowledge_dir,
      };
      const res = await saveSettings(payload);
      if (res.success) {
        setMessage({ type: "success", text: t("settings.saved") });
        setKeyEditing(false);
        // Reload to get updated masked key
        await loadSettings();
      } else {
        setMessage({ type: "error", text: res.error || t("common.error.requestFailed") });
      }
    } catch {
      setMessage({ type: "error", text: t("common.error.requestFailed") });
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="result-card" style={{ textAlign: "center", padding: "40px" }}>
        <p style={{ color: "#888" }}>{t("common.loading")}</p>
      </div>
    );
  }

  return (
    <div>
      <div className="result-card">
        <h3 className="result-title">{t("settings.llm.title")}</h3>
        <p className="settings-description">{t("settings.llm.description")}</p>

        <div className="settings-form">
          {/* API Key */}
          <div className="settings-field">
            <label className="settings-label">
              API Key
              {settings?.llm_api_key_set && (
                <span className="settings-badge success">{t("settings.llm.keySet")}</span>
              )}
              {!settings?.llm_api_key_set && (
                <span className="settings-badge warning">{t("settings.llm.keyNotSet")}</span>
              )}
            </label>
            {!keyEditing ? (
              <div className="settings-key-display">
                <code className="settings-masked-key">
                  {settings?.llm_api_key || t("settings.llm.keyEmpty")}
                </code>
                <button className="settings-edit-btn" onClick={() => setKeyEditing(true)}>
                  {t("settings.llm.keyChange")}
                </button>
              </div>
            ) : (
              <div className="settings-key-edit">
                <input
                  type="password"
                  value={form.llm_api_key}
                  onChange={(e) => setForm({ ...form, llm_api_key: e.target.value })}
                  placeholder={t("settings.llm.keyPlaceholder")}
                  className="settings-input"
                  autoComplete="off"
                />
                <button
                  className="settings-cancel-btn"
                  onClick={() => { setKeyEditing(false); setForm({ ...form, llm_api_key: "" }); }}
                >
                  {t("settings.cancel")}
                </button>
              </div>
            )}
          </div>

          {/* Base URL */}
          <div className="settings-field">
            <label className="settings-label">Base URL</label>
            <input
              type="text"
              value={form.llm_base_url}
              onChange={(e) => setForm({ ...form, llm_base_url: e.target.value })}
              placeholder="https://api.openai.com/v1"
              className="settings-input"
            />
            <span className="settings-hint">{t("settings.llm.baseUrlHint")}</span>
          </div>

          {/* Model */}
          <div className="settings-field">
            <label className="settings-label">{t("settings.llm.model")}</label>
            <input
              type="text"
              value={form.llm_model}
              onChange={(e) => setForm({ ...form, llm_model: e.target.value })}
              placeholder="claude-opus-5"
              className="settings-input"
            />
          </div>

          {/* Max Tokens & Temperature in a row */}
          <div className="settings-row">
            <div className="settings-field">
              <label className="settings-label">Max Tokens</label>
              <input
                type="number"
                value={form.llm_max_tokens}
                onChange={(e) => setForm({ ...form, llm_max_tokens: e.target.value })}
                placeholder="8000"
                className="settings-input"
              />
            </div>
            <div className="settings-field">
              <label className="settings-label">Temperature</label>
              <input
                type="text"
                value={form.llm_temperature}
                onChange={(e) => setForm({ ...form, llm_temperature: e.target.value })}
                placeholder={t("settings.llm.tempPlaceholder")}
                className="settings-input"
              />
              <span className="settings-hint">{t("settings.llm.tempHint")}</span>
            </div>
          </div>

          {/* Knowledge Dir */}
          <div className="settings-field">
            <label className="settings-label">{t("settings.llm.knowledgeDir")}</label>
            <input
              type="text"
              value={form.knowledge_dir}
              onChange={(e) => setForm({ ...form, knowledge_dir: e.target.value })}
              placeholder="knowledge"
              className="settings-input"
            />
            <span className="settings-hint">{t("settings.llm.knowledgeDirHint")}</span>
          </div>
        </div>

        {/* Message */}
        {message && (
          <div className={`settings-message ${message.type}`}>
            {message.text}
          </div>
        )}

        {/* Save button */}
        <div style={{ marginTop: "20px" }}>
          <button
            className={`btn${saving ? " loading" : ""}`}
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? t("settings.saving") : t("settings.save")}
          </button>
        </div>
      </div>
    </div>
  );
}
