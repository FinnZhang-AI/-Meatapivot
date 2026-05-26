"""DAG dependency graph for Ontology types with cycle detection.

P0-ONT-01: Kahn topological sorting + BFS impact set + cycle detection.
"""

from collections import defaultdict, deque
from typing import Dict, List, Optional, Set, Tuple
from uuid import UUID


class OntologyDAG:
    """Directed Acyclic Graph for Ontology type dependencies.
    
    Nodes: ObjectType IDs
    Edges: dependency relationships (e.g., interface implementation,
            link type source/target, action target)
    """
    
    def __init__(self):
        # Adjacency list: node -> set of dependents (nodes that depend on this node)
        self._dependents: Dict[UUID, Set[UUID]] = defaultdict(set)
        # Reverse: node -> set of dependencies (nodes this node depends on)
        self._dependencies: Dict[UUID, Set[UUID]] = defaultdict(set)
        self._nodes: Set[UUID] = set()
    
    def add_node(self, node_id: UUID) -> None:
        """Add a node to the graph."""
        self._nodes.add(node_id)
    
    def add_edge(self, from_node: UUID, to_node: UUID) -> None:
        """Add edge: from_node is depended upon by to_node.
        
        to_node depends on from_node.
        """
        self._nodes.add(from_node)
        self._nodes.add(to_node)
        self._dependents[from_node].add(to_node)
        self._dependencies[to_node].add(from_node)
    
    def remove_edge(self, from_node: UUID, to_node: UUID) -> None:
        """Remove an edge from the graph."""
        self._dependents[from_node].discard(to_node)
        self._dependencies[to_node].discard(from_node)
    
    def remove_node(self, node_id: UUID) -> None:
        """Remove a node and all its edges."""
        self._nodes.discard(node_id)
        # Remove from dependents of others
        for dep in list(self._dependencies[node_id]):
            self._dependents[dep].discard(node_id)
        # Remove from dependencies of others
        for dep in list(self._dependents[node_id]):
            self._dependencies[dep].discard(node_id)
        del self._dependents[node_id]
        del self._dependencies[node_id]
    
    def find_cycle(self) -> Optional[List[UUID]]:
        """Find a cycle in the graph using DFS. Returns the cycle path or None.
        
        P0-ONT-01: Returns cycle path like [A, B, C, A] instead of generic 500.
        """
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {node: WHITE for node in self._nodes}
        parent = {}
        
        def dfs(node: UUID) -> Optional[List[UUID]]:
            color[node] = GRAY
            
            for dependent in self._dependents[node]:
                if color[dependent] == GRAY:
                    # Found cycle - reconstruct path
                    cycle = [dependent]
                    current = node
                    while current != dependent:
                        cycle.append(current)
                        current = parent.get(current, dependent)
                    cycle.append(dependent)
                    cycle.reverse()
                    return cycle
                elif color[dependent] == WHITE:
                    parent[dependent] = node
                    result = dfs(dependent)
                    if result:
                        return result
            
            color[node] = BLACK
            return None
        
        for node in self._nodes:
            if color[node] == WHITE:
                result = dfs(node)
                if result:
                    return result
        
        return None
    
    def topological_sort(self) -> Tuple[List[UUID], Optional[List[UUID]]]:
        """Kahn's algorithm for topological sorting.
        
        Returns: (sorted_nodes, cycle_path)
        If cycle exists, sorted_nodes is empty and cycle_path is populated.
        """
        # Calculate in-degrees
        in_degree = {node: 0 for node in self._nodes}
        for node in self._nodes:
            for dependent in self._dependents[node]:
                in_degree[dependent] += 1
        
        # Queue nodes with no dependencies
        queue = deque([node for node, deg in in_degree.items() if deg == 0])
        sorted_nodes = []
        
        while queue:
            node = queue.popleft()
            sorted_nodes.append(node)
            
            for dependent in self._dependents[node]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
        
        if len(sorted_nodes) != len(self._nodes):
            cycle = self.find_cycle()
            return [], cycle
        
        return sorted_nodes, None
    
    def get_impact_set(self, node_id: UUID) -> Set[UUID]:
        """BFS to find all nodes that depend on node_id (directly or transitively).
        
        Used for incremental compilation: if node A changes, recompile all in impact set.
        """
        impact = set()
        queue = deque([node_id])
        visited = {node_id}
        
        while queue:
            current = queue.popleft()
            for dependent in self._dependents[current]:
                if dependent not in visited:
                    visited.add(dependent)
                    impact.add(dependent)
                    queue.append(dependent)
        
        return impact
    
    def get_dependency_chain(self, node_id: UUID) -> List[UUID]:
        """Get all dependencies of a node in topological order."""
        chain = []
        visited = set()
        queue = deque([node_id])
        
        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            if current != node_id:
                chain.append(current)
            for dep in self._dependencies[current]:
                if dep not in visited:
                    queue.append(dep)
        
        # Return in dependency order (dependencies first)
        chain.reverse()
        return chain
    
    def to_dict(self) -> Dict[str, List[str]]:
        """Serialize graph to dict for debugging."""
        return {
            "nodes": [str(n) for n in self._nodes],
            "edges": [
                {"from": str(src), "to": str(dst)}
                for src, dsts in self._dependents.items()
                for dst in dsts
            ],
        }
