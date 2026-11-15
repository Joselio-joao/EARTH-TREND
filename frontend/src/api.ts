export type ApiStatus = 'connected' | 'offline' | 'loading';

export type DatasetRecord = {
  id: string;
  name: string;
  variable?: string;
  purpose?: string;
  source?: string;
  variable_label?: string;
  status: string;
  ready?: boolean;
  coverage_start?: string;
  coverage_end?: string;
  coverage_note?: string;
  source_cadence?: string;
  spatial_resolution_m?: number;
  display_unit?: string;
  note?: string;
  provider?: string;
  map_range?: { min: number; max: number; unit?: string; palette?: string[] };
};

export type ProvinceRecord = {
  id: string;
  name: string;
  capital: string;
  latitude: number;
  longitude: number;
};

export type ApiCatalog = {
  datasets: DatasetRecord[];
  provinces: ProvinceRecord[];
};

const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'https://earthtrend-ai-api.onrender.com').replace(/\/$/, '');

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options?.headers || {}) },
  });
  if (!response.ok) {
    let detail = '';
    try {
      const body = await response.json();
      detail = body?.error?.message || body?.detail?.map?.((item: any) => `${(item.loc || []).join('.')}: ${item.msg}`).join('; ') || body?.detail || body?.message || '';
    } catch { /* resposta sem JSON */ }
    throw new Error(detail ? `API ${response.status}: ${detail}` : `API ${response.status}: o servidor rejeitou os dados enviados.`);
  }
  return response.json() as Promise<T>;
}

export async function loadApiCatalog(): Promise<ApiCatalog> {
  const [datasets, regions] = await Promise.all([
    request<{ datasets: DatasetRecord[] }>('/datasets'),
    request<{ regions: ProvinceRecord[] }>('/regions'),
  ]);
  return { datasets: datasets.datasets, provinces: regions.regions };
}

export async function checkApi(): Promise<boolean> {
  try {
    await request<{ status: string }>('/health');
    return true;
  } catch {
    return false;
  }
}


export async function runAnalysis(payload: {
  dataset_id: string; region_id: string; start: string; end: string;
  scale: string; question: string; include_trend_map?: boolean;
}) {
  return request<any>('/analyze', { method: 'POST', body: JSON.stringify(payload) });
}

export function mapPreviewUrl(payload: {dataset_id:string;region_id:string;start:string;end:string}) {
  const query = new URLSearchParams({
    dataset_id: payload.dataset_id,
    region_id: payload.region_id,
    start: payload.start,
    end: payload.end,
  });
  return `${API_BASE}/maps/preview?${query.toString()}`;
}
