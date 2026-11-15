import React, { useCallback, useEffect, useState } from 'react';

import Sidebar from '../partials/Sidebar';
import Header from '../partials/Header';
import Banner from '../partials/Banner';

import {
  DOMAINS,
  DOMAIN_LABELS,
  STATUS_STYLES,
  STATUS_DOT,
  getAstronauts,
  getLatestAssessments,
  getReadings,
  getAssessmentHistory,
} from '../lib/api';
import { isLoggedIn, login, logout, getRecord } from '../lib/pocketbase';

const STATUS_RANK = { green: 0, yellow: 1, orange: 2, red: 3 };

function worstDomain(domainMap) {
  let worst = null;
  for (const domain of DOMAINS) {
    const record = domainMap?.[domain];
    if (!record) continue;
    if (!worst || STATUS_RANK[record.domain_status] > STATUS_RANK[worst.domain_status]
        || (record.domain_status === worst.domain_status
            && record.risk_score > worst.risk_score)) {
      worst = record;
    }
  }
  return worst;
}

function StatusPill({ status }) {
  if (!status) return <span className="text-xs text-gray-400">no data</span>;
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold uppercase ${STATUS_STYLES[status] || ''}`}>
      {status}
    </span>
  );
}

function LoginScreen({ onLogin }) {
  const [identity, setIdentity] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      await login(identity, password);
      onLogin();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100 dark:bg-gray-900 px-4">
      <form onSubmit={submit} className="w-full max-w-sm bg-white dark:bg-gray-800 rounded-2xl shadow-lg p-8">
        <h1 className="text-2xl font-bold text-gray-800 dark:text-gray-100 mb-1">ASTRA</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">
          Astronaut Health Monitoring — sign in with a crew account.
        </p>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Email</label>
        <input
          type="email"
          required
          value={identity}
          onChange={(e) => setIdentity(e.target.value)}
          placeholder="a@astrocrates.local"
          className="w-full mb-4 rounded-lg border-gray-300 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100 text-sm"
        />
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Password</label>
        <input
          type="password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full mb-4 rounded-lg border-gray-300 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100 text-sm"
        />
        {error && <p className="text-sm text-red-600 dark:text-red-400 mb-4">{error}</p>}
        <button
          type="submit"
          disabled={busy}
          className="w-full btn bg-violet-600 text-white hover:bg-violet-500 disabled:opacity-50"
        >
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  );
}

function AstronautCard({ astronaut, domains, selected, onSelect }) {
  const worst = worstDomain(domains);
  return (
    <button
      onClick={onSelect}
      className={`text-left col-span-12 sm:col-span-6 xl:col-span-4 bg-white dark:bg-gray-800 rounded-2xl shadow-xs border p-5 transition hover:shadow-md ${
        selected ? 'border-violet-500 ring-1 ring-violet-500' : 'border-gray-200 dark:border-gray-700/60'
      }`}
    >
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="text-lg font-bold text-gray-800 dark:text-gray-100">
            {astronaut.name || astronaut.email}
          </div>
          <div className="text-xs text-gray-500 dark:text-gray-400">{astronaut.email}</div>
        </div>
        <div className="flex items-center gap-2">
          {worst && (
            <>
              <span className={`w-2.5 h-2.5 rounded-full ${STATUS_DOT[worst.domain_status] || 'bg-gray-400'}`} />
              <StatusPill status={worst.domain_status} />
            </>
          )}
        </div>
      </div>
      <div className="space-y-2">
        {DOMAINS.map((domain) => {
          const record = domains?.[domain];
          return (
            <div key={domain} className="flex items-center justify-between text-sm">
              <span className="text-gray-600 dark:text-gray-400">{DOMAIN_LABELS[domain]}</span>
              <span className="flex items-center gap-2">
                {record && (
                  <span className="text-xs font-semibold text-gray-500 dark:text-gray-400">
                    {record.risk_score}
                  </span>
                )}
                <StatusPill status={record?.domain_status} />
              </span>
            </div>
          );
        })}
      </div>
    </button>
  );
}

function DetailPanel({ astronaut, domains, readings, history }) {
  return (
    <div className="col-span-12 bg-white dark:bg-gray-800 rounded-2xl shadow-xs border border-gray-200 dark:border-gray-700/60 p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-bold text-gray-800 dark:text-gray-100">
          {astronaut.name || astronaut.email}
          <span className="ml-2 text-sm font-normal text-gray-500">{astronaut.email}</span>
        </h2>
        <span className="text-xs text-gray-400">status: {astronaut.status || '—'}</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
        {DOMAINS.map((domain) => {
          const record = domains?.[domain];
          const details = record?.details || {};
          return (
            <div key={domain} className="rounded-xl border border-gray-200 dark:border-gray-700/60 p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-semibold text-gray-700 dark:text-gray-200">
                  {DOMAIN_LABELS[domain]}
                </span>
                <StatusPill status={record?.domain_status} />
              </div>
              <div className="text-2xl font-bold text-gray-800 dark:text-gray-100">
                {record ? record.risk_score : '—'}
                <span className="text-xs font-normal text-gray-400">/100</span>
              </div>
              {details.trigger_message && (
                <p className="text-xs text-orange-600 dark:text-orange-400 mt-1">
                  {details.trigger_message}
                </p>
              )}
              {details.matched_rules?.length > 0 && (
                <ul className="mt-2 text-xs text-gray-500 dark:text-gray-400 space-y-1">
                  {details.matched_rules.map((rule, i) => (
                    <li key={i}>• {rule.description || rule.metric}</li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <div>
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-2">
            Recent sensor readings
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-gray-400 border-b border-gray-200 dark:border-gray-700">
                  <th className="py-2 pr-3">Metric</th>
                  <th className="py-2 pr-3">Value</th>
                  <th className="py-2 pr-3">Day</th>
                  <th className="py-2">Captured</th>
                </tr>
              </thead>
              <tbody>
                {(readings || []).slice(0, 12).map((row) => (
                  <tr key={row.id} className="border-b border-gray-100 dark:border-gray-700/40">
                    <td className="py-1.5 pr-3 font-mono text-xs">{row.select}</td>
                    <td className="py-1.5 pr-3">{row.value}{row.unit ? ` ${row.unit}` : ''}</td>
                    <td className="py-1.5 pr-3">{row.mission_day ?? '—'}</td>
                    <td className="py-1.5 text-xs text-gray-400">
                      {row.captured_at ? new Date(row.captured_at).toLocaleString() : '—'}
                    </td>
                  </tr>
                ))}
                {(!readings || readings.length === 0) && (
                  <tr><td colSpan={4} className="py-3 text-gray-400">No readings stored.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div>
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-2">
            Assessment history
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-gray-400 border-b border-gray-200 dark:border-gray-700">
                  <th className="py-2 pr-3">Domain</th>
                  <th className="py-2 pr-3">Status</th>
                  <th className="py-2 pr-3">Score</th>
                  <th className="py-2">Assessed</th>
                </tr>
              </thead>
              <tbody>
                {(history || []).slice(0, 12).map((row) => (
                  <tr key={row.id} className="border-b border-gray-100 dark:border-gray-700/40">
                    <td className="py-1.5 pr-3">{DOMAIN_LABELS[row.domain] || row.domain}</td>
                    <td className="py-1.5 pr-3"><StatusPill status={row.domain_status} /></td>
                    <td className="py-1.5 pr-3">{row.risk_score}</td>
                    <td className="py-1.5 text-xs text-gray-400">
                      {row.created ? new Date(row.created).toLocaleString() : '—'}
                    </td>
                  </tr>
                ))}
                {(!history || history.length === 0) && (
                  <tr><td colSpan={4} className="py-3 text-gray-400">No assessments yet.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

function Dashboard() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [authed, setAuthed] = useState(isLoggedIn());
  const [astronauts, setAstronauts] = useState([]);
  const [assessments, setAssessments] = useState({});
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState({ readings: [], history: [] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [crew, latest] = await Promise.all([getAstronauts(), getLatestAssessments()]);
      setAstronauts(crew);
      setAssessments(latest);
      setSelectedId((current) => current || crew[0]?.id || null);
    } catch (err) {
      setError(err.message);
      if (err.message && /401|403|Token/.test(err.message)) {
        logout();
        setAuthed(false);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (authed) load();
  }, [authed, load]);

  useEffect(() => {
    if (!selectedId) return;
    Promise.all([getReadings(selectedId), getAssessmentHistory(selectedId)])
      .then(([readings, history]) => setDetail({ readings, history }))
      .catch(() => setDetail({ readings: [], history: [] }));
  }, [selectedId, assessments]);

  if (!authed) {
    return <LoginScreen onLogin={() => setAuthed(true)} />;
  }

  const record = getRecord();
  const selected = astronauts.find((a) => a.id === selectedId);

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen} />

      <div className="relative flex flex-col flex-1 overflow-y-auto overflow-x-hidden">
        <Header sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen} />

        <main className="grow">
          <div className="px-4 sm:px-6 lg:px-8 py-8 w-full max-w-9xl mx-auto">

            <div className="sm:flex sm:justify-between sm:items-center mb-8">
              <div className="mb-4 sm:mb-0">
                <h1 className="text-2xl md:text-3xl text-gray-800 dark:text-gray-100 font-bold">
                  Crew Health
                </h1>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  Live domain assessments from PocketBase. Signed in as {record?.email || 'crew'}.
                </p>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={load}
                  disabled={loading}
                  className="btn bg-gray-900 text-gray-100 hover:bg-gray-800 dark:bg-gray-100 dark:text-gray-800 dark:hover:bg-white disabled:opacity-50"
                >
                  {loading ? 'Refreshing…' : 'Refresh'}
                </button>
                <button
                  onClick={() => { logout(); setAuthed(false); }}
                  className="btn border border-gray-300 text-gray-600 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700"
                >
                  Sign out
                </button>
              </div>
            </div>

            {error && (
              <div className="mb-6 rounded-xl border border-red-200 bg-red-50 dark:bg-red-500/10 dark:border-red-500/30 px-4 py-3 text-sm text-red-700 dark:text-red-300">
                {error}
              </div>
            )}

            <div className="grid grid-cols-12 gap-6">
              {astronauts.map((astronaut) => (
                <AstronautCard
                  key={astronaut.id}
                  astronaut={astronaut}
                  domains={assessments[astronaut.id]}
                  selected={astronaut.id === selectedId}
                  onSelect={() => setSelectedId(astronaut.id)}
                />
              ))}
              {astronauts.length === 0 && !loading && (
                <div className="col-span-12 text-center text-gray-400 py-12">
                  No astronauts found in the database.
                </div>
              )}

              {selected && (
                <DetailPanel
                  astronaut={selected}
                  domains={assessments[selected.id]}
                  readings={detail.readings}
                  history={detail.history}
                />
              )}
            </div>

          </div>
        </main>

        <Banner />
      </div>
    </div>
  );
}

export default Dashboard;
