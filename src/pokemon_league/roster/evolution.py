"""Deterministic, fail-closed evolution-family metadata assignment."""

from __future__ import annotations

import heapq
from collections import deque
from collections.abc import Sequence

from pokemon_league.schemas.roster import (
    Combatant,
    EvolutionEdge,
    ExcludedForm,
    RosterBuild,
)


def assign_evolution_metadata(
    build: RosterBuild, edges: Sequence[EvolutionEdge]
) -> RosterBuild:
    """Assign deterministic family IDs and longest-path stages to every form.

    Edges operate on represented base-species nodes.  All forms of a node receive
    the same family and stage, while separate regional nodes stay disconnected
    until a supplied edge explicitly joins them.
    """
    combatants, exclusions = _revalidate_build(build)
    validated_edges = tuple(
        EvolutionEdge.model_validate(edge.model_dump()) for edge in edges
    )
    nodes = {combatant.base_species_id for combatant in combatants}
    adjacency, reverse = _validated_graph(nodes, validated_edges)
    components = _weak_components(nodes, adjacency, reverse)
    metadata = _component_metadata(components, adjacency, reverse)
    updated = tuple(
        combatant.model_copy(
            update={
                "evolution_family_id": metadata[combatant.base_species_id][0],
                "evolution_stage": metadata[combatant.base_species_id][1],
            }
        )
        for combatant in sorted(combatants, key=canonical_sort_key)
    )
    return RosterBuild(combatants=updated, exclusions=exclusions)


def canonical_sort_key(combatant: Combatant) -> tuple[int, int, str]:
    """Return the project-wide canonical combatant traversal key."""
    return (
        combatant.national_number if combatant.national_number is not None else 9999,
        combatant.official_form_order,
        combatant.combatant_id,
    )


def _revalidate_build(
    build: RosterBuild,
) -> tuple[tuple[Combatant, ...], tuple[ExcludedForm, ...]]:
    """Reject model-copy bypasses at this public derived-data boundary."""
    combatants = tuple(
        Combatant.model_validate(combatant.model_dump()) for combatant in build.combatants
    )
    exclusions = tuple(
        ExcludedForm.model_validate(exclusion.model_dump())
        for exclusion in build.exclusions
    )
    return combatants, exclusions


def _validated_graph(
    nodes: set[str], edges: Sequence[EvolutionEdge]
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Construct a simple directed graph after all fail-closed edge checks."""
    adjacency: dict[str, set[str]] = {node: set() for node in nodes}
    reverse: dict[str, set[str]] = {node: set() for node in nodes}
    seen: set[tuple[str, str]] = set()
    for edge in edges:
        predecessor = edge.predecessor_species_id
        successor = edge.successor_species_id
        if predecessor == successor:
            raise ValueError(f"self evolution edge: {predecessor}")
        pair = (predecessor, successor)
        if pair in seen:
            raise ValueError(f"duplicate evolution edge: {predecessor} -> {successor}")
        seen.add(pair)
        unknown = sorted({predecessor, successor} - nodes)
        if unknown:
            noun = "node" if len(unknown) == 1 else "nodes"
            raise ValueError(f"unknown evolution {noun}: {', '.join(unknown)}")
        adjacency[predecessor].add(successor)
        reverse[successor].add(predecessor)

    _raise_for_cycle(nodes, adjacency, reverse)
    return adjacency, reverse


def _raise_for_cycle(
    nodes: set[str], adjacency: dict[str, set[str]], reverse: dict[str, set[str]]
) -> None:
    """Fail closed for a directed cycle with a stable cyclic-component diagnostic."""
    indegree = {node: len(reverse[node]) for node in nodes}
    ready = [node for node, degree in indegree.items() if degree == 0]
    heapq.heapify(ready)
    processed: set[str] = set()
    while ready:
        node = heapq.heappop(ready)
        processed.add(node)
        for successor in sorted(adjacency[node]):
            indegree[successor] -= 1
            if indegree[successor] == 0:
                heapq.heappush(ready, successor)
    remaining = nodes - processed
    if not remaining:
        return

    for node in sorted(remaining):
        forward = _reachable(node, adjacency, remaining)
        backward = _reachable(node, reverse, remaining)
        component = forward & backward
        if len(component) > 1:
            raise ValueError(f"evolution cycle: {', '.join(sorted(component))}")
    raise ValueError(f"evolution cycle: {', '.join(sorted(remaining))}")


def _reachable(
    start: str, graph: dict[str, set[str]], allowed: set[str]
) -> set[str]:
    """Return the directed reachability set using an iterative traversal."""
    found = {start}
    pending = [start]
    while pending:
        node = pending.pop()
        for neighbor in graph[node]:
            if neighbor in allowed and neighbor not in found:
                found.add(neighbor)
                pending.append(neighbor)
    return found


def _weak_components(
    nodes: set[str], adjacency: dict[str, set[str]], reverse: dict[str, set[str]]
) -> tuple[tuple[str, ...], ...]:
    """Return lexically ordered weak components without altering directed edges."""
    unvisited = set(nodes)
    components: list[tuple[str, ...]] = []
    while unvisited:
        start = min(unvisited)
        component = {start}
        pending: deque[str] = deque([start])
        unvisited.remove(start)
        while pending:
            node = pending.popleft()
            for neighbor in adjacency[node] | reverse[node]:
                if neighbor in unvisited:
                    unvisited.remove(neighbor)
                    component.add(neighbor)
                    pending.append(neighbor)
        components.append(tuple(sorted(component)))
    return tuple(components)


def _component_metadata(
    components: Sequence[tuple[str, ...]],
    adjacency: dict[str, set[str]],
    reverse: dict[str, set[str]],
) -> dict[str, tuple[str, int]]:
    """Calculate each component's canonical family ID and longest-path stages."""
    metadata: dict[str, tuple[str, int]] = {}
    for component in components:
        component_nodes = set(component)
        roots = sorted(node for node in component if not (reverse[node] & component_nodes))
        family_id = f"{roots[0]}-family"
        stages = {node: 1 for node in roots}
        indegree = {
            node: len(reverse[node] & component_nodes) for node in component_nodes
        }
        ready = list(roots)
        heapq.heapify(ready)
        while ready:
            node = heapq.heappop(ready)
            for successor in sorted(adjacency[node] & component_nodes):
                stages[successor] = max(stages.get(successor, 1), stages[node] + 1)
                indegree[successor] -= 1
                if indegree[successor] == 0:
                    heapq.heappush(ready, successor)
        metadata.update(
            {node: (family_id, stages[node]) for node in sorted(component_nodes)}
        )
    return metadata
