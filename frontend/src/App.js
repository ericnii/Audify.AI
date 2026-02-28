import { useEffect, useRef, useState } from "react";

const API_BASE = "http://localhost:8001";

function ProgressBar({ value }) {
  const v = Math.max(0, Math.min(100, Number(value ?? 0)));
  return (
    <div style={{ marginTop: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
        <span>Progress</span>
        <span>{v}%</span>
      </div>
      <div style={{ height: 10, background: "#eee", borderRadius: 999 }}>
        <div
          style={{
            height: "100%",
            width: `${v}%`,
            background: "#111",
            borderRadius: 999,
            transition: "width 0.4s ease",
          }}
        />
      </div>
    </div>
  );
}

export default function App() {
  const [file, setFile] = useState(null);
  const [clipSeconds, setClipSeconds] = useState(30);
  const [jobId, setJobId] = useState(null);
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);
  const pollRef = useRef(null);

  async function startJob() {
    setError(null);
    setJob(null);
    setJobId(null);

    if (!file) {
      setError("Pick an audio file first.");
      return;
    }

    const form = new FormData();
    form.append("file", file);
    form.append("clip_seconds", String(clipSeconds));

    const res = await fetch(`${API_BASE}/jobs`, {
      method: "POST",
      body: form,
    });

    if (!res.ok) {
      const text = await res.text().catch(() => "");
      setError(`Upload failed: ${res.status} ${text}`);
      return;
    }

    const data = await res.json();
    setJobId(data.job_id);
  }

  async function fetchJob(id) {
    const res = await fetch(`${API_BASE}/jobs/${id}`);
    if (!res.ok) throw new Error(`Status fetch failed: ${res.status}`);
    return await res.json();
  }

  // Poll job status
  useEffect(() => {
    if (!jobId) return;

    let cancelled = false;

    async function pollOnce() {
      try {
        const data = await fetchJob(jobId);
        if (cancelled) return;
        setJob(data);

        if (data.status === "done" || data.status === "error" || data.status === "not_found") {
          if (pollRef.current) clearInterval(pollRef.current);
          pollRef.current = null;
        }
      } catch (e) {
        setError(String(e));
      }
    }

    pollOnce(); // immediately
    pollRef.current = setInterval(pollOnce, 1500);

    return () => {
      cancelled = true;
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = null;
    };
  }, [jobId]);

  const vocalsUrl = job?.vocals_url ? `${API_BASE}${job.vocals_url}` : null;
  const instrumentalUrl = job?.instrumental_url ? `${API_BASE}${job.instrumental_url}` : null;

  const running = job && !["done", "error", "not_found"].includes(job.status);

  return (
    <div style={{ maxWidth: 980, margin: "40px auto", fontFamily: "system-ui" }}>
      <h1>Audify.AI — Transcription MVP</h1>

      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <input
          type="file"
          accept="audio/*"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
        />

        <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
          Clip seconds:
          <input
            type="number"
            min={5}
            max={60}
            value={clipSeconds}
            onChange={(e) => setClipSeconds(Number(e.target.value))}
            style={{ width: 80 }}
          />
        </label>

        <button onClick={startJob} disabled={!file || running}>
          {running ? "Running..." : "Start"}
        </button>
      </div>

      {error && (
        <div style={{ marginTop: 14, color: "crimson" }}>
          {error}
        </div>
      )}

      {jobId && (
        <div style={{ marginTop: 14 }}>
          <b>Job ID:</b> {jobId}
        </div>
      )}

      {job?.status && (
        <div style={{ marginTop: 10 }}>
          <b>Status:</b> {job.status}
          {job.stage && <div style={{ marginTop: 6 }}><b>Stage:</b> {job.stage}</div>}
          <ProgressBar value={job.progress} />
          {job.error && <div style={{ color: "crimson", marginTop: 6 }}>{job.error}</div>}
        </div>
      )}

      {(vocalsUrl || instrumentalUrl) && (
        <div style={{ marginTop: 22 }}>
          <h2>Outputs</h2>

          {instrumentalUrl && (
            <div style={{ marginBottom: 14 }}>
              <h3 style={{ marginBottom: 6 }}>Instrumental</h3>
              <audio controls src={instrumentalUrl} />
              <div>
                <a href={instrumentalUrl} target="_blank" rel="noreferrer">Download instrumental</a>
              </div>
            </div>
          )}

          {vocalsUrl && (
            <div>
              <h3 style={{ marginBottom: 6 }}>Extracted Vocals</h3>
              <audio controls src={vocalsUrl} />
              <div>
                <a href={vocalsUrl} target="_blank" rel="noreferrer">Download vocals</a>
              </div>
            </div>
          )}
        </div>
      )}

      {job?.segments?.length ? (
        <div style={{ marginTop: 26 }}>
          <h2>Transcript Segments</h2>
          <table width="100%" cellPadding="8" style={{ borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ textAlign: "left", borderBottom: "1px solid #ddd" }}>
                <th style={{ width: 90 }}>Start</th>
                <th style={{ width: 90 }}>End</th>
                <th>Original Text</th>
                <th>Translation</th>
              </tr>
            </thead>
            <tbody>
              {job.segments.map((s, i) => (
                <tr key={i} style={{ borderBottom: "1px solid #f0f0f0" }}>
                  <td>{Number(s.start).toFixed(2)}</td>
                  <td>{Number(s.end).toFixed(2)}</td>
                  <td>{s.text}</td>
                  <td>{s.translated || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}