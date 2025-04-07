import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  AlertCircle, CheckCircle, Clock, FileText, RefreshCw, ChevronRight,
  BarChart2, GitBranch, Shield, Package, Archive, BookOpen, Zap
} from 'lucide-react';
import { 
  LineChart, Line, BarChart, Bar, Cell, XAxis, YAxis, CartesianGrid, 
  Tooltip, Legend, ResponsiveContainer, PieChart, Pie 
} from 'recharts';

import { fetchAnalysis, fetchAnalysisDetails } from '../services/api';

const AnalysisReport = () => {
  const { analysisId } = useParams();
  const navigate = useNavigate();
  const [analysis, setAnalysis] = useState(null);
  const [details, setDetails] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const loadAnalysisData = async () => {
      try {
        setLoading(true);
        
        // Fetch basic analysis info
        const analysisData = await fetchAnalysis(analysisId);
        setAnalysis(analysisData);
        
        // Only fetch details if analysis is completed
        if (analysisData.status === 'completed') {
          const detailsData = await fetchAnalysisDetails(analysisId);
          setDetails(detailsData);
        }
      } catch (error) {
        console.error('Error loading analysis data:', error);
        setError('Failed to load analysis data. Please try again.');
      } finally {
        setLoading(false);
      }
    };
    
    loadAnalysisData();
  }, [analysisId]);
  
  // Get analysis type icon
  const getAnalysisIcon = () => {
    if (!analysis) return <Clock size={20} />;
    
    switch (analysis.analysis_type) {
      case 'impact_scoring':
        return <Package size={20} className="text-blue-500" />;
      case 'compatibility_prediction':
        return <GitBranch size={20} className="text-purple-500" />;
      case 'dependency_consolidation':
        return <Archive size={20} className="text-indigo-500" />;
      case 'health_monitoring':
        return <Shield size={20} className="text-green-500" />;
      case 'license_compliance':
        return <BookOpen size={20} className="text-orange-500" />;
      case 'performance_profiling':
        return <Zap size={20} className="text-yellow-500" />;
      default:
        return <FileText size={20} className="text-gray-500" />;
    }
  };
  
  // Format analysis type for display
  const formatAnalysisType = (type) => {
    return type.split('_').map(word => 
      word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ');
  };
  
  // Get status indicator
  const getStatusIndicator = () => {
    if (!analysis) return null;
    
    switch (analysis.status) {
      case 'completed':
        return (
          <span className="px-2 py-1 bg-green-100 text-green-800 rounded-full text-xs flex items-center">
            <CheckCircle size={12} className="mr-1" />
            Completed
          </span>
        );
      case 'running':
        return (
          <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded-full text-xs flex items-center">
            <RefreshCw size={12} className="mr-1 animate-spin" />
            Running
          </span>
        );
      case 'failed':
        return (
          <span className="px-2 py-1 bg-red-100 text-red-800 rounded-full text-xs flex items-center">
            <AlertCircle size={12} className="mr-1" />
            Failed
          </span>
        );
      default:
        return (
          <span className="px-2 py-1 bg-gray-100 text-gray-800 rounded-full text-xs flex items-center">
            <Clock size={12} className="mr-1" />
            {analysis.status}
          </span>
        );
    }
  };
  
  const renderAnalysisReport = () => {
    if (!analysis || !details) return null;
    
    switch (analysis.analysis_type) {
      case 'impact_scoring':
        return renderImpactScoringReport();
      case 'compatibility_prediction':
        return renderCompatibilityReport();
      case 'dependency_consolidation':
        return renderConsolidationReport();
      case 'health_monitoring':
        return renderHealthReport();
      case 'license_compliance':
        return renderLicenseReport();
      case 'performance_profiling':
        return renderPerformanceReport();
      default:
        return (
          <div className="bg-gray-50 p-4 rounded">
            <div className="text-gray-500 italic">
              No detailed report available for this analysis type.
            </div>
          </div>
        );
    }
  };
  
  const renderImpactScoringReport = () => {
    const scores = details.detailed_scores || [];
    
    // Prepare chart data
    const chartData = scores.map(score => ({
      name: score.dependency_name,
      'Business Value': score.business_value_score,
      'Usage': score.usage_score,
      'Complexity': score.complexity_score,
      'Health': score.health_score,
      'Overall': score.overall_score
    }));
    
    // Sort by overall score descending
    chartData.sort((a, b) => b.Overall - a.Overall);
    
    // Prepare pie chart data
    const highImpactCount = details.result_summary?.high_impact_count || 0;
    const mediumImpactCount = scores.filter(s => s.overall_score >= 0.5 && s.overall_score < 0.8).length;
    const lowImpactCount = scores.filter(s => s.overall_score < 0.5).length;
    
    const impactDistributionData = [
      { name: 'High Impact', value: highImpactCount, color: '#EF4444' },
      { name: 'Medium Impact', value: mediumImpactCount, color: '#F59E0B' },
      { name: 'Low Impact', value: lowImpactCount, color: '#10B981' }
    ];
    
    return (
      <div>
        <div className="bg-white p-4 rounded shadow mb-6">
          <h3 className="text-lg font-semibold mb-4">Impact Score Summary</h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
            <div className="bg-gray-50 p-4 rounded">
              <div className="text-sm text-gray-500 mb-1">Dependencies Analyzed</div>
              <div className="text-2xl font-bold">{scores.length}</div>
            </div>
            <div className="bg-red-50 p-4 rounded">
              <div className="text-sm text-red-700 mb-1">High Impact</div>
              <div className="text-2xl font-bold">{highImpactCount}</div>
            </div>
            <div className="bg-green-50 p-4 rounded">
              <div className="text-sm text-green-700 mb-1">Average Score</div>
              <div className="text-2xl font-bold">
                {details.result_summary?.average_score ? 
                  (details.result_summary.average_score * 100).toFixed(0) + '%' : 
                  'N/A'}
              </div>
            </div>
            <div className="bg-blue-50 p-4 rounded">
              <div className="text-sm text-blue-700 mb-1">Low Usage Count</div>
              <div className="text-2xl font-bold">{details.result_summary?.low_usage_count || 0}</div>
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h4 className="text-md font-medium mb-2">Impact Distribution</h4>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={impactDistributionData}
                      cx="50%"
                      cy="50%"
                      outerRadius={80}
                      dataKey="value"
                      label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                    >
                      {impactDistributionData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(value) => [`${value} dependencies`, 'Count']} />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
            
            <div>
              <h4 className="text-md font-medium mb-2">Score Components</h4>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData.slice(0, 10)}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                    <YAxis domain={[0, 1]} tickFormatter={(tick) => `${(tick * 100).toFixed(0)}%`} />
                    <Tooltip formatter={(value) => `${(value * 100).toFixed(0)}%`} />
                    <Legend />
                    <Bar dataKey="Overall" fill="#6366F1" />
                    <Bar dataKey="Business Value" fill="#3B82F6" />
                    <Bar dataKey="Usage" fill="#10B981" />
                    <Bar dataKey="Health" fill="#F59E0B" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </div>
        
        <div className="bg-white p-4 rounded shadow">
          <h3 className="text-lg font-semibold mb-4">Dependency Impact Scores</h3>
          <div className="overflow-x-auto">
            <table className="min-w-full border-collapse">
              <thead>
                <tr>
                  <th className="px-4 py-2 border-b-2 text-left">Dependency</th>
                  <th className="px-4 py-2 border-b-2 text-left">Overall</th>
                  <th className="px-4 py-2 border-b-2 text-left">Business Value</th>
                  <th className="px-4 py-2 border-b-2 text-left">Usage</th>
                  <th className="px-4 py-2 border-b-2 text-left">Complexity</th>
                  <th className="px-4 py-2 border-b-2 text-left">Health</th>
                  <th className="px-4 py-2 border-b-2 text-left">Used Features</th>
                </tr>
              </thead>
              <tbody>
                {scores.sort((a, b) => b.overall_score - a.overall_score).map((score, index) => (
                  <tr key={index} className="hover:bg-gray-50">
                    <td className="px-4 py-2 border-b font-medium">{score.dependency_name}</td>
                    <td className="px-4 py-2 border-b">
                      <div className="flex items-center">
                        <div className={`w-2 h-2 rounded-full mr-2 ${
                          score.overall_score >= 0.8 ? 'bg-red-500' :
                          score.overall_score >= 0.5 ? 'bg-yellow-500' :
                          'bg-green-500'
                        }`}></div>
                        {(score.overall_score * 100).toFixed(0)}%
                      </div>
                    </td>
                    <td className="px-4 py-2 border-b">{(score.business_value_score * 100).toFixed(0)}%</td>
                    <td className="px-4 py-2 border-b">{(score.usage_score * 100).toFixed(0)}%</td>
                    <td className="px-4 py-2 border-b">{(score.complexity_score * 100).toFixed(0)}%</td>
                    <td className="px-4 py-2 border-b">{(score.health_score * 100).toFixed(0)}%</td>
                    <td className="px-4 py-2 border-b">
                      {score.used_features && score.used_features.length > 0 ? 
                        score.used_features.length : 'Unknown'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    );
  };
  
  const renderCompatibilityReport = () => {
    const summary = details.result_summary || {};
    const timeline = details.timeline || {};
    
    // Prepare data for chart
    const issueCountData = [
      { name: 'Critical', value: summary.issue_counts?.critical || 0, color: '#EF4444' },
      { name: 'High', value: summary.issue_counts?.high || 0, color: '#F59E0B' },
      { name: 'Medium', value: summary.issue_counts?.medium || 0, color: '#10B981' },
      { name: 'Low', value: summary.issue_counts?.low || 0, color: '#3B82F6' }
    ];
    
    return (
      <div>
        <div className="bg-white p-4 rounded shadow mb-6">
          <h3 className="text-lg font-semibold mb-4">Compatibility Prediction Summary</h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
            <div className="bg-gray-50 p-4 rounded">
              <div className="text-sm text-gray-500 mb-1">Total Dependencies</div>
              <div className="text-2xl font-bold">{summary.total_dependencies || 0}</div>
            </div>
            <div className="bg-red-50 p-4 rounded">
              <div className="text-sm text-red-700 mb-1">Affected Dependencies</div>
              <div className="text-2xl font-bold">{summary.affected_dependencies || 0}</div>
            </div>
            <div className="bg-purple-50 p-4 rounded">
              <div className="text-sm text-purple-700 mb-1">Timeline Events</div>
              <div className="text-2xl font-bold">{details.timeline_count || 0}</div>
            </div>
            <div className="bg-blue-50 p-4 rounded">
              <div className="text-sm text-blue-700 mb-1">Time Horizon</div>
              <div className="text-2xl font-bold">{summary.time_horizon_days || 180} days</div>
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h4 className="text-md font-medium mb-2">Issue Severity Distribution</h4>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={issueCountData}
                      cx="50%"
                      cy="50%"
                      outerRadius={80}
                      dataKey="value"
                      label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                    >
                      {issueCountData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(value) => [`${value} issues`, 'Count']} />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
            
            <div>
              <h4 className="text-md font-medium mb-2">Affected Dependencies</h4>
              {summary.dependency_issues ? (
                <div className="overflow-y-auto h-64">
                  {Object.entries(summary.dependency_issues).map(([name, issues], index) => (
                    <div key={index} className="mb-2 p-2 border rounded hover:bg-gray-50">
                      <div className="font-medium flex items-center justify-between">
                        <span>{name}</span>
                        <span className={`px-2 py-0.5 rounded text-xs ${
                          issues.severity === 'high' ? 'bg-red-100 text-red-800' :
                          issues.severity === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                          'bg-blue-100 text-blue-800'
                        }`}>
                          {issues.severity}
                        </span>
                      </div>
                      <div className="text-sm text-gray-600">
                        {issues.issues && issues.issues.length > 0 && (
                          <div className="mt-1">
                            {issues.issues.slice(0, 2).map((issue, i) => (
                              <div key={i} className="flex items-center mt-1">
                                <ChevronRight size={14} className="text-gray-400 mr-1" />
                                <span>{issue.type.replace(/_/g, ' ')}: {issue.description || issue.version || ''}</span>
                              </div>
                            ))}
                            {issues.issues.length > 2 && (
                              <div className="text-xs text-blue-500 mt-1">
                                + {issues.issues.length - 2} more issues
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-gray-500 italic p-4">
                  No affected dependencies found.
                </div>
              )}
            </div>
          </div>
        </div>
        
        <div className="bg-white p-4 rounded shadow">
          <h3 className="text-lg font-semibold mb-4">Breaking Changes Timeline</h3>
          <div className="text-sm text-gray-500 mb-4">
            Showing predicted breaking changes, updates, and deprecations over the next {summary.time_horizon_days || 180} days.
          </div>
          
          {timeline && Object.keys(timeline).length > 0 ? (
            <div className="space-y-4">
              {Object.entries(timeline)
                .sort((a, b) => new Date(a[0]) - new Date(b[0])) // Sort by date
                .map(([date, events], index) => (
                  <div key={index} className="border-l-4 border-blue-500 pl-4 pb-4 relative">
                    <div className="absolute w-3 h-3 bg-blue-500 rounded-full -left-1.5"></div>
                    <div className="font-medium mb-2">
                      {new Date(date).toLocaleDateString()}
                      <span className="ml-2 text-xs text-gray-500">
                        ({events.length} event{events.length !== 1 ? 's' : ''})
                      </span>
                    </div>
                    <div className="space-y-2">
                      {events.map((event, i) => (
                        <div key={i} className={`p-2 rounded ${
                          event.event_type === 'breaking_change' ? 'bg-red-50' :
                          event.event_type === 'deprecation' ? 'bg-yellow-50' :
                          event.event_type === 'predicted_release' && event.is_major ? 'bg-purple-50' :
                          'bg-blue-50'
                        }`}>
                          <div className="flex items-center justify-between">
                            <span className="font-medium">{event.dependency}</span>
                            <span className="text-xs px-2 py-0.5 bg-white rounded-full">
                              {event.event_type.replace(/_/g, ' ')}
                              {event.version ? ` ${event.version}` : ''}
                            </span>
                          </div>
                          <div className="text-sm mt-1">
                            {event.details}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
            </div>
          ) : (
            <div className="text-gray-500 italic p-4">
              No timeline events found.
            </div>
          )}
        </div>
      </div>
    );
  };
  
  const renderConsolidationReport = () => {
    const metrics = details.metrics || {};
    const recommendations = details.recommendations || {};
    
    // Create chart data
    const reductionData = [
      { name: 'Duplicate Removals', value: metrics.duplicate_removals || 0 },
      { name: 'Chain Reduction', value: metrics.chain_reduction || 0 },
      { name: 'Remaining', value: metrics.total_dependencies - (metrics.potential_removals || 0) }
    ];
    
    const ecosystemData = Object.entries(metrics.ecosystem_counts || {}).map(([name, count]) => ({
      name,
      count
    }));
    
    return (
      <div>
        <div className="bg-white p-4 rounded shadow mb-6">
          <h3 className="text-lg font-semibold mb-4">Dependency Consolidation Summary</h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
            <div className="bg-gray-50 p-4 rounded">
              <div className="text-sm text-gray-500 mb-1">Total Dependencies</div>
              <div className="text-2xl font-bold">{metrics.total_dependencies || 0}</div>
            </div>
            <div className="bg-green-50 p-4 rounded">
              <div className="text-sm text-green-700 mb-1">Potential Removals</div>
              <div className="text-2xl font-bold">{metrics.potential_removals || 0}</div>
            </div>
            <div className="bg-blue-50 p-4 rounded">
              <div className="text-sm text-blue-700 mb-1">Reduction Percent</div>
              <div className="text-2xl font-bold">{metrics.reduction_percent || 0}%</div>
            </div>
            <div className="bg-purple-50 p-4 rounded">
              <div className="text-sm text-purple-700 mb-1">Ecosystems</div>
              <div className="text-2xl font-bold">{metrics.ecosystems?.length || 0}</div>
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h4 className="text-md font-medium mb-2">Potential Reduction</h4>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={reductionData}
                      cx="50%"
                      cy="50%"
                      outerRadius={80}
                      dataKey="value"
                      label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                    >
                      <Cell fill="#10B981" /> {/* duplicate removals */}
                      <Cell fill="#3B82F6" /> {/* chain reduction */}
                      <Cell fill="#6B7280" /> {/* remaining */}
                    </Pie>
                    <Tooltip formatter={(value) => [`${value} dependencies`, 'Count']} />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
            
            <div>
              <h4 className="text-md font-medium mb-2">Dependencies by Ecosystem</h4>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={ecosystemData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip formatter={(value) => [`${value} dependencies`, 'Count']} />
                    <Legend />
                    <Bar dataKey="count" fill="#8B5CF6" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Duplicate Functionality */}
          <div className="bg-white p-4 rounded shadow">
            <h3 className="text-lg font-semibold mb-4">Duplicate Functionality</h3>
            {recommendations.duplicates && recommendations.duplicates.length > 0 ? (
              <div className="space-y-4">
                {recommendations.duplicates.map((rec, index) => (
                  <div key={index} className="border border-green-200 bg-green-50 rounded p-3">
                    <div className="font-medium mb-2">{rec.description}</div>
                    <div className="text-sm mb-2">{rec.recommendation}</div>
                    <div className="bg-white rounded p-2 mb-2">
                      <div className="text-xs font-medium text-gray-500 mb-1">Keep:</div>
                      <div className="font-medium">{rec.keep.name}</div>
                      <div className="text-xs text-gray-600 mt-1">
                        Used features: {rec.keep.used_features.length}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs font-medium text-gray-500 mb-1">Remove:</div>
                      <div className="space-y-1">
                        {rec.remove.map((dep, i) => (
                          <div key={i} className="text-sm">
                            {dep.name}
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-gray-500 italic p-4">
                No duplicate functionality detected.
              </div>
            )}
          </div>
          
          {/* Version Inconsistencies */}
          <div className="bg-white p-4 rounded shadow">
            <h3 className="text-lg font-semibold mb-4">Version Inconsistencies</h3>
            {recommendations.versions && recommendations.versions.length > 0 ? (
              <div className="space-y-4">
                {recommendations.versions.map((rec, index) => (
                  <div key={index} className="border border-blue-200 bg-blue-50 rounded p-3">
                    <div className="font-medium mb-2">{rec.description}</div>
                    <div className="text-sm mb-2">{rec.recommendation}</div>
                    <div className="bg-white rounded p-2">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-medium text-gray-500">Dependency:</span>
                        <span className="text-xs font-medium text-gray-500">Recommended Version:</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="font-medium">{rec.dependency.name}</span>
                        <span className="font-medium text-green-600">{rec.dependency.recommended_version}</span>
                      </div>
                      <div className="mt-2 text-xs text-gray-600">
                        Current versions in use:
                      </div>
                      <div className="mt-1 space-y-1">
                        {rec.dependency.versions.map((version, i) => (
                          <div key={i} className="text-xs flex items-center">
                            <span className="px-1.5 py-0.5 bg-gray-100 rounded mr-1">{version}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-gray-500 italic p-4">
                No version inconsistencies detected.
              </div>
            )}
          </div>
        </div>
        
        {/* Transitive Dependencies */}
        <div className="bg-white p-4 rounded shadow mt-6">
          <h3 className="text-lg font-semibold mb-4">Transitive Dependency Recommendations</h3>
          {recommendations.transitive && recommendations.transitive.length > 0 ? (
            <div className="space-y-4">
              {recommendations.transitive.map((rec, index) => (
                <div key={index} className="border border-purple-200 bg-purple-50 rounded p-3">
                  <div className="font-medium mb-2">{rec.description}</div>
                  <div className="text-sm mb-2">{rec.recommendation}</div>
                  {rec.path && (
                    <div className="bg-white rounded p-2">
                      <div className="text-xs font-medium text-gray-500 mb-1">Dependency Chain:</div>
                      <div className="flex items-center flex-wrap">
                        {rec.path.map((dep, i, arr) => (
                          <React.Fragment key={i}>
                            <span className="font-medium">{dep}</span>
                            {i < arr.length - 1 && (
                              <ChevronRight size={16} className="text-gray-400 mx-1" />
                            )}
                          </React.Fragment>
                        ))}
                      </div>
                    </div>
                  )}
                  {rec.dependency && (
                    <div className="bg-white rounded p-2 mt-2">
                      <div className="text-xs font-medium text-gray-500 mb-1">Details:</div>
                      <div className="font-medium">{rec.dependency.name}</div>
                      <div className="text-xs text-gray-600 mt-1">
                        Referenced by {rec.dependency.parent_count || rec.dependency.direct_parents?.length || 0} dependencies
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="text-gray-500 italic p-4">
              No transitive dependency recommendations available.
            </div>
          )}
        </div>
      </div>
    );
  };
  
  const renderHealthReport = () => {
    if (!details || !details.result_summary) {
      return (
        <div className="bg-white p-4 rounded shadow">
          <div className="text-gray-500 italic">
            No health report data available.
          </div>
        </div>
      );
    }
    
    const summary = details.result_summary;
    const recommendations = details.recommendations || [];
    
    // Create chart data
    const healthDistributionData = [
      { name: 'Healthy', value: summary.health_distribution?.healthy || 0, color: '#10B981' },
      { name: 'Moderate', value: summary.health_distribution?.moderate || 0, color: '#F59E0B' },
      { name: 'At Risk', value: summary.health_distribution?.at_risk || 0, color: '#EF4444' }
    ];
    
    const riskFactorsData = (summary.risk_factors || []).map(risk => ({
      name: risk.name.replace(/_/g, ' '),
      count: risk.count
    }));
    
    return (
      <div>
        <div className="bg-white p-4 rounded shadow mb-6">
          <h3 className="text-lg font-semibold mb-4">Dependency Health Summary</h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
            <div className="bg-gray-50 p-4 rounded">
              <div className="text-sm text-gray-500 mb-1">Dependencies Analyzed</div>
              <div className="text-2xl font-bold">{summary.dependency_count || 0}</div>
            </div>
            <div className="bg-green-50 p-4 rounded">
              <div className="text-sm text-green-700 mb-1">Average Health Score</div>
              <div className="text-2xl font-bold">{(summary.average_health_score * 100).toFixed(0)}%</div>
            </div>
            <div className="bg-red-50 p-4 rounded">
              <div className="text-sm text-red-700 mb-1">Deprecated</div>
              <div className="text-2xl font-bold">{summary.deprecated_dependencies || 0}</div>
            </div>
            <div className="bg-yellow-50 p-4 rounded">
              <div className="text-sm text-yellow-700 mb-1">Outdated</div>
              <div className="text-2xl font-bold">{summary.outdated_dependencies || 0}</div>
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h4 className="text-md font-medium mb-2">Health Distribution</h4>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={healthDistributionData}
                      cx="50%"
                      cy="50%"
                      outerRadius={80}
                      dataKey="value"
                      label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                    >
                      {healthDistributionData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(value) => [`${value} dependencies`, 'Count']} />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
            
            <div>
              <h4 className="text-md font-medium mb-2">Common Risk Factors</h4>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={riskFactorsData} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" />
                    <YAxis dataKey="name" type="category" width={140} tick={{ fontSize: 12 }} />
                    <Tooltip />
                    <Bar dataKey="count" fill="#EF4444" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </div>
        
        <div className="bg-white p-4 rounded shadow">
          <h3 className="text-lg font-semibold mb-4">Health Recommendations</h3>
          {recommendations && recommendations.length > 0 ? (
            <div className="space-y-4">
              {recommendations.map((rec, index) => (
                <div key={index} className={`border rounded p-3 ${
                  rec.urgency === 'high' ? 'border-red-200 bg-red-50' :
                  rec.urgency === 'medium' ? 'border-yellow-200 bg-yellow-50' :
                  'border-blue-200 bg-blue-50'
                }`}>
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="font-medium mb-1">{rec.dependency} - {rec.recommendation_type}</div>
                      <div className="text-sm mb-2">{rec.reason}</div>
                      <div className="text-sm font-medium">Suggested action: {rec.suggested_action}</div>
                    </div>
                    <div className={`px-2 py-1 rounded text-xs ${
                      rec.urgency === 'high' ? 'bg-red-100 text-red-800' :
                      rec.urgency === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                      'bg-blue-100 text-blue-800'
                    }`}>
                      {rec.urgency} priority
                    </div>
                  </div>
                  
                  {rec.alternative && (
                    <div className="mt-3 bg-white p-2 rounded border">
                      <div className="text-xs font-medium text-gray-500 mb-1">Recommended Alternative:</div>
                      <div className="font-medium">{rec.alternative.name}</div>
                      <div className="text-sm text-gray-600 mt-1">{rec.alternative.reason}</div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="text-gray-500 italic p-4">
              No health recommendations available.
            </div>
          )}
        </div>
      </div>
    );
  };
  
  const renderLicenseReport = () => {
    if (!details || !details.result_summary) {
      return (
        <div className="bg-white p-4 rounded shadow">
          <div className="text-gray-500 italic">
            No license compliance data available.
          </div>
        </div>
      );
    }
    
    const summary = details.result_summary;
    const reports = details.license_reports || [];
    
    // Create chart data
    const riskDistributionData = [
      { name: 'High Risk', value: summary.risk_counts?.high || 0, color: '#EF4444' },
      { name: 'Medium Risk', value: summary.risk_counts?.medium || 0, color: '#F59E0B' },
      { name: 'Low Risk', value: summary.risk_counts?.low || 0, color: '#10B981' }
    ];
    
    const licenseTypesData = Object.entries(summary.license_types || {}).map(([type, count]) => ({
      name: type === 'weak-copyleft' ? 'Weak Copyleft' : type.charAt(0).toUpperCase() + type.slice(1),
      count
    }));
    
    return (
      <div>
        <div className="bg-white p-4 rounded shadow mb-6">
          <h3 className="text-lg font-semibold mb-4">License Compliance Summary</h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
            <div className="bg-blue-50 p-4 rounded">
              <div className="text-sm text-blue-700 mb-1">Target License</div>
              <div className="text-2xl font-bold capitalize">{summary.target_license || 'Unknown'}</div>
            </div>
            <div className="bg-green-50 p-4 rounded">
              <div className="text-sm text-green-700 mb-1">Compliance Rate</div>
              <div className="text-2xl font-bold">{summary.compliance_percentage || 0}%</div>
            </div>
            <div className="bg-red-50 p-4 rounded">
              <div className="text-sm text-red-700 mb-1">High Risk Dependencies</div>
              <div className="text-2xl font-bold">{summary.risk_counts?.high || 0}</div>
            </div>
            <div className="bg-gray-50 p-4 rounded">
              <div className="text-sm text-gray-500 mb-1">Overall Risk Level</div>
              <div className="text-2xl font-bold capitalize">{summary.overall_risk_level || 'Unknown'}</div>
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h4 className="text-md font-medium mb-2">Risk Distribution</h4>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={riskDistributionData}
                      cx="50%"
                      cy="50%"
                      outerRadius={80}
                      dataKey="value"
                      label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                    >
                      {riskDistributionData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(value) => [`${value} dependencies`, 'Count']} />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
            
            <div>
              <h4 className="text-md font-medium mb-2">License Types</h4>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={licenseTypesData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip formatter={(value) => [`${value} dependencies`, 'Count']} />
                    <Bar dataKey="count" fill="#8B5CF6" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </div>
        
        {/* High Risk Dependencies */}
        {summary.high_risk_dependencies && summary.high_risk_dependencies.length > 0 && (
          <div className="bg-white p-4 rounded shadow mb-6">
            <h3 className="text-lg font-semibold mb-4">High Risk Dependencies</h3>
            <div className="space-y-4">
              {summary.high_risk_dependencies.map((dep, index) => (
                <div key={index} className="border border-red-200 bg-red-50 rounded p-3">
                  <div className="flex items-start justify-between">
                    <div className="font-medium">{dep.name}</div>
                    <div className="px-2 py-1 bg-white rounded text-xs">
                      {dep.licenses.join(', ')}
                    </div>
                  </div>
                  
                  {dep.issues && dep.issues.length > 0 && (
                    <div className="mt-2">
                      <div className="text-xs font-medium mb-1">Compatibility Issues:</div>
                      <ul className="list-disc list-inside text-sm space-y-1">
                        {dep.issues.map((issue, i) => (
                          <li key={i}>
                            {issue.description}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
        
        {/* License Reports */}
        <div className="bg-white p-4 rounded shadow">
          <h3 className="text-lg font-semibold mb-4">License Details by Dependency</h3>
          {reports && reports.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="min-w-full border-collapse">
                <thead>
                  <tr>
                    <th className="px-4 py-2 border-b-2 text-left">Dependency</th>
                    <th className="px-4 py-2 border-b-2 text-left">Licenses</th>
                    <th className="px-4 py-2 border-b-2 text-left">Risk Level</th>
                    <th className="px-4 py-2 border-b-2 text-left">Compatibility</th>
                    <th className="px-4 py-2 border-b-2 text-left">Issues</th>
                  </tr>
                </thead>
                <tbody>
                  {reports.map((report, index) => (
                    <tr key={index} className="hover:bg-gray-50">
                      <td className="px-4 py-2 border-b font-medium">
                        {report.dependency}
                        <div className="text-xs text-gray-500">{report.version}</div>
                      </td>
                      <td className="px-4 py-2 border-b">
                        {report.licenses.map((license, i) => (
                          <div key={i} className="inline-block px-2 py-1 bg-gray-100 rounded text-xs mr-1 mb-1">
                            {license.license_id}
                          </div>
                        ))}
                      </td>
                      <td className="px-4 py-2 border-b">
                        <span className={`px-2 py-1 rounded text-xs ${
                          report.risk_level === 'high' ? 'bg-red-100 text-red-800' :
                          report.risk_level === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                          'bg-green-100 text-green-800'
                        }`}>
                          {report.risk_level}
                        </span>
                      </td>
                      <td className="px-4 py-2 border-b">
                        {report.compatibility_issues.length === 0 ? (
                          <span className="px-2 py-1 bg-green-100 text-green-800 rounded text-xs">
                            Compatible
                          </span>
                        ) : (
                          <span className="px-2 py-1 bg-red-100 text-red-800 rounded text-xs">
                            Issues Found
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2 border-b">
                        {report.compatibility_issues.length > 0 ? (
                          <ul className="list-disc list-inside text-xs">
                            {report.compatibility_issues.slice(0, 2).map((issue, i) => (
                              <li key={i}>
                                {issue.description}
                              </li>
                            ))}
                            {report.compatibility_issues.length > 2 && (
                              <li className="text-gray-500">
                                +{report.compatibility_issues.length - 2} more
                              </li>
                            )}
                          </ul>
                        ) : (
                          <span className="text-gray-500 text-xs">None</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-gray-500 italic p-4">
              No license reports available.
            </div>
          )}
        </div>
      </div>
    );
  };
  
  const renderPerformanceReport = () => {
    if (!details || !details.detailed_results) {
      return (
        <div className="bg-white p-4 rounded shadow">
          <div className="text-gray-500 italic">
            No performance data available.
          </div>
        </div>
      );
    }
    
    const results = details.detailed_results;
    const profileType = details.result_summary?.profile_type || 'bundle_size';
    const isBundle = profileType === 'bundle_size';
    
    // Prepare data for charts
    let chartData = [];
    
    if (isBundle) {
      // For bundle size, sort by size
      const sizeMetrics = results.size_metrics || {};
      chartData = Object.entries(sizeMetrics)
        .map(([name, metrics]) => ({
          name,
          minified: metrics.minified_size ? Math.round(metrics.minified_size / 1024) : 0,
          gzipped: metrics.gzipped_size ? Math.round(metrics.gzipped_size / 1024) : 0
        }))
        .sort((a, b) => b.gzipped - a.gzipped)
        .slice(0, 10); // Top 10
    } else {
      // For runtime performance
      const perfMetrics = results.performance_metrics || {};
      chartData = Object.entries(perfMetrics)
        .map(([name, metrics]) => ({
          name,
          startup: metrics.startup_impact || 0,
          runtime: metrics.runtime_impact || 0,
          memory: metrics.memory_impact || 0
        }))
        .sort((a, b) => b.runtime - a.runtime)
        .slice(0, 10); // Top 10
    }
    
    return (
      <div>
        <div className="bg-white p-4 rounded shadow mb-6">
          <h3 className="text-lg font-semibold mb-4">
            Performance Profiling: {isBundle ? 'Bundle Size' : 'Runtime Performance'}
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
            <div className="bg-gray-50 p-4 rounded">
              <div className="text-sm text-gray-500 mb-1">Total Dependencies</div>
              <div className="text-2xl font-bold">{results.total_dependencies || 0}</div>
            </div>
            <div className="bg-blue-50 p-4 rounded">
              <div className="text-sm text-blue-700 mb-1">Direct Dependencies</div>
              <div className="text-2xl font-bold">{results.direct_dependencies || 0}</div>
            </div>
            
            {isBundle ? (
              <>
                <div className="bg-purple-50 p-4 rounded">
                  <div className="text-sm text-purple-700 mb-1">Total Size (Gzipped)</div>
                  <div className="text-2xl font-bold">
                    {results.total_size_gzipped ? 
                      `${(results.total_size_gzipped / (1024 * 1024)).toFixed(2)} MB` : 
                      'Unknown'}
                  </div>
                </div>
                <div className="bg-green-50 p-4 rounded">
                  <div className="text-sm text-green-700 mb-1">Direct Size (Gzipped)</div>
                  <div className="text-2xl font-bold">
                    {results.direct_size_gzipped ? 
                      `${(results.direct_size_gzipped / (1024 * 1024)).toFixed(2)} MB` : 
                      'Unknown'}
                  </div>
                </div>
              </>
            ) : (
              <>
                <div className="bg-yellow-50 p-4 rounded">
                  <div className="text-sm text-yellow-700 mb-1">Avg Runtime Impact</div>
                  <div className="text-2xl font-bold">
                    {results.avg_runtime_impact_ms ? 
                      `${results.avg_runtime_impact_ms.toFixed(2)} ms` : 
                      'Unknown'}
                  </div>
                </div>
                <div className="bg-red-50 p-4 rounded">
                  <div className="text-sm text-red-700 mb-1">Avg Memory Impact</div>
                  <div className="text-2xl font-bold">
                    {results.avg_memory_impact_mb ? 
                      `${results.avg_memory_impact_mb.toFixed(2)} MB` : 
                      'Unknown'}
                  </div>
                </div>
              </>
            )}
          </div>
          
          <div className="h-80">
            <h4 className="text-md font-medium mb-2">
              {isBundle ? 'Largest Dependencies (KB)' : 'Highest Impact Dependencies'}
            </h4>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} layout={isBundle ? "vertical" : "horizontal"}>
                <CartesianGrid strokeDasharray="3 3" />
                {isBundle ? (
                  <>
                    <XAxis type="number" />
                    <YAxis dataKey="name" type="category" width={120} />
                    <Bar dataKey="gzipped" name="Gzipped (KB)" fill="#3B82F6" />
                    <Bar dataKey="minified" name="Minified (KB)" fill="#6366F1" />
                  </>
                ) : (
                  <>
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Bar dataKey="runtime" name="Runtime Impact (ms)" fill="#F59E0B" />
                    <Bar dataKey="startup" name="Startup Impact (ms)" fill="#10B981" />
                    <Bar dataKey="memory" name="Memory Impact (MB)" fill="#EF4444" />
                  </>
                )}
                <Tooltip />
                <Legend />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
        
        {/* Detailed Metrics */}
        <div className="bg-white p-4 rounded shadow">
          <h3 className="text-lg font-semibold mb-4">
            {isBundle ? 'Bundle Size Details' : 'Performance Metrics'}
          </h3>
          <div className="overflow-x-auto">
            <table className="min-w-full border-collapse">
              <thead>
                <tr>
                  <th className="px-4 py-2 border-b-2 text-left">Dependency</th>
                  {isBundle ? (
                    <>
                      <th className="px-4 py-2 border-b-2 text-left">Minified Size</th>
                      <th className="px-4 py-2 border-b-2 text-left">Gzipped Size</th>
                      <th className="px-4 py-2 border-b-2 text-left">% of Total</th>
                    </>
                  ) : (
                    <>
                      <th className="px-4 py-2 border-b-2 text-left">Startup Impact</th>
                      <th className="px-4 py-2 border-b-2 text-left">Runtime Impact</th>
                      <th className="px-4 py-2 border-b-2 text-left">Memory Impact</th>
                    </>
                  )}
                  <th className="px-4 py-2 border-b-2 text-left">Type</th>
                </tr>
              </thead>
              <tbody>
                {isBundle ? (
                  // Bundle size metrics
                  Object.entries(results.size_metrics || {})
                    .sort((a, b) => {
                      const aSize = a[1].gzipped_size || 0;
                      const bSize = b[1].gzipped_size || 0;
                      return bSize - aSize;
                    })
                    .slice(0, 20) // Top 20
                    .map(([name, metrics], index) => {
                      const minSize = metrics.minified_size || 0;
                      const gzipSize = metrics.gzipped_size || 0;
                      const totalSize = results.total_size_gzipped || 1;
                      const percentage = (gzipSize / totalSize) * 100;
                      
                      return (
                        <tr key={index} className="hover:bg-gray-50">
                          <td className="px-4 py-2 border-b font-medium">{name}</td>
                          <td className="px-4 py-2 border-b">
                            {minSize ? `${(minSize / 1024).toFixed(1)} KB` : 'Unknown'}
                          </td>
                          <td className="px-4 py-2 border-b">
                            {gzipSize ? `${(gzipSize / 1024).toFixed(1)} KB` : 'Unknown'}
                          </td>
                          <td className="px-4 py-2 border-b">
                            {percentage.toFixed(1)}%
                          </td>
                          <td className="px-4 py-2 border-b">
                            <span className={`px-2 py-1 rounded text-xs ${
                              percentage > 10 ? 'bg-red-100 text-red-800' :
                              percentage > 5 ? 'bg-yellow-100 text-yellow-800' :
                              'bg-green-100 text-green-800'
                            }`}>
                              {percentage > 10 ? 'Large' : percentage > 5 ? 'Medium' : 'Small'}
                            </span>
                          </td>
                        </tr>
                      );
                    })
                ) : (
                  // Runtime performance metrics
                  Object.entries(results.performance_metrics || {})
                    .sort((a, b) => {
                      const aImpact = a[1].runtime_impact || 0;
                      const bImpact = b[1].runtime_impact || 0;
                      return bImpact - aImpact;
                    })
                    .slice(0, 20) // Top 20
                    .map(([name, metrics], index) => {
                      const startupImpact = metrics.startup_impact || 0;
                      const runtimeImpact = metrics.runtime_impact || 0;
                      const memoryImpact = metrics.memory_impact || 0;
                      
                      return (
                        <tr key={index} className="hover:bg-gray-50">
                          <td className="px-4 py-2 border-b font-medium">{name}</td>
                          <td className="px-4 py-2 border-b">
                            {startupImpact.toFixed(1)} ms
                          </td>
                          <td className="px-4 py-2 border-b">
                            {runtimeImpact.toFixed(1)} ms
                          </td>
                          <td className="px-4 py-2 border-b">
                            {memoryImpact.toFixed(1)} MB
                          </td>
                          <td className="px-4 py-2 border-b">
                            <span className={`px-2 py-1 rounded text-xs ${
                              runtimeImpact > 10 ? 'bg-red-100 text-red-800' :
                              runtimeImpact > 5 ? 'bg-yellow-100 text-yellow-800' :
                              'bg-green-100 text-green-800'
                            }`}>
                              {runtimeImpact > 10 ? 'High Impact' : runtimeImpact > 5 ? 'Medium Impact' : 'Low Impact'}
                            </span>
                          </td>
                        </tr>
                      );
                    })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    );
  };
  
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="flex flex-col items-center">
          <RefreshCw size={32} className="animate-spin text-blue-500 mb-2" />
          <p className="text-gray-700">Loading analysis data...</p>
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
            onClick={() => navigate(-1)}
          >
            Go Back
          </button>
        </div>
      </div>
    );
  }
  
  if (!analysis) {
    return (
      <div className="p-6">
        <div className="bg-red-50 text-red-800 p-4 rounded mb-4">
          <h3 className="font-bold">Analysis Not Found</h3>
          <p>The requested analysis could not be found.</p>
          <button 
            className="mt-2 text-blue-500 hover:text-blue-700"
            onClick={() => navigate(-1)}
          >
            Go Back
          </button>
        </div>
      </div>
    );
  }
  
  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between mb-6">
        <div className="flex items-center">
          {getAnalysisIcon()}
          <h1 className="text-2xl font-bold ml-2">
            {formatAnalysisType(analysis.analysis_type)} Report
          </h1>
          <div className="ml-2">
            {getStatusIndicator()}
          </div>
        </div>
        
        <div className="mt-2 md:mt-0 text-gray-500 text-sm">
          {analysis.created_at && (
            <span className="inline-flex items-center mr-4">
              <Clock size={16} className="mr-1" /> 
              Created: {new Date(analysis.created_at).toLocaleString()}
            </span>
          )}
          <button 
            className="text-blue-500 hover:text-blue-700"
            onClick={() => navigate(`/projects/${analysis.project_id}`)}
          >
            Back to Project
          </button>
        </div>
      </div>
      
      {/* Status messages */}
      {analysis.status === 'running' && (
        <div className="bg-blue-50 text-blue-800 p-4 rounded mb-6 flex items-center">
          <RefreshCw size={20} className="animate-spin mr-2" />
          <div>
            <h3 className="font-bold">Analysis in progress</h3>
            <p>This analysis is currently running. Results will be available once it completes.</p>
          </div>
        </div>
      )}
      
      {analysis.status === 'failed' && (
        <div className="bg-red-50 text-red-800 p-4 rounded mb-6">
          <h3 className="font-bold">Analysis Failed</h3>
          <p>{analysis.error_message || 'An error occurred during analysis.'}</p>
        </div>
      )}
      
      {/* Report Content */}
      {analysis.status === 'completed' ? (
        renderAnalysisReport()
      ) : (
        <div className="bg-white p-4 rounded shadow">
          <div className="text-gray-500 italic">
            Analysis report will be available once the analysis completes.
          </div>
        </div>
      )}
    </div>
  );
};

export default AnalysisReport;