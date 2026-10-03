"""Generate the protocol catalog once, then execute its unique configurations."""
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from itertools import product
from pathlib import Path
import re
import sys

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from agent_crisis_sim.config import compile_config, object_hash, stable_json, _fields, _number
from agent_crisis_sim.simulation import simulate, VECTOR_METRICS, SCALAR_METRICS


def base_config():
    return yaml.load((ROOT / 'configs/base.yaml').read_text(encoding='utf-8'), Loader=yaml.CSafeLoader)


def protocol():
    text = (ROOT / 'docs/experiment_protocol.md').read_text(encoding='utf-8')
    match = re.search(r'<!-- BEGIN EXPERIMENT SPEC -->\s*```yaml\n(.*?)```\s*<!-- END EXPERIMENT SPEC -->', text, re.S)
    if match is None:
        raise ValueError('Final experiment specification missing')
    spec = yaml.load(match.group(1), Loader=yaml.CSafeLoader)
    if set(spec) != {'sampling', 'families', 'primary_effects', 'evaluation_views'}:
        raise ValueError('Unexpected experiment specification')
    sampling = spec['sampling']
    _fields(sampling, {'pilot_runs', 'formal_runs', 'bootstrap_repetitions', 'smoke_runs', 'smoke_bootstrap', 'seeds'}, 'sampling')
    for key in set(sampling) - {'seeds'}:
        _number(sampling[key], key, lower=2, integer=True)
    _fields(sampling['seeds'], {'pilot', 'formal', 'bootstrap', 'smoke'}, 'seeds')
    for value in sampling['seeds'].values():
        _number(value, 'master_seed', integer=True)
    if not isinstance(spec['evaluation_views'], dict) or 'primary' not in spec['evaluation_views']:
        raise ValueError('Primary evaluation view required')
    for view in spec['evaluation_views'].values():
        _fields(view, {'members', 'function_criticality', 'timeliness', 'compromised_utility'}, 'evaluation view')
        if view['members'] not in {'configured', 'equal', 'agent_criticality'} or view['function_criticality'] not in {'configured', 'equal'} or view['timeliness'] not in {'hard', 'linear_grace'}:
            raise ValueError('Invalid evaluation view')
        if view['compromised_utility'] != 'base':
            _number(view['compromised_utility'], 'compromised utility', upper=1)
    if not isinstance(spec['families'], list) or not spec['families'] or len({f['id'] for f in spec['families']}) != len(spec['families']):
        raise ValueError('Unique nonempty experiment families required')
    if not isinstance(spec['primary_effects'], list) or len({e['id'] for e in spec['primary_effects']}) != len(spec['primary_effects']):
        raise ValueError('Unique primary effects required')
    for effect in spec['primary_effects']:
        _fields(effect, {'id', 'rq', 'statistic', 'terms'}, 'primary effect')
        if effect['rq'] not in {'RQ1', 'RQ2', 'RQ3'} or effect['statistic'] not in {'mean', 'ES95'} or not isinstance(effect['terms'], list) or not effect['terms']:
            raise ValueError('Invalid primary effect')
        for term in effect['terms']:
            _fields(term, {'coefficient', 'select'}, 'primary term')
            if not isinstance(term['select'], dict):
                raise ValueError('Select must be a complete patch')
    return spec


def normalize_terms(terms, known):
    merged = defaultdict(float)
    for cell, coefficient in terms:
        if cell not in known or type(coefficient) not in (int, float) or not np.isfinite(coefficient):
            raise ValueError('Unknown reference or nonfinite coefficient')
        merged[cell] += coefficient
    result = [[cell, coefficient] for cell, coefficient in sorted(merged.items()) if coefficient != 0]
    if sum(coefficient for _, coefficient in result) != 0:
        raise ValueError('Contrast must have zero-sum coefficients')
    return result


def build_catalog(spec=None, base=None):
    spec = protocol() if spec is None else spec
    base = base_config() if base is None else base
    compile_config(base)
    cells, roles, contrasts, estimands = {}, [], {}, {}
    family_roles = defaultdict(list)
    full_parameters = {}
    for family in spec['families']:
        if set(family) != {'id', 'rq', 'tier', 'fixed', 'axes'} or family['rq'] not in {'RQ1', 'RQ2', 'RQ3'} or family['tier'] not in {'primary', 'secondary', 'sensitivity'} or not isinstance(family['fixed'], dict) or not isinstance(family['axes'], dict) or any(not isinstance(axis, list) or not axis for axis in family['axes'].values()):
            raise ValueError('Invalid family')
        keys = sorted(family['axes'])
        for values in product(*(family['axes'][key] for key in keys)):
            axes = dict(zip(keys, values))
            patch = family['fixed'] | axes
            if 'shock_type' not in patch or 'initial_nodes' not in patch:
                raise ValueError('Family must explicitly specify its exogenous scenario')
            config = deepcopy(base)
            if set(patch) - set(config['parameters']):
                raise ValueError('Unknown protocol parameter')
            config['parameters'].update(patch)
            m = compile_config(config)
            cell_id = m.digest
            cells.setdefault(cell_id, dict(id=cell_id, parameters=m.parameters, groups=m.groups))
            role_id = family['id'] + ':' + object_hash(axes)[:16]
            role = dict(id=role_id, family=family['id'], rq=family['rq'],
                        tier=family['tier'], axes=axes, cell_id=cell_id)
            roles.append(role)
            family_roles[family['id']].append(role)
            full_parameters[role_id] = config['parameters']

    def resolve(patch):
        config = deepcopy(base)
        if set(patch) - set(config['parameters']):
            raise ValueError('Unknown select parameter')
        config['parameters'].update(patch)
        cell = compile_config(config).digest
        if cell not in cells:
            raise ValueError('Registered term not generated by a family: ' + stable_json(patch))
        return cell

    function_metrics = [f['id'] for f in base['functions']]
    all_metrics = ['service_deficit'] + function_metrics + list(SCALAR_METRICS) + ['service_blocking', 'worst_function_deficit']
    primary_views = ['primary', 'grace', 'equal_function', 'low_compromised_utility', 'high_compromised_utility']

    def register(purpose, rq, tier, terms, kind='direct', dims=None, statistics=('mean',), metrics=None, views=('primary',)):
        terms = normalize_terms(terms, cells)
        key = object_hash(terms)
        contrast = contrasts.setdefault(key, dict(id=key, terms=terms, structural_zero=not terms, roles={}))
        role = dict(purpose=purpose, rq=rq, tier=tier, kind=kind, dimensions=dims or {})
        role_id = object_hash(role)
        contrast['roles'][role_id] = role
        for view, metric, statistic in product(views, metrics or all_metrics, statistics):
            signature = dict(contrast_id=key, view=view, metric=metric, statistic=statistic)
            identity = object_hash(signature)
            estimand = estimands.setdefault(identity, dict(id=identity, **signature, role_ids=[]))
            if role_id not in estimand['role_ids']:
                estimand['role_ids'].append(role_id)

    def direct(purpose, role, target_patch, reference_patch, *, statistics=('mean',), metrics=None):
        register(purpose, role['rq'], 'secondary' if role['tier'] == 'primary' else role['tier'],
                 [(resolve(target_patch), 1), (resolve(reference_patch), -1)],
                 dims=dict(family=role['family'], **role['axes']), statistics=statistics, metrics=metrics)

    def interaction(purpose, rq, target, reference, dims=None):
        register(purpose, rq, 'secondary', target + [(cell, -coef) for cell, coef in reference],
                 'interaction', dims)

    for effect in spec['primary_effects']:
        terms = [(resolve(term['select']), term['coefficient']) for term in effect['terms']]
        kind = 'interaction' if len(effect['terms']) == 4 else 'direct'
        register(effect['id'], effect['rq'], 'primary', terms, kind,
                 statistics=(effect['statistic'],), metrics=['service_deficit'] + [f['id'] for f in base['functions']], views=primary_views)
    for role in roles:
        family, axes = role['family'], role['axes']
        p = full_parameters[role['id']]
        if family == 'position':
            continue
        if family in {'dependency', 'dependency_partition'}:
            if p['resource_groups'] == 1:
                continue
            grid = sorted(next(f for f in spec['families'] if f['id'] == 'dependency')['axes']['resource_groups'])
            previous = grid[grid.index(p['resource_groups']) - 1] if family == 'dependency' else grid[0]
            ref = p | dict(resource_groups=previous, partition_seed=0)
            direct('dependency', role, p, ref, metrics=['service_deficit', 'ever_compromised_count', 'wrong_actions', 'worst_function_deficit'] + function_metrics)
            direct('dependency', role, p, ref, statistics=('ES95',), metrics=['service_deficit'])
        elif family == 'fixed_budget':
            grid = sorted(next(f for f in spec['families'] if f['id'] == family)['axes']['monitoring_offset'])
            for offset in grid[:grid.index(p['monitoring_offset'])]:
                ref = p | dict(monitoring_offset=offset)
                direct('fixed_budget', role, p, ref)
                direct('fixed_budget', role, p, ref, statistics=('ES95',), metrics=['service_deficit'] + function_metrics)
        elif family == 'oversight_capacity':
            direct('oversight_capacity', role, p, p | dict(oversight='autonomy'))
        elif family == 'observation':
            if p['automatic_isolation']:
                direct('isolation', role, p, p | dict(automatic_isolation=False))
            if p['shock_profile'] == 'progressive':
                direct('profile', role, p, p | dict(shock_profile='abrupt'))
        elif family == 'detection':
            direct('detection_combination', role, p, p | dict(automatic_isolation=False, detection_probability=base['parameters']['detection_probability'], false_alarm_probability=base['parameters']['false_alarm_probability']))
            for field in ('detection_probability', 'false_alarm_probability'):
                grid = sorted(next(f for f in spec['families'] if f['id'] == family)['axes'][field])
                index = grid.index(p[field])
                if index:
                    direct(field, role, p, p | {field: grid[index - 1]})
        elif family in {'verification', 'verification_quality'}:
            if family == 'verification' and p['verification_mode'] != 'none':
                direct('verification', role, p, p | dict(verification_mode='none'))
            if family == 'verification' and p['verification_mode'] == 'critical':
                direct('critical_global', role, p, p | dict(verification_mode='global'))
            if p['initial_nodes'] == ['A04'] and p['verification_mode'] != 'none':
                grid = sorted({base['parameters']['verification_effectiveness']} | {v for f in spec['families'] if f['id'] == 'verification_quality' for v in f['axes']['verification_effectiveness']})
                index = grid.index(p['verification_effectiveness'])
                if index:
                    direct('verification_quality', role, p, p | dict(verification_effectiveness=grid[index - 1]))
        elif family in {'human', 'review_sensitivity', 'review_specificity', 'review_duration', 'execution', 'horizon'}:
            if p['oversight'] == 'full':
                direct('human', role, p, p | dict(oversight='autonomy'))
            if family.startswith('review_'):
                field = 'review_service_time' if family == 'review_duration' else family
                direct(family, role, p, p | {field: base['parameters'][field]})
            if family == 'horizon' and p['oversight'] == 'full':
                target = [(resolve(p | dict(oversight='full')), 1), (resolve(p | dict(oversight='autonomy')), -1)]
                center = [(resolve(p | dict(horizon=base['parameters']['horizon'], oversight='full')), 1), (resolve(p | dict(horizon=base['parameters']['horizon'], oversight='autonomy')), -1)]
                interaction('window_dependence', 'RQ3', target, center, axes)
        elif family == 'triage':
            if p['review_priority'] != 'fifo':
                direct('triage', role, p, p | dict(review_priority='fifo'))
        elif family in {'command', 'command_with_human', 'command_capacity_quality'}:
            if p['command_structure'] != 'distributed':
                direct('command', role, p, p | dict(command_structure='distributed'))
            if p['command_structure'] == 'centralized':
                direct('centralized_selective', role, p, p | dict(command_structure='selective'))
            if family == 'command_capacity_quality':
                capacity_grid = sorted(next(f for f in spec['families'] if f['id'] == family)['axes']['command_capacity'])
                quality_grid = sorted(next(f for f in spec['families'] if f['id'] == family)['axes']['command_intercept_effectiveness'])
                if p['command_capacity'] == capacity_grid[-1]:
                    direct('command_capacity', role, p, p | dict(command_capacity=capacity_grid[0]))
                index = quality_grid.index(p['command_intercept_effectiveness'])
                if index:
                    direct('command_quality', role, p, p | dict(command_intercept_effectiveness=quality_grid[index - 1]))
        elif family == 'information':
            policies = ['fast', 'balanced', 'integrated']
            for ref in policies[:policies.index(p['information_policy'])]:
                direct('information', role, p, p | dict(information_policy=ref))
            if p['oversight'] == 'full':
                direct('human', role, p, p | dict(oversight='autonomy'))
        elif family == 'review_scope':
            if p['review_scope'] != 'all':
                direct('review_scope', role, p, p | dict(review_scope='all'))
        elif family in {'information_error', 'supplemental_check'} and p['information_policy'] == 'integrated':
            field = 'information_error_rate' if family == 'information_error' else 'supplemental_check_effectiveness'
            direct(family, role, p, p | dict(information_policy='fast'))
            target = [(resolve(p), 1), (resolve(p | dict(information_policy='fast')), -1)]
            center = [(resolve(p | {field: base['parameters'][field]}), 1), (resolve(p | {field: base['parameters'][field], 'information_policy': 'fast'}), -1)]
            interaction(family + '_interaction', 'RQ3', target, center, axes)
        else:
            if family not in {'information_error', 'supplemental_check'}:
                raise ValueError('Unconsumed family: ' + family)

    observation = next(f for f in spec['families'] if f['id'] == 'observation')['fixed']
    for profile in ('abrupt', 'progressive'):
        terms = []
        for level, coef in ((2, 1), (0, -1)):
            for isolated, sign in ((True, 1), (False, -1)):
                terms.append((resolve(observation | dict(shock_profile=profile, observation_level=level, automatic_isolation=isolated)), coef * sign))
        register('observation_interaction', 'RQ2', 'secondary', terms, 'interaction', dict(profile=profile))
    for level in (0, 2):
        terms = []
        for profile, coef in (('progressive', 1), ('abrupt', -1)):
            for isolated, sign in ((True, 1), (False, -1)):
                terms.append((resolve(observation | dict(shock_profile=profile, observation_level=level, automatic_isolation=isolated)), coef * sign))
        register('profile_interaction', 'RQ2', 'secondary', terms, 'interaction', dict(observation_level=level))
    triage = next(f for f in spec['families'] if f['id'] == 'triage')['fixed']
    capacities = sorted(next(f for f in spec['families'] if f['id'] == 'triage')['axes']['review_capacity'])
    for priority in ('due_first', 'life_safety'):
        terms = [(resolve(triage | dict(deadline_window=5, review_capacity=cap, review_priority=policy)), a * b)
                 for cap, a in ((capacities[0], 1), (capacities[1], -1))
                 for policy, b in ((priority, 1), ('fifo', -1))]
        register('triage_capacity_interaction', 'RQ3', 'secondary', terms, 'interaction', dict(priority=priority))
    information = next(f for f in spec['families'] if f['id'] == 'information')['fixed']
    terms = [(resolve(information | dict(oversight='full', deadline_window=d, information_policy=policy)), a * b)
             for d, a in ((2, 1), (10, -1)) for policy, b in (('integrated', 1), ('fast', -1))]
    register('information_human_interaction', 'RQ3', 'secondary', terms, 'interaction')

    # Level records are registered too; analysis does not choose metrics or comparisons.
    for cell in sorted(cells):
        for metric in all_metrics:
            signature = dict(cell_id=cell, metric=metric, view='primary', statistic='mean')
            estimands[object_hash(signature)] = dict(id=object_hash(signature), **signature, role_ids=[])
        for metric in ['service_deficit'] + [f['id'] for f in base['functions']]:
            signature = dict(cell_id=cell, metric=metric, view='primary', statistic='ES95')
            estimands[object_hash(signature)] = dict(id=object_hash(signature), **signature, role_ids=[])
    for estimand in estimands.values():
        estimand['role_ids'].sort()
    for contrast in contrasts.values():
        contrast['roles'] = dict(sorted(contrast['roles'].items()))
    return dict(sampling=spec['sampling'], evaluation_views=spec['evaluation_views'],
                cells=[cells[key] for key in sorted(cells)], roles=sorted(roles, key=lambda r: r['id']),
                contrasts=[contrasts[key] for key in sorted(contrasts)],
                estimands=[estimands[key] for key in sorted(estimands)],
                position=dict(roles=sorted(r['id'] for r in family_roles['position']),
                              views=['primary', 'equal_member', 'agent_criticality']))


def _estimand_roles(estimand, contrasts):
    return [contrasts[estimand['contrast_id']]['roles'][key] for key in estimand['role_ids']]


def configuration(cell, base=None):
    config = base_config() if base is None else deepcopy(base)
    config['parameters'].update(cell['parameters'])
    if cell['parameters']['shock_type'] != 'none':
        config['parameters']['resource_groups'] = len(cell['groups'])
    return compile_config(config, cell['groups'])


def validate_python():
    if sys.version_info[:2] != (3, 12):
        raise ValueError('Scientific reproduction requires Python 3.12')


def validate_raw(raw, runs, model):
    if set(raw) != {*VECTOR_METRICS, *SCALAR_METRICS, 'run_index'} or not np.issubdtype(raw['run_index'].dtype, np.integer) or not np.array_equal(raw['run_index'], np.arange(runs)):
        raise ValueError('Invalid raw schema/run index')
    n, horizon = len(model.agents), model.parameters['horizon']
    for key in VECTOR_METRICS:
        if raw[key].shape != (runs, n):
            raise ValueError('Invalid raw vector dimensions')
    for key in SCALAR_METRICS:
        if raw[key].shape != (runs,):
            raise ValueError('Invalid raw scalar dimensions')
    if any(not np.isfinite(value).all() for value in raw.values()):
        raise ValueError('Nonfinite raw')
    for mode in ('hard', 'grace'):
        b, c = raw['base_deficit_' + mode], raw['compromised_weight_' + mode]
        if (b < 0).any() or (c < 0).any() or (b + c > horizon + 1e-12).any():
            raise ValueError('Service integral bounds violated')
    blocking = sum(raw[key + '_blocking'] for key in ('information', 'review', 'denial', 'command', 'isolation'))
    if (blocking > n * horizon).any() or any((raw[key] < 0).any() for key in SCALAR_METRICS):
        raise ValueError('Invalid scalar/blocking bounds')
    for key in ('mean_information_coverage', 'mean_clean_information_fraction'):
        if (raw[key] > 1).any():
            raise ValueError('Invalid coverage bounds')
    if (raw['mean_clean_information_fraction'] > raw['mean_information_coverage'] + 1e-12).any():
        raise ValueError('Clean coverage exceeds observed coverage')
    for key in ('ever_compromised_count', 'wrong_actions', 'unfinished_tasks', 'active_harms_at_horizon', 'deadline_misses'):
        if (raw[key] > n).any():
            raise ValueError('Invalid task/node count')
    count_metrics = set(SCALAR_METRICS) - {'function_failure_time', 'mean_information_coverage', 'mean_clean_information_fraction'}
    if any(not np.equal(raw[key], np.floor(raw[key])).all() for key in count_metrics):
        raise ValueError('Noninteger count metric')
    if ((raw['wrong_actions'] > sum(model.external)).any()
            or (raw['human_review_load'] > sum(model.review_targets)).any()
            or (raw['command_review_load'] > sum(model.command_targets)).any()
            or (raw['completed_reviews'] > raw['human_review_load']).any()
            or (raw['false_review_denials'] > raw['completed_reviews']).any()
            or (raw['review_queue_time'] > n * horizon).any()
            or (raw['critical_review_queue_time'] > 2 * raw['review_queue_time']).any()
            or (raw['true_detections'] + raw['false_isolations'] > raw['monitoring_requests']).any()
            or (raw['monitoring_requests'] > n * horizon).any()
            or (raw['active_harms_at_horizon'] > raw['wrong_actions']).any()
            or (raw['function_failure_time'] > horizon * sum(model.function_criticality) + 1e-9).any()):
        raise ValueError('Task/service accounting bounds violated')
    if model.parameters['automatic_isolation'] and model.parameters['monitoring_offset'] is not None:
        expected = sum(a['release'] + model.parameters['monitoring_offset'] < horizon for a in model.agents)
        if not (raw['monitoring_requests'] == expected).all():
            raise ValueError('Fixed-budget monitoring request count violated')


def run_cell(task):
    model, runs, master, output = task
    rows = [simulate(model, master, index) for index in range(runs)]
    raw = {key: np.asarray([row[key] for row in rows], dtype=float) for key in (*VECTOR_METRICS, *SCALAR_METRICS)}
    raw['run_index'] = np.arange(runs, dtype=np.int64)
    validate_raw(raw, runs, model)
    path = Path(output) / 'raw' / (model.digest + '.npz')
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **raw)


def load_raw(path):
    with np.load(path, allow_pickle=False) as file:
        return {key: file[key] for key in file.files}


def execute(output, runs, master, workers, models):
    tasks = [(model, runs, master, str(output)) for model in models.values()]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for index, _ in enumerate(pool.map(run_cell, tasks), 1):
            if index % 10 == 0 or index == len(tasks):
                print(f'Completed {index}/{len(tasks)} unique configurations', flush=True)
