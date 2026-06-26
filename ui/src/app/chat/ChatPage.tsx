import { useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Answer } from "./Answer.tsx";
import { MetaBadges } from "./MetaBadges.tsx";
import { useQueryMutation } from "./useQuery.ts";
import { useProgressiveReveal } from "./useProgressiveReveal.ts";
import { ApiError } from "../../lib/apiClient.ts";
import type { QueryResponse } from "../../lib/types.ts";

/** Map a backend failure to a calm, user-facing message (no stack/raw body leak). */
function friendlyError(err: unknown): string {
  if (err instanceof ApiError) {
    switch (err.status) {
      case 402:
        return "Daily budget exceeded — the cost cap was hit. Try again later.";
      case 413:
        return "That question is too long. Please shorten it.";
      case 429:
        return "Rate limit reached. Please wait a moment and retry.";
      case 503:
        return "The answering service is temporarily unavailable. Please retry shortly.";
      default:
        return `Request failed (${err.status}).`;
    }
  }
  return "Network error — is the gateway running?";
}

interface Turn {
  id: number;
  query: string;
  response?: QueryResponse;
  error?: string;
}

/** Assistant bubble: AI-generated label + progressively revealed cited answer + badges. */
function AssistantBubble({ response }: { response: QueryResponse }) {
  const { text, done } = useProgressiveReveal(response.answer);
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-2 flex items-center gap-2">
        <span className="rounded bg-indigo-50 px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-indigo-700">
          AI-generated
        </span>
        {!done && <span className="text-xs text-slate-400">typing…</span>}
      </div>
      <Answer markdown={text} citations={done ? response.citations : []} />
      <div className="mt-3 border-t border-slate-100 pt-2">
        <MetaBadges
          routing={response.routing}
          cache={response.cache}
          cost={response.cost}
          redaction={response.redaction}
        />
      </div>
    </div>
  );
}

export function ChatPage() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [disclosed, setDisclosed] = useState(false);
  const mutation = useQueryMutation();
  const nextIdRef = useRef(0);

  async function submit() {
    const query = input.trim();
    if (!query || mutation.isPending) return;
    const id = nextIdRef.current++;
    setInput("");
    setTurns((t) => [...t, { id, query }]);
    try {
      const response = await mutation.mutateAsync(query);
      setTurns((t) => t.map((turn) => (turn.id === id ? { ...turn, response } : turn)));
    } catch (err) {
      const message = friendlyError(err);
      setTurns((t) => t.map((turn) => (turn.id === id ? { ...turn, error: message } : turn)));
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void submit();
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void submit();
    }
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      {!disclosed && (
        <aside
          role="note"
          className="flex items-start justify-between gap-3 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
        >
          <span>
            You are interacting with an <strong>AI system</strong>. Responses are AI-generated, may
            be inaccurate, and must be verified before any action is taken.
          </span>
          <button
            type="button"
            onClick={() => setDisclosed(true)}
            className="shrink-0 text-amber-800 underline"
          >
            Got it
          </button>
        </aside>
      )}

      <ol className="space-y-4">
        {turns.map((turn) => (
          <li key={turn.id} className="space-y-2">
            <div className="ml-auto w-fit max-w-[80%] rounded-lg bg-slate-800 px-4 py-2 text-sm text-white">
              {turn.query}
            </div>
            {turn.response ? (
              <AssistantBubble response={turn.response} />
            ) : turn.error ? (
              <p role="alert" className="text-sm text-red-700">
                {turn.error}
              </p>
            ) : (
              <div
                aria-label="Thinking"
                className="flex w-fit gap-1 rounded-lg border border-slate-200 bg-white px-4 py-3"
              >
                <span className="h-2 w-2 animate-pulse rounded-full bg-slate-300" />
                <span className="h-2 w-2 animate-pulse rounded-full bg-slate-300" />
                <span className="h-2 w-2 animate-pulse rounded-full bg-slate-300" />
              </div>
            )}
          </li>
        ))}
      </ol>

      <form onSubmit={onSubmit} className="sticky bottom-0 flex gap-2 bg-slate-50 pt-2">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          rows={2}
          placeholder="Ask Atlas… (Enter to send, Shift+Enter for newline)"
          aria-label="Ask a question"
          className="flex-1 resize-none rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
        />
        <button
          type="submit"
          disabled={mutation.isPending || input.trim().length === 0}
          className="rounded-lg bg-slate-800 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </div>
  );
}
