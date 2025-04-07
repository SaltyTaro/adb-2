import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  PackageOpen, ExternalLink, RefreshCw, Heart, AlertTriangle, 
  Clock, Tag, CheckCircle, XCircle, Shield, Archive, Code
} from 'lucide-react';

import { fetchDependency, refreshDependency, fetchDependencyVersions, fetchDependencyRecommendations } from '../services/api';

const DependencyDetail = () => {
  const { dependencyId } = useParams();
  const navigate = useNavigate();
  const [dependency, setDependency] = useState(null);
  const [versions, setVersions] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');

  useEffect(() => {
    const loadDependencyData = async () => {
      try {
        setLoading(true);
        const dependencyData = await fetchDependency(dependencyId);
        setDependency(dependencyData);
        
        // Fetch versions if available
        if (dependencyData.versions) {
          setVersions(dependencyData.versions);
        } else {
          const versionsData = await fetchDependencyVersions(dependencyId);
          setVersions(versionsData);
        }
        
        // Fetch recommendations
        const recommendationsData = await fetchDependencyRecommendations(dependencyId);
        setRecommendations(recommendationsData);
      } catch (error) {
        console.error('Error loading dependency data:', error);
      } finally {
        setLoading(false);
      }
    };
    
    loadDependencyData();
  }, [dependencyId]);
  
  const handleRefresh = async () => {
    try {
      setRefreshing(true);
      const refreshedData = await refreshDependency(dependencyId);
      setDependency(refreshedData);
    } catch (error) {
      console.error('Error refreshing dependency:', error);
    } finally {
      setRefreshing(false);
    }
  };
  
  // Render health status badge
  const renderHealthStatus = () => {
    if (!dependency || dependency.health_score === null) {
      return (
        <span className="px-2 py-1 rounded bg-gray-200 text-gray-800 text-xs">
          Unknown
        </span>
      );
    }
    
    const score = dependency.health_score;
    if (score >= 0.7) {
      return (
        <span className="px-2 py-1 rounded bg-green-100 text-green-800 text-xs flex items-center">
          <CheckCircle size={12} className="mr-1" />
          Healthy ({(score * 100).toFixed(0)}%)
        </span>
      );
    } else if (score >= 0.4) {
      return (
        <span className="px-2 py-1 rounded bg-yellow-100 text-yellow-800 text-xs flex items-center">
          <AlertTriangle size={12} className="mr-1" />
          Moderate ({(score * 100).toFixed(0)}%)
        </span>
      );
    } else {
      return (
        <span className="px-2 py-1 rounded bg-red-100 text-red-800 text-xs flex items-center">
          <XCircle size={12} className="mr-1" />
          At Risk ({(score * 100).toFixed(0)}%)
        </span>
      );
    }
  };
  
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="flex flex-col items-center">
          <RefreshCw size={32} className="animate-spin text-blue-500 mb-2" />
          <p className="text-gray-700">Loading dependency data...</p>
        </div>
      </div>
    );
  }
  
  if (!dependency) {
    return (
      <div className="p-6">
        <div className="bg-red-50 text-red-800 p-4 rounded mb-4">
          <h3 className="font-bold">Error</h3>
          <p>Dependency not found or there was an error loading it.</p>
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
        <div className="flex items-center mb-4 md:mb-0">
          <PackageOpen size={24} className="text-blue-500 mr-2" />
          <h1 className="text-2xl font-bold">{dependency.name}</h1>
          <span className="ml-2 px-2 py-1 bg-gray-100 rounded text-xs">
            {dependency.ecosystem}
          </span>
          {dependency.latest_version && (
            <span className="ml-2 px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs flex items-center">
              <Tag size={12} className="mr-1" />
              {dependency.latest_version}
            </span>
          )}
          {dependency.is_deprecated && (
            <span className="ml-2 px-2 py-1 bg-red-100 text-red-800 rounded text-xs flex items-center">
              <AlertTriangle size={12} className="mr-1" />
              Deprecated
            </span>
          )}
          <div className="ml-2">
            {renderHealthStatus()}
          </div>
        </div>
        
        <div className="flex">
          <button
            onClick={handleRefresh}
            className="flex items-center px-3 py-1 bg-gray-100 hover:bg-gray-200 rounded text-sm mr-2"
            disabled={refreshing}
          >
            <RefreshCw size={16} className={`mr-1 ${refreshing ? 'animate-spin' : ''}`} />
            {refreshing ? 'Refreshing...' : 'Refresh'}
          </button>
          
          {dependency.repository_url && (
            <a
              href={dependency.repository_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center px-3 py-1 bg-gray-100 hover:bg-gray-200 rounded text-sm"
            >
              <ExternalLink size={16} className="mr-1" />
              Repository
            </a>
          )}
        </div>
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
              activeTab === 'versions'
                ? 'border-b-2 border-blue-500 text-blue-500'
                : 'text-gray-600 hover:text-blue-500'
            }`}
            onClick={() => setActiveTab('versions')}
          >
            Versions
          </button>
          <button
            className={`px-4 py-2 ${
              activeTab === 'licenses'
                ? 'border-b-2 border-blue-500 text-blue-500'
                : 'text-gray-600 hover:text-blue-500'
            }`}
            onClick={() => setActiveTab('licenses')}
          >
            Licenses
          </button>
          <button
            className={`px-4 py-2 ${
              activeTab === 'vulnerabilities'
                ? 'border-b-2 border-blue-500 text-blue-500'
                : 'text-gray-600 hover:text-blue-500'
            }`}
            onClick={() => setActiveTab('vulnerabilities')}
          >
            Vulnerabilities
          </button>
        </nav>
      </div>
      
      {/* Content */}
      <div className="bg-white rounded shadow p-6">
        {activeTab === 'overview' && (
          <div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Basic Info */}
              <div>
                <h3 className="text-lg font-semibold mb-4">Basic Information</h3>
                <table className="w-full">
                  <tbody>
                    <tr>
                      <td className="py-2 pr-4 text-gray-600 align-top">Name:</td>
                      <td className="py-2 font-medium">{dependency.name}</td>
                    </tr>
                    <tr>
                      <td className="py-2 pr-4 text-gray-600 align-top">Ecosystem:</td>
                      <td className="py-2">{dependency.ecosystem}</td>
                    </tr>
                    <tr>
                      <td className="py-2 pr-4 text-gray-600 align-top">Latest Version:</td>
                      <td className="py-2">{dependency.latest_version || 'Unknown'}</td>
                    </tr>
                    <tr>
                      <td className="py-2 pr-4 text-gray-600 align-top">Description:</td>
                      <td className="py-2">{dependency.description || 'No description available'}</td>
                    </tr>
                    {dependency.homepage_url && (
                      <tr>
                        <td className="py-2 pr-4 text-gray-600 align-top">Homepage:</td>
                        <td className="py-2">
                          <a
                            href={dependency.homepage_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-500 hover:text-blue-700 flex items-center"
                          >
                            {dependency.homepage_url}
                            <ExternalLink size={14} className="ml-1" />
                          </a>
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
              
              {/* Health Metrics */}
              <div>
                <h3 className="text-lg font-semibold mb-4">Health & Maintenance</h3>
                
                {dependency.metadata && dependency.metadata.community_metrics ? (
                  <div>
                    <div className="mb-4">
                      <div className="flex justify-between mb-1">
                        <span className="text-sm text-gray-600">Health Score</span>
                        <span className="text-sm font-medium">
                          {dependency.health_score !== null ? 
                            `${(dependency.health_score * 100).toFixed(0)}%` : 
                            'Unknown'}
                        </span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2.5">
                        <div
                          className={`h-2.5 rounded-full ${
                            dependency.health_score >= 0.7
                              ? 'bg-green-500'
                              : dependency.health_score >= 0.4
                              ? 'bg-yellow-500'
                              : 'bg-red-500'
                          }`}
                          style={{
                            width: dependency.health_score !== null
                              ? `${(dependency.health_score * 100)}%`
                              : '0%'
                          }}
                        ></div>
                      </div>
                    </div>
                    
                    <table className="w-full">
                      <tbody>
                        {dependency.metadata.maintenance_status && (
                          <tr>
                            <td className="py-2 pr-4 text-gray-600">Status:</td>
                            <td className="py-2 capitalize">
                              {dependency.metadata.maintenance_status}
                            </td>
                          </tr>
                        )}
                        {dependency.metadata.days_since_update !== undefined && (
                          <tr>
                            <td className="py-2 pr-4 text-gray-600">Last Updated:</td>
                            <td className="py-2">
                              {dependency.metadata.days_since_update} days ago
                            </td>
                          </tr>
                        )}
                        {dependency.metadata.community_metrics.contributor_count !== undefined && (
                          <tr>
                            <td className="py-2 pr-4 text-gray-600">Contributors:</td>
                            <td className="py-2">
                              {dependency.metadata.community_metrics.contributor_count}
                            </td>
                          </tr>
                        )}
                        {dependency.metadata.community_metrics.stars !== undefined && (
                          <tr>
                            <td className="py-2 pr-4 text-gray-600">GitHub Stars:</td>
                            <td className="py-2">
                              {dependency.metadata.community_metrics.stars.toLocaleString()}
                            </td>
                          </tr>
                        )}
                        {dependency.metadata.community_metrics.forks !== undefined && (
                          <tr>
                            <td className="py-2 pr-4 text-gray-600">Forks:</td>
                            <td className="py-2">
                              {dependency.metadata.community_metrics.forks.toLocaleString()}
                            </td>
                          </tr>
                        )}
                        {dependency.metadata.community_metrics.open_issues !== undefined && (
                          <tr>
                            <td className="py-2 pr-4 text-gray-600">Open Issues:</td>
                            <td className="py-2">
                              {dependency.metadata.community_metrics.open_issues.toLocaleString()}
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="text-gray-500 italic">
                    Health metrics not available. Try refreshing dependency data.
                  </div>
                )}
              </div>
            </div>
            
            {/* Risk Factors */}
            {dependency.metadata && dependency.metadata.risk_factors && 
            dependency.metadata.risk_factors.length > 0 && (
              <div className="mt-6">
                <h3 className="text-lg font-semibold mb-4">Risk Factors</h3>
                <div className="bg-yellow-50 border border-yellow-200 rounded p-4">
                  <ul className="list-disc pl-5 space-y-1">
                    {dependency.metadata.risk_factors.map((risk, index) => (
                      <li key={index} className="text-yellow-800">
                        {risk.replace(/_/g, ' ')}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            )}
            
            {/* Recommendations */}
            {recommendations.length > 0 && (
              <div className="mt-6">
                <h3 className="text-lg font-semibold mb-4">Recommendations</h3>
                <div className="space-y-4">
                  {recommendations.map((rec, index) => (
                    <div 
                      key={index}
                      className={`border rounded p-4 ${
                        rec.type === 'health' 
                          ? 'border-yellow-200 bg-yellow-50' 
                          : rec.type === 'deprecation'
                          ? 'border-red-200 bg-red-50'
                          : 'border-blue-200 bg-blue-50'
                      }`}
                    >
                      <div className="font-medium mb-2">
                        {rec.message || rec.name || 'Recommendation'}
                      </div>
                      <p className="text-gray-800 mb-2">
                        {rec.action || rec.description || ''}
                      </p>
                      {rec.alternatives && (
                        <div className="mt-2">
                          <span className="text-sm font-medium">Alternatives: </span>
                          {rec.alternatives}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
        
        {activeTab === 'versions' && (
          <div>
            <h3 className="text-lg font-semibold mb-4">Available Versions</h3>
            {versions.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="min-w-full border-collapse">
                  <thead>
                    <tr>
                      <th className="px-4 py-2 border-b-2 text-left">Version</th>
                      <th className="px-4 py-2 border-b-2 text-left">Published</th>
                      <th className="px-4 py-2 border-b-2 text-left">Size</th>
                      <th className="px-4 py-2 border-b-2 text-left">Status</th>
                      <th className="px-4 py-2 border-b-2 text-left">Security</th>
                    </tr>
                  </thead>
                  <tbody>
                    {versions.map((version) => (
                      <tr key={version.id} className="hover:bg-gray-50">
                        <td className="px-4 py-2 border-b font-medium">{version.version}</td>
                        <td className="px-4 py-2 border-b">
                          {version.published_at ? new Date(version.published_at).toLocaleDateString() : 'Unknown'}
                        </td>
                        <td className="px-4 py-2 border-b">
                          {version.size_bytes ? `${(version.size_bytes / 1024).toFixed(0)} KB` : 'Unknown'}
                        </td>
                        <td className="px-4 py-2 border-b">
                          {version.is_yanked ? (
                            <span className="px-2 py-1 bg-red-100 text-red-800 rounded text-xs flex items-center">
                              <XCircle size={12} className="mr-1" />
                              Yanked
                            </span>
                          ) : (
                            <span className="px-2 py-1 bg-green-100 text-green-800 rounded text-xs flex items-center">
                              <CheckCircle size={12} className="mr-1" />
                              Available
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-2 border-b">
                          {version.security_vulnerabilities > 0 ? (
                            <span className="px-2 py-1 bg-red-100 text-red-800 rounded text-xs flex items-center">
                              <Shield size={12} className="mr-1" />
                              {version.security_vulnerabilities} Issues
                            </span>
                          ) : (
                            <span className="px-2 py-1 bg-green-100 text-green-800 rounded text-xs flex items-center">
                              <Shield size={12} className="mr-1" />
                              Secure
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-gray-500 italic">
                No version information available.
              </div>
            )}
          </div>
        )}
        
        {activeTab === 'licenses' && (
          <div>
            <h3 className="text-lg font-semibold mb-4">License Information</h3>
            {dependency.license_reports && dependency.license_reports.length > 0 ? (
              <div className="space-y-4">
                {dependency.license_reports.map((license, index) => (
                  <div key={index} className="border rounded p-4">
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="font-medium">{license.license_name || license.license_id}</h4>
                      <span className={`px-2 py-1 rounded text-xs ${
                        license.risk_level === 'high'
                          ? 'bg-red-100 text-red-800'
                          : license.risk_level === 'medium'
                          ? 'bg-yellow-100 text-yellow-800'
                          : 'bg-green-100 text-green-800'
                      }`}>
                        {license.risk_level} risk
                      </span>
                    </div>
                    <div className="text-sm">
                      <div className="mb-1">
                        <span className="font-medium">Type: </span>
                        <span className="capitalize">{license.license_type || 'Unknown'}</span>
                      </div>
                      <div className="mb-1">
                        <span className="font-medium">Compliance: </span>
                        <span>{license.is_compliant ? 'Compliant' : 'Non-compliant'}</span>
                      </div>
                      {license.compliance_notes && (
                        <div className="mt-2 text-gray-600">
                          {license.compliance_notes}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-gray-500 italic">
                No license information available.
              </div>
            )}
          </div>
        )}
        
        {activeTab === 'vulnerabilities' && (
          <div>
            <h3 className="text-lg font-semibold mb-4">Security Vulnerabilities</h3>
            {dependency.vulnerability_reports && dependency.vulnerability_reports.length > 0 ? (
              <div className="space-y-4">
                {dependency.vulnerability_reports.map((vuln, index) => (
                  <div key={index} className="border border-red-200 bg-red-50 rounded p-4">
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="font-medium">{vuln.title || 'Vulnerability'}</h4>
                      <div className="flex items-center space-x-2">
                        <span className={`px-2 py-1 rounded text-xs ${
                          vuln.severity === 'critical' || vuln.severity === 'high'
                            ? 'bg-red-100 text-red-800'
                            : vuln.severity === 'medium'
                            ? 'bg-yellow-100 text-yellow-800'
                            : 'bg-green-100 text-green-800'
                        }`}>
                          {vuln.severity} severity
                        </span>
                        <span className="px-2 py-1 bg-gray-100 rounded text-xs">
                          {vuln.version}
                        </span>
                      </div>
                    </div>
                    <div className="text-sm">
                      {vuln.description && (
                        <div className="mb-2 text-gray-800">
                          {vuln.description}
                        </div>
                      )}
                      {vuln.cve_id && (
                        <div className="mb-1">
                          <span className="font-medium">CVE: </span>
                          <a 
                            href={`https://nvd.nist.gov/vuln/detail/${vuln.cve_id}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:text-blue-800"
                          >
                            {vuln.cve_id}
                          </a>
                        </div>
                      )}
                      {vuln.fixed_in && (
                        <div className="mb-1">
                          <span className="font-medium">Fixed in: </span>
                          <span className="bg-green-100 px-1 py-0.5 rounded">
                            {vuln.fixed_in}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-green-600 flex items-center">
                <Shield size={18} className="mr-2" />
                No known vulnerabilities found.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default DependencyDetail;