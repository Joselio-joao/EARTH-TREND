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


export type NasaCmrCollection = {
  id?: string | null;
  short_name?: string | null;
  title?: string | null;
  version?: string | null;
  provider?: string | null;
  summary?: string;
  start_date?: string | null;
  end_date?: string | null;
  bbox?: any;
  metadata_url?: string | null;
  earthdata_url: string;
  source: string;
  catalog_status: string;
};

export type NasaCmrCollectionsResponse = {
  query: string;
  count: number;
  total_hits?: number | null;
  results: NasaCmrCollection[];
  source: string;
  catalogue_url: string;
  retrieval: 'metadata_only';
  notice: string;
};

export type NasaCmrGranule = {
  id?: string | null;
  title?: string | null;
  producer_granule_id?: string | null;
  short_name?: string | null;
  collection_concept_id?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  cloud_cover?: number | null;
  day_night?: string | null;
  size_mb?: number | null;
  data_links: string[];
  browse_links: string[];
  metadata_url?: string | null;
  source: string;
  catalog_status: string;
};

export type NasaCmrGranulesResponse = {
  short_name: string;
  start_date: string;
  end_date: string;
  max_cloud_cover?: number | null;
  count: number;
  total_hits?: number | null;
  items: NasaCmrGranule[];
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


export async function searchNasaCmrCollections(query: string, limit = 10): Promise<NasaCmrCollectionsResponse> {
  const params = new URLSearchParams({ q: query, limit: String(limit) });
  return request<NasaCmrCollectionsResponse>(`/search/nasa/cmr/collections?${params.toString()}`);
}

export async function searchNasaCmrGranules(shortName: string, start: string, end: string, limit = 10, maxCloudCover?: number): Promise<NasaCmrGranulesResponse> {
  const params = new URLSearchParams({ short_name: shortName, start, end, limit: String(limit) });
  if (maxCloudCover !== undefined) params.set('max_cloud_cover', String(maxCloudCover));
  return request<NasaCmrGranulesResponse>(`/search/nasa/cmr/granules?${params.toString()}`);
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


export type USGSEvent = { id:string; magnitude:number|null; place:string; time:number; depth_km:number|null; longitude:number; latitude:number; url:string };
export type USGSEventsResponse = { count:number; events:USGSEvent[]; source:string; query_url:string };
export async function searchUSGSEvents(start:string,end:string,minMagnitude=2.5,limit=50):Promise<USGSEventsResponse>{
 const p=new URLSearchParams({format:'geojson',starttime:start,endtime:end,minmagnitude:String(minMagnitude),minlatitude:'-18.04',maxlatitude:'-4.38',minlongitude:'11.66',maxlongitude:'24.08',orderby:'time',limit:String(limit)});
 const url='https://earthquake.usgs.gov/fdsnws/event/1/query?'+p.toString();
 const response=await fetch(url,{headers:{Accept:'application/geo+json'}});
 if(!response.ok)throw new Error('USGS respondeu HTTP '+response.status);
 const data=await response.json();
 const events=(data.features||[]).map((f:any)=>({id:String(f.id||f.properties?.code||f.properties?.ids||''),magnitude:f.properties?.mag??null,place:f.properties?.place||'Localização não indicada',time:Number(f.properties?.time||0),depth_km:f.geometry?.coordinates?.[2]??null,longitude:f.geometry?.coordinates?.[0],latitude:f.geometry?.coordinates?.[1],url:f.properties?.url||''}));
 return {count:events.length,events,source:'USGS ComCat / FDSN Event API',query_url:url};
}
export type ArcGISItem={id:string;title:string;snippet:string;type:string;owner:string;modified:number;url:string;item_url:string};
export async function searchArcGIS(query:string,limit=8):Promise<{count:number;items:ArcGISItem[];query_url:string}>{
 const p=new URLSearchParams({q:query,num:String(limit),f:'json',sortField:'relevance',sortOrder:'desc'});
 const url='https://www.arcgis.com/sharing/rest/search?'+p.toString();
 const response=await fetch(url,{headers:{Accept:'application/json'}});
 if(!response.ok)throw new Error('ArcGIS respondeu HTTP '+response.status);
 const data=await response.json();
 if(data.error)throw new Error(data.error.message||'Erro de pesquisa ArcGIS');
 return {count:Number(data.total||0),items:(data.results||[]).map((x:any)=>({id:x.id,title:x.title||'Sem título',snippet:x.snippet||'',type:x.type||'Item',owner:x.owner||'—',modified:Number(x.modified||0),url:x.url||'',item_url:'https://www.arcgis.com/home/item.html?id='+encodeURIComponent(x.id)})),query_url:url};
}
export type OSMFeature={type:string;id:number;tags:Record<string,string>;lat?:number;lon?:number;center?:{lat:number;lon:number}};
export async function searchOSMNamedFeatures(query:string,limit=20):Promise<{count:number;features:OSMFeature[];source_url:string}>{
 const safe=query.trim().replace(/[\\\\"|]/g,' ').slice(0,80); if(!safe)throw new Error('Indica um nome ou tipo geográfico para pesquisar.');
 const bbox='-18.04,11.66,-4.38,24.08';
 const q='[out:json][timeout:25];(node["name"~"'+safe+'",i]('+bbox+');way["name"~"'+safe+'",i]('+bbox+');relation["name"~"'+safe+'",i]('+bbox+'););out center 20;';
 const endpoint='https://overpass-api.de/api/interpreter';
 const response=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded;charset=UTF-8'},body:'data='+encodeURIComponent(q)});
 if(!response.ok)throw new Error('Overpass/OSM respondeu HTTP '+response.status+'; pode estar ocupado ou limitar consultas.');
 const data=await response.json(); return {count:(data.elements||[]).length,features:data.elements||[],source_url:'https://www.openstreetmap.org/'};
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
