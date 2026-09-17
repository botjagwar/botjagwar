import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";

import { sendGemmaChat } from "../api";
import { useI18n } from "../i18n";
import type { GemmaChatMessage } from "../types";

const MAX_MESSAGE_LENGTH = 8_000;

export function GemmaChatWorkspace() {
  const { t } = useI18n();
  const [messages, setMessages] = useState<GemmaChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [model, setModel] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const controllerRef = useRef<AbortController | null>(null);
  const transcriptRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => () => controllerRef.current?.abort(), []);

  useEffect(() => {
    if (transcriptRef.current) transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight;
  }, [busy, messages]);

  async function submit(event?: FormEvent): Promise<void> {
    event?.preventDefault();
    const content = draft.trim();
    if (!content || busy) return;
    const conversation = [...messages, { role: "user", content } satisfies GemmaChatMessage];
    const controller = new AbortController();
    controllerRef.current = controller;
    setMessages(conversation);
    setDraft("");
    setError("");
    setBusy(true);
    try {
      const response = await sendGemmaChat(conversation, controller.signal);
      setMessages((current) => [...current, response.message]);
      setModel(response.model);
    } catch (caught) {
      if (!controller.signal.aborted) {
        setError(caught instanceof Error ? caught.message : t("Tsy afaka namaly i Gemma.", "Gemma could not respond."));
      }
    } finally {
      if (!controller.signal.aborted) setBusy(false);
      if (controllerRef.current === controller) controllerRef.current = null;
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submit();
    }
  }

  function clearConversation() {
    controllerRef.current?.abort();
    controllerRef.current = null;
    setMessages([]);
    setDraft("");
    setModel("");
    setError("");
    setBusy(false);
  }

  return (
    <section className="gemma-chat" aria-label={t("Resaka amin'i Gemma", "Chat with Gemma")}>
      <header className="gemma-chat__header">
        <div className="gemma-chat__identity" aria-hidden="true"><span>G</span><i /></div>
        <div>
          <p className="eyebrow">Gemma / {t("Modely lavitra", "Remote model")}</p>
          <h2>{t("Efitra firesahana", "Conversation room")}</h2>
          <p>{t("Miresaha mivantana amin'ny endpoint Gemma voaaro sy voakirakira ao amin'ny mpizara.", "Talk to the protected Gemma endpoint configured on the server.")}</p>
        </div>
        <div className="gemma-chat__status"><span /><div><small>{t("Fifandraisana", "Connection")}</small><strong>{model || t("Vonona", "Ready")}</strong></div></div>
      </header>

      <div className="gemma-chat__transcript" ref={transcriptRef} aria-live="polite" aria-busy={busy}>
        {messages.length === 0 ? (
          <div className="gemma-chat__empty">
            <span aria-hidden="true">G</span>
            <p className="eyebrow">Gemma 4</p>
            <h3>{t("Inona no tianao ho fantatra?", "What would you like to explore?")}</h3>
            <p>{t("Hijanona eto amin'ity fivoriana ity ny tantaran'ny resaka ary halefa miaraka amin'ny hafatrao manaraka.", "Conversation history stays in this session and is sent with each follow-up.")}</p>
          </div>
        ) : messages.map((message, index) => (
          <article className={`gemma-message gemma-message--${message.role}`} key={`${message.role}-${index}`}>
            <div className="gemma-message__author"><span>{message.role === "user" ? t("Ianao", "You") : "Gemma"}</span><small>{String(index + 1).padStart(2, "0")}</small></div>
            <p>{message.content}</p>
          </article>
        ))}
        {busy && <div className="gemma-message gemma-message--assistant gemma-message--thinking"><div className="gemma-message__author"><span>Gemma</span></div><p><i /><i /><i /><span className="sr-only">{t("Mieritreritra i Gemma", "Gemma is thinking")}</span></p></div>}
      </div>

      <footer className="gemma-chat__composer">
        {error && <p className="notice notice--error" role="alert">{error}</p>}
        <form onSubmit={(event) => void submit(event)}>
          <label htmlFor="gemma-message">{t("Hafatra", "Message")}</label>
          <textarea id="gemma-message" value={draft} maxLength={MAX_MESSAGE_LENGTH} rows={3} disabled={busy} onChange={(event) => setDraft(event.target.value)} onKeyDown={handleKeyDown} placeholder={t("Soraty eto ny hafatrao...", "Write your message...")} />
          <div className="gemma-chat__composer-meta"><span>{draft.length.toLocaleString()} / {MAX_MESSAGE_LENGTH.toLocaleString()}</span><span>{t("Enter handefa · Shift + Enter andalana vaovao", "Enter to send · Shift + Enter for a new line")}</span></div>
          <div className="gemma-chat__actions">
            <button className="button button--ghost" type="button" onClick={clearConversation} disabled={!messages.length && !draft && !busy}>{t("Hamafa ny resaka", "Clear chat")}</button>
            <button className="button button--primary" type="submit" disabled={!draft.trim() || busy}>{busy ? t("Miandry an'i Gemma...", "Waiting for Gemma...") : t("Handefa hafatra", "Send message")}<span aria-hidden="true">↗</span></button>
          </div>
        </form>
      </footer>
    </section>
  );
}
