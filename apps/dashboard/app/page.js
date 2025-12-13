'use client';
import { useEffect, useState } from 'react';


const BASE_URL = 'http://127.0.0.1:8000';  //where /error-producer/main.py is running

export default function Home() {
  const [data, setData] = useState({ errors: [], groups: [] });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/groups')
      .then(res => res.json())
      .then(setData)
      .finally(() => setLoading(false));
  }, []);

  async function markResolved(id) {
    await fetch(`${BASE_URL}/groups/${id}/resolve`, { method: "POST" });
    const res = await fetch('/api/groups');
    const fresh = await res.json();
    setData(fresh);
  }

  


function parseSummary(aiSummary) {
  if (!aiSummary) return null;
  try {
    return JSON.parse(aiSummary);
  } catch {
    return null;
  }
}
async function runSummary(clusterKey) {
  try {
    setLoading(true);

    // trigger summarize
    await fetch(
      `${BASE_URL}/groups/${encodeURIComponent(clusterKey)}/summarize`,
      { method: "POST" }
    );

    // polling for up to 30 seconds
    let freshData;
    const start = Date.now();
    while (Date.now() - start < 30000) { // 30s max
      const res = await fetch("/api/groups");
      freshData = await res.json();

      const group = freshData.groups.find(g => g.cluster_key === clusterKey);
      if (group?.ai_summary) {
        // break as soon as summary is available
        break;
      }

      await new Promise(r => setTimeout(r, 2000));
    }

    setData(freshData);
  } catch (e) {
    console.error("Error calling summarize:", e);
  } finally {
    setLoading(false);
  }
}

function StatusBadge({ status }) {
  const base = "px-2 py-0.5 rounded text-sm font-mono";
  if (status === "OPEN") return <span className={base + " bg-red-900 text-red-100"}>OPEN</span>;
  if (status === "QUIET") return <span className={base + " bg-yellow-800 text-yellow-100"}>QUIET</span>;
  if (status === "RESOLVED") return <span className={base + " bg-green-900 text-green-100"}>RESOLVED</span>;
  return <span className={base + " bg-gray-700 text-gray-200"}>UNKNOWN</span>;
}


  return (
    <div style={{ padding: '1.5rem', fontFamily: 'monospace', maxWidth: '1100px', margin: '0 auto', fontSize: '1rem', background: '#111', color: '#eee' }}>
      <h1 style={{ fontSize: '1.75rem', marginBottom: '1rem', color: '#eee' }}>
        Error Flow Agent
      </h1>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
        
        {/* Recent errors */}
        <div>
          <h2 style={{ fontSize: '1.25rem', marginBottom: '0.5rem', color: '#f87171' }}>
            Errors ({data.errors.length})
          </h2>
          <div style={{ border: '1px solid #333', borderRadius: '6px', padding: '0.75rem', maxHeight: '450px', overflow: 'auto', background: '#1a1a1a' }}>
            {data.errors.map(error => (
              <div key={error.id} style={{ marginBottom: '0.75rem', borderBottom: '1px solid #333', paddingBottom: '0.5rem' }}>
                <div style={{ fontWeight: 'bold', color: '#f87171', fontSize: '1rem' }}>
                  {error.service} :: {error.error_type}
                </div>
                <pre style={{ fontSize: '0.9rem', whiteSpace: 'pre-wrap', color: '#fca5a5' }}>{error.message}</pre>
                <div style={{ fontSize: '0.8rem', color: '#9ca3af' }}>
                  {new Date(error.timestamp).toLocaleString()} UTC
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Error groups */}
        <div>
          <h2 style={{ fontSize: '1.25rem', marginBottom: '0.5rem', color: '#34d399' }}>
            Groups ({data.groups.length})
          </h2>
          <div style={{ border: '1px solid #333', borderRadius: '6px', padding: '0.75rem', maxHeight: '450px', overflow: 'auto', background: '#1a1a1a' }}>
            {data.groups.map(group => {
              const ai = parseSummary(group.ai_summary);
              return (
                <div key={group.id} style={{ marginBottom: '0.75rem', borderBottom: '1px solid #333', paddingBottom: '0.5rem' }}>
                  <div><strong>Cluster:</strong> {group.cluster_key}</div>
                  <div><strong>Status:</strong> <StatusBadge status={group.status} /></div>
                  <div><strong>Count:</strong> {group.count}</div>
                  <div><strong>Severity:</strong> {ai?.severity ?? group.severity ?? 'unknown'}</div>

                  {ai && (
                    <div style={{ marginTop: '0.5rem' }}>
                      <div style={{ fontWeight: 'bold' }}>AI Summary:</div>
                      <pre style={{ fontSize: '0.9rem', whiteSpace: 'pre-wrap', color: '#d1fae5' }}>{ai.summary}</pre>
                      {Array.isArray(ai.next_steps) && (
                        <ul style={{ fontSize: '0.9rem', marginTop: '0.5rem', color: '#a7f3d0' }}>
                          {ai.next_steps.map((step, i) => <li key={i}>{step}</li>)}
                        </ul>
                      )}
                    </div>
                  )}

                  <div style={{ fontSize: '0.8rem', color: '#9ca3af' }}>
                    Last Seen: {new Date(group.last_seen).toLocaleString()} UTC
                  </div>

                  {group.status !== "RESOLVED" && (
                    <button
                      onClick={() => runSummary(group.cluster_key)}
                      style={{
                        marginTop: '0.5rem',
                        marginRight: '0.5rem',
                        padding: '0.3rem 0.8rem',
                        fontSize: '0.8rem',
                        borderRadius: '6px',
                        border: 'none',
                        background: '#10b981',
                        color: 'white',
                        cursor: loading ? 'not-allowed' : 'pointer',
                      }}
                    >
                      {loading ? "Loading..." : "Get AI summary"}
                    </button>
            )}

                  {group.status !== "RESOLVED" && (
                    <button
                      onClick={() => markResolved(group.id)}
                      style={{ marginTop: '0.5rem', fontSize: '0.8rem', padding: '0.4rem 0.8rem', background: '#374151', color: '#fff', border: 'none', borderRadius: '4px' }}
                    >
                      Resolve
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div style={{ marginTop: '2rem', padding: '1rem', border: '1px solid #333', borderRadius: '6px', textAlign: 'center', background: '#1a1a1a' }}>
        <h3 style={{ fontSize: '1.25rem', marginBottom: '0.5rem', color: '#eee' }}>Test Production</h3>
        <pre style={{ background: '#000', color: '#eee', padding: '0.75rem', borderRadius: '4px', fontSize: '0.9rem' }}>
          curl -X POST {BASE_URL}/errors/with-kestra
        </pre>
        <button
          onClick={async () => {
            setLoading(true);
            try {
              await fetch(`${BASE_URL}/errors/with-kestra`, { method: 'POST' });
              const res = await fetch('/api/groups');
              const fresh = await res.json();
              setData(fresh);
            } catch (error) {
              console.error('Error:', error);
            } finally {
              setLoading(false);
            }
          }}
          style={{ marginTop: '0.75rem', fontSize: '0.9rem', padding: '0.6rem 1.2rem', background: '#2563eb', color: '#fff', border: 'none', borderRadius: '4px' }}
        >
          Refresh
        </button>
      </div>
    </div>
  );
}