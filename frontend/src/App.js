import { useEffect, useRef, useState } from "react";
import "./App.css";
import logo from "./logo.png";

const API_BASE = "http://localhost:8000";
const TERMINAL_STATUSES = ["done", "error", "not_found"];

function ProgressBar({ value }) {
  const v = Math.max(0, Math.min(100, Number(value ?? 0)));
  return (
    <div className="progress-wrap">
      <div className="progress-row">
        <span>Progress</span>
        <span>{v}%</span>
      </div>
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${v}%` }} />
      </div>
    </div>
  );
}

export default function App() {
  const [file, setFile] = useState(null);
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [language, setLanguage] = useState("Spanish");
  const [jobId, setJobId] = useState(null);
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);
  const [startedAt, setStartedAt] = useState(null);
  const [finishedAt, setFinishedAt] = useState(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const pollRef = useRef(null);

  async function startJob() {
    setError(null);
    setJob(null);
    setJobId(null);
    setStartedAt(null);
    setFinishedAt(null);
    setElapsedSeconds(0);

    if (!file) {
      setError("Pick an audio file first.");
      return;
    }
    if ((startTime === "") !== (endTime === "")) {
      setError("Provide both start and end time, or leave both blank.");
      return;
    }
    if (startTime !== "" && endTime !== "") {
      const startNum = Number(startTime);
      const endNum = Number(endTime);
      if (!Number.isFinite(startNum) || !Number.isFinite(endNum)) {
        setError("Start and end time must be numbers.");
        return;
      }
      if (startNum < 0) {
        setError("Start time must be >= 0.");
        return;
      }
      if (endNum <= startNum) {
        setError("End time must be greater than start time.");
        return;
      }
    }

    const form = new FormData();
    form.append("file", file);
    if (startTime !== "" && endTime !== "") {
      form.append("start_time", String(Number(startTime)));
      form.append("end_time", String(Number(endTime)));
    }
    form.append("language", language);

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
    setStartedAt(Date.now());
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

        if (TERMINAL_STATUSES.includes(data.status)) {
          setFinishedAt((prev) => prev ?? Date.now());
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

  useEffect(() => {
    if (!startedAt) return;

    const tick = () => {
      const endTs = finishedAt ?? Date.now();
      setElapsedSeconds(Math.max(0, Math.floor((endTs - startedAt) / 1000)));
    };

    tick();
    if (finishedAt) return;

    const timer = setInterval(tick, 1000);
    return () => clearInterval(timer);
  }, [startedAt, finishedAt]);

  const vocalsUrl = job?.vocals_url ? `${API_BASE}${job.vocals_url}` : null;
  const instrumentalUrl = job?.instrumental_url ? `${API_BASE}${job.instrumental_url}` : null;
  const progressValue = job?.status === "done" ? 100 : Number(job?.progress ?? 0);
  const running = Boolean(job && !TERMINAL_STATUSES.includes(job.status));
  const hasTimer = startedAt !== null;

  return (
    <div className="app-shell">
      <div className="app-card">
        <header className="app-header">
          <img src={logo} alt="Audify.AI" className="app-logo" />
          <p>AI-powered song translation studio</p>
        </header>

        <div className="controls">
          <div className="file-input-wrap">
            <input
              type="file"
              accept="audio/*"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
            <div className="file-input-label">
              <strong>Drop audio file</strong> or click to browse
            </div>
            {file && <div className="file-name">{file.name}</div>}
          </div>

          <label className="field">
            <span>Start (s)</span>
            <input
              type="number"
              min={0}
              step="0.1"
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
              placeholder="0.0"
            />
          </label>

          <label className="field">
            <span>End (s)</span>
            <input
              type="number"
              min={0}
              step="0.1"
              value={endTime}
              onChange={(e) => setEndTime(e.target.value)}
              placeholder="30.0"
            />
          </label>

          <label className="field">
            <span>Language</span>
            <select value={language} onChange={(e) => setLanguage(e.target.value)}>
              <option value="Spanish">Spanish</option>
              <option value="French">French</option>
              <option value="German">German</option>
              <option value="Japanese">Japanese</option>
              <option value="Korean">Korean</option>
              <option value="Portuguese">Portuguese</option>
              <option value="Italian">Italian</option>
              <option value="Mandarin">Mandarin</option>
            </select>
          </label>

          <label className="field">
            <span>&nbsp;</span>
            <span>&nbsp;</span>
          </label>

          <button className="start-btn" onClick={startJob} disabled={!file || running}>
            {running ? "Processing..." : "Translate"}
          </button>
        </div>

        {error && <div className="error">{error}</div>}

        {jobId && (
          <div className="meta-row">
            <div><strong>Job:</strong> {jobId.slice(0, 8)}</div>
            {hasTimer && (
              <div>
                <strong>Elapsed:</strong> {elapsedSeconds}s
              </div>
            )}
          </div>
        )}

        {job?.status && (
          <div className="status-card">
            <div><strong>Status: </strong>{job.status}</div>
            {job.stage && <div><strong>Stage: </strong>{job.stage}</div>}
            <ProgressBar value={progressValue} />
            {job.error && <div className="error">{job.error}</div>}
          </div>
        )}

        {(vocalsUrl || instrumentalUrl) && (
          <div className="section">
            <h2>Output</h2>

            {instrumentalUrl && (
              <div className="output-block">
                <h3>Instrumental</h3>
                <audio controls src={instrumentalUrl} />
                <div>
                  <a href={instrumentalUrl} target="_blank" rel="noreferrer">Download</a>
                </div>
              </div>
            )}

            {vocalsUrl && (
              <div className="output-block">
                <h3>Extracted Vocals</h3>
                <audio controls src={vocalsUrl} />
                <div>
                  <a href={vocalsUrl} target="_blank" rel="noreferrer">Download</a>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
