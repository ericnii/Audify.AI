import { useEffect, useRef, useState } from "react";
import "./App.css";

const API_BASE = "http://localhost:8000";
const TERMINAL_STATUSES = ["done", "error", "not_found"];
const LANGUAGE_OPTIONS = ["Spanish", "French", "German"];

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

function JobCard({ title, entry }) {
  if (!entry) return null;

  const data = entry.job;
  const vocalsUrl = data?.vocals_url ? `${API_BASE}${data.vocals_url}` : null;
  const instrumentalUrl = data?.instrumental_url ? `${API_BASE}${data.instrumental_url}` : null;
  const progressValue = data?.status === "done" ? 100 : Number(data?.progress ?? 0);

  return (
    <div className="status-card">
      <h3>{title}</h3>
      <div><strong>Job ID:</strong> {entry.jobId}</div>
      <div><strong>Elapsed:</strong> {entry.elapsedSeconds}s</div>
      {data?.status && <div><strong>Status:</strong> {data.status}</div>}
      {data?.stage && <div><strong>Stage:</strong> {data.stage}</div>}
      <ProgressBar value={progressValue} />
      {entry.error && <div className="error">{entry.error}</div>}
      {data?.error && <div className="error">{data.error}</div>}

      {(vocalsUrl || instrumentalUrl) && (
        <div className="section">
          <h4>Outputs</h4>
          {instrumentalUrl && (
            <div className="output-block">
              <audio controls src={instrumentalUrl} />
            </div>
          )}
          {vocalsUrl && (
            <div className="output-block">
              <audio controls src={vocalsUrl} />
            </div>
          )}
        </div>
      )}
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
  const [history, setHistory] = useState([]);
  const pollRef = useRef(null);

  async function startJob() {
    setError(null);

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
    form.append("language", language);
    if (startTime !== "" && endTime !== "") {
      form.append("start_time", String(Number(startTime)));
      form.append("end_time", String(Number(endTime)));
    }

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

    if (jobId) {
      const archivedEntry = {
        jobId,
        job,
        error,
        elapsedSeconds,
        finishedAt: finishedAt ?? Date.now(),
      };
      setHistory((prev) => [archivedEntry, ...prev]);
    }

    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }

    setJob(null);
    setJobId(data.job_id);
    setStartedAt(Date.now());
    setFinishedAt(null);
    setElapsedSeconds(0);
  }

  async function fetchJob(id) {
    const res = await fetch(`${API_BASE}/jobs/${id}`);
    if (!res.ok) throw new Error(`Status fetch failed: ${res.status}`);
    return await res.json();
  }

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

    pollOnce();
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

  const running = Boolean(job && !TERMINAL_STATUSES.includes(job.status));
  const currentEntry = jobId
    ? { jobId, job, error, elapsedSeconds, finishedAt }
    : null;

  return (
    <div className="app-shell">
      <div className="app-card">
        <header className="app-header">
          <h1>Audify.AI</h1>
          <p>Upload a track, trim if needed, extract vocals, and translate transcript segments.</p>
        </header>

        <div className="controls">
          <label htmlFor="audio-file" className="file-picker-btn">Choose Audio File</label>
          <input
            id="audio-file"
            className="file-input-hidden"
            type="file"
            accept="audio/*"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
          <span className="file-name">{file?.name || "No file selected"}</span>

          <label className="field">
            <span>Language</span>
            <select value={language} onChange={(e) => setLanguage(e.target.value)}>
              {LANGUAGE_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>Start (s)</span>
            <input
              type="number"
              min={0}
              step="0.1"
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
              placeholder="optional"
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
              placeholder="optional"
            />
          </label>

          <button className="start-btn" onClick={startJob} disabled={!file || running}>
            {running ? "Running..." : "Start Job"}
          </button>
        </div>

        {error && <div className="error">{error}</div>}

        {currentEntry && <JobCard title="Current Job" entry={currentEntry} />}

        {job?.segments?.length ? (
          <div className="section">
            <h2>Transcript Segments (For Translation)</h2>
            <div className="table-wrap">
              <table width="100%" cellPadding="8">
                <thead>
                  <tr>
                    <th>Start</th>
                    <th>End</th>
                    <th>Original Text</th>
                    <th>Translated Text</th>
                  </tr>
                </thead>
                <tbody>
                  {job.segments.map((segment, i) => (
                    <tr key={i}>
                      <td>{Number(segment.start).toFixed(2)}</td>
                      <td>{Number(segment.end).toFixed(2)}</td>
                      <td><strong>{segment.text}</strong></td>
                      <td>{segment.translated || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}

        {job?.words?.length ? (
          <div className="section">
            <h2>Word-Level Timing</h2>
            <div className="table-wrap">
              <table width="100%" cellPadding="8">
                <thead>
                  <tr>
                    <th>Word</th>
                    <th>Start (s)</th>
                    <th>End (s)</th>
                    <th>Duration (s)</th>
                    <th>Break After (s)</th>
                    <th>Segment</th>
                  </tr>
                </thead>
                <tbody>
                  {job.words.map((word, i) => (
                    <tr key={i}>
                      <td><strong>{word.text}</strong></td>
                      <td>{Number(word.start).toFixed(2)}</td>
                      <td>{Number(word.end).toFixed(2)}</td>
                      <td>{Number(word.duration).toFixed(3)}</td>
                      <td>{Number(word.break_after).toFixed(3)}</td>
                      <td>#{word.segment_id}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}

        {history.length > 0 && (
          <div className="section">
            <h2>Previous Jobs</h2>
            <div className="history-list">
              {history.map((entry) => (
                <JobCard key={entry.jobId} title="Past Job" entry={entry} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
