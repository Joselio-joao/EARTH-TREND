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
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 95_000);
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      signal: controller.signal,
      headers: { 'Content-Type': 'application/json', ...(options?.headers || {}) },
    });
    if (!response.ok) {
      let detail = '';
      try {
        const body = await response.json();
        detail = body?.error?.message || body?.detail?.map?.((item: any) => `${(item.loc || []).join('.')}: ${item.msg}`).join('; ') || body?.detail || body?.message || '';
      } catch { /* resposta sem JSON */ }
      if (response.status === 429) throw new Error(detail || 'O serviço está ocupado. Aguarda um pouco antes de repetir a análise.');
      if (response.status >= 500) throw new Error(detail || 'O serviço de análise está temporariamente indisponível. Os dados não foram substituídos.');
      throw new Error(detail ? `API ${response.status}: ${detail}` : `API ${response.status}: verifica os parâmetros do pedido.`);
    }
    return await response.json() as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error('A consulta excedeu o tempo de espera da aplicação. O servidor pode ainda estar a concluir o pedido; evita enviar várias tentativas seguidas.');
    }
    if (error instanceof TypeError) throw new Error('Não foi possível contactar o servidor. Verifica a ligação à internet e tenta novamente mais tarde.');
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
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
