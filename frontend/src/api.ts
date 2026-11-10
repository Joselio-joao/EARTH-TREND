export type ApiStatus = 'connected' | 'offline' | 'loading';

export type DatasetRecord = {
  id: string;
  name: string;
  variable: string;
  purpose: string;
  source: string;
  status: string;
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

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options?.headers || {}) },
  });
  if (!response.ok) throw new Error(`API ${response.status}`);
  return response.json() as Promise<T>;
}

export async function loadApiCatalog(): Promise<ApiCatalog> {
  const [datasets, regions] = await Promise.all([
    request<{ datasets: DatasetRecord[] }>('/datasets'),
    request<{ provinces: ProvinceRecord[] }>('/regions'),
  ]);
  return { datasets: datasets.datasets, provinces: regions.provinces };
}

export async function checkApi(): Promise<boolean> {
  try {
    await request<{ status: string }>('/health');
    return true;
  } catch {
    return false;
  }
}
