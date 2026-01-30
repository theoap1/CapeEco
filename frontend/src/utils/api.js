import axios from 'axios';

const api = axios.create({ baseURL: '/api' });

export const searchProperties = (q) =>
  api.get('/search', { params: { q, limit: 10 } }).then(r => r.data);

export const getProperty = (id) =>
  api.get(`/property/${id}`).then(r => r.data);

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

export const getPropertyReport = (id) =>
  api.get(`/property/${id}/report`).then(r => r.data);

export const getAiAnalysis = (section, context) =>
  api.post('/ai/analyze', { section, context }).then(r => r.data);
