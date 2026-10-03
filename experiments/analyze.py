"""Consume catalog estimands; derive all scores from the four raw integrals."""
from collections import defaultdict
from math import fsum
from pathlib import Path

import numpy as np
import pandas as pd

from study import _estimand_roles
from agent_crisis_sim.simulation import SCALAR_METRICS

LOSS = 'service_deficit'


def projection(base, view):
    ids = {a['id']: i for i, a in enumerate(sorted(base['agents'], key=lambda a: a['id']))}
    criticality = {a['id']: a['criticality'] for a in base['agents']}
    matrix = np.zeros((len(base['functions']), len(ids)))
    functions = sorted(base['functions'], key=lambda f: f['id'])
    for j, function in enumerate(functions):
        for name, value in function['members'].items():
            weight = 1 if view['members'] == 'equal' else value * criticality[name] if view['members'] == 'agent_criticality' else value
            matrix[j, ids[name]] = weight
        matrix[j] /= matrix[j].sum()
    c = np.ones(len(functions)) if view['function_criticality'] == 'equal' else np.array([f['criticality'] for f in functions])
    return matrix, c


def evaluate(raw, base, view):
    mode = 'hard' if view['timeliness'] == 'hard' else 'grace'
    q = base['fixed']['primary_contaminated_utility'] if view['compromised_utility'] == 'base' else view['compromised_utility']
    deficits = raw['base_deficit_' + mode] + (1 - q) * raw['compromised_weight_' + mode]
    matrix, weights = projection(base, view)
    functions = deficits @ matrix.T
    return functions @ weights, functions, weights


def tail_weights(values):
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or not len(values) or not np.isfinite(values).all():
        raise ValueError('Finite nonempty one-dimensional tail input required')
    # Express 5% as integer tail mass, avoiding the extra rounding in .05*N.
    boundary = np.sort(values)[len(values) - (len(values) + 19) // 20]
    above, equal = values > boundary, values == boundary
    weights = 20. * above
    weights[equal] = (len(values) - 20 * int(above.sum())) / int(equal.sum())
    return weights / len(values)


def bootstrap_indices(n, repetitions, seed, domain=0):
    if type(n) is not int or n <= 0 or type(repetitions) is not int or repetitions < 0 or domain not in (0, 1, 2):
        raise ValueError('Invalid bootstrap dimensions/domain')
    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed, domain])))
    return rng.integers(0, n, size=(repetitions, n), dtype=np.int64)


def _roundoff(scale, operations):
    """Bound roundoff by gamma_k = k*eps/(1-k*eps) times absolute scale.

    eps (rather than eps/2) is conservative. There is no absolute tolerance
    or scale floor of 1: this is a numerical bound, not an effect threshold.
    """
    error = operations * np.finfo(float).eps
    return error / (1 - error) * np.asarray(scale)


def _canonical_zero(value, error):
    return np.where(np.abs(value) <= error, 0., value)


def _sum(terms):
    """Use fsum along the term axis and retain the absolute summand scale."""
    terms = np.asarray(terms, dtype=float)
    shape = terms.shape[1:]
    columns = terms.reshape(len(terms), -1).T
    value = np.array([fsum(column) for column in columns]).reshape(shape)
    scale = np.array([fsum(abs(column)) for column in columns]).reshape(shape)
    return value, scale


def _mean_contrast(vectors, coefficients, frequencies):
    # Pair by run_index before averaging, preserving the registered linear mean.
    paired, scale = _sum(np.asarray(coefficients)[:, None] * vectors)
    point = fsum(paired) / len(paired)
    sample = frequencies @ paired
    # Coefficient multiplication + fsum, then frequency division and N-term dot.
    input_error = _roundoff(scale, 2)
    error = frequencies @ input_error + _roundoff(frequencies @ abs(paired), len(paired) + 2)
    point_error = fsum(input_error) / len(paired) + _roundoff(fsum(abs(paired)) / len(paired), 2)
    return float(_canonical_zero(point, point_error)), sample, error


def _tail_contrast(terms):
    # Two tail-weight divisions, product, fsum, coefficient product, final fsum.
    # Registered cell metrics are nonnegative, so absolute summands also bound
    # the upstream cell-statistic errors. ES95 is always computed per cell.
    value, scale = _sum(terms)
    errors = _roundoff(scale, 6)
    return _canonical_zero(value, errors), errors


def interval(values, errors=None):
    if not len(values) or not np.isfinite(values).all():
        return np.nan, np.nan
    if errors is None:
        return tuple(np.quantile(values, [.025, .975], method='linear'))
    # Normalize draws before sorting/interpolation, then propagate to endpoints.
    values = _canonical_zero(np.asarray(values), errors)
    order = np.argsort(values, kind='stable')
    values, errors = values[order], np.asarray(errors)[order]
    ranks = (len(values) - 1) * np.array([.025, .975])
    lower, upper = np.floor(ranks).astype(int), np.ceil(ranks).astype(int)
    weight = ranks - lower
    bounds = (1 - weight) * errors[lower] + weight * errors[upper]
    # Quantile rank and interpolation rounding; rank error scales with B.
    bounds += _roundoff(abs(values[lower]) + abs(values[upper]), 3 * len(values))
    return tuple(_canonical_zero(np.quantile(values, [.025, .975], method='linear'), bounds))


def direction(low, high):
    return 'positive' if low > 0 else 'negative' if high < 0 else 'uncertain'


def crossfit(k, losses):
    """Two parity folds, m0(K) and m1(K,position), with registered fallbacks."""
    if k.shape != losses.shape or k.ndim != 2 or k.shape[0] < 2 or not np.isfinite(losses).all():
        raise ValueError('Position arrays require aligned finite run x position data')
    sse0 = sse1 = sst = 0.0
    for parity in (0, 1):
        train_k, train_y = k[parity::2], losses[parity::2]
        test_k, test_y = k[1-parity::2], losses[1-parity::2]
        train_mean = train_y.mean()
        m0 = {value: train_y[train_k == value].mean() for value in np.unique(train_k)}
        m1 = {(value, s): train_y[:, s][train_k[:, s] == value].mean()
              for s in range(k.shape[1]) for value in np.unique(train_k[:, s])}
        pred0 = np.array([[m0.get(value, train_mean) for value in row] for row in test_k])
        pred1 = np.array([[m1.get((value, s), pred0[i, s]) for s, value in enumerate(row)] for i, row in enumerate(test_k)])
        sse0 += np.square(test_y - pred0).sum()
        sse1 += np.square(test_y - pred1).sum()
        sst += np.square(test_y - train_mean).sum()
    return dict(value=(sse0 - sse1) / sst if sst > 0 else np.nan,
                denominator=sst, status='defined' if sst > 0 else 'undefined',
                reason='' if sst > 0 else 'zero_SST')


def _position_example(strata):
    supported = strata[(strata['view'] == 'primary') & (strata['size'] > 1) & (strata['count'] >= 20)]
    candidates = supported.groupby('size').agg(positions=('initial_node', 'count'), records=('count', 'sum'))
    candidates = candidates[candidates['positions'] >= 2].sort_values(['records', 'size'], ascending=[False, True])
    selected = None if candidates.empty else int(candidates.index[0])
    return supported[supported['size'] == selected].sort_values('initial_node')


def position_analysis(raws, design, base, repetitions):
    roles = {r['id']: r for r in design['roles']}
    positions = [roles[name] for name in design['position']['roles']]
    positions.sort(key=lambda r: r['axes']['initial_nodes'][0])
    k = np.column_stack([raws[r['cell_id']]['ever_compromised_count'] for r in positions])
    n = len(k)
    seed = design['sampling']['seeds']['bootstrap']
    indices = [bootstrap_indices(len(k[p::2]), repetitions, seed, p+1) for p in (0, 1)]
    rows, strata = [], []
    for view_id in design['position']['views']:
        losses = np.column_stack([evaluate(raws[r['cell_id']], base, design['evaluation_views'][view_id])[0] for r in positions])
        result = crossfit(k, losses)
        draws = []
        if result['status'] == 'defined':
            for b in range(repetitions):
                sampled_k, sampled_y = np.empty_like(k), np.empty_like(losses)
                for parity in (0, 1):
                    sampled_k[parity::2] = k[parity::2][indices[parity][b]]
                    sampled_y[parity::2] = losses[parity::2][indices[parity][b]]
                draws.append(crossfit(sampled_k, sampled_y)['value'])
        low, high = interval(draws)
        if result['status'] == 'defined' and (not len(draws) or not np.isfinite(draws).all()):
            result['reason'] = 'bootstrap_zero_SST' if len(draws) else 'no_bootstrap_draws'
        rows.append(dict(view=view_id, **result, ci_low=low, ci_high=high,
                         bootstrap_valid=int(np.isfinite(draws).sum()),
                         bootstrap_requested=repetitions, ci_status='defined' if len(draws) and np.isfinite(draws).all() else 'undefined',
                         n_runs=n, n_total=int(k.size)))
        for s, role in enumerate(positions):
            for value in np.unique(k[:, s]):
                mask = k[:, s] == value
                strata.append(dict(view=view_id, size=int(value), initial_node=role['axes']['initial_nodes'][0],
                                   count=int(mask.sum()), mean=float(losses[:, s][mask].mean())))
    return pd.DataFrame(rows), pd.DataFrame(strata)


def _statistic_plan(design):
    points, bootstrap = defaultdict(lambda: defaultdict(set)), defaultdict(lambda: defaultdict(set))
    contrasts = {c['id']: c for c in design['contrasts']}
    for estimand in design['estimands']:
        contrast = contrasts.get(estimand.get('contrast_id'))
        # Linear means consume paired vectors, not separate cell moments/draws.
        if contrast is not None and estimand['statistic'] == 'mean':
            continue
        terms = contrast['terms'] if contrast is not None else [(estimand['cell_id'], 1)]
        for cell, _ in terms:
            signature = estimand['view'], estimand['statistic']
            points[cell][signature].add(estimand['metric'])
            if contrast is not None:
                bootstrap[cell][signature].add(estimand['metric'])
    return points, bootstrap


def _tail_statistic(loss, matrix):
    weights = tail_weights(loss)
    return np.array([fsum(weights * column) for column in matrix.T])


def _bootstrap_tail(loss, matrix, indices):
    return np.array([_tail_statistic(loss[index], matrix[index]) for index in indices]).reshape(len(indices), matrix.shape[1])


def _metric_unit(metric, difference=True):
    if metric.startswith('F') and metric[1:].isdigit() or metric == 'worst_function_deficit':
        return '归一化服务缺口 × 抽象tick'
    if metric == LOSS or metric == 'function_failure_time':
        return '功能关键性 × 抽象tick'
    unit = ('Agent-tick' if metric.endswith('_blocking') or metric == 'review_queue_time' else
            '覆盖比例' if metric.startswith('mean_') else
            '分层权重 × Agent-tick' if metric == 'critical_review_queue_time' else
            '节点数' if metric == 'ever_compromised_count' else '次数')
    return unit + ((' 差' if 'tick' in unit else '差') if difference else '')


def _selected_rows(effects, design, *, purpose, statistic='mean', metric=LOSS, view='primary', **dims):
    """Select registered roles and order by explanatory variables, never outcomes."""
    contrasts = {c['id']: c for c in design['contrasts']}
    cells = {c['id']: c for c in design['cells']}
    # Semantic order comes from the fixed protocol categories, not catalog hashes.
    categories = ('model', 'data', 'tool', 'abrupt', 'progressive', 'autonomy', 'full',
                  'fifo', 'due_first', 'life_safety', 'fast', 'balanced', 'integrated',
                  'distributed', 'selective', 'centralized', 'none', 'critical', 'global')
    short = {'shock_type': 'type', 'shock_probability': 'p', 'resource_groups': 'K',
             'partition_seed': 'partition', 'shock_profile': 'profile', 'observation_level': 'O',
             'monitoring_offset': 'offset',
             'oversight': 'review', 'deadline_window': 'd', 'review_capacity': 'cap',
             'review_priority': 'priority', 'information_policy': 'information', 'command_structure': 'command'}

    def order(value):
        if value == 'unlimited':
            return (0, np.inf)
        if isinstance(value, (int, float)):
            return (0, value)
        return (1, categories.index(value)) if value in categories else (2, str(value))

    selected = []
    for estimand in design['estimands']:
        if (estimand['statistic'], estimand['metric'], estimand['view']) != (statistic, metric, view):
            continue
        matches = []
        for role in _estimand_roles(estimand, contrasts):
            if role['purpose'] != purpose:
                continue
            dimensions = role['dimensions'].copy()
            terms = contrasts[estimand['contrast_id']]['terms']
            comparison, field = purpose, None
            comparison_order = ()
            if len(terms) == 2 and sorted(coef for _, coef in terms) == [-1, 1]:
                target_cell = cells[next(cell for cell, coef in terms if coef == 1)]
                target = target_cell['parameters']
                reference = cells[next(cell for cell, coef in terms if coef == -1)]['parameters']
                if purpose == 'dependency':
                    dimensions.setdefault('resource_groups', len(target_cell['groups']))
                    dimensions.setdefault('partition_seed', 0)
                field = next((k for k in ('monitoring_offset', 'information_policy', 'command_structure', 'oversight', 'review_priority', 'automatic_isolation')
                              if target.get(k) != reference.get(k)), None)
                if field:
                    comparison = f'{target[field]} − {reference[field]}'
                    comparison_order = (order(target[field]), order(reference[field]))
            if not all(dimensions.get(k) == v for k, v in dims.items()):
                continue
            label = ','.join(f'{title}={dimensions[k]}' for k, title in short.items() if k in dimensions and k != field)
            key = tuple(order(dimensions[k]) if k in dimensions else (-1, 0) for k in short) + comparison_order
            matches.append((key, label + '\n' + comparison))
        if matches:
            key, label = min(matches)
            selected.append((key, label, estimand['id']))
    selected.sort()
    labels = [label for _, label, _ in selected]
    if len(set(labels)) != len(labels):
        raise ValueError('Presentation labels must be unique')
    frame = effects.set_index('estimand_id').loc[[identity for _, _, identity in selected]].reset_index()
    frame['label'] = labels
    frame.attrs['unit'] = _metric_unit(metric)
    return frame


def _presentation(tables, design, base, spec):
    """Build transient, ordered rendering frames from the three statistical tables."""
    effects = tables['effects']

    def select(purpose, **kwargs):
        return _selected_rows(effects, design, purpose=purpose, **kwargs)

    example = _position_example(tables['position_strata'])

    triage = sorted((r for r in design['roles'] if r['family'] == 'triage'),
                    key=lambda r: (r['axes']['review_capacity'], r['axes']['deadline_window'],
                                   ('fifo', 'due_first', 'life_safety').index(r['axes']['review_priority'])))
    levels = effects[effects['estimand_type'].eq('level') & effects['view'].eq('primary') & effects['statistic'].eq('mean')].set_index(['catalog_id', 'metric'])

    def family_levels(family, axis):
        roles = sorted((r for r in design['roles'] if r['family'] == family),
                       key=lambda r: np.inf if r['axes'][axis] == 'unlimited' else r['axes'][axis])
        return pd.DataFrame([dict(condition=r['axes'][axis], cell_id=r['cell_id'],
                                  **levels.loc[r['cell_id'], 'value'].to_dict()) for r in roles])

    function_ids = [f['id'] for f in base['functions']]
    monitoring_metrics = [LOSS, *function_ids, 'worst_function_deficit', 'true_detections',
                          'false_isolations', 'monitoring_requests', 'ever_compromised_count', 'wrong_actions']
    capacity_metrics = [LOSS, *function_ids, 'worst_function_deficit', 'human_review_load',
                        'completed_reviews', 'review_queue_time', 'critical_review_queue_time',
                        'unfinished_tasks', 'deadline_misses', 'false_review_denials', 'wrong_actions',
                        'information_blocking', 'review_blocking', 'denial_blocking',
                        'command_blocking', 'isolation_blocking']
    lines = []
    for capacity in sorted({r['axes']['review_capacity'] for r in triage}):
        for priority in ('fifo', 'due_first', 'life_safety'):
            roles = [r for r in triage if r['axes']['review_capacity'] == capacity and r['axes']['review_priority'] == priority]
            frame = pd.DataFrame({'deadline': [r['axes']['deadline_window'] for r in roles],
                                  **{metric: [levels.loc[(r['cell_id'], metric), 'value'] for r in roles]
                                     for metric in (LOSS, 'critical_review_queue_time')}})
            frame.attrs['units'] = {metric: _metric_unit(metric, difference=False) for metric in (LOSS, 'critical_review_queue_time')}
            lines.append((f'cap={capacity}, {priority}', frame))
    functions = []
    for function in base['functions']:
        frame = pd.DataFrame(dict(value=[levels.loc[(r['cell_id'], function['id']), 'value'] for r in triage],
            label=[f'cap={r["axes"]["review_capacity"]},d={r["axes"]["deadline_window"]}\n{r["axes"]["review_priority"]}' for r in triage]))
        frame.attrs['unit'] = _metric_unit(function['id'], difference=False)
        functions.append((function['id'] + ' ' + function['name'], frame))
    contrasts = {c['id']: c for c in design['contrasts']}
    primary_names = {
        'R1_dependency_mean': 'H1b：共同依赖均值差',
        'R1_dependency_ES95': 'H1b：共同依赖 ES95 差',
        'R2_observation_interaction': 'H2a：观察阶段与隔离交互',
        'R2_profile_interaction': 'H2b：暴露节奏与隔离交互',
        'R3_human_deadline': 'H3a：审核时限交互',
        'R3_human_capacity': 'H3a：审核容量交互',
        'R3_life_vs_fifo': 'H3b：生命安全分诊与 FIFO',
        'R3_command_deadline': 'H3c：附加指挥复核时限交互',
        'R3_information_deadline': 'H3d：信息等待时限交互',
    }
    primary_order = [e['id'] for e in spec['primary_effects']]
    views, metrics = list(design['evaluation_views']), [LOSS] + [f['id'] for f in base['functions']]
    primary = []
    for estimand in design['estimands']:
        for role in _estimand_roles(estimand, contrasts):
            if role['tier'] == 'primary':
                purpose = role['purpose']
                primary.append((primary_order.index(purpose), views.index(estimand['view']),
                                metrics.index(estimand['metric']), estimand['id'],
                                role['rq'] + ' / ' + primary_names[purpose]))
    primary.sort()
    primary_frame = effects.set_index('estimand_id').loc[[r[3] for r in primary]].reset_index()
    primary_frame['label'] = [r[4] for r in primary]
    capacity_effect = select('oversight_capacity')
    reference = next(cell for cell, coefficient in contrasts[capacity_effect['catalog_id'].iloc[0]]['terms'] if coefficient == -1)
    return dict(position=tables['position'].set_index('view').loc[design['position']['views']].reset_index(),
        position_example=example, triage_lines=lines, triage_functions=functions,
        dependency=[select('dependency', statistic=s, shock_type='data', shock_probability=.2, resource_groups=2) for s in ('mean', 'ES95')],
        isolation=[select('isolation', metric=m) for m in (LOSS, 'service_blocking', 'false_isolations')],
        isolation_functions=[(f['id'], select('isolation', metric=f['id'])) for f in base['functions']],
        human=select('human', family='human'), command=select('command', family='command'),
        command_blocking=select('command', family='command', metric='command_blocking'),
        command_with_human=select('command', family='command_with_human'),
        information=[select('information', metric=m) for m in (LOSS, 'mean_information_coverage', 'mean_clean_information_fraction', 'service_blocking')],
        fixed_budget=[(metric, select('fixed_budget', metric=metric)) for metric in monitoring_metrics],
        fixed_budget_tail=[(metric, select('fixed_budget', metric=metric, statistic='ES95')) for metric in [LOSS, *function_ids]],
        monitoring_levels=family_levels('fixed_budget', 'monitoring_offset'),
        oversight_capacity=[(metric, select('oversight_capacity', metric=metric)) for metric in capacity_metrics],
        capacity_levels=family_levels('oversight_capacity', 'review_capacity'),
        capacity_reference=pd.DataFrame([dict(condition='autonomy', cell_id=reference, **levels.loc[reference, 'value'].to_dict())]),
        function_vectors={purpose: [(metric, select(purpose, metric=metric)) for metric in [*function_ids, 'worst_function_deficit']]
                          for purpose in ('dependency', 'triage')},
        primary=primary_frame, config_count=len(design['cells']), settings=base['parameters'])


def analyze(raws, output, repetitions, design, base):
    counts = {len(raw['run_index']) for raw in raws.values()}
    if len(counts) != 1:
        raise ValueError('Run counts differ across cells')
    n = counts.pop()
    seed = design['sampling']['seeds']['bootstrap']
    indices = bootstrap_indices(n, repetitions, seed)
    # The same bootstrap row applies to every cell and every estimand.
    frequencies = np.array([np.bincount(row, minlength=n) for row in indices], dtype=float) / n
    contrasts = {c['id']: c for c in design['contrasts']}
    required, bootstrap = _statistic_plan(design)
    moments, draws, values = {}, {}, {}

    def data_for(cell_id, view_id):
        if (cell_id, view_id) not in values:
            raw = raws[cell_id]
            loss, functions, _ = evaluate(raw, base, design['evaluation_views'][view_id])
            values[cell_id, view_id] = {LOSS: loss,
                'worst_function_deficit': functions.max(axis=1),
                **{f['id']: functions[:, j] for j, f in enumerate(sorted(base['functions'], key=lambda f: f['id']))},
                **{key: raw[key] for key in SCALAR_METRICS},
                'service_blocking': sum(raw[key + '_blocking'] for key in ('information', 'review', 'denial', 'command', 'isolation'))}
        return values[cell_id, view_id]

    for ci, cell in enumerate(design['cells'], 1):
        cell_id = cell['id']
        for view_id, statistic in sorted(required[cell_id]):
            data = data_for(cell_id, view_id)
            loss = data[LOSS]
            keys = sorted(required[cell_id][view_id, statistic])
            matrix = np.column_stack([data[key] for key in keys])
            if statistic == 'mean':
                point = matrix.mean(axis=0)
            else:
                point = _tail_statistic(loss, matrix)
            for j, metric in enumerate(keys):
                signature = cell_id, view_id, statistic, metric
                moments[signature] = float(point[j])
            draw_keys = sorted(bootstrap[cell_id][view_id, statistic])
            if not draw_keys:
                continue
            samples = _bootstrap_tail(loss, np.column_stack([data[key] for key in draw_keys]), indices)
            for j, metric in enumerate(draw_keys):
                signature = cell_id, view_id, statistic, metric
                draws[signature] = samples[:, j]
        if ci % 50 == 0:
            print(f'Analyzed {ci}/{len(design["cells"])} configurations', flush=True)
    rows = []
    for estimand in design['estimands']:
        contrast = contrasts.get(estimand.get('contrast_id'))
        terms = contrast['terms'] if contrast is not None else [(estimand['cell_id'], 1)]
        metric, view, statistic = (estimand[key] for key in ('metric', 'view', 'statistic'))
        structural = contrast is not None and contrast['structural_zero']
        if structural:
            value, low, high, status, sign = 0.0, 0.0, 0.0, 'structural_zero', 'zero'
        elif contrast is None:
            value = moments[estimand['cell_id'], view, statistic, metric]
            low, high, status, sign = np.nan, np.nan, 'not_computed', 'not_computed'
        else:
            if statistic == 'mean':
                value, sample, errors = _mean_contrast(
                    np.array([data_for(cell, view)[metric] for cell, _ in terms]),
                    [coef for _, coef in terms], frequencies)
            else:
                value = float(_tail_contrast([coef * moments[cell, view, statistic, metric] for cell, coef in terms])[0])
                sample, errors = _tail_contrast([coef * draws[cell, view, statistic, metric] for cell, coef in terms])
            sample = _canonical_zero(sample, errors)
            low, high = interval(sample, errors)
            status = 'defined' if np.isfinite([low, high]).all() else 'undefined'
            sign = direction(low, high) if status == 'defined' else 'undefined'
        kind = 'level' if contrast is None else 'structural_zero' if structural else 'interaction' if any(r['kind'] == 'interaction' for r in contrast['roles'].values()) else 'direct'
        row = dict(estimand_id=estimand['id'], estimand_type=kind, statistic=statistic,
                   view=view, metric=metric, value=value, ci_low=low, ci_high=high,
                   status=status, direction=sign, n_runs=n,
                   catalog_id=contrast['id'] if contrast else estimand['cell_id'],
                   tail_component=statistic == 'ES95' and metric != LOSS)
        rows.append(row)
    position, strata = position_analysis(raws, design, base, repetitions)
    tables = dict(effects=pd.DataFrame(rows), position=position, position_strata=strata)
    output = Path(output)
    (output / 'tables').mkdir(parents=True, exist_ok=True)
    for name, frame in tables.items():
        frame.to_csv(output / 'tables' / (name + '.csv'), index=False, lineterminator='\n')
    return tables
