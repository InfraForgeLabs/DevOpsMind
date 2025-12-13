export default {
  async fetch(request, env, ctx) {
    try {
      if (request.method === "OPTIONS") {
        return new Response(null, { headers: corsHeaders() });
      }

      if (request.method !== "POST") {
        return new Response(JSON.stringify({ error: "Method not allowed" }), {
          status: 405,
          headers: corsHeaders({ "Content-Type": "application/json" }),
        });
      }

      const contentLength = Number(request.headers.get("content-length") || 0);
      if (contentLength > 65536) {
        return new Response(JSON.stringify({ error: "Payload too large (max 64 KiB)" }), {
          status: 413,
          headers: corsHeaders({ "Content-Type": "application/json" }),
        });
      }

      const body = await request.text();
      if (!body.trim()) {
        return new Response(JSON.stringify({ ok: false, error: "Empty submission" }), {
          status: 200,
          headers: corsHeaders({ "Content-Type": "application/json" }),
        });
      }

      const digest = await sha256base16(body);
      const payload = {
        event_type: "player_submission",
        client_payload: {
          yaml: body,
          received_at: new Date().toISOString(),
          sha256: digest,
        },
      };

      const ghRes = await fetch(
        "https://api.github.com/repos/InfraForgeLabs/DevOpsMind/dispatches",
        {
          method: "POST",
          headers: {
            "Authorization": `Bearer ${env.REPO_PAT}`,
            "Accept": "application/vnd.github+json",
            "User-Agent": "devopsmind-relay",
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        }
      );

      if (!ghRes.ok) {
        const err = await ghRes.text();
        return new Response(
          JSON.stringify({ ok: false, error: "GitHub dispatch failed", body: err }),
          { status: 200, headers: corsHeaders({ "Content-Type": "application/json" }) }
        );
      }

      return new Response(JSON.stringify({ ok: true, sha256: digest }), {
        status: 200,
        headers: corsHeaders({ "Content-Type": "application/json" }),
      });
    } catch (err) {
      return new Response(JSON.stringify({ ok: false, error: err.message }), {
        status: 200,
        headers: corsHeaders({ "Content-Type": "application/json" }),
      });
    }
  },
};

function corsHeaders(extra = {}) {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    ...extra,
  };
}

async function sha256base16(text) {
  const enc = new TextEncoder().encode(text);
  const hash = await crypto.subtle.digest("SHA-256", enc);
  return [...new Uint8Array(hash)].map((b) => b.toString(16).padStart(2, "0")).join("");
}
