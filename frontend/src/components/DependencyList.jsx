import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { 
  Search, Package, Shield, AlertTriangle, CheckCircle, 
  RefreshCw, ExternalLink, ChevronDown, ChevronUp, Filter
} from 'lucide-react';

const DependencyList = ({ dependencies }) => {
  const [filteredDeps, setFilteredDeps] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortField, setSortField] = useState('name');
  const [sortDirection, setSortDirection] = useState('asc');
  const [filters, setFilters] = useState({
    ecosystem: 'all',
    health: 'all',
    deprecated: 'all'
  });
  
  useEffect(() => {
    // Apply filters and search
    let result = [...dependencies];
    
    // Apply ecosystem filter
    if (filters.ecosystem !== 'all') {
      result = result.filter(dep => dep.ecosystem === filters.ecosystem);
    }
    
    // Apply health filter
    if (filters.health !== 'all') {
      switch (filters.health) {
        case 'healthy':
          result = result.filter(dep => dep.health_score >= 0.7);
          break;
        case 'moderate':
          result = result.filter(dep => dep.health_score >= 0.4 && dep.health_score < 0.7);
          break;
        case 'at_risk':
          result = result.filter(dep => dep.health_score < 0.4);
          break;
        case 'unknown':
          result = result.filter(dep => dep.health_score === null || dep.health_score === undefined);
          break;
        default:
          break;
      }
    }
    
    // Apply deprecated filter
    if (filters.deprecated !== 'all') {
      const isDeprecated = filters.deprecated === 'deprecated';
      result = result.filter(dep => dep.is_deprecated === isDeprecated);
    }
    
    // Apply search
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      result = result.filter(dep => 
        dep.name.toLowerCase().includes(term) ||
        (dep.description && dep.description.toLowerCase().includes(term))
      );
    }
    
    // Apply sorting
    result.sort((a, b) => {
      let aValue = a[sortField];
      let bValue = b[sortField];
      
      // Handle special cases
      if (sortField === 'health_score') {
        aValue = aValue === null ? -1 : aValue;
        bValue = bValue === null ? -1 : bValue;
      }
      
      if (aValue < bValue) {
        return sortDirection === 'asc' ? -1 : 1;
      }
      if (aValue > bValue) {
        return sortDirection === 'asc' ? 1 : -1;
      }
      return 0;
    });
    
    setFilteredDeps(result);
  }, [dependencies, searchTerm, sortField, sortDirection, filters]);
  
  // Get unique ecosystems for filter
  const ecosystems = ['all', ...new Set(dependencies.map(dep => dep.ecosystem))];
  
  // Handle sort change
  const handleSort = (field) => {
    if (field === sortField) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };
  
  // Render sort indicator
  const renderSortIndicator = (field) => {
    if (sortField !== field) return null;
    return sortDirection === 'asc' ? 
      <ChevronUp size={16} className="ml-1" /> : 
      <ChevronDown size={16} className="ml-1" />;
  };
  
  // Render health status badge
  const renderHealthStatus = (healthScore) => {
    if (healthScore === null || healthScore === undefined) {
      return (
        <span className="px-2 py-1 rounded bg-gray-200 text-gray-800 text-xs">
          Unknown
        </span>
      );
    }
    
    if (healthScore >= 0.7) {
      return (
        <span className="px-2 py-1 rounded bg-green-100 text-green-800 text-xs flex items-center">
          <CheckCircle size={12} className="mr-1" />
          Healthy ({(healthScore * 100).toFixed(0)}%)
        </span>
      );
    } else if (healthScore >= 0.4) {
      return (
        <span className="px-2 py-1 rounded bg-yellow-100 text-yellow-800 text-xs flex items-center">
          <AlertTriangle size={12} className="mr-1" />
          Moderate ({(healthScore * 100).toFixed(0)}%)
        </span>
      );
    } else {
      return (
        <span className="px-2 py-1 rounded bg-red-100 text-red-800 text-xs flex items-center">
          <AlertTriangle size={12} className="mr-1" />
          At Risk ({(healthScore * 100).toFixed(0)}%)
        </span>
      );
    }
  };
  
  return (
    <div>
      {/* Search and Filters */}
      <div className="mb-4 flex flex-col md:flex-row md:items-center gap-2">
        <div className="relative flex-1">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Search size={16} className="text-gray-400" />
          </div>
          <input
            type="text"
            placeholder="Search dependencies..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10 pr-4 py-2 w-full border rounded"
          />
        </div>
        
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center">
            <div className="bg-gray-100 p-1 rounded mr-2">
              <Filter size={16} className="text-gray-500" />
            </div>
            <select
              value={filters.ecosystem}
              onChange={(e) => setFilters({ ...filters, ecosystem: e.target.value })}
              className="border rounded p-2"
            >
              <option value="all">All Ecosystems</option>
              {ecosystems.filter(e => e !== 'all').map(eco => (
                <option key={eco} value={eco}>{eco}</option>
              ))}
            </select>
          </div>
          
          <select
            value={filters.health}
            onChange={(e) => setFilters({ ...filters, health: e.target.value })}
            className="border rounded p-2"
          >
            <option value="all">All Health</option>
            <option value="healthy">Healthy</option>
            <option value="moderate">Moderate</option>
            <option value="at_risk">At Risk</option>
            <option value="unknown">Unknown</option>
          </select>
          
          <select
            value={filters.deprecated}
            onChange={(e) => setFilters({ ...filters, deprecated: e.target.value })}
            className="border rounded p-2"
          >
            <option value="all">All Status</option>
            <option value="active">Active</option>
            <option value="deprecated">Deprecated</option>
          </select>
        </div>
      </div>
      
      {/* Results summary */}
      <div className="mb-4 text-sm text-gray-500">
        Found {filteredDeps.length} dependencies
        {searchTerm && ` matching "${searchTerm}"`}
        {filters.ecosystem !== 'all' && ` in ${filters.ecosystem}`}
        {filters.health !== 'all' && ` with ${filters.health.replace('_', ' ')} health`}
        {filters.deprecated !== 'all' && ` that are ${filters.deprecated}`}
      </div>
      
      {/* Dependencies table */}
      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse">
          <thead>
            <tr>
              <th 
                className="px-4 py-2 border-b-2 text-left cursor-pointer"
                onClick={() => handleSort('name')}
              >
                <div className="flex items-center">
                  Name
                  {renderSortIndicator('name')}
                </div>
              </th>
              <th 
                className="px-4 py-2 border-b-2 text-left cursor-pointer"
                onClick={() => handleSort('ecosystem')}
              >
                <div className="flex items-center">
                  Ecosystem
                  {renderSortIndicator('ecosystem')}
                </div>
              </th>
              <th 
                className="px-4 py-2 border-b-2 text-left cursor-pointer"
                onClick={() => handleSort('latest_version')}
              >
                <div className="flex items-center">
                  Version
                  {renderSortIndicator('latest_version')}
                </div>
              </th>
              <th 
                className="px-4 py-2 border-b-2 text-left cursor-pointer"
                onClick={() => handleSort('health_score')}
              >
                <div className="flex items-center">
                  Health
                  {renderSortIndicator('health_score')}
                </div>
              </th>
              <th className="px-4 py-2 border-b-2 text-left">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredDeps.map((dep) => (
              <tr key={dep.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 border-b">
                  <div className="flex items-start">
                    <Package size={16} className="text-gray-400 mt-1 mr-2" />
                    <div>
                      <div className="font-medium flex items-center">
                        {dep.name}
                        {dep.is_deprecated && (
                          <span className="ml-2 px-2 py-0.5 bg-red-100 text-red-800 rounded text-xs">
                            Deprecated
                          </span>
                        )}
                      </div>
                      {dep.description && (
                        <div className="text-sm text-gray-500 mt-1">
                          {dep.description.length > 100 ? 
                            `${dep.description.substring(0, 100)}...` : 
                            dep.description
                          }
                        </div>
                      )}
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3 border-b">
                  <span className="px-2 py-1 bg-gray-100 rounded text-xs">
                    {dep.ecosystem}
                  </span>
                </td>
                <td className="px-4 py-3 border-b">
                  {dep.latest_version || 'Unknown'}
                </td>
                <td className="px-4 py-3 border-b">
                  {renderHealthStatus(dep.health_score)}
                </td>
                <td className="px-4 py-3 border-b">
                  <div className="flex items-center space-x-2">
                    <Link
                      to={`/dependencies/${dep.id}`}
                      className="text-blue-500 hover:text-blue-700"
                    >
                      Details
                    </Link>
                    {dep.repository_url && (
                      <a
                        href={dep.repository_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-gray-500 hover:text-gray-700"
                        title="Repository"
                      >
                        <ExternalLink size={16} />
                      </a>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {filteredDeps.length === 0 && (
              <tr>
                <td colSpan="5" className="px-4 py-8 text-center text-gray-500">
                  No dependencies match your filters. Try adjusting your search or filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default DependencyList;