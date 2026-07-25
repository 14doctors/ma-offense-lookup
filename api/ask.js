// Vercel serverless function: plain-English offense lookup via the Claude API.
// Requires ANTHROPIC_API_KEY in the deployment's environment variables.
// The static app works without this function; the AI search box simply
// reports that it is unavailable on hosts that can't run it.

import fs from "node:fs";
import path from "node:path";
import Anthropic from "@anthropic-ai/sdk";

// Constructed lazily so a missing ANTHROPIC_API_KEY surfaces as a clean JSON
// error from the handler instead of a module-initialization crash.
let client = null;
function getClient() {
  if (!client) client = new Anthropic();
  return client;
}

// Build the corpus digest once per warm instance. One line per offense:
//   row | L<level><flag> | penalty | citation | title | notes
const corpus = (() => {
  const raw = JSON.parse(
    fs.readFileSync(path.join(process.cwd(), "data", "crime_list.json"), "utf8"),
  );
  const F = {};
  raw.fields.forEach((name, i) => {
    F[name] = i;
  });
  const lines = raw.rows.map((row, i) => {
    const status = row[F.level_status];
    const flag = status && status !== "F" ? "(" + status + ")" : "";
    return [
      i,
      "L" + (row[F.level_number] || "?") + flag,
      row[F.penalty_type] || "",
      row[F.offense_ref] || "",
      row[F.offense_title] || "",
      row[F.notes] || "",
    ].join(" | ");
  });
  return { lineCount: lines.length, text: lines.join("\n") };
})();

const INSTRUCTIONS = `You are the lookup assistant for the Massachusetts Sentencing Commission's Felony & Misdemeanor Master Crime List (December 2015 edition). The full list follows in the next block, one offense per line:

row | L<level><flag> | penalty type | statutory citation | offense title | notes

"row" is the offense's row number — identify matches by it. Level is seriousness 1-9; "(T)" marks Note K tentative rankings, "(C)" contingent.

The user describes an offense in plain English — possibly a factual scenario, or non-Massachusetts terminology (e.g. "DUI" for OUI, "battery" for A&B, "burglary" for B&E). Find the offenses on the list that plausibly cover it:

- Return up to 12 matches, most relevant first. Include closely related variants (subsequent-offense tiers, aggravated forms, value thresholds) when relevant.
- Only offenses actually on the list, each identified by its exact row number.
- "why": one short clause on why that row matches (e.g. "third-offense OUI tier").
- "interpretation": one sentence stating how you read the query in Massachusetts terms.
- "caveats": ambiguity, plausible alternate readings, or places where post-2015 amendments likely changed the law; empty string if none.
- If nothing on the list matches, return an empty matches array and say so in "interpretation".

This is a legislative-drafting reference, not legal advice; keep output factual and terse.`;

const OUTPUT_SCHEMA = {
  type: "object",
  properties: {
    interpretation: { type: "string" },
    matches: {
      type: "array",
      items: {
        type: "object",
        properties: {
          row: { type: "integer" },
          why: { type: "string" },
        },
        required: ["row", "why"],
        additionalProperties: false,
      },
    },
    caveats: { type: "string" },
  },
  required: ["interpretation", "matches", "caveats"],
  additionalProperties: false,
};

export default async function handler(req, res) {
  if (req.method !== "POST") {
    res.status(405).json({ error: "POST only" });
    return;
  }
  const query = typeof req.body?.query === "string" ? req.body.query.trim() : "";
  if (!query) {
    res.status(400).json({ error: "Missing query" });
    return;
  }
  if (query.length > 500) {
    res.status(400).json({ error: "Query too long (500 characters max)" });
    return;
  }

  let api;
  try {
    api = getClient();
  } catch (_) {
    res.status(500).json({ error: "Server is missing a valid ANTHROPIC_API_KEY." });
    return;
  }

  try {
    const response = await api.messages.create({
      model: "claude-opus-5",
      max_tokens: 16000,
      // Interactive search over a provided list is routine work; medium effort
      // keeps latency inside the function's time limit at no real quality cost.
      output_config: {
        effort: "medium",
        format: { type: "json_schema", schema: OUTPUT_SCHEMA },
      },
      system: [
        { type: "text", text: INSTRUCTIONS },
        {
          type: "text",
          text: corpus.text,
          cache_control: { type: "ephemeral", ttl: "1h" },
        },
      ],
      messages: [{ role: "user", content: query }],
    });

    if (response.stop_reason === "refusal") {
      const detail = response.stop_details?.explanation;
      res.status(422).json({
        error: "The model declined this query" + (detail ? ": " + detail : "."),
      });
      return;
    }
    if (response.stop_reason === "max_tokens") {
      res.status(502).json({ error: "Response was truncated — try a narrower query." });
      return;
    }

    const text = response.content.find((b) => b.type === "text")?.text ?? "";
    let parsed;
    try {
      parsed = JSON.parse(text);
    } catch {
      res.status(502).json({ error: "Model returned unparseable output — try again." });
      return;
    }
    parsed.matches = (parsed.matches || []).filter(
      (m) => Number.isInteger(m.row) && m.row >= 0 && m.row < corpus.lineCount,
    );
    res.status(200).json(parsed);
  } catch (err) {
    if (err instanceof Anthropic.AuthenticationError) {
      res.status(500).json({ error: "Server is missing a valid ANTHROPIC_API_KEY." });
    } else if (err instanceof Anthropic.RateLimitError) {
      res.status(429).json({ error: "Rate limited — try again in a moment." });
    } else if (err instanceof Anthropic.APIConnectionError) {
      res.status(502).json({ error: "Could not reach the Claude API — try again." });
    } else if (err instanceof Anthropic.APIError) {
      res.status(502).json({ error: "Claude API error (" + err.status + ")." });
    } else {
      console.error(err);
      res.status(500).json({ error: "Unexpected server error." });
    }
  }
}
