import axios from 'axios';

const api = axios.create({ baseURL: '/api' });

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('siteline_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// On 401, clear token and redirect to login
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && !error.config?.url?.includes('/auth/')) {
      localStorage.removeItem('siteline_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Search
export const searchProperties = (q) =>
  api.get('/search', { params: { q, limit: 10 } }).then(r => r.data);

// Property
export const getProperty = (id) =>
  api.get(`/property/${id}`).then(r => r.data);

// Analysis
export const getBiodiversityAnalysis = (id, footprintSqm) =>
  api.get(`/property/${id}/biodiversity`, { params: { footprint_sqm: footprintSqm } }).then(r => r.data);

export const getNetZeroAnalysis = (id) =>
  api.get(`/property/${id}/netzero`).then(r => r.data);

export const getSolarAnalysis = (id) =>
  api.get(`/property/${id}/solar`).then(r => r.data);

export const getWaterAnalysis = (id) =>
  api.get(`/property/${id}/water`).then(r => r.data);

export const getConstraintMap = (id) =>
  api.get(`/property/${id}/constraint-map`).then(r => r.data);

// Map layers
export const getBiodiversityLayer = (bounds) =>
  api.get('/layers/biodiversity', {
    params: { west: bounds.west, south: bounds.south, east: bounds.east, north: bounds.north },
  }).then(r => r.data);

export const getPropertiesLayer = (bounds) =>
  api.get('/layers/properties', {
    params: { west: bounds.west, south: bounds.south, east: bounds.east, north: bounds.north },
  }).then(r => r.data);

export const getEcosystemLayer = (bounds) =>
  api.get('/layers/ecosystem-types', {
    params: { west: bounds.west, south: bounds.south, east: bounds.east, north: bounds.north },
  }).then(r => r.data);

export const getHeritageLayer = (bounds) =>
  api.get('/layers/heritage', {
    params: { west: bounds.west, south: bounds.south, east: bounds.east, north: bounds.north },
  }).then(r => r.data);

// Reports
export const getPropertyReport = (id) =>
  api.get(`/property/${id}/report`).then(r => r.data);

// AI
export const getAiAnalysis = (section, context) =>
  api.post('/ai/analyze', { section, context }).then(r => r.data);

// AI Chat (SSE streaming)
export async function* streamChat(messages, propertyId = null) {
  const token = localStorage.getItem('siteline_token');
  const response = await fetch('/api/ai/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify({ messages, property_id: propertyId }),
  });

  if (!response.ok) {
    throw new Error(`Chat request failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6);
        if (data === '[DONE]') return;
        try {
          yield JSON.parse(data);
        } catch {
          // skip malformed events
        }
      }
    }
  }
}

// Development Potential
export const getDevelopmentPotential = (id) =>
  api.get(`/property/${id}/development-potential`).then(r => r.data);

export const getSitePlan = (id) =>
  api.get(`/property/${id}/site-plan`).then(r => r.data);

export const getMassing = (id) =>
  api.get(`/property/${id}/massing`).then(r => r.data);

export const getUnitLayout = (id) =>
  api.get(`/property/${id}/unit-layout`).then(r => r.data);

// New data sources
export const getLoadshedding = (id) =>
  api.get(`/property/${id}/loadshedding`).then(r => r.data);

export const getCrimeRisk = (id) =>
  api.get(`/property/${id}/crime`).then(r => r.data);

export const getMunicipalHealth = (id) =>
  api.get(`/property/${id}/municipal`).then(r => r.data);

// Comparison
export const getRadiusComparison = (id, radiusKm = 1.0) =>
  api.get(`/property/${id}/compare/radius`, { params: { radius_km: radiusKm } }).then(r => r.data);

export const getSuburbComparison = (id) =>
  api.get(`/property/${id}/compare/suburb`).then(r => r.data);

export const getConstructionCost = (id) =>
  api.get(`/property/${id}/construction-cost`).then(r => r.data);

// Conversations
export const getConversations = (limit = 50) =>
  api.get('/conversations', { params: { limit } }).then(r => r.data);

export const createConversation = (title) =>
  api.post('/conversations', { title }).then(r => r.data);

export const getConversation = (id) =>
  api.get(`/conversations/${id}`).then(r => r.data);

export const updateConversationTitle = (id, title) =>
  api.patch(`/conversations/${id}`, { title }).then(r => r.data);

export const deleteConversation = (id) =>
  api.delete(`/conversations/${id}`).then(r => r.data);

export const saveConversationMessages = (id, messages) =>
  api.post(`/conversations/${id}/messages`, { messages }).then(r => r.data);

export default api;
