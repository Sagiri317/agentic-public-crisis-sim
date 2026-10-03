"""Strict input boundary, semantic identity and one compiled business graph."""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math


PROBABILITIES = {
    'information_error_rate', 'supplemental_check_effectiveness',
    'propagation_probability', 'local_verification_probability',
    'verification_effectiveness', 'detection_probability', 'false_alarm_probability',
    'execution_autonomy', 'rollback_success', 'review_sensitivity',
    'review_specificity', 'command_intercept_effectiveness',
    'command_error_probability', 'shock_probability',
}
POSITIVE_TIMES = {'horizon', 'deadline_window', 'recovery_delay',
                  'review_service_time', 'false_denial_hold', 'command_service_time'}
OPTIONS = {
    'information_policy': {'fast', 'balanced', 'integrated'},
    'verification_mode': {'none', 'critical', 'global'},
    'oversight': {'autonomy', 'full'},
    'review_scope': {'all', 'external', 'direct_control'},
    'review_priority': {'fifo', 'due_first', 'life_safety'},
    'command_structure': {'distributed', 'selective', 'centralized'},
    'shock_type': {'none', 'model', 'data', 'tool'},
    'shock_profile': {'abrupt', 'progressive'},
}
PARAMETER_FIELDS = PROBABILITIES | POSITIVE_TIMES | set(OPTIONS) | {
    'observation_level', 'automatic_isolation', 'initial_nodes', 'shock_time',
    'resource_groups', 'partition_seed', 'review_capacity', 'command_capacity',
}
FIXED_FIELDS = {'primary_contaminated_utility', 'deadline_grace', 'progressive_steps',
                'function_failure_threshold', 'information_policies',
                'life_safety_functions', 'command_agent', 'external_action_stages',
                'message_latency', 'edge_transmission_weight'}
STAGES = {'sensing', 'assessment', 'planning', 'execution', 'communication', 'coordination'}


def stable_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False)


def object_hash(value):
    return hashlib.sha256(stable_json(value).encode('utf-8')).hexdigest()


def _fields(value, expected, label):
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f'Invalid {label} fields; expected {sorted(expected)}')


def _number(value, label, lower=0, upper=None, integer=False, strict_lower=False):
    valid = type(value) is int if integer else type(value) in (int, float)
    if (not valid or not math.isfinite(value) or value < lower
            or (strict_lower and value == lower) or (upper is not None and value > upper)):
        raise ValueError(f'Invalid {label}: {value!r}')
    return value if integer else float(value)


def partition(users, kind, count, seed):
    ordered = sorted(users)
    if seed:
        ordered.sort(key=lambda name: (hashlib.sha256(
            f'partition|{seed}|{kind}|{name}'.encode('utf-8')).digest(), name))
    return sorted(sorted(ordered[j::count]) for j in range(count))


@dataclass
class Compiled:
    config: dict
    parameters: dict
    groups: list
    digest: str
    agents: list
    outgoing: list
    required: list
    supplemental: list
    external: list
    review_targets: list
    command_targets: list
    life_tier: list
    command_index: int
    function_weights: list
    function_criticality: list


def compile_config(config, resource_members=None):
    _fields(config, {'parameters', 'fixed', 'agents', 'functions', 'edges', 'resource_users'}, 'config')
    c = deepcopy(config)
    p, fixed = c['parameters'], c['fixed']
    _fields(p, PARAMETER_FIELDS, 'parameters')
    _fields(fixed, FIXED_FIELDS, 'fixed')
    for key in PROBABILITIES:
        p[key] = _number(p[key], key, upper=1)
    for key in POSITIVE_TIMES:
        _number(p[key], key, lower=1, integer=True)
    for key, choices in OPTIONS.items():
        if not isinstance(p[key], str) or p[key] not in choices:
            raise ValueError(f'Invalid {key}')
    for key in ('shock_time', 'partition_seed'):
        _number(p[key], key, integer=True)
    for key in ('resource_groups', 'command_capacity'):
        _number(p[key], key, lower=1, integer=True)
    if p['review_capacity'] != 'unlimited':
        _number(p['review_capacity'], 'review_capacity', lower=1, integer=True)
    _number(p['observation_level'], 'observation_level', upper=2, integer=True)
    if type(p['automatic_isolation']) is not bool:
        raise ValueError('automatic_isolation must be boolean')
    for key in ('primary_contaminated_utility', 'function_failure_threshold', 'edge_transmission_weight'):
        fixed[key] = _number(fixed[key], key, upper=1)
    for key in ('deadline_grace', 'progressive_steps', 'message_latency'):
        _number(fixed[key], key, lower=1, integer=True)
    _fields(fixed['information_policies'], {'fast', 'balanced', 'integrated'}, 'information_policies')
    for policy in fixed['information_policies'].values():
        _fields(policy, {'threshold', 'max_wait'}, 'information policy')
        policy['threshold'] = _number(policy['threshold'], 'threshold', upper=1)
        _number(policy['max_wait'], 'max_wait', integer=True)
    stages = fixed['external_action_stages']
    if not isinstance(stages, list) or not stages or any(not isinstance(s, str) or s not in STAGES for s in stages) or len(stages) != len(set(stages)):
        raise ValueError('Invalid external_action_stages')
    agents = c['agents']
    if not isinstance(agents, list) or not agents:
        raise ValueError('Nonempty agents required')
    for agent in agents:
        _fields(agent, {'id', 'name', 'stage', 'release', 'authority', 'criticality', 'reversibility'}, 'agent')
        if any(not isinstance(agent[k], str) or not agent[k] for k in ('id', 'name')) or not isinstance(agent['stage'], str) or agent['stage'] not in STAGES:
            raise ValueError('Invalid agent identity/stage')
        _number(agent['release'], 'release', integer=True)
        _number(agent['authority'], 'authority', upper=2, integer=True)
        for key in ('criticality', 'reversibility'):
            agent[key] = _number(agent[key], key, upper=1)
    agents.sort(key=lambda a: a['id'])
    ids = {a['id']: i for i, a in enumerate(agents)}
    if len(ids) != len(agents) or not isinstance(fixed['command_agent'], str) or fixed['command_agent'] not in ids:
        raise ValueError('Duplicate agent or unknown command_agent')
    initial = p['initial_nodes']
    if not isinstance(initial, list) or any(not isinstance(a, str) or a not in ids for a in initial) or len(initial) != len(set(initial)):
        raise ValueError('initial_nodes must be unique known IDs')
    p['initial_nodes'] = sorted(initial)
    functions = c['functions']
    if not isinstance(functions, list) or not functions:
        raise ValueError('Nonempty functions required')
    for function in functions:
        _fields(function, {'id', 'name', 'criticality', 'members'}, 'function')
        if any(not isinstance(function[k], str) or not function[k] for k in ('id', 'name')):
            raise ValueError('Invalid function identity')
        function['criticality'] = _number(function['criticality'], 'function criticality', upper=1, strict_lower=True)
        members = function['members']
        if not isinstance(members, dict) or not members:
            raise ValueError('Nonempty function members required')
        for name, value in members.items():
            if name not in ids:
                raise ValueError('Unknown function member')
            members[name] = _number(value, 'member weight', strict_lower=True)
        if not math.isfinite(sum(members.values())):
            raise ValueError('Nonfinite member total')
    functions.sort(key=lambda f: f['id'])
    fids = {f['id'] for f in functions}
    safety = fixed['life_safety_functions']
    if len(fids) != len(functions) or not isinstance(safety, list) or not safety or any(not isinstance(f, str) or f not in fids for f in safety) or len(set(safety)) != len(safety):
        raise ValueError('Duplicate function or invalid life_safety_functions')
    fixed['life_safety_functions'] = sorted(safety)
    fixed['external_action_stages'] = sorted(stages)
    n = len(agents)
    tier = [0] * n
    weights = []
    for function in functions:
        total = sum(function['members'].values())
        weights.append([(ids[name], value / total) for name, value in sorted(function['members'].items())])
        if function['id'] in safety:
            for name, value in function['members'].items():
                tier[ids[name]] = max(tier[ids[name]], 2 if value >= 2 else 1)
    outgoing, required, supplemental = ([[] for _ in agents] for _ in range(3))
    if not isinstance(c['edges'], list):
        raise ValueError('edges must be a list')
    seen = set()
    for edge in c['edges']:
        _fields(edge, {'source', 'target', 'role', 'verify'}, 'edge')
        if any(not isinstance(edge[k], str) for k in ('source', 'target', 'role')) or edge['source'] not in ids or edge['target'] not in ids or edge['role'] not in {'required', 'supplemental'} or type(edge['verify']) is not bool:
            raise ValueError('Invalid edge endpoint/role/verify')
        pair = edge['source'], edge['target']
        if pair in seen or pair[0] == pair[1]:
            raise ValueError('Duplicate/self edge')
        seen.add(pair)
    c['edges'].sort(key=lambda e: (e['source'], e['target']))
    for index, edge in enumerate(c['edges']):
        i, j = ids[edge['source']], ids[edge['target']]
        outgoing[i].append(index)
        (required if edge['role'] == 'required' else supplemental)[j].append(index)
    indegree = list(map(len, required))
    ready = [i for i, degree in enumerate(indegree) if not degree]
    visited = 0
    while ready:
        i = ready.pop()
        visited += 1
        for e in outgoing[i]:
            if c['edges'][e]['role'] == 'required':
                j = ids[c['edges'][e]['target']]
                indegree[j] -= 1
                if not indegree[j]:
                    ready.append(j)
    if visited != n:
        raise ValueError('Required information must be acyclic')
    external = [a['stage'] in stages for a in agents]
    _fields(c['resource_users'], {'model', 'data', 'tool'}, 'resource_users')
    for kind, users in c['resource_users'].items():
        if not isinstance(users, list) or not users or any(not isinstance(name, str) or name not in ids for name in users) or len(users) != len(set(users)):
            raise ValueError('Invalid resource users')
        if kind == 'tool' and any(not external[ids[name]] for name in users):
            raise ValueError('Tool users must execute external actions')
        c['resource_users'][kind] = sorted(users)
    kind = p['shock_type']
    if kind != 'none' and p['resource_groups'] > len(c['resource_users'][kind]):
        raise ValueError('K exceeds resource users')
    if resource_members is None:
        groups = partition(c['resource_users'][kind], kind, p['resource_groups'], p['partition_seed']) if kind != 'none' else []
    else:
        if not isinstance(resource_members, list) or any(not isinstance(group, list) or not group or any(not isinstance(name, str) for name in group) for group in resource_members):
            raise ValueError('Invalid materialized resource groups')
        groups = sorted(sorted(group) for group in resource_members)
        members = [name for group in groups for name in group]
        expected = c['resource_users'][kind] if kind != 'none' else []
        if sorted(members) != expected or len(members) != len(set(members)) or kind != 'none' and len(groups) != p['resource_groups']:
            raise ValueError('Materialized resource groups must partition all resource users')
    review_targets = [p['oversight'] == 'full' and (p['review_scope'] == 'all' or external[i] and (p['review_scope'] == 'external' or a['authority'] == 2)) for i, a in enumerate(agents)]
    command_targets = [external[i] and (p['command_structure'] == 'centralized' or p['command_structure'] == 'selective' and tier[i] == 2) and i != ids[fixed['command_agent']] for i in range(n)]
    active = dict(p)
    if kind == 'none':
        for key in ('shock_probability', 'shock_time', 'shock_profile'):
            del active[key]
    for key in ('resource_groups', 'partition_seed'):
        del active[key]
    if p['oversight'] == 'autonomy':
        for key in ('review_scope', 'review_priority', 'review_capacity', 'review_service_time', 'review_sensitivity', 'review_specificity', 'false_denial_hold'):
            del active[key]
    if p['command_structure'] == 'distributed':
        for key in ('command_capacity', 'command_service_time', 'command_intercept_effectiveness', 'command_error_probability'):
            del active[key]
    if not p['automatic_isolation']:
        for key in ('observation_level', 'detection_probability', 'false_alarm_probability', 'recovery_delay', 'rollback_success'):
            del active[key]
    if p['verification_mode'] == 'none':
        del active['verification_effectiveness']
    identity = dict(c, parameters=active)
    for section in ('agents', 'functions'):
        identity[section] = [{key: value for key, value in item.items() if key != 'name'}
                             for item in c[section]]
    del identity['resource_users']
    identity['resource_members'] = groups
    return Compiled(c, active, groups, object_hash(identity), agents, outgoing,
                    required, supplemental, external, review_targets, command_targets,
                    tier, ids[fixed['command_agent']], weights,
                    [f['criticality'] for f in functions])
