import express from "express";
import fetch from "node-fetch";
import path from "path";
import { fileURLToPath } from "url";

const app = express();
app.use(express.json());

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Config
const ADDON_VERSION = process.env.ADDON_VERSION || "dev";
const TIMELIMIT_SERVER_URL =
  process.env.TIMELIMIT_SERVER_URL || "http://192.168.68.30:8080";

console.log("[timelimit-ui] Backend starting...");
console.log("[timelimit-ui] Version:", ADDON_VERSION);
console.log("[timelimit-ui] TimeLimit server URL:", TIMELIMIT_SERVER_URL);

// Serve UI
app.use("/", express.static(path.join(__dirname, "..", "ui")));

// Health/version endpoint
app.get("/api/version", (req, res) => {
  res.json({
    addon: "timelimit-ui",
    version: ADDON_VERSION,
    server_url: TIMELIMIT_SERVER_URL
  });
});

// Helper: proxy naar TimeLimit server
async function proxy(path, options = {}) {
  const url = TIMELIMIT_SERVER_URL.replace(/\/+$/, "") + path;
  const res = await fetch(url, options);
  const text = await res.text();

  let json;
  try {
    json = JSON.parse(text);
  } catch {
    json = { raw: text };
  }

  return { status: res.status, headers: res.headers, body: json };
}

// Login
app.post("/api/login", async (req, res) => {
  try {
    const { status, headers, body } = await proxy("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req.body)
    });

    const setCookie = headers.get("set-cookie") || null;

    res.status(status).json({
      data: body,
      cookie: setCookie
    });
  } catch (e) {
    console.error("[timelimit-ui] /api/login error:", e);
    res.status(500).json({ error: e.message });
  }
});

// Example: get children (requires cookie from client)
app.post("/api/children", async (req, res) => {
  try {
    const cookie = req.body.cookie || "";
    const { status, body } = await proxy("/parent/children", {
      method: "GET",
      headers: {
        Cookie: cookie
      }
    });

    res.status(status).json(body);
  } catch (e) {
    console.error("[timelimit-ui] /api/children error:", e);
    res.status(500).json({ error: e.message });
  }
});

// Example: time test
app.get("/api/time", async (req, res) => {
  try {
    const { status, body } = await proxy("/time", {
      method: "GET"
    });
    res.status(status).json(body);
  } catch (e) {
    console.error("[timelimit-ui] /api/time error:", e);
    res.status(500).json({ error: e.message });
  }
});

const PORT = 3000;
app.listen(PORT, () => {
  console.log(`[timelimit-ui] Listening on port ${PORT}`);
});