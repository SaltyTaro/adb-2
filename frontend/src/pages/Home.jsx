import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Plus, Package, GitBranch, AlertCircle, 
  BarChart2, RefreshCw
} from 'lucide-react';

import { fetchProjects } from '../services/api';

const Home = () => {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const navigate = useNavigate();
  
  useEffect(() => {
    const loadProjects = async () => {
      try {
        setLoading(true);
        const projectsData = await fetchProjects();
        setProjects(projectsData);
      } catch (error) {
        console.error('Error loading projects:', error);
        setError('Failed to load projects. Please try again.');
      } finally {
        setLoading(false);
      }
    };
    
    loadProjects();
  }, []);
  
  const handleCreateProject = () => {
    navigate('/projects/new');
  };
  
  // Get risk level badge
  const getRiskLevelBadge = (riskLevel) => {
    if (!riskLevel || riskLevel === 'unknown') {
      return (
        <span className="px-2 py-1 bg-gray-100 text-gray-700 rounded-full text-xs">
          Unknown
        </span>
      );
    }
    
    switch (riskLevel.toLowerCase()) {
      case 'critical':
      case 'high':
        return (
          <span className="px-2 py-1 bg-red-100 text-red-700 rounded-full text-xs">
            {riskLevel}
          </span>
        );
      case 'medium':
        return (
          <span className="px-2 py-1 bg-yellow-100 text-yellow-700 rounded-full text-xs">
            {riskLevel}
          </span>
        );
      case 'low':
        return (
          <span className="px-2 py-1 bg-green-100 text-green-700 rounded-full text-xs">
            {riskLevel}
          </span>
        );
      default:
        return (
          <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded-full text-xs">
            {riskLevel}
          </span>
        );
    }
  };
  
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="flex flex-col items-center">
          <RefreshCw size={32} className="animate-spin text-blue-500 mb-2" />
          <p className="text-gray-700">Loading projects...</p>
        </div>
      </div>
    );
  }
  
  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Your Projects</h1>
        <button
          onClick={handleCreateProject}
          className="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 flex items-center"
        >
          <Plus size={18} className="mr-2" />
          New Project
        </button>
      </div>
      
      {error && (
        <div className="bg-red-50 text-red-800 p-4 rounded mb-6">
          <div className="flex">
            <AlertCircle size={20} className="mr-2" />
            <div>
              <h3 className="font-bold">Error</h3>
              <p>{error}</p>
            </div>
          </div>
        </div>
      )}
      
      {projects.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {projects.map(project => (
            <div 
              key={project.id} 
              className="bg-white rounded-lg shadow hover:shadow-md transition-shadow cursor-pointer"
              onClick={() => navigate(`/projects/${project.id}`)}
            >
              <div className="p-4 border-b">
                <div className="flex items-start justify-between">
                  <div>
                    <h2 className="text-lg font-bold">{project.name}</h2>
                    <p className="text-sm text-gray-500 mt-1">{project.ecosystem}</p>
                  </div>
                  {getRiskLevelBadge(project.risk_level)}
                </div>
                
                {project.description && (
                  <p className="text-gray-600 text-sm mt-3 line-clamp-2">
                    {project.description}
                  </p>
                )}
              </div>
              
              <div className="p-4 bg-gray-50">
                <div className="grid grid-cols-2 gap-4">
                  <div className="text-center">
                    <div className="text-gray-500 text-xs mb-1">Dependencies</div>
                    <div className="flex items-center justify-center">
                      <Package size={14} className="text-blue-500 mr-1" />
                      <span className="font-bold">{project.dependency_count || 0}</span>
                    </div>
                  </div>
                  
                  <div className="text-center">
                    <div className="text-gray-500 text-xs mb-1">Analyses</div>
                    <div className="flex items-center justify-center">
                      <BarChart2 size={14} className="text-green-500 mr-1" />
                      <span className="font-bold">{project.analyses_count || 0}</span>
                    </div>
                  </div>
                </div>
                
                {project.last_analysis && (
                  <div className="text-xs text-gray-500 mt-3 text-center">
                    Last analyzed: {new Date(project.last_analysis).toLocaleDateString()}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-white p-10 rounded-lg shadow text-center">
          <Package size={48} className="mx-auto text-gray-300 mb-4" />
          <h2 className="text-xl font-bold mb-2">No Projects Yet</h2>
          <p className="text-gray-600 mb-6">
            Create your first project to start analyzing dependencies.
          </p>
          <button
            onClick={handleCreateProject}
            className="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600"
          >
            Create a Project
          </button>
        </div>
      )}
    </div>
  );
};

export default Home;