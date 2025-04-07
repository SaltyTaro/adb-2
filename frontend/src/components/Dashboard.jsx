import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, BarChart, Bar } from 'recharts';
import { 
  GitBranch, Shield, Package, Archive, BookOpen, Zap, 
  AlertCircle, Check, Clock, RefreshCw
} from 'lucide-react';

import { fetchProjects, fetchProjectAnalyses, fetchRecommendations } from '../services/api';

const Dashboard = () => {
  const [projects, setProjects] = useState([]);
  const [analyses, setAnalyses] = useState({});
  const [recommendations, setRecommendations] = useState({});
  const [loading, setLoading] = useState(true);
  const [activeProjects, setActiveProjects] = useState([]);
  const navigate = useNavigate();

  useEffect(() => {
    const loadDashboardData = async () => {
      try {
        setLoading(true);
        
        // Fetch all projects
        const projectsData = await fetchProjects();
        setProjects(projectsData);
        
        // Get the 5 most recent projects
        const recentProjects = [...projectsData]
          .sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at))
          .slice(0, 5);
          
        setActiveProjects(recentProjects);
        
        // Fetch analyses and recommendations for each project
        const analysesData = {};
        const recommendationsData = {};
        
        for (const project of recentProjects) {
          const projectAnalyses = await fetchProjectAnalyses(project.id);
          analysesData[project.id] = projectAnalyses;
          
          const projectRecommendations = await fetchRecommendations(project.id);
          recommendationsData[project.id] = projectRecommendations;
        }
        
        setAnalyses(analysesData);
        setRecommendations(recommendationsData);
      } catch (error) {
        console.error('Error loading dashboard data:', error);
      } finally {
        setLoading(false);
      }
    };
    
    loadDashboardData();
  }, []);
  
  // Prepare chart data for dependency counts across projects
  const dependencyChartData = projects.map(project => ({
    name: project.name,
    dependencies: project.dependency_count || 0
  }));
  
  // Prepare chart data for analysis types
  const prepareAnalysisTypesData = () => {
    const analysisTypes = {};
    
    Object.values(analyses).forEach(projectAnalyses => {
      projectAnalyses.forEach(analysis => {
        const type = analysis.analysis_type;
        analysisTypes[type] = (analysisTypes[type] || 0) + 1;
      });
    });
    
    return Object.entries(analysisTypes).map(([type, count]) => ({
      name: formatAnalysisType(type),
      count
    }));
  };
  
  // Prepare chart data for recommendation severities
  const prepareRecommendationSeverityData = () => {
    const severities = { high: 0, medium: 0, low: 0 };
    
    Object.values(recommendations).forEach(projectRecs => {
      projectRecs.forEach(rec => {
        severities[rec.severity] = (severities[rec.severity] || 0) + 1;
      });
    });
    
    return Object.entries(severities).map(([severity, count]) => ({
      name: severity.charAt(0).toUpperCase() + severity.slice(1),
      count
    }));
  };
  
  // Format analysis type for display
  const formatAnalysisType = (type) => {
    return type.split('_').map(word => 
      word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ');
  };
  
  // Get icon for analysis type
  const getAnalysisIcon = (type) => {
    switch (type) {
      case 'impact_scoring':
        return <Package size={18} />;
      case 'compatibility_prediction':
        return <GitBranch size={18} />;
      case 'dependency_consolidation':
        return <Archive size={18} />;
      case 'health_monitoring':
        return <Shield size={18} />;
      case 'license_compliance':
        return <BookOpen size={18} />;
      case 'performance_profiling':
        return <Zap size={18} />;
      default:
        return <Clock size={18} />;
    }
  };
  
  // Get severity icon
  const getSeverityIcon = (severity) => {
    switch (severity) {
      case 'high':
        return <AlertCircle size={18} className="text-red-500" />;
      case 'medium':
        return <AlertCircle size={18} className="text-yellow-500" />;
      case 'low':
        return <Check size={18} className="text-green-500" />;
      default:
        return <Check size={18} className="text-gray-500" />;
    }
  };
  
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="flex flex-col items-center">
          <RefreshCw size={32} className="animate-spin text-blue-500 mb-2" />
          <p className="text-gray-700">Loading dashboard data...</p>
        </div>
      </div>
    );
  }
  
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">Dependency Intelligence Dashboard</h1>
      
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div className="bg-white p-4 rounded shadow">
          <div className="flex items-center justify-between">
            <h3 className="text-gray-500 text-sm">Total Projects</h3>
            <Package size={20} className="text-blue-500" />
          </div>
          <p className="text-2xl font-bold">{projects.length}</p>
        </div>
        
        <div className="bg-white p-4 rounded shadow">
          <div className="flex items-center justify-between">
            <h3 className="text-gray-500 text-sm">Total Dependencies</h3>
            <Archive size={20} className="text-purple-500" />
          </div>
          <p className="text-2xl font-bold">
            {projects.reduce((sum, project) => sum + (project.dependency_count || 0), 0)}
          </p>
        </div>
        
        <div className="bg-white p-4 rounded shadow">
          <div className="flex items-center justify-between">
            <h3 className="text-gray-500 text-sm">Total Analyses</h3>
            <GitBranch size={20} className="text-green-500" />
          </div>
          <p className="text-2xl font-bold">
            {Object.values(analyses).reduce((sum, projectAnalyses) => sum + projectAnalyses.length, 0)}
          </p>
        </div>
        
        <div className="bg-white p-4 rounded shadow">
          <div className="flex items-center justify-between">
            <h3 className="text-gray-500 text-sm">Critical Recommendations</h3>
            <AlertCircle size={20} className="text-red-500" />
          </div>
          <p className="text-2xl font-bold">
            {Object.values(recommendations).reduce(
              (sum, projectRecs) => sum + projectRecs.filter(rec => rec.severity === 'high').length, 
              0
            )}
          </p>
        </div>
      </div>
      
      {/* Charts Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        <div className="bg-white p-4 rounded shadow">
          <h3 className="text-lg font-semibold mb-4">Dependencies by Project</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={dependencyChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="dependencies" fill="#3B82F6" name="Dependencies" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
        
        <div className="bg-white p-4 rounded shadow">
          <h3 className="text-lg font-semibold mb-4">Analysis Types</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={prepareAnalysisTypesData()}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="count" fill="#8B5CF6" name="Count" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
      
      {/* Recent Projects */}
      <div className="bg-white p-4 rounded shadow mb-6">
        <h3 className="text-lg font-semibold mb-4">Recent Projects</h3>
        <div className="overflow-x-auto">
          <table className="min-w-full border-collapse">
            <thead>
              <tr>
                <th className="px-4 py-2 border-b-2 text-left">Project</th>
                <th className="px-4 py-2 border-b-2 text-left">Ecosystem</th>
                <th className="px-4 py-2 border-b-2 text-left">Dependencies</th>
                <th className="px-4 py-2 border-b-2 text-left">Risk Level</th>
                <th className="px-4 py-2 border-b-2 text-left">Last Analysis</th>
                <th className="px-4 py-2 border-b-2 text-left">Actions</th>
              </tr>
            </thead>
            <tbody>
              {activeProjects.map(project => (
                <tr key={project.id} className="hover:bg-gray-50">
                  <td className="px-4 py-2 border-b">{project.name}</td>
                  <td className="px-4 py-2 border-b">{project.ecosystem}</td>
                  <td className="px-4 py-2 border-b">{project.dependency_count || 0}</td>
                  <td className="px-4 py-2 border-b">
                    <div className="flex items-center">
                      {getSeverityIcon(project.risk_level || 'unknown')}
                      <span className="ml-1 capitalize">{project.risk_level || 'Unknown'}</span>
                    </div>
                  </td>
                  <td className="px-4 py-2 border-b">
                    {project.last_analysis ? 
                      new Date(project.last_analysis).toLocaleDateString() : 
                      'Never'
                    }
                  </td>
                  <td className="px-4 py-2 border-b">
                    <button 
                      onClick={() => navigate(`/projects/${project.id}`)}
                      className="text-blue-500 hover:text-blue-700"
                    >
                      View
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      
      {/* Recent Recommendations */}
      <div className="bg-white p-4 rounded shadow">
        <h3 className="text-lg font-semibold mb-4">Critical Recommendations</h3>
        <div className="overflow-x-auto">
          <table className="min-w-full border-collapse">
            <thead>
              <tr>
                <th className="px-4 py-2 border-b-2 text-left">Project</th>
                <th className="px-4 py-2 border-b-2 text-left">Recommendation</th>
                <th className="px-4 py-2 border-b-2 text-left">Type</th>
                <th className="px-4 py-2 border-b-2 text-left">Severity</th>
                <th className="px-4 py-2 border-b-2 text-left">Actions</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(recommendations).flatMap(([projectId, projectRecs]) => 
                projectRecs
                  .filter(rec => rec.severity === 'high')
                  .slice(0, 5)
                  .map(rec => {
                    const project = projects.find(p => p.id === projectId);
                    return (
                      <tr key={rec.id} className="hover:bg-gray-50">
                        <td className="px-4 py-2 border-b">{project?.name || 'Unknown'}</td>
                        <td className="px-4 py-2 border-b">{rec.title}</td>
                        <td className="px-4 py-2 border-b">{formatAnalysisType(rec.recommendation_type)}</td>
                        <td className="px-4 py-2 border-b">
                          <div className="flex items-center">
                            {getSeverityIcon(rec.severity)}
                            <span className="ml-1 capitalize">{rec.severity}</span>
                          </div>
                        </td>
                        <td className="px-4 py-2 border-b">
                          <button 
                            onClick={() => navigate(`/projects/${projectId}`)}
                            className="text-blue-500 hover:text-blue-700"
                          >
                            View
                          </button>
                        </td>
                      </tr>
                    );
                  })
              )}
              {Object.values(recommendations).every(recs => 
                !recs.some(rec => rec.severity === 'high')
              ) && (
                <tr>
                  <td colSpan="5" className="px-4 py-2 border-b text-center text-gray-500">
                    No critical recommendations found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;