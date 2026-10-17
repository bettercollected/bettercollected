// The client against a mocked server (node:http): what it sends, what it
// returns, and how it reports errors.
import assert from "node:assert/strict";
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import type { AddressInfo } from "node:net";
import { after, before, beforeEach, describe, it } from "node:test";

import { BetterCollected, BetterCollectedError, type FormSpec } from "../src/index.ts";

interface Seen {
  method: string;
  url: string;
  headers: IncomingMessage["headers"];
  body: unknown;
}

type Handler = (seen: Seen, res: ServerResponse) => void;

const SPEC: FormSpec = {
  specVersion: "1",
  title: "Event sign-up",
  pages: [{ id: "page-1", fields: [{ id: "name", type: "short_text", title: "Your name" }] }],
};

let handler: Handler;
let seen: Seen[] = [];
let baseUrl = "";
const server = createServer((req, res) => {
  const chunks: Buffer[] = [];
  req.on("data", (chunk: Buffer) => chunks.push(chunk));
  req.on("end", () => {
    const text = Buffer.concat(chunks).toString();
    const entry = {
      method: req.method ?? "",
      url: req.url ?? "",
      headers: req.headers,
      body: text ? JSON.parse(text) : undefined,
    };
    seen.push(entry);
    handler(entry, res);
  });
});

function reply(res: ServerResponse, status: number, body: unknown, headers: Record<string, string> = {}) {
  res.writeHead(status, { "Content-Type": "application/json", ...headers });
  res.end(JSON.stringify(body));
}

before(async () => {
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  baseUrl = `http://127.0.0.1:${(server.address() as AddressInfo).port}/`;
});
after(() => server.close());
beforeEach(() => {
  seen = [];
});

const client = () => new BetterCollected({ apiKey: "bc_test", baseUrl });

describe("BetterCollected", () => {
  it("sends the key as a Bearer token and reads a form with its ETag", async () => {
    handler = (_, res) => reply(res, 200, SPEC, { ETag: '"1-abc"' });
    const form = await client().getForm("f1");
    assert.deepEqual(form, { value: SPEC, etag: '"1-abc"' });
    assert.equal(seen[0]?.method, "GET");
    assert.equal(seen[0]?.url, "/api/v1/public/v1/forms/f1");
    assert.equal(seen[0]?.headers.authorization, "Bearer bc_test");
    assert.equal(seen[0]?.headers.cookie, undefined);
  });

  it("lists forms with paging", async () => {
    handler = (_, res) => reply(res, 200, { items: [], page: 2, size: 10, total: 11 });
    const list = await client().listForms({ page: 2, size: 10 });
    assert.equal(list.total, 11);
    assert.equal(seen[0]?.url, "/api/v1/public/v1/forms?page=2&size=10");
  });

  it("creates with an idempotency key", async () => {
    handler = (_, res) => reply(res, 201, { formId: "f2", form: SPEC }, { ETag: '"2-x"' });
    const created = await client().createForm(SPEC, { idempotencyKey: "once" });
    assert.deepEqual(created, { formId: "f2", value: SPEC, etag: '"2-x"' });
    assert.equal(seen[0]?.headers["idempotency-key"], "once");
    assert.equal(seen[0]?.headers["content-type"], "application/json");
    assert.deepEqual(seen[0]?.body, SPEC);
  });

  it("replaces with If-Match", async () => {
    handler = (_, res) => reply(res, 200, SPEC, { ETag: '"3-y"' });
    const replaced = await client().replaceForm("f1", SPEC, { ifMatch: '"1-abc"' });
    assert.equal(replaced.etag, '"3-y"');
    assert.equal(seen[0]?.method, "PUT");
    assert.equal(seen[0]?.headers["if-match"], '"1-abc"');
  });

  it("applies ops atomically by default", async () => {
    handler = (_, res) =>
      reply(res, 200, { applied: true, atomic: true, results: [], form: SPEC }, { ETag: '"4-z"' });
    const ops = [{ op: "update_form_info", title: "New" }];
    const result = await client().applyOps("f1", ops);
    assert.equal(result.value.applied, true);
    assert.deepEqual(seen[0]?.body, { ops, atomic: true });
    assert.equal(seen[0]?.headers["if-match"], undefined);

    await client().dryRunOps("f1", ops, { atomic: false });
    assert.equal(seen[1]?.url, "/api/v1/public/v1/forms/f1/ops/dry-run");
    assert.deepEqual(seen[1]?.body, { ops, atomic: false });
  });

  it("reads responses", async () => {
    handler = (entry, res) =>
      entry.url.endsWith("/r1")
        ? reply(res, 200, { responseId: "r1", formId: "f1", answers: {}, internalAnswers: {} })
        : reply(res, 200, { items: [], page: 1, size: 20, total: 0 });
    assert.equal((await client().listResponses("f1")).total, 0);
    assert.equal((await client().getResponse("f1", "r1")).responseId, "r1");
    assert.equal(seen[1]?.url, "/api/v1/public/v1/forms/f1/responses/r1");
  });

  it("throws the API's error, with the located errors", async () => {
    handler = (_, res) =>
      reply(res, 422, {
        code: "invalid_spec",
        message: "The document is not a valid form spec.",
        errors: [{ path: "/pages/0/id", message: "This property is required." }],
      });
    await assert.rejects(client().createForm(SPEC), (error: unknown) => {
      assert.ok(error instanceof BetterCollectedError);
      assert.equal(error.status, 422);
      assert.equal(error.code, "invalid_spec");
      assert.equal(error.errors?.[0]?.path, "/pages/0/id");
      return true;
    });
  });

  it("reports Retry-After on 429", async () => {
    handler = (_, res) =>
      reply(res, 429, { code: "rate_limited", message: "Too many requests." }, { "Retry-After": "17" });
    await assert.rejects(client().listForms(), (error: unknown) => {
      assert.ok(error instanceof BetterCollectedError);
      assert.equal(error.retryAfter, 17);
      return true;
    });
  });

  it("drops trailing slashes from the base URL", async () => {
    handler = (_, res) => reply(res, 200, { items: [], page: 1, size: 50, total: 0 });
    await new BetterCollected({ apiKey: "bc_test", baseUrl: baseUrl + "///" }).listForms();
    assert.equal(seen[0]?.url, "/api/v1/public/v1/forms");
  });

  it("warns when the key would travel over plain http to another host", (t) => {
    const warn = t.mock.method(console, "warn", () => {});
    new BetterCollected({ apiKey: "bc_test", baseUrl: "http://127.0.0.1:8000" });
    new BetterCollected({ apiKey: "bc_test", baseUrl: "http://localhost" });
    new BetterCollected({ apiKey: "bc_test", baseUrl: "https://forms.example.org" });
    assert.equal(warn.mock.callCount(), 0);
    new BetterCollected({ apiKey: "bc_test", baseUrl: "http://forms.example.org" });
    assert.equal(warn.mock.callCount(), 1);
  });

  it("needs an API key", () => {
    assert.throws(() => new BetterCollected({ apiKey: "", baseUrl }));
  });
});
