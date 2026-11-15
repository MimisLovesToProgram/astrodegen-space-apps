// Data access for the ASTRA crew health dashboard.
// Reads astronauts, domain_assessments, and sensor_readings from PocketBase.

import { listRecords } from './pocketbase';

export const DOMAINS = ['immune', 'cardiovascular', 'behavioral', 'bone_loss'];

export const DOMAIN_LABELS = {
  immune: 'Immune',
  cardiovascular: 'Cardiovascular',
  behavioral: 'Behavioral',
  bone_loss: 'Bone Loss',
};

export const STATUS_STYLES = {
  green: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400',
  yellow: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-400',
  orange: 'bg-orange-100 text-orange-700 dark:bg-orange-500/15 dark:text-orange-400',
  red: 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-400',
};

export const STATUS_DOT = {
  green: 'bg-emerald-500',
  yellow: 'bg-amber-500',
  orange: 'bg-orange-500',
  red: 'bg-red-500',
};

export async function getAstronauts() {
  return listRecords('astronauts', {
    sort: 'name',
    fields: 'id,email,name,status,created',
  });
}

// Returns { [astronautId]: { [domain]: latestRecord } } keeping only the
// newest assessment per domain (records arrive newest-first).
export async function getLatestAssessments() {
  const records = await listRecords('domain_assessments', {
    sort: '-created',
    perPage: 500,
    fields: 'astronaut,domain,domain_status,risk_score,details,created',
  });
  const latest = {};
  for (const record of records) {
    const astronaut = typeof record.astronaut === 'object'
      ? record.astronaut.id
      : record.astronaut;
    if (!astronaut || latest[astronaut]?.[record.domain]) continue;
    latest[astronaut] = latest[astronaut] || {};
    latest[astronaut][record.domain] = record;
  }
  return latest;
}

export async function getReadings(astronautId, perPage = 60) {
  return listRecords('sensor_readings', {
    filter: `astronaut="${astronautId}"`,
    sort: '-captured_at,-id',
    perPage,
    fields: 'select,value,unit,captured_at,mission_day',
  });
}

// All assessment records for one astronaut, newest first — used for the
// risk-score history view.
export async function getAssessmentHistory(astronautId, perPage = 200) {
  return listRecords('domain_assessments', {
    filter: `astronaut="${astronautId}"`,
    sort: '-created',
    perPage,
    fields: 'domain,domain_status,risk_score,details,created',
  });
}
