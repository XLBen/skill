// workflow-visibility.js - S12b OpenCode plugin for model-pinned observer dispatch.
//
// Install / runtime prerequisites:
//   * OpenCode loads project plugins from `<project>/.opencode/plugins/`. This file
//     imports `@opencode-ai/plugin` (already resolvable from `.opencode/node_modules`
//     in this repository). On a fresh checkout run `npm install` inside `.opencode`
//     (or keep `@opencode-ai/plugin` in `.opencode/package.json`) or the plugin will
//     fail to load.
//   * Plugins are read at startup: RESTART OpenCode (or start a new server) before
//     `visibility_dispatch` / `visibility_status` become available. Editing this file
//     has no effect on an already-running host.
//   * This file does NOT modify any global OpenCode configuration and never changes
//     the main chat model. It only reads the project-local selection written by S11
//     at `<directory>/.opencode/mvp/visibility.json` and dispatches through the host
//     SDK client (`session.create` + `session.prompt`).
//
// Machine-checked by `node --test tests/js/` (tests/js/visibility-plugin.test.mjs).
// Real host dispatch remains verification-pending until OpenCode is restarted (S21).

import { tool } from "@opencode-ai/plugin";
import { readFileSync } from "node:fs";
import path from "node:path";

export const VISIBILITY_RELATIVE_PATH = ".opencode/mvp/visibility.json";

export const ROLES = ["product-observer", "reviewer"];

export const AGENT_BY_ROLE = {
  "product-observer": "mvp-product-observer",
  reviewer: "mvp-reviewer",
};

export function parseModelRef(value) {
  if (typeof value !== "string") return null;
  const parts = value.split("/");
  if (parts.length !== 2) return null;
  const [providerID, modelID] = parts;
  if (!providerID || !modelID) return null;
  return { providerID, modelID };
}

function selectionProblem(origin, selection) {
  if (selection === undefined || selection === null) {
    return `${origin} is missing`;
  }
  if (typeof selection !== "object" || Array.isArray(selection)) {
    return `${origin} must be a JSON object`;
  }
  if (selection.status !== "selected") {
    return `${origin}.status is ${JSON.stringify(selection.status)} (expected "selected")`;
  }
  const providerID = selection.provider_id;
  const modelID = selection.model_id;
  if (
    typeof providerID !== "string" ||
    !providerID ||
    typeof modelID !== "string" ||
    !modelID
  ) {
    return `${origin}.provider_id/model_id must be non-empty strings`;
  }
  if (!parseModelRef(`${providerID}/${modelID}`)) {
    return `${origin} must identify a provider/model pair (got ${JSON.stringify(
      `${providerID}/${modelID}`,
    )})`;
  }
  return null;
}

export function resolveSelection(directory, role, explicitModel) {
  if (explicitModel !== undefined && explicitModel !== null) {
    const parsed = parseModelRef(explicitModel);
    if (!parsed) {
      return {
        error: `explicit model ${JSON.stringify(explicitModel)} is not a provider/model id`,
      };
    }
    return parsed;
  }

  if (role !== "product-observer" && role !== "reviewer") {
    return {
      error: `unknown role ${JSON.stringify(
        role,
      )} (expected product-observer or reviewer)`,
    };
  }

  const filePath = path.join(directory, VISIBILITY_RELATIVE_PATH);
  let document;
  try {
    document = JSON.parse(readFileSync(filePath, "utf8"));
  } catch (error) {
    if (error && error.code === "ENOENT") {
      return { error: `no visibility settings at ${filePath}` };
    }
    return {
      error: `visibility settings at ${filePath} are not readable JSON: ${error.message}`,
    };
  }
  if (!document || typeof document !== "object" || Array.isArray(document)) {
    return { error: `visibility settings at ${filePath} must be a JSON object` };
  }

  let origin =
    role === "reviewer" ? "visibility settings reviewer_selection" : "visibility settings selection";
  let selection = role === "reviewer" ? document.reviewer_selection : document.selection;
  if (role === "reviewer" && selection === undefined) {
    origin = "visibility settings selection";
    selection = document.selection;
  }

  const problem = selectionProblem(origin, selection);
  if (problem) return { error: problem };
  return { providerID: selection.provider_id, modelID: selection.model_id };
}

export function buildDispatchBody({ agent, model, prompt }) {
  return {
    agent,
    model,
    parts: [{ type: "text", text: prompt }],
  };
}

export function extractOutput(parts) {
  if (!Array.isArray(parts)) return "";
  return parts
    .filter(
      (part) =>
        part &&
        typeof part === "object" &&
        part.type === "text" &&
        typeof part.text === "string",
    )
    .map((part) => part.text)
    .join("");
}

function describeError(error) {
  if (error instanceof Error) return error.message;
  if (error && typeof error === "object" && typeof error.message === "string") {
    return error.message;
  }
  try {
    return JSON.stringify(error);
  } catch {
    return String(error);
  }
}

function unwrapHostResult(result) {
  if (result && typeof result === "object" && !Array.isArray(result) && "data" in result) {
    if (result.error) {
      throw new Error(`host API error: ${describeError(result.error)}`);
    }
    return result.data;
  }
  return result;
}

export default async function workflowVisibilityPlugin({ client, directory }) {
  const projectDirectory = directory;

  const visibilityDispatch = tool({
    description:
      "Dispatch a prompt to a model-pinned subagent session. Reads the project-local " +
      "model selection from .opencode/mvp/visibility.json (S11) and fails closed when " +
      "no explicit selection exists; never falls back to a default model. Pass an " +
      "explicit model as provider/model to override for one dispatch.",
    args: {
      role: tool.schema
        .enum(ROLES)
        .describe("Seat to dispatch: product-observer or reviewer."),
      prompt: tool.schema.string().min(1).describe("Prompt text sent to the seat."),
      description: tool.schema
        .string()
        .optional()
        .describe("Short dispatch description (used as the session title when no title is given)."),
      model: tool.schema
        .string()
        .optional()
        .describe("Optional explicit provider/model override for this dispatch only."),
      session_id: tool.schema
        .string()
        .optional()
        .describe("Resume an existing session instead of creating a child session."),
      title: tool.schema
        .string()
        .optional()
        .describe("Title for a newly created session."),
    },
    async execute(args, context) {
      const directory = (context && context.directory) || projectDirectory;
      const resolved = resolveSelection(directory, args.role, args.model);
      if (resolved.error) {
        throw new Error(`visibility_dispatch: ${resolved.error}`);
      }
      const agent = AGENT_BY_ROLE[args.role];
      if (!agent) {
        throw new Error(`visibility_dispatch: unknown role ${JSON.stringify(args.role)}`);
      }

      const title = args.title || args.description || "observer dispatch";
      let sessionID = args.session_id;

      try {
        if (!sessionID) {
          const session = unwrapHostResult(
            await client.session.create({
              body: {
                parentID: context && context.sessionID,
                title,
              },
            }),
          );
          if (!session || typeof session.id !== "string" || !session.id) {
            throw new Error("session.create did not return a session id");
          }
          sessionID = session.id;
        }

        const response = unwrapHostResult(
          await client.session.prompt({
            path: { sessionID },
            body: buildDispatchBody({ agent, model: resolved, prompt: args.prompt }),
          }),
        );

        return {
          title,
          output: extractOutput(response && response.parts),
          metadata: {
            session_id: sessionID,
            provider_id: resolved.providerID,
            model_id: resolved.modelID,
            agent,
          },
        };
      } catch (error) {
        throw new Error(`visibility_dispatch: ${describeError(error)}`);
      }
    },
  });

  const visibilityStatus = tool({
    description:
      "Show the project-local visibility model selection from " +
      ".opencode/mvp/visibility.json. Reports unconfigured instead of throwing when " +
      "the file is missing.",
    args: {
      role: tool.schema
        .enum(ROLES)
        .optional()
        .describe("Which seat selection to show (default: product-observer)."),
    },
    async execute(args, context) {
      const directory = (context && context.directory) || projectDirectory;
      const role = args.role || "product-observer";
      const filePath = path.join(directory, VISIBILITY_RELATIVE_PATH);
      const metadata = { path: filePath, role, status: "unconfigured" };

      let document;
      try {
        document = JSON.parse(readFileSync(filePath, "utf8"));
      } catch (error) {
        const output =
          error && error.code === "ENOENT"
            ? `unconfigured: no visibility settings at ${filePath}`
            : `unreadable: visibility settings at ${filePath} are not valid JSON: ${error.message}`;
        return { title: "visibility_status", output, metadata };
      }

      if (!document || typeof document !== "object" || Array.isArray(document)) {
        return {
          title: "visibility_status",
          output: `unconfigured: visibility settings at ${filePath} are not a JSON object`,
          metadata,
        };
      }

      let selection = role === "reviewer" ? document.reviewer_selection : document.selection;
      if (role === "reviewer" && selection === undefined) {
        selection = document.selection;
      }
      if (selection === undefined || selection === null) {
        return {
          title: "visibility_status",
          output: `unconfigured: no selection for role ${role} at ${filePath}`,
          metadata,
        };
      }

      const status =
        selection && typeof selection === "object" && !Array.isArray(selection)
          ? selection.status ?? "missing-status"
          : "invalid";
      return {
        title: "visibility_status",
        output: JSON.stringify(selection, null, 2),
        metadata: { path: filePath, role, status },
      };
    },
  });

  return {
    tool: {
      visibility_dispatch: visibilityDispatch,
      visibility_status: visibilityStatus,
    },
  };
}
