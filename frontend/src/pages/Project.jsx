import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  Package, Edit, Trash2, Upload, FileUp, Play, RefreshCw, AlertCircle, 
  CheckCircle, Clock, ChevronRight, Download, List, BarChart2, FileText
} from 'lucide-react';

import { 
  fetchProject, 
  updateProject, 
  deleteProject, 
  uploadProjectFiles, 
  fetchProjectDependencies, 
  fetchProjectAnalyses,
  fetchRecommendations,
  startAnalysis,
  generateRecommendations
} from '../services/api';

import DependencyList from '../components/DependencyList';

const Project = () => {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [dependencies, setDependencies] = useState([]);
  const [analyses, setAnalyses] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // UI state
  const [editMode, setEditMode] = useState(false);
  const [editForm, setEditForm] = useState({ name: '', description: '', repository_url: '' });
  const [uploading, setUploading] = useState(false);
  const [uploadFiles, setUploadFiles] = useState([]);
  const [runningAnalysis, setRunningAnalysis] = useState(false);
  const [selectedAnalysisType, setSelectedAnalysisType] = useState('impact_scoring');
  const [activeTab, setActiveTab] = useState('overview');
  const [generatingRecommendations, setGeneratingRecommendations] = useState(false);

  // Load project data
  useEffect(() => {
    const loadProjectData = async () => {
      try {
        setLoading(true);
        
        // Fetch project details
        const projectData = await fetchProject(projectId);
        setProject(projectData);
        setEditForm({
          name: projectData.name,
          description: projectData.description || '',
          repository_url: projectData.repository_url || '',
          ecosystem: projectData.ecosystem
        });
        
        // Fetch dependencies
        const dependenciesData = await fetchProjectDependencies(projectId);
        setDependencies(dependenciesData);
        
        // Fetch analyses
        const analysesData = await fetchProjectAnalyses(projectId);
        setAnalyses(analysesData);
        
        // Fetch recommendations
        const recommendationsData = await fetchRecommendations(projectId);
        setRecommendations(recommendationsData);
        
      } catch (error) {
        console.error('Error loading project data:', error);
        setError('Failed to load project data. Please try again.');
      } finally {
        setLoading(false);
      }
    };
    
    loadProjectData();
  }, [projectId]);
  
  const handleEditSubmit = async (e) => {
    e.preventDefault();
    try {
      const updatedProject = await updateProject(projectId, editForm);
      setProject(updatedProject);
      setEditMode(false);
    } catch (error) {
      console.error('Error updating project:', error);
      setError('Failed to update project. Please try again.');
    }
  };
  
  const handleDeleteProject = async () => {
    if (!window.confirm('Are you sure you want to delete this project? This action cannot be undone.')) {
      return;
    }
    
    try {
      await deleteProject(projectId);
      navigate('/'); // Redirect to homepage
    } catch (error) {
      console.error('Error deleting project:', error);
      setError('Failed to delete project. Please try again.');
    }
  };
  
  const handleFileChange = (e) => {
    setUploadFiles(Array.from(e.target.files));
  };
  
  const handleFileUpload = async (e) => {
    e.preventDefault();
    if (uploadFiles.length === 0) {
      return;
    }
    
    try {
      setUploading(true);
      await uploadProjectFiles(projectId, uploadFiles);
      
      // Refresh dependencies after upload
      const dependenciesData = await fetchProjectDependencies(projectId);
      setDependencies(dependenciesData);
      
      // Reset form
      setUploadFiles([]);
      document.getElementById('file-upload').value = '';
      
    } catch (error) {
      console.error('Error uploading files:', error);
      setError('Failed to upload files. Please try again.');
    } finally {
      setUploading(false);
    }
  };
  
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
      
      // Switch to analyses tab
      setActiveTab('analyses');
      
    } catch (error) {
      console.error('Error starting analysis:', error);
      setError('Failed to start analysis. Please try again.');
    } finally {
      setRunningAnalysis(false);
    }
  };
  
  const handleGenerateRecommendations = async () => {
    try {
      setGeneratingRecommendations(true);
      
      await generateRecommendations(projectId);
      
      // Refresh recommendations
      const recommendationsData = await fetchRecommendations(projectId);
      setRecommendations(recommendationsData);
      
      // Switch to recommendations tab
      setActiveTab('recommendations');
      
    } catch (error) {
      console.error('Error generating recommendations:', error);
      setError('Failed to generate recommendations. Please try again.');
    } finally {
      setGeneratingRecommendations(false);
    }
  };
  
  // Format analysis type for display
  const formatAnalysisType = (type) => {
    return type.split('_').map(word => 
      word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ');
  };
  
  // Get analysis status badge
  const getAnalysisStatusBadge = (status) => {
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
            <AlertCircle size={16} className="mr-1" />
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
  
  // Get status color for recommendation severity
  const getSeverityColor = (severity) => {
    switch (severity) {
      case 'high':
        return 'text-red-600 bg-red-100';
      case 'medium':
        return 'text-yellow-600 bg-yellow-100';
      case 'low':
        return 'text-green-600 bg-green-100';
      default:
        return 'text-gray-600 bg-gray-100';
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
            onClick={() => navigate('/')}
          >
            Return to Dashboard
          </button>
        </div>
      </div>
    );
  }
  
  if (!project) {
    return (
      <div className="p-6">
        <div className="bg-gray-50 text-gray-800 p-4 rounded mb-4">
          <h3 className="font-bold">Project Not Found</h3>
          <p>The requested project could not be found.</p>
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
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between mb-6">
        <div className="flex items-center mb-4 md:mb-0">
          <Package size={24} className="text-blue-500 mr-2" />
          {editMode ? (
            <div className="flex-1">
              <form onSubmit={handleEditSubmit} className="flex items-center">
                <input
                  type="text"
                  value={editForm.name}
                  onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                  className="border rounded px-2 py-1 mr-2"
                  required
                />
                <button 
                  type="submit"
                  className="bg-blue-500 text-white px-3 py-1 rounded hover:bg-blue-600"
                >
                  Save
                </button>
                <button 
                  type="button"
                  onClick={() => setEditMode(false)}
                  className="ml-2 text-gray-500 hover:text-gray-700"
                >
                  Cancel
                </button>
              </form>
            </div>
          ) : (
            <>
              <h1 className="text-2xl font-bold">{project.name}</h1>
              <span className="ml-2 px-2 py-1 bg-gray-100 rounded text-xs">
                {project.ecosystem}
              </span>
              <button 
                onClick={() => setEditMode(true)}
                className="ml-2 text-gray-400 hover:text-gray-600"
                title="Edit Project"
              >
                <Edit size={16} />
              </button>
            </>
          )}
        </div>
        
        <div className="flex space-x-2">
          <button
            onClick={handleDeleteProject}
            className="flex items-center px-3 py-1 bg-red-100 hover:bg-red-200 text-red-700 rounded text-sm"
          >
            <Trash2 size={16} className="mr-1" />
            Delete
          </button>
        </div>
      </div>
      
      {/* Project details */}
      {!editMode && (
        <div className="bg-white rounded shadow p-4 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <h3 className="font-medium mb-2">Project Details</h3>
              <p className="text-gray-600 text-sm mb-2">
                {project.description || 'No description provided'}
              </p>
              {project.repository_url && (
                <div className="flex items-center text-sm">
                  <span className="text-gray-500 mr-2">Repository:</span>
                  <a 
                    href={project.repository_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-500 hover:text-blue-700 flex items-center"
                  >
                    {project.repository_url}
                    <ChevronRight size={14} className="ml-1" />
                  </a>
                </div>
              )}
            </div>
            
            <div>
              <h3 className="font-medium mb-2">Stats</h3>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-gray-500 text-sm">Dependencies</div>
                  <div className="text-xl font-bold">{dependencies.length}</div>
                </div>
                <div>
                  <div className="text-gray-500 text-sm">Analyses</div>
                  <div className="text-xl font-bold">{analyses.length}</div>
                </div>
                <div>
                  <div className="text-gray-500 text-sm">Recommendations</div>
                  <div className="text-xl font-bold">{recommendations.length}</div>
                </div>
                <div>
                  <div className="text-gray-500 text-sm">Last Updated</div>
                  <div className="text-sm">
                    {new Date(project.updated_at).toLocaleDateString()}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
      
      {/* Upload form */}
      <div className="bg-white rounded shadow p-4 mb-6">
        <h3 className="font-medium mb-2">Upload Project Files</h3>
        <p className="text-sm text-gray-600 mb-4">
          Upload dependency files (package.json, requirements.txt, etc.) to analyze your project dependencies.
        </p>
        
        <form onSubmit={handleFileUpload} className="flex flex-col md:flex-row items-start md:items-end">
          <div className="flex-1 mb-2 md:mb-0 md:mr-4">
            <label className="block text-sm text-gray-600 mb-1">Select Files</label>
            <input
              id="file-upload"
              type="file"
              onChange={handleFileChange}
              multiple
              className="border p-2 w-full rounded"
              disabled={uploading}
            />
          </div>
          <button
            type="submit"
            className="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600 flex items-center"
            disabled={uploadFiles.length === 0 || uploading}
          >
            {uploading ? (
              <>
                <RefreshCw size={16} className="mr-2 animate-spin" />
                Uploading...
              </>
            ) : (
              <>
                <Upload size={16} className="mr-2" />
                Upload Files
              </>
            )}
          </button>
        </form>
        
        {uploadFiles.length > 0 && (
          <div className="mt-4">
            <div className="text-sm text-gray-600 mb-1">Selected Files:</div>
            <ul className="text-sm">
              {uploadFiles.map((file, index) => (
                <li key={index} className="flex items-center mb-1">
                  <FileUp size={14} className="mr-1 text-gray-400" />
                  {file.name} 
                  <span className="text-gray-400 ml-1">
                    ({(file.size / 1024).toFixed(1)} KB)
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
      
      {/* Run Analysis */}
      <div className="bg-white rounded shadow p-4 mb-6">
        <h3 className="font-medium mb-2">Run Analysis</h3>
        <p className="text-sm text-gray-600 mb-4">
          Start a new analysis to get insights about your dependencies.
        </p>
        
        <div className="flex flex-col md:flex-row items-start md:items-end">
          <div className="flex-1 mb-2 md:mb-0 md:mr-4">
            <label className="block text-sm text-gray-600 mb-1">Analysis Type</label>
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
          <button
            onClick={handleStartAnalysis}
            className="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600 flex items-center"
            disabled={runningAnalysis || dependencies.length === 0}
          >
            {runningAnalysis ? (
              <>
                <RefreshCw size={16} className="mr-2 animate-spin" />
                Running...
              </>
            ) : (
              <>
                <Play size={16} className="mr-2" />
                Start Analysis
              </>
            )}
          </button>
        </div>
        
        {dependencies.length === 0 && (
          <div className="mt-4 p-2 bg-yellow-50 text-yellow-700 rounded text-sm">
            <AlertCircle size={16} className="inline-block mr-1" />
            Please upload dependency files first to enable analysis.
          </div>
        )}
      </div>
      
      {/* Tabs */}
      <div className="border-b mb-6">
        <nav className="flex">
          <button
            className={`px-4 py-2 ${
              activeTab === 'overview'
                ? 'border-b-2 border-blue-500 text-blue-500'
                : 'text-gray-600 hover:text-blue-500'
            }`}
            onClick={() => setActiveTab('overview')}
          >
            Overview
          </button>
          <button
            className={`px-4 py-2 ${
              activeTab === 'dependencies'
                ? 'border-b-2 border-blue-500 text-blue-500'
                : 'text-gray-600 hover:text-blue-500'
            }`}
            onClick={() => setActiveTab('dependencies')}
          >
            Dependencies
          </button>
          <button
            className={`px-4 py-2 ${
              activeTab === 'analyses'
                ? 'border-b-2 border-blue-500 text-blue-500'
                : 'text-gray-600 hover:text-blue-500'
            }`}
            onClick={() => setActiveTab('analyses')}
          >
            Analyses
          </button>
          <button
            className={`px-4 py-2 ${
              activeTab === 'recommendations'
                ? 'border-b-2 border-blue-500 text-blue-500'
                : 'text-gray-600 hover:text-blue-500'
            }`}
            onClick={() => setActiveTab('recommendations')}
          >
            Recommendations
          </button>
        </nav>
      </div>
      
      {/* Tab Content */}
      <div className="bg-white rounded shadow p-4">
        {activeTab === 'overview' && (
          <div>
            <h3 className="text-lg font-semibold mb-4">Project Overview</h3>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
              <div className="bg-blue-50 p-4 rounded">
                <h4 className="font-medium text-blue-800 mb-2">Dependency Health</h4>
                <div className="text-3xl font-bold mb-2">
                  {dependencies.length}
                </div>
                <div className="text-sm text-blue-700">
                  Total dependencies
                </div>
                
                <div className="mt-4">
                  <button
                    onClick={() => setActiveTab('dependencies')}
                    className="text-blue-600 hover:text-blue-800 text-sm flex items-center"
                  >
                    View Dependencies
                    <ChevronRight size={16} />
                  </button>
                </div>
              </div>
              
              <div className="bg-green-50 p-4 rounded">
                <h4 className="font-medium text-green-800 mb-2">Recent Analyses</h4>
                <div className="text-3xl font-bold mb-2">
                  {analyses.length}
                </div>
                <div className="text-sm text-green-700">
                  Total analyses
                </div>
                
                <div className="mt-4">
                  <button
                    onClick={() => setActiveTab('analyses')}
                    className="text-green-600 hover:text-green-800 text-sm flex items-center"
                  >
                    View Analyses
                    <ChevronRight size={16} />
                  </button>
                </div>
              </div>
              
              <div className="bg-yellow-50 p-4 rounded">
                <h4 className="font-medium text-yellow-800 mb-2">Recommendations</h4>
                <div className="text-3xl font-bold mb-2">
                  {recommendations.length}
                </div>
                <div className="text-sm text-yellow-700">
                  Total recommendations
                </div>
                
                <div className="mt-4">
                  <button
                    onClick={handleGenerateRecommendations}
                    className="text-yellow-600 hover:text-yellow-800 text-sm flex items-center"
                    disabled={generatingRecommendations}
                  >
                    {generatingRecommendations ? (
                      <>
                        <RefreshCw size={14} className="mr-1 animate-spin" />
                        Generating...
                      </>
                    ) : (
                      <>
                        Generate Recommendations
                        <ChevronRight size={16} />
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
            
            {/* Recent Activities */}
            <h4 className="font-medium mb-2">Recent Activity</h4>
            <div className="border rounded overflow-hidden">
              <div className="bg-gray-50 px-4 py-2 font-medium text-sm">
                Recent Analyses
              </div>
              <div className="divide-y">
                {analyses.length > 0 ? (
                  analyses.slice(0, 5).map((analysis) => (
                    <div key={analysis.id} className="px-4 py-3 hover:bg-gray-50">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center">
                          <span className="font-medium">
                            {formatAnalysisType(analysis.analysis_type)}
                          </span>
                          <span className="mx-2 text-gray-400">•</span>
                          {getAnalysisStatusBadge(analysis.status)}
                        </div>
                        <div className="text-sm text-gray-500">
                          {new Date(analysis.created_at).toLocaleString()}
                        </div>
                      </div>
                      {analysis.status === 'completed' && (
                        <div className="mt-2">
                          <button
                            onClick={() => navigate(`/analyses/${analysis.id}`)}
                            className="text-blue-500 hover:text-blue-700 text-sm flex items-center"
                          >
                            View Report
                            <ChevronRight size={14} className="ml-1" />
                          </button>
                        </div>
                      )}
                    </div>
                  ))
                ) : (
                  <div className="px-4 py-3 text-gray-500 italic">
                    No analyses have been run yet.
                  </div>
                )}
              </div>
              {analyses.length > 5 && (
                <div className="bg-gray-50 px-4 py-2 text-right">
                  <button
                    onClick={() => setActiveTab('analyses')}
                    className="text-blue-500 hover:text-blue-700 text-sm"
                  >
                    View All
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
        
        {activeTab === 'dependencies' && (
          <div>
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold">Dependencies</h3>
              {dependencies.length > 0 && (
                <button
                  onClick={() => {
                    // Implementation would depend on how export is handled
                    console.log('Export dependencies');
                  }}
                  className="text-blue-500 hover:text-blue-700 flex items-center text-sm"
                >
                  <Download size={16} className="mr-1" />
                  Export
                </button>
              )}
            </div>
            
            {dependencies.length > 0 ? (
              <DependencyList dependencies={dependencies} />
            ) : (
              <div className="text-center py-8 text-gray-500">
                <Package size={48} className="mx-auto mb-2 text-gray-300" />
                <p>No dependencies found.</p>
                <p className="text-sm mt-2">
                  Upload project files to analyze dependencies.
                </p>
              </div>
            )}
          </div>
        )}
        
        {activeTab === 'analyses' && (
          <div>
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold">Analyses</h3>
              <button
                onClick={handleStartAnalysis}
                className="bg-green-500 text-white px-3 py-1 rounded hover:bg-green-600 flex items-center text-sm"
                disabled={runningAnalysis || dependencies.length === 0}
              >
                <Play size={14} className="mr-1" />
                New Analysis
              </button>
            </div>
            
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
                        <td className="px-4 py-3 border-b font-medium">
                          {formatAnalysisType(analysis.analysis_type)}
                        </td>
                        <td className="px-4 py-3 border-b">
                          {getAnalysisStatusBadge(analysis.status)}
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
                              <FileText size={16} className="mr-1" />
                              View Report
                            </button>
                          ) : analysis.status === 'failed' ? (
                            <span className="text-red-500 text-sm">
                              {analysis.error_message || 'Analysis failed'}
                            </span>
                          ) : (
                            <span className="text-gray-400 text-sm">
                              {analysis.status === 'running' ? 'Running...' : 'Pending'}
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
                <p>No analyses found.</p>
                <p className="text-sm mt-2">
                  Run an analysis to gain insights about your dependencies.
                </p>
              </div>
            )}
          </div>
        )}
        
        {activeTab === 'recommendations' && (
          <div>
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold">Recommendations</h3>
              <button
                onClick={handleGenerateRecommendations}
                className="bg-yellow-500 text-white px-3 py-1 rounded hover:bg-yellow-600 flex items-center text-sm"
                disabled={generatingRecommendations || analyses.length === 0}
              >
                {generatingRecommendations ? (
                  <>
                    <RefreshCw size={14} className="mr-1 animate-spin" />
                    Generating...
                  </>
                ) : (
                  <>
                    <RefreshCw size={14} className="mr-1" />
                    Generate
                  </>
                )}
              </button>
            </div>
            
            {recommendations.length > 0 ? (
              <div className="space-y-4">
                {recommendations.map((rec) => (
                  <div 
                    key={rec.id} 
                    className={`border rounded p-4 ${
                      rec.severity === 'high' ? 'border-red-200' :
                      rec.severity === 'medium' ? 'border-yellow-200' :
                      'border-green-200'
                    }`}
                  >
                    <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2">
                      <div>
                        <div className="flex items-center">
                          <h4 className="font-medium">{rec.title}</h4>
                          <span className={`ml-2 px-2 py-0.5 rounded-full text-xs ${getSeverityColor(rec.severity)}`}>
                            {rec.severity}
                          </span>
                        </div>
                        <p className="text-gray-600 text-sm mt-1">
                          {rec.description}
                        </p>
                      </div>
                      <div className="flex items-center text-sm">
                        <div className="mr-4">
                          <span className="text-gray-500">Type:</span>
                          <span className="ml-1">{formatAnalysisType(rec.recommendation_type)}</span>
                        </div>
                        {rec.dependency_name && (
                          <div>
                            <span className="text-gray-500">Dependency:</span>
                            <span className="ml-1">{rec.dependency_name}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <List size={48} className="mx-auto mb-2 text-gray-300" />
                <p>No recommendations found.</p>
                <p className="text-sm mt-2">
                  Generate recommendations based on your analyses.
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default Project;