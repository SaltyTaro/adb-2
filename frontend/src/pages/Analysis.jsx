import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { 
  Package, BarChart2, GitBranch, Shield, BookOpen, Zap,
  Clock, AlertTriangle, CheckCircle, RefreshCw, ChevronRight
} from 'lucide-react';

import { fetchProject, fetchProjectAnalyses, startAnalysis } from '../services/api';

const Analysis = () => {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [analyses, setAnalyses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedAnalysisType, setSelectedAnalysisType] = useState('impact_scoring');
  const [runningAnalysis, setRunningAnalysis] = useState(false);
  
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        
        // Load project and analyses
        const projectData = await fetchProject(projectId);
        const analysesData = await fetchProjectAnalyses(projectId);
        
        setProject(projectData);
        setAnalyses(analysesData);
      } catch (error) {
        console.error('Error loading data:', error);
        setError('Failed to load project data');
      } finally {
        setLoading(false);
      }
    };
    
    loadData();
  }, [projectId]);
  
  const handleStartAnalysis = async () => {
    try {
      setRunningAnalysis(true);
      
      // Set up configuration based on analysis type
      let config = {};
      
      if (selectedAnalysisType === 'compatibility_prediction') {
        config = { time_horizon: 180 }; // 6 months
      } else if (selectedAnalysisType === 'license_compliance') {
        config = { target_license: 'mit' };
      } else if (selectedAnalysisType === 'performance_profiling') {
        config = { profile_type: 'bundle_size' };
      }
      
      const analysisResult = await startAnalysis(projectId, selectedAnalysisType, config);
      
      // Refresh analyses list
      const analysesData = await fetchProjectAnalyses(projectId);
      setAnalyses(analysesData);
      
      // Navigate to the new analysis
      if (analysisResult && analysisResult.id) {
        navigate(`/analyses/${analysisResult.id}`);
      }
      
    } catch (error) {
      console.error('Error starting analysis:', error);
      setError('Failed to start analysis. Please try again.');
    } finally {
      setRunningAnalysis(false);
    }
  };
  
  // Format analysis type for display
  const formatAnalysisType = (type) => {
    return type.split('_').map(word => 
      word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ');
  };
  
  // Get analysis icon
  const getAnalysisIcon = (type) => {
    switch (type) {
      case 'impact_scoring':
        return <Package size={20} className="text-blue-500" />;
      case 'compatibility_prediction':
        return <GitBranch size={20} className="text-purple-500" />;
      case 'dependency_consolidation':
        return <Package size={20} className="text-indigo-500" />;
      case 'health_monitoring':
        return <Shield size={20} className="text-green-500" />;
      case 'license_compliance':
        return <BookOpen size={20} className="text-orange-500" />;
      case 'performance_profiling':
        return <Zap size={20} className="text-yellow-500" />;
      default:
        return <BarChart2 size={20} className="text-gray-500" />;
    }
  };
  
  // Get status indicator
  const getStatusIndicator = (status) => {
    switch (status) {
      case 'completed':
        return (
          <span className="flex items-center text-green-600">
            <CheckCircle size={16} className="mr-1" />
            Completed
          </span>
        );
      case 'running':
        return (
          <span className="flex items-center text-blue-600">
            <RefreshCw size={16} className="mr-1 animate-spin" />
            Running
          </span>
        );
      case 'failed':
        return (
          <span className="flex items-center text-red-600">
            <AlertTriangle size={16} className="mr-1" />
            Failed
          </span>
        );
      default:
        return (
          <span className="flex items-center text-gray-600">
            <Clock size={16} className="mr-1" />
            {status}
          </span>
        );
    }
  };
  
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="flex flex-col items-center">
          <RefreshCw size={32} className="animate-spin text-blue-500 mb-2" />
          <p className="text-gray-700">Loading project data...</p>
        </div>
      </div>
    );
  }
  
  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 text-red-800 p-4 rounded mb-4">
          <h3 className="font-bold">Error</h3>
          <p>{error}</p>
          <button 
            className="mt-2 text-blue-500 hover:text-blue-700"
            onClick={() => navigate(`/projects/${projectId}`)}
          >
            Return to Project
          </button>
        </div>
      </div>
    );
  }
  
  if (!project) {
    return (
      <div className="p-6">
        <div className="bg-red-50 text-red-800 p-4 rounded mb-4">
          <h3 className="font-bold">Error</h3>
          <p>Project not found</p>
          <button 
            className="mt-2 text-blue-500 hover:text-blue-700"
            onClick={() => navigate('/')}
          >
            Return to Dashboard
          </button>
        </div>
      </div>
    );
  }
  
  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Analyze Project: {project.name}</h1>
          <p className="text-gray-600 text-sm">
            Run analyses to gain insights about your project dependencies
          </p>
        </div>
        <button
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          onClick={() => navigate(`/projects/${projectId}`)}
        >
          Back to Project
        </button>
      </div>
      
      {/* Run Analysis */}
      <div className="bg-white rounded shadow p-4 mb-6">
        <h3 className="font-medium mb-4">Run a New Analysis</h3>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
          <div>
            <label className="block text-sm text-gray-600 mb-2">Analysis Type</label>
            <select
              value={selectedAnalysisType}
              onChange={(e) => setSelectedAnalysisType(e.target.value)}
              className="border p-2 w-full rounded"
              disabled={runningAnalysis}
            >
              <option value="impact_scoring">Impact Scoring</option>
              <option value="compatibility_prediction">Compatibility Prediction</option>
              <option value="dependency_consolidation">Dependency Consolidation</option>
              <option value="health_monitoring">Health Monitoring</option>
              <option value="license_compliance">License Compliance</option>
              <option value="performance_profiling">Performance Profiling</option>
            </select>
          </div>
          
          <div className="md:col-span-2">
            <label className="block text-sm text-gray-600 mb-2">Description</label>
            <div className="border p-3 rounded bg-gray-50 h-full">
              {selectedAnalysisType === 'impact_scoring' && (
                <div className="flex items-start">
                  <Package size={20} className="text-blue-500 mr-2 mt-1" />
                  <div>
                    <div className="font-medium">Impact Scoring</div>
                    <p className="text-sm text-gray-600">
                      Analyzes the importance and risk profile of each dependency based on usage patterns, dependency complexity, and project structure.
                    </p>
                  </div>
                </div>
              )}
              
              {selectedAnalysisType === 'compatibility_prediction' && (
                <div className="flex items-start">
                  <GitBranch size={20} className="text-purple-500 mr-2 mt-1" />
                  <div>
                    <div className="font-medium">Compatibility Prediction</div>
                    <p className="text-sm text-gray-600">
                      Forecasts potential compatibility issues and breaking changes for your dependencies over the next 6 months.
                    </p>
                  </div>
                </div>
              )}
              
              {selectedAnalysisType === 'dependency_consolidation' && (
                <div className="flex items-start">
                  <Package size={20} className="text-indigo-500 mr-2 mt-1" />
                  <div>
                    <div className="font-medium">Dependency Consolidation</div>
                    <p className="text-sm text-gray-600">
                      Identifies duplicate functionality and opportunities to optimize your dependency tree.
                    </p>
                  </div>
                </div>
              )}
              
              {selectedAnalysisType === 'health_monitoring' && (
                <div className="flex items-start">
                  <Shield size={20} className="text-green-500 mr-2 mt-1" />
                  <div>
                    <div className="font-medium">Health Monitoring</div>
                    <p className="text-sm text-gray-600">
                      Analyzes the maintenance status, community activity, and overall health of each dependency.
                    </p>
                  </div>
                </div>
              )}
              
              {selectedAnalysisType === 'license_compliance' && (
                <div className="flex items-start">
                  <BookOpen size={20} className="text-orange-500 mr-2 mt-1" />
                  <div>
                    <div className="font-medium">License Compliance</div>
                    <p className="text-sm text-gray-600">
                      Analyzes the licenses of all dependencies and identifies potential compliance issues.
                    </p>
                  </div>
                </div>
              )}
              
              {selectedAnalysisType === 'performance_profiling' && (
                <div className="flex items-start">
                  <Zap size={20} className="text-yellow-500 mr-2 mt-1" />
                  <div>
                    <div className="font-medium">Performance Profiling</div>
                    <p className="text-sm text-gray-600">
                      Analyzes the runtime performance and bundle size impact of your dependencies.
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
        
        <div className="text-right">
          <button
            onClick={handleStartAnalysis}
            className="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600 flex items-center ml-auto"
            disabled={runningAnalysis}
          >
            {runningAnalysis ? (
              <>
                <RefreshCw size={16} className="mr-2 animate-spin" />
                Running Analysis...
              </>
            ) : (
              <>
                {getAnalysisIcon(selectedAnalysisType)}
                <span className="ml-2">Run Analysis</span>
              </>
            )}
          </button>
        </div>
      </div>
      
      {/* Recent Analyses */}
      <div className="bg-white rounded shadow p-4">
        <h3 className="font-medium mb-4">Recent Analyses</h3>
        
        {analyses.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="min-w-full border-collapse">
              <thead>
                <tr>
                  <th className="px-4 py-2 border-b-2 text-left">Type</th>
                  <th className="px-4 py-2 border-b-2 text-left">Status</th>
                  <th className="px-4 py-2 border-b-2 text-left">Created</th>
                  <th className="px-4 py-2 border-b-2 text-left">Completed</th>
                  <th className="px-4 py-2 border-b-2 text-left">Actions</th>
                </tr>
              </thead>
              <tbody>
                {analyses.map((analysis) => (
                  <tr key={analysis.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 border-b">
                      <div className="flex items-center">
                        {getAnalysisIcon(analysis.analysis_type)}
                        <span className="ml-2 font-medium">
                          {formatAnalysisType(analysis.analysis_type)}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 border-b">
                      {getStatusIndicator(analysis.status)}
                    </td>
                    <td className="px-4 py-3 border-b text-sm">
                      {new Date(analysis.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 border-b text-sm">
                      {analysis.completed_at ? 
                        new Date(analysis.completed_at).toLocaleString() : 
                        '-'
                      }
                    </td>
                    <td className="px-4 py-3 border-b">
                      {analysis.status === 'completed' ? (
                        <button
                          onClick={() => navigate(`/analyses/${analysis.id}`)}
                          className="text-blue-500 hover:text-blue-700 flex items-center"
                        >
                          View Report
                          <ChevronRight size={16} className="ml-1" />
                        </button>
                      ) : (
                        <span className="text-gray-400">
                          {analysis.status === 'failed' ? 'Failed' : 'In Progress'}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500">
            <BarChart2 size={48} className="mx-auto mb-2 text-gray-300" />
            <p>No analyses found for this project</p>
            <p className="text-sm mt-2">
              Run your first analysis to get started
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default Analysis;