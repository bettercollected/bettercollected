// A small typed client for the BetterCollected public API (docs/api).
// Runtime dependencies: none beyond `fetch`.
import type { components } from "./generated/openapi.ts";
import type { FormSpec } from "./generated/form-spec.ts";

export type * from "./generated/form-spec.ts";
export type { components, paths } from "./generated/openapi.ts";

type Schemas = components["schemas"];
export type FormList = Schemas["FormList"];
export type FormSummary = Schemas["FormSummary"];
export type OpResult = Schemas["OpResult"];
export type OpsResult = Schemas["OpsResult"];
export type DryRunResult = Schemas["DryRunResult"];
export type ValidationResult = Schemas["ValidationResult"];
export type ReplacePreview = Schemas["ReplacePreview"];
export type PublishResult = Schemas["PublishResult"];
export type ResponseList = Schemas["ResponseList"];
export type ResponseDetail = Schemas["ResponseDetail"];
export type ApiErrorBody = Schemas["Error"];
/** One edit operation, e.g. `{ op: "add_field", pageId, field }` (docs/api/README.md). */
export type Operation = { op: string; [key: string]: unknown };

export interface ClientOptions {
  /** A workspace API key (`bc_...`). Keep it out of source code. */
  apiKey: string;
  /** The instance's origin, e.g. `https://forms.example.org`. */
  baseUrl: string;
  /** A `fetch` implementation; the global one by default. */
  fetch?: typeof fetch;
}

/** A form with the version it was read at. */
export interface Versioned<T> {
  value: T;
  /** Send it back as `ifMatch` to change exactly this version. */
  etag: string;
}

/** Any non-2xx answer, with the API's error body. */
export class BetterCollectedError extends Error {
  readonly status: number;
  readonly code: string;
  readonly errors: ApiErrorBody["errors"];
  /** Seconds to wait, on a 429. */
  readonly retryAfter: number | undefined;

  constructor(status: number, body: ApiErrorBody, retryAfter?: number) {
    super(body.message);
    this.name = "BetterCollectedError";
    this.status = status;
    this.code = body.code;
    this.errors = body.errors;
    this.retryAfter = retryAfter;
  }
}

export const API_PATH = "/api/v1/public/v1";

const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]", "::1"]);

/** Whether a base URL would send the key unencrypted to another machine. */
export function sendsKeyInClear(baseUrl: string): boolean {
  let url: URL;
  try {
    url = new URL(baseUrl);
  } catch {
    return false;
  }
  const host = url.hostname.toLowerCase();
  return url.protocol === "http:" && !LOCAL_HOSTS.has(host) && !host.endsWith(".localhost");
}

interface RequestOptions {
  body?: unknown;
  query?: Record<string, number | undefined>;
  headers?: Record<string, string | undefined>;
}

export class BetterCollected {
  readonly #apiKey: string;
  readonly #base: string;
  readonly #fetch: typeof fetch;

  constructor(options: ClientOptions) {
    if (!options.apiKey) throw new Error("apiKey is required");
    this.#apiKey = options.apiKey;
    let base = options.baseUrl;
    while (base.endsWith("/")) base = base.slice(0, -1);
    if (sendsKeyInClear(base)) {
      console.warn(
        "BetterCollected: the base URL uses http://; the API key is sent unencrypted. Use https://.",
      );
    }
    this.#base = base + API_PATH;
    this.#fetch = options.fetch ?? globalThis.fetch.bind(globalThis);
  }

  async #request(
    method: string,
    path: string,
    options: RequestOptions = {},
  ): Promise<{ body: any; headers: Headers }> {
    const url = new URL(this.#base + path);
    for (const [name, value] of Object.entries(options.query ?? {})) {
      if (value !== undefined) url.searchParams.set(name, String(value));
    }
    const headers: Record<string, string> = {
      Authorization: `Bearer ${this.#apiKey}`,
      Accept: "application/json",
    };
    for (const [name, value] of Object.entries(options.headers ?? {})) {
      if (value !== undefined) headers[name] = value;
    }
    let body: string | undefined;
    if (options.body !== undefined) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(options.body);
    }
    const response = await this.#fetch(url, { method, headers, body });
    const text = await response.text();
    const parsed = text ? JSON.parse(text) : undefined;
    if (!response.ok) {
      const retry = response.headers.get("Retry-After");
      throw new BetterCollectedError(
        response.status,
        parsed && typeof parsed.code === "string"
          ? parsed
          : { code: "http_error", message: `HTTP ${response.status}` },
        retry ? Number(retry) : undefined,
      );
    }
    return { body: parsed, headers: response.headers };
  }

  static #etag(headers: Headers): string {
    return headers.get("ETag") ?? "";
  }

  /** The workspace's forms, `size` per page (at most 100). */
  async listForms(options: { page?: number; size?: number } = {}): Promise<FormList> {
    return (await this.#request("GET", "/forms", { query: options })).body;
  }

  /** Create a draft from a whole document (nothing is created on any error). */
  async createForm(
    spec: FormSpec,
    options: { idempotencyKey?: string } = {},
  ): Promise<Versioned<FormSpec> & { formId: string }> {
    const { body, headers } = await this.#request("POST", "/forms", {
      body: spec,
      headers: { "Idempotency-Key": options.idempotencyKey },
    });
    return { formId: body.formId, value: body.form, etag: BetterCollected.#etag(headers) };
  }

  /** Check a document without storing it. */
  async validateForm(spec: unknown): Promise<ValidationResult> {
    return (await this.#request("POST", "/forms/validate", { body: spec })).body;
  }

  /** A form as a spec document, with its ETag. */
  async getForm(formId: string): Promise<Versioned<FormSpec>> {
    const { body, headers } = await this.#request("GET", `/forms/${encodeURIComponent(formId)}`);
    return { value: body, etag: BetterCollected.#etag(headers) };
  }

  /** Replace a form, only while it is still the version `ifMatch` names. */
  async replaceForm(
    formId: string,
    spec: FormSpec,
    options: { ifMatch: string },
  ): Promise<Versioned<FormSpec>> {
    const { body, headers } = await this.#request("PUT", `/forms/${encodeURIComponent(formId)}`, {
      body: spec,
      headers: { "If-Match": options.ifMatch },
    });
    return { value: body, etag: BetterCollected.#etag(headers) };
  }

  /** What `replaceForm` would store, and the diff. Stores nothing. */
  async previewReplace(formId: string, spec: FormSpec): Promise<ReplacePreview> {
    return (
      await this.#request("POST", `/forms/${encodeURIComponent(formId)}/replace/dry-run`, {
        body: spec,
      })
    ).body;
  }

  /** Apply edit operations (atomic unless `atomic: false`). */
  async applyOps(
    formId: string,
    ops: Operation[],
    options: { atomic?: boolean; ifMatch?: string; idempotencyKey?: string } = {},
  ): Promise<Versioned<OpsResult>> {
    const { body, headers } = await this.#request("POST", `/forms/${encodeURIComponent(formId)}/ops`, {
      body: { ops, atomic: options.atomic ?? true },
      headers: { "If-Match": options.ifMatch, "Idempotency-Key": options.idempotencyKey },
    });
    return { value: body, etag: BetterCollected.#etag(headers) };
  }

  /** Preview edit operations. Stores nothing. */
  async dryRunOps(
    formId: string,
    ops: Operation[],
    options: { atomic?: boolean } = {},
  ): Promise<DryRunResult> {
    return (
      await this.#request("POST", `/forms/${encodeURIComponent(formId)}/ops/dry-run`, {
        body: { ops, atomic: options.atomic ?? true },
      })
    ).body;
  }

  async publishForm(formId: string, options: { idempotencyKey?: string } = {}): Promise<PublishResult> {
    return (
      await this.#request("POST", `/forms/${encodeURIComponent(formId)}/publish`, {
        headers: { "Idempotency-Key": options.idempotencyKey },
      })
    ).body;
  }

  async listResponses(
    formId: string,
    options: { page?: number; size?: number } = {},
  ): Promise<ResponseList> {
    return (
      await this.#request("GET", `/forms/${encodeURIComponent(formId)}/responses`, { query: options })
    ).body;
  }

  async getResponse(formId: string, responseId: string): Promise<ResponseDetail> {
    return (
      await this.#request(
        "GET",
        `/forms/${encodeURIComponent(formId)}/responses/${encodeURIComponent(responseId)}`,
      )
    ).body;
  }
}
