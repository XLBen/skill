import test from "node:test";
import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

import workflowVisibilityPlugin, {
  AGENT_BY_ROLE,
  buildDispatchBody,
  extractOutput,
  parseModelRef,
  resolveSelection,
  ROLES,
  VISIBILITY_RELATIVE_PATH,
} from "../../.opencode/plugins/workflow-visibility.js";

const selected = (providerID, modelID) => ({
  provider_id: providerID,
  model_id: modelID,
  status: "selected",
});

function makeDocument(selection, reviewerSelection) {
  const document = {
    schema: "workflow-visibility/1",
    updated_at: "2026-09-21T00:00:00Z",
    selection,
  };
  if (reviewerSelection !== undefined) {
    document.reviewer_selection = reviewerSelection;
  }
  return document;
}

function makeProject(t, document) {
  const directory = mkdtempSync(path.join(tmpdir(), "visibility-plugin-"));
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  if (document !== undefined) {
    const target = path.join(directory, VISIBILITY_RELATIVE_PATH);
    mkdirSync(path.dirname(target), { recursive: true });
    writeFileSync(target, JSON.stringify(document), "utf8");
  }
  return directory;
}

function makeFakeClient({ sessionID = "ses_new_1", parts, createError, promptError } = {}) {
  const calls = { create: [], prompt: [] };
  return {
    calls,
    session: {
      create: async (options) => {
        calls.create.push(options);
        if (createError) throw createError;
        return { data: { id: sessionID }, error: undefined, request: {}, response: {} };
      },
      prompt: async (options) => {
        calls.prompt.push(options);
        if (promptError) throw promptError;
        return {
          data: {
            info: { id: "msg_1" },
            parts: parts ?? [{ type: "text", text: "ok" }],
          },
          error: undefined,
          request: {},
          response: {},
        };
      },
    },
  };
}

async function makeHooks(client, directory) {
  return workflowVisibilityPlugin({ client, directory, worktree: directory });
}

test("parseModelRef accepts exactly one slash with non-empty sides", () => {
  assert.deepEqual(parseModelRef("openai/gpt-5.6-luna"), {
    providerID: "openai",
    modelID: "gpt-5.6-luna",
  });
  assert.equal(parseModelRef("openai/gpt-5.6/luna"), null);
  assert.equal(parseModelRef("openai/"), null);
  assert.equal(parseModelRef("/gpt-5.6-luna"), null);
  assert.equal(parseModelRef(""), null);
  assert.equal(parseModelRef("no-slash"), null);
  assert.equal(parseModelRef(42), null);
  assert.equal(parseModelRef(null), null);
  assert.equal(parseModelRef(undefined), null);
  assert.equal(parseModelRef({ providerID: "a", modelID: "b" }), null);
});

test("resolveSelection prefers an explicit provider/model", (t) => {
  const directory = makeProject(t, makeDocument(selected("openai", "gpt-5.6-luna")));
  assert.deepEqual(resolveSelection(directory, "product-observer", "zhipuai/glm-4.6v"), {
    providerID: "zhipuai",
    modelID: "glm-4.6v",
  });
  assert.deepEqual(resolveSelection(directory, "product-observer", "openai/gpt-6-astra"), {
    providerID: "openai",
    modelID: "gpt-6-astra",
  });
});

test("resolveSelection rejects an invalid explicit model", (t) => {
  const directory = makeProject(t, makeDocument(selected("openai", "gpt-5.6-luna")));
  assert.match(resolveSelection(directory, "product-observer", "bad").error, /explicit model/);
  assert.match(resolveSelection(directory, "product-observer", "a/b/c").error, /explicit model/);
  assert.match(resolveSelection(directory, "product-observer", "").error, /explicit model/);
});

test("resolveSelection reads selection for product-observer", (t) => {
  const directory = makeProject(
    t,
    makeDocument(selected("openai", "gpt-5.6-luna"), selected("deepseek", "deepseek-v4-vision")),
  );
  assert.deepEqual(resolveSelection(directory, "product-observer"), {
    providerID: "openai",
    modelID: "gpt-5.6-luna",
  });
});

test("resolveSelection reads reviewer_selection for reviewer", (t) => {
  const directory = makeProject(
    t,
    makeDocument(selected("openai", "gpt-5.6-luna"), selected("deepseek", "deepseek-v4-vision")),
  );
  assert.deepEqual(resolveSelection(directory, "reviewer"), {
    providerID: "deepseek",
    modelID: "deepseek-v4-vision",
  });
});

test("resolveSelection falls back to selection when reviewer_selection is absent", (t) => {
  const directory = makeProject(t, makeDocument(selected("openai", "gpt-5.6-luna")));
  assert.deepEqual(resolveSelection(directory, "reviewer"), {
    providerID: "openai",
    modelID: "gpt-5.6-luna",
  });
});

test("resolveSelection does not fall back when reviewer_selection is invalid", (t) => {
  const directory = makeProject(
    t,
    makeDocument(selected("openai", "gpt-5.6-luna"), { status: "unverified" }),
  );
  assert.match(resolveSelection(directory, "reviewer").error, /reviewer_selection/);
});

test("resolveSelection fails closed when the file is missing", (t) => {
  const directory = makeProject(t);
  assert.match(resolveSelection(directory, "product-observer").error, /no visibility settings/);
});

test("resolveSelection fails closed for non-selected or missing fields", (t) => {
  const unconfigured = makeProject(t, makeDocument({ status: "unverified" }));
  assert.match(resolveSelection(unconfigured, "product-observer").error, /status/);

  const missingProvider = makeProject(t, makeDocument({ model_id: "m", status: "selected" }));
  assert.match(resolveSelection(missingProvider, "product-observer").error, /provider_id/);

  const missingModel = makeProject(t, makeDocument({ provider_id: "p", status: "selected" }));
  assert.match(resolveSelection(missingModel, "product-observer").error, /model_id/);

  const noSelection = makeProject(t, { schema: "workflow-visibility/1" });
  assert.match(resolveSelection(noSelection, "product-observer").error, /selection is missing/);
});

test("resolveSelection rejects unreadable settings and unknown roles", (t) => {
  const directory = makeProject(t);
  const target = path.join(directory, VISIBILITY_RELATIVE_PATH);
  mkdirSync(path.dirname(target), { recursive: true });
  writeFileSync(target, "{ not json", "utf8");

  assert.match(resolveSelection(directory, "product-observer").error, /not readable JSON/);
  assert.match(resolveSelection(directory, "bogus").error, /unknown role/);
});

test("buildDispatchBody has the SDK prompt shape", () => {
  assert.deepEqual(
    buildDispatchBody({
      agent: "mvp-reviewer",
      model: { providerID: "openai", modelID: "gpt-5.6-luna" },
      prompt: "review this",
    }),
    {
      agent: "mvp-reviewer",
      model: { providerID: "openai", modelID: "gpt-5.6-luna" },
      parts: [{ type: "text", text: "review this" }],
    },
  );
});

test("extractOutput keeps text parts in order and tolerates gaps", () => {
  assert.equal(
    extractOutput([
      { type: "text", text: "one" },
      { type: "reasoning", text: "hidden" },
      { type: "text", text: "two" },
    ]),
    "onetwo",
  );
  assert.equal(extractOutput([{ type: "text", text: "" }]), "");
  assert.equal(extractOutput([{ type: "tool", state: {} }]), "");
  assert.equal(extractOutput([]), "");
  assert.equal(extractOutput(undefined), "");
  assert.equal(extractOutput("nope"), "");
});

test("AGENT_BY_ROLE maps both seats", () => {
  assert.deepEqual(ROLES, ["product-observer", "reviewer"]);
  assert.equal(AGENT_BY_ROLE["product-observer"], "mvp-product-observer");
  assert.equal(AGENT_BY_ROLE.reviewer, "mvp-reviewer");
});

test("visibility_dispatch creates a child session and returns pinned metadata", async (t) => {
  const directory = makeProject(t, makeDocument(selected("openai", "gpt-5.6-luna")));
  const client = makeFakeClient({
    sessionID: "ses_child_1",
    parts: [
      { type: "text", text: "part-1" },
      { type: "reasoning", text: "part-hidden" },
      { type: "text", text: "part-2" },
    ],
  });
  const hooks = await makeHooks(client, directory);

  const result = await hooks.tool.visibility_dispatch.execute(
    { role: "product-observer", prompt: "look at the product", description: "observe now" },
    { sessionID: "ses_parent_1", directory },
  );

  assert.equal(client.calls.create.length, 1);
  assert.deepEqual(client.calls.create[0], {
    body: { parentID: "ses_parent_1", title: "observe now" },
  });
  assert.equal(client.calls.prompt.length, 1);
  assert.deepEqual(client.calls.prompt[0], {
    path: { sessionID: "ses_child_1" },
    body: {
      agent: "mvp-product-observer",
      model: { providerID: "openai", modelID: "gpt-5.6-luna" },
      parts: [{ type: "text", text: "look at the product" }],
    },
  });
  assert.equal(result.title, "observe now");
  assert.equal(result.output, "part-1part-2");
  assert.deepEqual(result.metadata, {
    session_id: "ses_child_1",
    provider_id: "openai",
    model_id: "gpt-5.6-luna",
    agent: "mvp-product-observer",
  });
});

test("visibility_dispatch falls back to the plugin directory when context has none", async (t) => {
  const directory = makeProject(t, makeDocument(selected("openai", "gpt-5.6-luna")));
  const client = makeFakeClient();
  const hooks = await makeHooks(client, directory);

  const result = await hooks.tool.visibility_dispatch.execute(
    { role: "product-observer", prompt: "hello" },
    { sessionID: "ses_parent_1" },
  );

  assert.equal(result.metadata.session_id, "ses_new_1");
  assert.equal(result.title, "observer dispatch");
});

test("visibility_dispatch applies an explicit model override", async (t) => {
  const directory = makeProject(t);
  const client = makeFakeClient();
  const hooks = await makeHooks(client, directory);

  const result = await hooks.tool.visibility_dispatch.execute(
    { role: "reviewer", prompt: "review", model: "zhipuai-coding-plan/glm-4.6v" },
    { sessionID: "ses_parent_1", directory },
  );

  assert.equal(client.calls.prompt[0].body.model.providerID, "zhipuai-coding-plan");
  assert.equal(client.calls.prompt[0].body.model.modelID, "glm-4.6v");
  assert.equal(client.calls.prompt[0].body.agent, "mvp-reviewer");
  assert.equal(result.metadata.provider_id, "zhipuai-coding-plan");
  assert.equal(result.metadata.model_id, "glm-4.6v");
});

test("visibility_dispatch resumes an existing session without creating one", async (t) => {
  const directory = makeProject(
    t,
    makeDocument(selected("openai", "gpt-5.6-luna"), selected("deepseek", "deepseek-v4-vision")),
  );
  const client = makeFakeClient({ parts: [{ type: "text", text: "resumed" }] });
  const hooks = await makeHooks(client, directory);

  const result = await hooks.tool.visibility_dispatch.execute(
    { role: "reviewer", prompt: "continue", session_id: "ses_existing" },
    { sessionID: "ses_parent_1", directory },
  );

  assert.equal(client.calls.create.length, 0);
  assert.equal(client.calls.prompt.length, 1);
  assert.equal(client.calls.prompt[0].path.sessionID, "ses_existing");
  assert.deepEqual(client.calls.prompt[0].body.model, {
    providerID: "deepseek",
    modelID: "deepseek-v4-vision",
  });
  assert.equal(result.metadata.session_id, "ses_existing");
  assert.equal(result.output, "resumed");
});

test("visibility_dispatch fails closed without a selection and never calls the API", async (t) => {
  const directory = makeProject(t);
  const client = makeFakeClient();
  const hooks = await makeHooks(client, directory);

  await assert.rejects(
    () =>
      hooks.tool.visibility_dispatch.execute(
        { role: "product-observer", prompt: "x" },
        { sessionID: "ses_parent_1", directory },
      ),
    /visibility_dispatch: no visibility settings/,
  );
  assert.equal(client.calls.create.length, 0);
  assert.equal(client.calls.prompt.length, 0);
});

test("visibility_dispatch surfaces host API failures", async (t) => {
  const directory = makeProject(t, makeDocument(selected("openai", "gpt-5.6-luna")));
  const client = makeFakeClient({ promptError: new Error("pipe exploded") });
  const hooks = await makeHooks(client, directory);

  await assert.rejects(
    () =>
      hooks.tool.visibility_dispatch.execute(
        { role: "product-observer", prompt: "x" },
        { sessionID: "ses_parent_1", directory },
      ),
    /visibility_dispatch: pipe exploded/,
  );
  assert.equal(client.calls.create.length, 1);
  assert.equal(client.calls.prompt.length, 1);
});

test("visibility_dispatch surfaces a returned SDK error result", async (t) => {
  const directory = makeProject(t, makeDocument(selected("openai", "gpt-5.6-luna")));
  const client = makeFakeClient();
  client.session.prompt = async (options) => {
    client.calls.prompt.push(options);
    return { data: undefined, error: { message: "model not found" }, request: {}, response: {} };
  };
  const hooks = await makeHooks(client, directory);

  await assert.rejects(
    () =>
      hooks.tool.visibility_dispatch.execute(
        { role: "product-observer", prompt: "x" },
        { sessionID: "ses_parent_1", directory },
      ),
    /visibility_dispatch: host API error: model not found/,
  );
});

test("visibility_status prints the configured selection as JSON", async (t) => {
  const selection = selected("openai", "gpt-5.6-luna");
  const directory = makeProject(t, makeDocument(selection));
  const hooks = await makeHooks(makeFakeClient(), directory);

  const result = await hooks.tool.visibility_status.execute({}, { directory });

  assert.deepEqual(JSON.parse(result.output), selection);
  assert.match(result.output, /\n {2}"/);
  assert.equal(result.metadata.path, path.join(directory, VISIBILITY_RELATIVE_PATH));
  assert.equal(result.metadata.role, "product-observer");
  assert.equal(result.metadata.status, "selected");
});

test("visibility_status reports reviewer_selection when asked", async (t) => {
  const directory = makeProject(
    t,
    makeDocument(selected("openai", "gpt-5.6-luna"), selected("deepseek", "deepseek-v4-vision")),
  );
  const hooks = await makeHooks(makeFakeClient(), directory);

  const result = await hooks.tool.visibility_status.execute({ role: "reviewer" }, { directory });

  assert.equal(JSON.parse(result.output).provider_id, "deepseek");
  assert.equal(result.metadata.role, "reviewer");
});

test("visibility_status does not throw when the file is missing", async (t) => {
  const directory = makeProject(t);
  const hooks = await makeHooks(makeFakeClient(), directory);

  const result = await hooks.tool.visibility_status.execute({}, { directory });

  assert.match(result.output, /^unconfigured:/);
  assert.equal(result.metadata.status, "unconfigured");
});
