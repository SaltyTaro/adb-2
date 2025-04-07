import axios from 'axios';
import { getToken, clearToken } from './auth';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1';

// Create axios instance with default config
const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor to add auth token to requests
api.interceptors.request.use(
  (config) => {
    const token = getToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Add response interceptor to handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      // Clear token and redirect to login
      clearToken();
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Auth API calls
export const login = async (username, password) => {
  const formData = new FormData();
  formData.append('username', username);
  formData.append('password', password);
  
  const response = await axios.post(`${API_URL}/auth/token`, formData, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  });
  
  return response.data;
};

export const register = async (userData) => {
  const response = await axios.post(`${API_URL}/auth/register`, userData);
  return response.data;
};

export const getCurrentUser = async () => {
  const response = await api.get('/auth/me');
  return response.data;
};

// Projects API calls
export const fetchProjects = async (params = {}) => {
  const response = await api.get('/projects/', { params });
  return response.data;
};

export const fetchProject = async (id) => {
  const response = await api.get(`/projects/${id}`);
  return response.data;
};

export const createProject = async (projectData) => {
  const response = await api.post('/projects/', projectData);
  return response.data;
};

export const updateProject = async (id, projectData) => {
  const response = await api.put(`/projects/${id}`, projectData);
  return response.data;
};

export const deleteProject = async (id) => {
  const response = await api.delete(`/projects/${id}`);
  return response.data;
};

export const uploadProjectFiles = async (projectId, files) => {
  const formData = new FormData();
  
  files.forEach((file) => {
    formData.append('files', file);
  });
  
  const response = await api.post(`/projects/${projectId}/upload`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  
  return response.data;
};

export const fetchProjectDependencies = async (projectId) => {
  const response = await api.get(`/projects/${projectId}/dependencies`);
  return response.data;
};

// Analyses API calls
export const fetchProjectAnalyses = async (projectId, params = {}) => {
  const response = await api.get(`/projects/${projectId}/analyses`, { params });
  return response.data;
};

export const startAnalysis = async (projectId, analysisType, config = {}) => {
  const response = await api.post(`/projects/${projectId}/analyze`, {
    analysis_type: analysisType,
    config,
  });
  return response.data;
};

export const fetchAnalysis = async (analysisId) => {
  const response = await api.get(`/analyses/${analysisId}`);
  return response.data;
};

export const fetchAnalysisDetails = async (analysisId) => {
  const response = await api.get(`/analyses/${analysisId}/details`);
  return response.data;
};

// Dependencies API calls
export const fetchDependencies = async (params = {}) => {
  const response = await api.get('/dependencies/', { params });
  return response.data;
};

export const fetchDependency = async (id) => {
  const response = await api.get(`/dependencies/${id}`);
  return response.data;
};

export const refreshDependency = async (id) => {
  const response = await api.post(`/dependencies/${id}/refresh`);
  return response.data;
};

export const searchDependencies = async (query, ecosystem) => {
  const params = { q: query };
  if (ecosystem) {
    params.ecosystem = ecosystem;
  }
  const response = await api.get('/dependencies/search/', { params });
  return response.data;
};

export const fetchDependencyVersions = async (id) => {
  const response = await api.get(`/dependencies/${id}/versions`);
  return response.data;
};

export const fetchDependencyRecommendations = async (id) => {
  const response = await api.get(`/dependencies/${id}/recommendations`);
  return response.data;
};

// Recommendations API calls
export const fetchRecommendations = async (projectId, params = {}) => {
  const response = await api.get(`/projects/${projectId}/recommendations`, { params });
  return response.data;
};

export const createRecommendation = async (projectId, recommendationData) => {
  const response = await api.post(`/projects/${projectId}/recommendations`, recommendationData);
  return response.data;
};

export const deleteRecommendation = async (id) => {
  const response = await api.delete(`/recommendations/${id}`);
  return response.data;
};

export const generateRecommendations = async (projectId) => {
  const response = await api.get(`/projects/${projectId}/generate-recommendations`);
  return response.data;
};

export default api;