import React, { useEffect, useRef, useState } from 'react';
import { Network } from 'vis-network';
import { DataSet } from 'vis-data';
import { Package, GitMerge, Filter } from 'lucide-react';

const DependencyGraph = ({ dependencies, maxDepth = 2 }) => {
  const networkRef = useRef(null);
  const containerRef = useRef(null);
  const [showTransitive, setShowTransitive] = useState(true);
  const [selectedDependency, setSelectedDependency] = useState(null);
  const [graphData, setGraphData] = useState({ nodes: [], edges: [] });
  const [networkInstance, setNetworkInstance] = useState(null);
  
  useEffect(() => {
    if (!dependencies || dependencies.length === 0) return;
    
    const buildGraphData = () => {
      const nodes = new DataSet();
      const edges = new DataSet();
      
      // Create a root node for the project
      nodes.add({
        id: 'project',
        label: 'Your Project',
        title: 'Your Project',
        color: '#3B82F6',
        shape: 'box',
        font: { size: 16, color: 'white' },
        level: 0
      });
      
      // Track processed nodes to avoid duplicates
      const processedNodes = new Set(['project']);
      
      // Process direct dependencies
      dependencies.forEach(dep => {
        if (!processedNodes.has(dep.name)) {
          processedNodes.add(dep.name);
          
          const nodeColor = dep.is_deprecated ? '#EF4444' :
                          dep.health_score >= 0.7 ? '#10B981' :
                          dep.health_score >= 0.4 ? '#F59E0B' : '#9CA3AF';
          
          nodes.add({
            id: dep.name,
            label: dep.name,
            title: `${dep.name}\n${dep.latest_version || 'Unknown'}`,
            color: nodeColor,
            shape: 'dot',
            level: 1
          });
          
          // Add edge from project to dependency
          edges.add({
            from: 'project',
            to: dep.name,
            arrows: 'to',
            color: { color: '#9CA3AF', opacity: 0.6 },
            width: 1
          });
        }
        
        // Process transitive dependencies up to maxDepth
        if (showTransitive && dep.metadata && dep.metadata.dependencies) {
          processTransitiveDependencies(
            dep.name,
            dep.metadata.dependencies,
            nodes,
            edges,
            processedNodes,
            2,
            maxDepth
          );
        }
      });
      
      return { nodes: nodes.get(), edges: edges.get() };
    };
    
    const data = buildGraphData();
    setGraphData(data);
    
    // Create and initialize the network
    if (containerRef.current) {
      const options = {
        layout: {
          hierarchical: {
            direction: 'UD',
            sortMethod: 'directed',
            levelSeparation: 150,
            nodeSpacing: 150
          }
        },
        nodes: {
          borderWidth: 1,
          borderWidthSelected: 2,
          size: 25,
          font: {
            size: 14
          }
        },
        edges: {
          smooth: { type: 'cubicBezier' }
        },
        physics: {
          hierarchicalRepulsion: {
            centralGravity: 0.0,
            springLength: 150,
            springConstant: 0.01,
            nodeDistance: 180
          },
          solver: 'hierarchicalRepulsion'
        },
        interaction: {
          hover: true,
          tooltipDelay: 200
        }
      };
      
      const network = new Network(
        containerRef.current,
        { nodes: data.nodes, edges: data.edges },
        options
      );
      
      // Add event listeners
      network.on('click', params => {
        if (params.nodes.length > 0) {
          const nodeId = params.nodes[0];
          if (nodeId !== 'project') {
            const dependency = dependencies.find(dep => dep.name === nodeId);
            setSelectedDependency(dependency);
          } else {
            setSelectedDependency(null);
          }
        } else {
          setSelectedDependency(null);
        }
      });
      
      setNetworkInstance(network);
    }
    
    return () => {
      if (networkInstance) {
        networkInstance.destroy();
      }
    };
  }, [dependencies, showTransitive, maxDepth]);
  
  // Function to process transitive dependencies
  const processTransitiveDependencies = (
    parentName,
    dependencies,
    nodes,
    edges,
    processedNodes,
    currentLevel,
    maxLevel
  ) => {
    if (currentLevel > maxLevel) return;
    
    Object.keys(dependencies).forEach(depName => {
      const fullId = `${depName}_${currentLevel}`;
      
      if (!processedNodes.has(fullId)) {
        processedNodes.add(fullId);
        
        // Add node
        nodes.add({
          id: fullId,
          label: depName,
          title: `${depName}\n${dependencies[depName] || 'Unknown'}`,
          color: '#9CA3AF',
          shape: 'dot',
          size: 20 - (currentLevel * 3),
          level: currentLevel
        });
        
        // Add edge from parent to this dependency
        edges.add({
          from: parentName,
          to: fullId,
          arrows: 'to',
          color: { color: '#CBD5E1', opacity: 0.5 },
          width: 0.5
        });
        
        // If we have nested dependencies and haven't reached max depth,
        // process them recursively (in a real app, you'd need to fetch this data)
        // This is a simplified example, as we don't have nested dep data
      }
    });
  };
  
  return (
    <div className="dependency-graph">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold">Dependency Graph</h3>
        <div className="flex items-center space-x-4">
          <div className="flex items-center">
            <input
              type="checkbox"
              id="show-transitive"
              checked={showTransitive}
              onChange={() => setShowTransitive(!showTransitive)}
              className="mr-2"
            />
            <label htmlFor="show-transitive" className="text-sm flex items-center">
              <GitMerge size={16} className="mr-1" />
              Show Transitive Dependencies
            </label>
          </div>
          
          <div className="flex items-center">
            <Filter size={16} className="mr-1 text-gray-600" />
            <select
              value={maxDepth}
              onChange={(e) => setMaxDepth(parseInt(e.target.value))}
              className="border rounded p-1 text-sm"
            >
              <option value="1">Depth: 1</option>
              <option value="2">Depth: 2</option>
              <option value="3">Depth: 3</option>
              <option value="4">Depth: 4</option>
            </select>
          </div>
        </div>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-2">
        <div className="flex items-center p-2 bg-green-50 rounded">
          <div className="w-3 h-3 bg-green-500 rounded-full mr-2"></div>
          <span className="text-xs text-gray-700">Healthy</span>
        </div>
        <div className="flex items-center p-2 bg-yellow-50 rounded">
          <div className="w-3 h-3 bg-yellow-500 rounded-full mr-2"></div>
          <span className="text-xs text-gray-700">Moderate Health</span>
        </div>
        <div className="flex items-center p-2 bg-gray-50 rounded">
          <div className="w-3 h-3 bg-gray-400 rounded-full mr-2"></div>
          <span className="text-xs text-gray-700">Unknown Health</span>
        </div>
        <div className="flex items-center p-2 bg-red-50 rounded">
          <div className="w-3 h-3 bg-red-500 rounded-full mr-2"></div>
          <span className="text-xs text-gray-700">Deprecated</span>
        </div>
      </div>
      
      <div className="border rounded">
        <div 
          ref={containerRef} 
          className="h-96"
          style={{ background: "#fafafa" }}
        ></div>
      </div>
      
      {selectedDependency && (
        <div className="mt-4 p-4 border rounded bg-blue-50">
          <div className="flex items-start">
            <Package size={20} className="mr-2 text-blue-500 mt-1" />
            <div>
              <h4 className="font-medium">{selectedDependency.name}</h4>
              <div className="text-sm text-gray-600 mt-1">
                <div>Version: {selectedDependency.latest_version || 'Unknown'}</div>
                <div>Ecosystem: {selectedDependency.ecosystem}</div>
                {selectedDependency.description && (
                  <div className="mt-2">{selectedDependency.description}</div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DependencyGraph;