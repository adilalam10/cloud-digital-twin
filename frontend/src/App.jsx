import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity, BarChart3, BrainCircuit, Cloud, LayoutDashboard, Server,
  SlidersHorizontal, Plus, Play, RotateCcw, Zap, ServerCrash, RefreshCw,
} from "lucide-react";
import {
  Area, AreaChart, CartesianGrid, Line, LineChart, Legend,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "./services/api.js";

const tabs = [
  ["dashboard", "Dashboard", LayoutDashboard],
  ["infrastructure", "Infrastructure", Server],
  ["simulation", "Simulation Lab", SlidersHorizontal],
  ["prediction", "Prediction", BrainCircuit],
  ["analytics", "Analytics", BarChart3],
];

function Metric({ label, value, note }) {
  return <div className="metric"><small>{label}</small><strong>{value}</strong><span>{note}</span></div>;
}

function EvaluationCard({ title, result }) {
  const mae = result?.mae;
  const rmse = result?.rmse;
  return (
    <div className="metric evaluation-card">
      <small>{title} holdout evaluation</small>
      <div className="evaluation-values">
        <div><span>MAE</span><strong>{mae == null ? "N/A" : `${mae.toFixed(3)}%`}</strong></div>
        <div><span>RMSE</span><strong>{rmse == null ? "N/A" : `${rmse.toFixed(3)}%`}</strong></div>
      </div>
    </div>
  );
}

function App() {
  const [page, setPage] = useState("dashboard");
  const [refresh, setRefresh] = useState(0);
  const [dash, setDash] = useState(null);
  const [servers, setServers] = useState([]);
  const [metrics, setMetrics] = useState([]);
  const [history, setHistory] = useState([]);
  const [prediction, setPrediction] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [scenario, setScenario] = useState("workload");
  const [change, setChange] = useState(40);
  const [serverId, setServerId] = useState("");
  const [result, setResult] = useState(null);
  const [name, setName] = useState("");

  const reload = useCallback(() => setRefresh((value) => value + 1), []);
  const runningServers = useMemo(() => servers.filter((s) => s.status === "Running"), [servers]);
  const selectedServerId = useMemo(() => {
    if (serverId && runningServers.some((s) => String(s.id) === String(serverId))) return serverId;
    return "";
  }, [serverId, runningServers]);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.dashboard(), api.servers(), api.metrics(), api.simulations()])
      .then(([d, s, m, h]) => {
        if (cancelled) return;
        setDash(d); setServers(s); setMetrics(m); setHistory(h); setErr("");
        if (serverId && !s.some((item) => String(item.id) === String(serverId) && item.status === "Running")) {
          setServerId("");
        }
      })
      .catch((e) => { if (!cancelled) setErr(e.message); });
    return () => { cancelled = true; };
  }, [refresh]);

  useEffect(() => {
    if (page !== "prediction") return undefined;
    let cancelled = false;
    api.prediction()
      .then((value) => { if (!cancelled) { setPrediction(value); setErr(""); } })
      .catch((e) => { if (!cancelled) setErr(e.message); });
    return () => { cancelled = true; };
  }, [page, refresh]);

  async function runSimulation() {
    setBusy(true); setErr("");
    try {
      const validId = selectedServerId ? Number(selectedServerId) : null;
      const value = await api.simulate({
        scenario,
        workload_change: Number(change),
        server_id: scenario === "failure" ? validId : null,
      });
      setResult(value);
      setServerId("");
      reload();
    } catch (e) {
      setErr(e.message);
      // Refresh the available-server list if the selected node became unavailable.
      api.servers().then(setServers).catch(() => {});
      setServerId("");
    } finally {
      setBusy(false);
    }
  }

  async function addServer(event) {
    event.preventDefault();
    if (!name.trim()) return;
    setErr("");
    try {
      await api.addServer({ name: name.trim(), cpu: 15, ram: 20, storage: 20, network: 10, workload: 15 });
      setName(""); reload();
    } catch (e) { setErr(e.message); }
  }

  async function restoreServer(id) {
    setErr("");
    try { await api.restore(id); reload(); }
    catch (e) { setErr(e.message); }
  }

  async function refreshPrediction() {
    setBusy(true); setErr("");
    try { setPrediction(await api.prediction()); }
    catch (e) { setErr(e.message); }
    finally { setBusy(false); }
  }

  const current = tabs.find((item) => item[0] === page)?.[1];

  return (
    <div className="shell">
      <aside className="side">
        <div className="brand"><span><Cloud /></span><div><b>CloudTwin</b><small>INFRASTRUCTURE LAB</small></div></div>
        <label>WORKSPACE</label>
        {tabs.map(([id, title, Icon]) => (
          <button className={page === id ? "nav active" : "nav"} key={id} onClick={() => setPage(id)}>
            <Icon size={17} />{title}
          </button>
        ))}
        <div className="sidefoot"><i />Local simulation<br /><small>API-connected prototype</small></div>
      </aside>

      <main>
        <header><span>Workspace　/　{current}</span><span className="online">● System online</span></header>
        <section className="content">
          {err && <div className="error">{err}</div>}

          {page === "dashboard" && <>
            <div className="heading"><div><label>OVERVIEW</label><h1>Infrastructure Dashboard</h1><p>Live state of your simulated cloud environment.</p></div><span className="pill">● LOCAL SIMULATION</span></div>
            {dash && <div className="metrics">
              <Metric label="Total servers" value={dash.total_servers} note="Virtual server fleet" />
              <Metric label="Active servers" value={dash.active_servers} note={`${dash.failed_servers} failed`} />
              <Metric label="Average CPU" value={`${dash.average_cpu}%`} note={`${dash.high_risk_servers} high-risk servers`} />
              <Metric label="Average RAM" value={`${dash.average_ram}%`} note="Running servers" />
            </div>}
            <div className="panel"><h2>Fleet resource utilization</h2><p>Average CPU and RAM across running virtual servers</p>
              <div className="chart"><ResponsiveContainer width="100%" height="100%"><AreaChart data={metrics}>
                <CartesianGrid strokeDasharray="3 3" stroke="#29364b" /><XAxis dataKey="id" stroke="#8492a8" /><YAxis domain={[0, 100]} stroke="#8492a8" /><Tooltip />
                <Area dataKey="cpu" name="Average CPU" stroke="#8995ff" fill="#8995ff" fillOpacity={0.15} />
                <Area dataKey="ram" name="Average RAM" stroke="#35c99e" fill="transparent" />
              </AreaChart></ResponsiveContainer></div>
            </div>
            <div className="notice"><b>Digital Twin environment is active</b><p>Workload and failure scenarios update the virtual fleet and are recorded in SQLite. No physical cloud resources are modified.</p></div>
          </>}

          {page === "infrastructure" && <>
            <div className="heading"><div><label>VIRTUAL FLEET</label><h1>Infrastructure</h1><p>Inspect and manage your virtual cloud servers.</p></div></div>
            <form className="panel add" onSubmit={addServer}><div><b>Add a virtual server</b><p>Join another node to the simulated infrastructure.</p></div><input placeholder="Server name" aria-label="Server name" value={name} onChange={(e) => setName(e.target.value)} /><button type="submit"><Plus size={15} />Add server</button></form>
            <div className="servergrid">{servers.map((s) => <div className="panel server" key={s.id}>
              <div className="servertop"><b>{s.name}</b><span className={s.status === "Running" ? "good" : "bad"}>{s.status}</span></div>
              <p>Virtual node #{s.id}</p>
              <div className="barlabel">CPU <b>{Number(s.cpu).toFixed(1)}%</b></div><div className="bar"><i style={{ width: `${s.cpu}%` }} /></div>
              <div className="barlabel">RAM <b>{Number(s.ram).toFixed(1)}%</b></div><div className="bar green"><i style={{ width: `${s.ram}%` }} /></div>
              <small>Storage {s.storage}%　 Network {Number(s.network).toFixed(1)}%</small>
              {s.status !== "Running" && <button className="secondary" onClick={() => restoreServer(s.id)}><RotateCcw size={14} />Restore server</button>}
            </div>)}</div>
          </>}

          {page === "simulation" && <>
            <div className="heading"><div><label>WHAT-IF ANALYSIS</label><h1>Simulation Lab</h1><p>Test infrastructure changes safely inside the Digital Twin.</p></div></div>
            <div className="twocol">
              <div className="panel"><h2>Configure scenario</h2><p>Choose a change to apply to the virtual environment.</p>
                <div className="choices">
                  <button type="button" className={scenario === "workload" ? "chosen" : ""} onClick={() => setScenario("workload")}><Zap size={16} />Workload change</button>
                  <button type="button" className={scenario === "failure" ? "chosen" : ""} onClick={() => { setScenario("failure"); setServerId(""); }}><ServerCrash size={16} />Server failure</button>
                </div>
                {scenario === "workload" ? <>
                  <div className="barlabel">Workload adjustment <b>{change > 0 ? "+" : ""}{change}%</b></div>
                  <input type="range" min="-50" max="150" step="5" value={change} onChange={(e) => setChange(Number(e.target.value))} />
                </> : <>
                  <label>Select a running server</label>
                  <select value={selectedServerId} onChange={(e) => setServerId(e.target.value)}>
                    <option value="">Automatically choose first running server</option>
                    {runningServers.map((s) => <option value={s.id} key={s.id}>{s.name}</option>)}
                  </select>
                  {!runningServers.length && <p className="inline-warning">There are no running servers. Restore one in Infrastructure first.</p>}
                </>}
                <button className="run" onClick={runSimulation} disabled={busy || (scenario === "failure" && !runningServers.length)}><Play size={15} />{busy ? "Running..." : "Run simulation"}</button>
              </div>
              <div className="panel"><h2>Simulation result</h2>{!result ? <div className="empty">Configure a scenario and run it to compare infrastructure metrics.</div> : <>
                <span className="good">SIMULATION COMPLETED</span><p>{result.description}</p>
                <div className="resultgrid"><div>Average CPU<strong>{result.before_cpu}% → {result.after_cpu}%</strong></div><div>Average RAM<strong>{result.before_ram}% → {result.after_ram}%</strong></div></div>
                <div className="notice"><b>Recommendation</b><p>{result.recommendation}</p></div>
              </>}</div>
            </div>
          </>}

          {page === "prediction" && <>
            <div className="heading"><div><label>PREDICTIVE ANALYSIS</label><h1>Resource Prediction</h1><p>Forecast near-term fleet utilization and evaluate held-out predictions.</p></div><button className="secondary" onClick={refreshPrediction} disabled={busy}><RefreshCw size={14} />Refresh prediction</button></div>
            {prediction && <>
              <div className="panel"><label>PREDICTION METHOD</label><h2>{prediction.method}</h2><span className={`risk ${prediction.risk.toLowerCase()}`}>{prediction.risk} RISK</span>
                <div className="resultgrid"><div>CPU<strong>{prediction.current_cpu}% → {prediction.predicted_cpu}%</strong></div><div>RAM<strong>{prediction.current_ram}% → {prediction.predicted_ram}%</strong></div></div>
                <div className="notice"><b>Resource recommendation</b><p>{prediction.recommendation}</p></div>
              </div>
              <div className="metrics evaluation-grid">
                <EvaluationCard title="CPU" result={prediction.evaluation?.cpu} />
                <EvaluationCard title="RAM" result={prediction.evaluation?.ram} />
              </div>
              <div className="panel"><h2>Model evaluation protocol</h2>
                <div className="evaluation-meta"><span><b>Split:</b> {prediction.evaluation?.split || "Chronological 80/20 holdout"}</span><span><b>Training samples:</b> {prediction.evaluation?.training_samples ?? 0}</span><span><b>Testing samples:</b> {prediction.evaluation?.testing_samples ?? 0}</span></div>
                <p className="footnote">{prediction.evaluation?.note}</p>
                <div className="twocol eval-charts">
                  <div><h3>Actual vs predicted CPU</h3><div className="chart small-chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={prediction.evaluation?.cpu_points || []}><CartesianGrid strokeDasharray="3 3" stroke="#29364b" /><XAxis dataKey="sample" stroke="#8492a8" /><YAxis domain={[0, 100]} stroke="#8492a8" /><Tooltip /><Legend /><Line dataKey="actual" name="Actual CPU" stroke="#35c99e" /><Line dataKey="predicted" name="Predicted CPU" stroke="#8995ff" /></LineChart></ResponsiveContainer></div></div>
                  <div><h3>Actual vs predicted RAM</h3><div className="chart small-chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={prediction.evaluation?.ram_points || []}><CartesianGrid strokeDasharray="3 3" stroke="#29364b" /><XAxis dataKey="sample" stroke="#8492a8" /><YAxis domain={[0, 100]} stroke="#8492a8" /><Tooltip /><Legend /><Line dataKey="actual" name="Actual RAM" stroke="#35c99e" /><Line dataKey="predicted" name="Predicted RAM" stroke="#8995ff" /></LineChart></ResponsiveContainer></div></div>
                </div>
              </div>
              <p className="footnote">MAE and RMSE are percentage-point errors on the chronological held-out test set, not training data. With the small simulated dataset, treat them as preliminary results and report the sample counts alongside them.</p>
            </>}
          </>}

          {page === "analytics" && <>
            <div className="heading"><div><label>PERFORMANCE INSIGHTS</label><h1>Analytics</h1><p>Fleet-level historical metrics and what-if simulation records.</p></div></div>
            <div className="panel"><h2>Fleet CPU and RAM trend</h2><p>Each point is the average across running servers at one recorded snapshot.</p>
              <div className="chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={metrics}><CartesianGrid strokeDasharray="3 3" stroke="#29364b" /><XAxis dataKey="id" stroke="#8492a8" /><YAxis domain={[0, 100]} stroke="#8492a8" /><Tooltip /><Legend /><Line dataKey="cpu" name="Average CPU" stroke="#8995ff" dot={false} /><Line dataKey="ram" name="Average RAM" stroke="#35c99e" dot={false} /></LineChart></ResponsiveContainer></div>
            </div>
            <div className="panel history"><h2>Simulation history</h2><div className="tablewrap"><table><thead><tr><th>Scenario</th><th>CPU before</th><th>CPU after</th><th>RAM before</th><th>RAM after</th></tr></thead><tbody>
              {history.map((h) => <tr key={h.id}><td>{h.description}</td><td>{Number(h.before_cpu).toFixed(1)}%</td><td>{Number(h.after_cpu).toFixed(1)}%</td><td>{Number(h.before_ram).toFixed(1)}%</td><td>{Number(h.after_ram).toFixed(1)}%</td></tr>)}
              {!history.length && <tr><td colSpan="5">No simulations run yet.</td></tr>}
            </tbody></table></div></div>
          </>}
        </section>
        <footer>Cloud Digital Twin　•　Software simulation prototype</footer>
      </main>
    </div>
  );
}

export default App;
