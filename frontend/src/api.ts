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

export type CopernicusCollection = {
  id: string;
  title: string;
  description: string;
  license: string;
  updated?: string | null;
  temporal_start?: string | null;
  temporal_end?: string | null;
  bbox?: number[] | null;
  keywords: string[];
  providers: string[];
  thumbnail_url?: string | null;
  collection_url: string;
  source: string;
  catalog_status: string;
};

export type CopernicusCollectionsResponse = {
  query: string;
  count: number;
  results: CopernicusCollection[];
  source: string;
  catalogue_url: string;
  retrieval: 'metadata_only';
  notice: string;
};

export type CopernicusItem = {
  id: string;
  collection: string;
  datetime?: string | null;
  platform?: string | null;
  instruments: string[];
  cloud_cover?: number | null;
  gsd_m?: number | null;
  processing_level?: string | null;
  product_type?: string | null;
  bbox?: number[] | null;
  item_url: string;
  source: string;
  catalog_status: string;
};

export type CopernicusItemsResponse = {
  collection: string;
  start_date: string;
  end_date: string;
  count: number;
  items: CopernicusItem[];
  has_more: boolean;
  max_cloud_cover?: number | null;
  source: string;
  spatial_scope: string;
  retrieval: 'metadata_only';
  notice: string;
};

const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'https://earthtrend-ai-api.onrender.com').replace(/\/$/, '');

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 95_000);
  try {
    const method = String(options?.method || 'GET').toUpperCase();
    const headers = new Headers(options?.headers || {});
    if (method !== 'GET' && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      method,
      cache: method === 'GET' ? 'no-store' : options?.cache,
      credentials: 'omit',
      signal: controller.signal,
      headers,
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
  // Safari should still receive the model catalogue if the optional region
  // request fails independently (or is served from a stale cache).
  const [datasetsResult, regionsResult] = await Promise.allSettled([
    request<{ datasets: DatasetRecord[] }>('/datasets'),
    request<{ regions: ProvinceRecord[] }>('/regions'),
  ]);
  if (datasetsResult.status === 'rejected') throw datasetsResult.reason;
  return {
    datasets: Array.isArray(datasetsResult.value.datasets) ? datasetsResult.value.datasets : [],
    provinces: regionsResult.status === 'fulfilled' && Array.isArray(regionsResult.value.regions)
      ? regionsResult.value.regions : [],
  };
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

export async function searchCatalog(query: string): Promise<{query:string;count:number;results:DatasetRecord[];engine:any}> {
  const params = new URLSearchParams({q:query,limit:'30'});
  return request<{query:string;count:number;results:DatasetRecord[];engine:any}>(`/search/catalog?${params.toString()}`);
}

export async function searchCopernicusCollections(query: string, limit = 10): Promise<CopernicusCollectionsResponse> {
  const params = new URLSearchParams({ q: query, limit: String(limit) });
  return request<CopernicusCollectionsResponse>(`/search/copernicus/collections?${params.toString()}`);
}

export async function searchCopernicusItems(collection: string, start: string, end: string, limit = 10, maxCloudCover?: number): Promise<CopernicusItemsResponse> {
  const params = new URLSearchParams({ collection, start, end, limit: String(limit) });
  if (maxCloudCover !== undefined) params.set('max_cloud_cover', String(maxCloudCover));
  return request<CopernicusItemsResponse>(`/search/copernicus/items?${params.toString()}`);
}

export async function loadRegionGeoJSON(regionId: string): Promise<any> {
  return request<any>(`/regions/${encodeURIComponent(regionId)}/geojson`);
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
