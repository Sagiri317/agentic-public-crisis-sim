"""Protocol coverage, ownership, estimators and raw production contracts."""
from copy import deepcopy
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'experiments'), str(ROOT / 'reproducibility')]
import analyze
import figures
import study
import run_all
from agent_crisis_sim.config import compile_config
from agent_crisis_sim.simulation import keyed_uniform, simulate, VECTOR_METRICS, SCALAR_METRICS


def test_exact_protocol_expansion_semantic_dedup_and_primary_terms():
    c = study.build_catalog()
    assert [len(c[key]) for key in ('cells', 'roles', 'contrasts', 'estimands')] == [255, 310, 306, 19260]
    assert {rq: sum(r['rq'] == rq for r in c['roles']) for rq in ('RQ1', 'RQ2', 'RQ3')} == dict(RQ1=114, RQ2=52, RQ3=144)
    assert len({cell['id'] for cell in c['cells']}) == len(c['cells'])
    assert {r['rq'] for r in c['roles']} == {'RQ1', 'RQ2', 'RQ3'}
    assert len([r for r in c['roles'] if r['family'] == 'position']) == 30
    contrasts = {row['id']: row for row in c['contrasts']}
    registered = {r['purpose'] for e in c['estimands'] for r in study._estimand_roles(e, contrasts) if r['tier'] == 'primary'}
    assert registered == {e['id'] for e in study.protocol()['primary_effects']}
    for cell in c['cells']:
        model = study.configuration(cell)
        assert (model.digest, model.parameters, model.groups) == (cell['id'], cell['parameters'], cell['groups'])


def test_no_inactive_parameters_in_materialized_configs():
    for cell in study.build_catalog()['cells']:
        p = cell['parameters']
        assert 'partition_seed' not in p and 'resource_groups' not in p
        if p['shock_type'] == 'none':
            assert not {'shock_time', 'shock_profile', 'shock_probability'} & set(p)
        if p['oversight'] == 'autonomy':
            assert not any(k.startswith('review_') for k in p)
        if p['command_structure'] == 'distributed':
            assert not {'command_capacity', 'command_intercept_effectiveness'} & set(p)
        if p['verification_mode'] == 'none':
            assert 'verification_effectiveness' not in p
        if not p['automatic_isolation']:
            assert not {'observation_level', 'monitoring_offset', 'detection_probability', 'false_alarm_probability'} & set(p)


def test_every_active_behavior_field_is_read_and_no_control_uses_config_identity():
    class Reads(dict):
        def __init__(self, data):
            super().__init__(data)
            self.read = set()
        def __getitem__(self, key):
            self.read.add(key)
            return super().__getitem__(key)
    active, read = set(), set()
    seed = study.protocol()['sampling']['seeds']['smoke']
    for cell in study.build_catalog()['cells']:
        model = study.configuration(cell)
        reads = Reads(model.parameters)
        model.parameters = reads
        simulate(model, seed, 0)
        active |= set(reads)
        read |= reads.read
    # Branches need a semantic consumer, not a hit in every sampled run.
    # The remaining conditional fields have dedicated extreme fixtures above;
    # scope/structure are consumed when targets are compiled before simulation.
    conditional = {'review_scope', 'command_structure', 'false_denial_hold',
                   'rollback_success', 'command_error_probability',
                   'detection_probability', 'command_intercept_effectiveness'}
    assert active - read <= conditional
    assert set(SCALAR_METRICS) <= {e['metric'] for e in study.build_catalog()['estimands']}


def test_shared_reference_algebra_and_structural_zeros_are_unique():
    known = {'a', 'b', 'c'}
    assert study.normalize_terms([('a', 1), ('b', -1), ('c', -1), ('b', 1)], known) == [['a', 1.], ['c', -1.]]
    assert study.normalize_terms([('a', 1), ('a', -1)], known) == []
    for terms in ([('missing', 1), ('a', -1)], [('a', float('nan'))], [('a', 1)]):
        with pytest.raises(ValueError):
            study.normalize_terms(terms, known)
    c = study.build_catalog()
    signatures = [(e.get('contrast_id'), e.get('cell_id'), e['view'], e['metric'], e['statistic']) for e in c['estimands']]
    assert len(signatures) == len(set(signatures))
    contrasts = {row['id']: row for row in c['contrasts']}
    effect = next(e for e in c['estimands'] if e['view'] == 'primary' and e['metric'] == analyze.LOSS and any(r['purpose'] == 'R3_human_capacity' for r in study._estimand_roles(e, contrasts)))
    contrast = next(c for c in c['contrasts'] if c['id'] == effect['contrast_id'])
    assert len(contrast['terms']) == 2
    assert any(c['structural_zero'] for c in c['contrasts'])


def test_es95_exact_mass_and_tied_function_contributions():
    for values, expected in ((np.r_[np.zeros(99), 100.], 20.),
                             (np.array([0., 10., 20.]), 20.),
                             (np.arange(21.), (20. + .05 * 19.) / 1.05)):
        assert analyze._tail_statistic(values, values[:, None])[0] == pytest.approx(expected)
    functions = np.zeros((3, 7))
    functions[1, 0], functions[2, 1] = 10., 5.
    criticality = np.arange(1., 8.)
    loss = functions @ criticality
    weights = analyze.tail_weights(loss)
    assert np.array_equal(weights, [0., .5, .5])
    components = analyze._tail_statistic(loss, functions)
    assert np.array_equal(components, [5., 2.5, 0., 0., 0., 0., 0.])
    assert components @ criticality == analyze._tail_statistic(loss, loss[:, None])[0]
    indices = np.array([[0, 1, 2], [1, 1, 2], [0, 0, 0]])
    assert analyze._bootstrap_tail(loss, functions, indices) @ criticality == pytest.approx(
        analyze._bootstrap_tail(loss, loss[:, None], indices)[:, 0])
    assert np.array_equal(weights[::-1], analyze.tail_weights(loss[::-1]))
    a, b = np.array([100., 0.]), np.array([0., 100.])
    difference, _ = analyze._tail_contrast([analyze._tail_statistic(a, a[:, None]),
                                           -analyze._tail_statistic(b, b[:, None])])
    assert difference[0] != analyze._tail_statistic(a-b, (a-b)[:, None])[0]


def test_paired_mean_zero_percentile_endpoint_is_uncertain():
    # 41 draws put the 2.5th percentile exactly at sorted draw 1.
    # The first two draws have (1 + 1 - 2)/3 = 0; all others equal 1.
    vectors = np.array([[1., 1., 0.], [0., 0., 2.]])
    frequencies = np.array([[1/3, 1/3, 1/3]] * 2 + [[1., 0., 0.]] * 39)
    point, draws, errors = analyze._mean_contrast(vectors, [1., -1.], frequencies)
    assert point == 0
    low, high = analyze.interval(draws, errors)
    assert (low, high) == (0., 1.)
    assert analyze.direction(low, high) == 'uncertain'


def test_cell_es95_difference_zero_upper_endpoint_is_uncertain():
    # ES95 for N=2 is max. 39 draws yield 0-100, two yield 100-100.
    a, b = np.array([100., 0.]), np.array([0., 100.])
    indices = np.array([[1, 1]] * 39 + [[0, 1]] * 2)
    ta = analyze._bootstrap_tail(a, a[:, None], indices)[:, 0]
    tb = analyze._bootstrap_tail(b, b[:, None], indices)[:, 0]
    draws, errors = analyze._tail_contrast([ta, -tb])
    assert analyze.interval(draws, errors) == (-100., 0.)
    assert analyze.direction(*analyze.interval(draws, errors)) == 'uncertain'
    difference_tail = analyze._bootstrap_tail(a-b, (a-b)[:, None], indices)[:, 0]
    assert draws[-1] == 0. and difference_tail[-1] == 100.
    # Distinct rounded cell statistics may leave an ULP-sized cancellation.
    rounded = np.nextafter(tb, -np.inf)
    stable, bound = analyze._tail_contrast([ta, -rounded])
    assert analyze.interval(stable, bound)[1] == 0.


@pytest.mark.parametrize('sign', [-1, 1])
@pytest.mark.parametrize('scale,delta', [(1e-20, 1e-22), (1., 1e-10)])
def test_small_resolvable_intervals_keep_their_sign(sign, scale, delta):
    vectors = np.array([[scale + sign*delta] * 4, [scale] * 4])
    frequencies = np.full((41, 4), .25)
    point, sample, errors = analyze._mean_contrast(vectors, [1., -1.], frequencies)
    assert point * sign > 0
    assert analyze.direction(*analyze.interval(sample, errors)) == ('positive' if sign > 0 else 'negative')
    tail, bound = analyze._tail_contrast([np.full(41, scale + sign*delta), np.full(41, -scale)])
    assert analyze.direction(*analyze.interval(tail, bound)) == ('positive' if sign > 0 else 'negative')


def test_four_integral_projection_all_views_and_function_bounds():
    base, views = study.base_config(), study.protocol()['evaluation_views']
    raw = dict(base_deficit_hard=np.zeros((2, 30)),
               compromised_weight_hard=np.ones((2, 30)),
               base_deficit_grace=np.full((2, 30), 2.),
               compromised_weight_grace=np.ones((2, 30)))
    for view in views.values():
        loss, f, weights = analyze.evaluate(raw, base, view)
        q = base['fixed']['primary_contaminated_utility'] if view['compromised_utility'] == 'base' else view['compromised_utility']
        expected = 1-q + (2 if view['timeliness'] == 'linear_grace' else 0)
        assert f == pytest.approx(np.full((2, 7), expected))
        assert loss == pytest.approx(np.full(2, expected * weights.sum()))


def test_crossfit_negative_unclipped_zero_denominator_and_fallbacks():
    k = np.ones((8, 2))
    losses = np.tile([[-1., 1.], [1., -1.]], (4, 1))
    assert analyze.crossfit(k, losses)['value'] == -3.
    constant = analyze.crossfit(k, np.ones_like(k))
    assert constant['status'] == 'undefined' and np.isnan(constant['value'])
    # Unseen K falls back to train mean, not a full-sample fit.
    k[1::2] = 2
    assert analyze.crossfit(k, losses)['value'] == 0.


def test_bootstrap_domains_paired_folds_and_chunk_invariance():
    a = analyze.bootstrap_indices(20, 50, 2026100303)
    b = analyze.bootstrap_indices(20, 100, 2026100303)
    assert np.array_equal(a, b[:50])
    assert not np.array_equal(a, analyze.bootstrap_indices(20, 50, 2026100303, 1))
    assert np.array_equal(a, np.random.Generator(np.random.PCG64(np.random.SeedSequence([2026100303, 0]))).integers(0, 20, size=(50, 20), dtype=np.int64))
    assert analyze.interval([0., 10.]) == (.25, 9.75)
    low, high = analyze.interval([1., np.nan])
    assert np.isnan(low) and np.isnan(high)
    assert analyze.direction(0., 1.) == 'uncertain'
    assert analyze.direction(-1., 0.) == 'uncertain'


def test_position_bootstrap_clusters_and_selection_no_result_filter():
    design, base = study.build_catalog(), study.base_config()
    positions = [r for r in design['roles'] if r['family'] == 'position']
    raws = {}
    for i, role in enumerate(positions):
        n = 40
        k = np.full(n, 2 if i < 3 else 1)
        raw = {metric: np.zeros((n, 30)) for metric in VECTOR_METRICS}
        raw['ever_compromised_count'] = k
        raw['compromised_weight_hard'][:, i] = np.arange(n) % 2 + 1
        raw['compromised_weight_grace'][:, i] = raw['compromised_weight_hard'][:, i]
        raws[role['cell_id']] = raw
    table, strata = analyze.position_analysis(raws, design, base, 3)
    assert analyze._position_example(strata)['size'].eq(2).all() and table['bootstrap_valid'].eq(3).all()
    assert set(table['view']) == {'primary', 'equal_member', 'agent_criticality'}
    assert len(strata[(strata['size'] == 2) & (strata['view'] == 'primary')]) == 3
    assert strata['count'].eq(40).all()


def test_worker_bytes_determinism_and_raw_schema(tmp_path):
    cells = study.build_catalog()['cells'][:2]
    models = {cell['id']: study.configuration(cell) for cell in cells}
    contents = []
    for folder in ('one', 'two'):
        for cell in cells:
            study.run_cell((models[cell['id']], 3, 2026100304, str(tmp_path / folder)))
            raw = study.load_raw(tmp_path / folder / 'raw' / (cell['id'] + '.npz'))
            study.validate_raw(raw, 3, study.configuration(cell))
            contents.append((tmp_path / folder / 'raw' / (cell['id'] + '.npz')).read_bytes())
    assert contents[:2] == contents[2:]
    raw['run_index'] = np.array([1, 2, 3])
    with pytest.raises(ValueError, match='run index'):
        study.validate_raw(raw, 3, study.configuration(cells[-1]))


@pytest.mark.parametrize('change', ['nan', 'dimension', 'missing', 'bounds', 'blocking', 'coverage'])
def test_raw_negative_checks(change):
    cell = study.build_catalog()['cells'][0]
    model = study.configuration(cell)
    row = simulate(model, 2026100304, 0)
    raw = {key: np.asarray([value], dtype=float) for key, value in row.items()}
    raw['run_index'] = np.array([0])
    if change == 'nan': raw['wrong_actions'][0] = np.nan
    elif change == 'dimension': raw['base_deficit_hard'] = np.zeros((1, 2))
    elif change == 'missing': del raw['human_review_load']
    elif change == 'bounds': raw['compromised_weight_hard'][:] = 1000
    elif change == 'blocking': raw['review_blocking'][:] = 1000
    else: raw['mean_clean_information_fraction'][:] = 2
    with pytest.raises(ValueError):
        study.validate_raw(raw, 1, model)


def test_output_scope_is_restricted_to_run_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(run_all, 'ROOT', tmp_path)
    for path in (tmp_path / 'results', tmp_path / '.run', tmp_path.parent / 'other', tmp_path / '.run/nested/run'):
        with pytest.raises(ValueError, match='gitignored'):
            run_all.temporary_output(path)
    output = tmp_path / '.run/empty'
    assert run_all.temporary_output(output) == output
    output.mkdir(parents=True)
    assert run_all.temporary_output(output) == output


def test_output_check_precedes_execution_and_preserves_existing_outputs(monkeypatch, tmp_path):
    monkeypatch.setattr(run_all, 'ROOT', tmp_path)
    output = tmp_path / '.run/existing'
    output.mkdir(parents=True)
    report = output / 'report.md'
    report.write_text('existing output', encoding='utf-8')
    before = report.read_bytes()

    def forbidden(*args):
        pytest.fail('simulation must not run for a nonempty output')

    monkeypatch.setattr(study, 'execute', forbidden)
    with pytest.raises(ValueError, match='overwrite'):
        run_all.pipeline('smoke', output, 1)
    assert report.read_bytes() == before
    file = output.parent / 'file'
    file.write_text('existing output', encoding='utf-8')
    with pytest.raises(ValueError, match='overwrite'):
        run_all.temporary_output(file)


def test_keyed_CRN_is_treatment_independent_even_after_unused_calls():
    c = study.base_config()
    model = compile_config(c)
    for unused in range(10):
        keyed_uniform(2026100304, 0, 'false_alarm', 'A01', unused)
    result = simulate(model, 2026100304, 0, True)
    model.digest = 'unused identity'
    assert result == simulate(model, 2026100304, 0, True)
    c['parameters'].update(automatic_isolation=False, observation_level=2, detection_probability=1.)
    assert result == simulate(c, 2026100304, 0, True)


def test_fixed_figure_coverage():
    assert len(figures.TITLES) == 10
    font = figures.chinese_font()
    assert 'last resort' not in font.lower()
    path = figures.font_manager.findfont(font, fallback_to_default=False)
    assert set(map(ord, '公共危机审核−×Δ²Σ')) <= set(figures.FT2Font(path).get_charmap())


def test_cjk_font_preference_excludes_last_resort(monkeypatch):
    path = figures.font_manager.findfont(figures.chinese_font(), fallback_to_default=False)
    entries = [SimpleNamespace(name='AAA Last Resort', fname='must-not-open'),
               SimpleNamespace(name='Other CJK', fname=path)]
    monkeypatch.setattr(figures.font_manager.fontManager, 'ttflist', entries)
    assert figures.chinese_font() == 'Other CJK'
    entries.append(SimpleNamespace(name='Noto Sans CJK SC', fname=path))
    assert figures.chinese_font() == 'Noto Sans CJK SC'
    entries.append(SimpleNamespace(name='Microsoft YaHei', fname=path))
    assert figures.chinese_font() == 'Microsoft YaHei'


@pytest.mark.parametrize('value,low,high,status,ci_status,state', [
    (2., 1., 3., 'defined', 'defined', 'defined'),
    (1., 0., 3., 'defined', 'defined', 'uncertain'),
    (2., np.nan, np.nan, 'defined', 'undefined', 'undefined'),
    (2., 1., np.inf, 'defined', 'defined', 'undefined'),
    (2., 1., 3., 'defined', 'undefined', 'undefined'),
    (0., 0., 0., 'structural_zero', 'structural_zero', 'structural_zero'),
])
def test_ci_display_preserves_points_and_interval_states(value, low, high, status, ci_status, state):
    frame = pd.DataFrame([dict(value=value, ci_low=low, ci_high=high, status=status, ci_status=ci_status)])
    before = frame.copy(deep=True)
    fig, axes = figures.plt.subplots(1, 4)
    try:
        assert figures._ci_state(low, high, ci_status) == state
        figures._forest(axes[0], frame, ['estimate'])
        figures._line(axes[1], frame, [1], 'blue', 'o')
        for ax, annotate in zip(axes[2:], (False, True)):
            figures._heatmap(ax, np.array([[value]]), ['row'], ['column'],
                             intervals=np.array([[[low, high]]]), statuses=np.array([[ci_status]]), annotate=annotate)
        for ax in axes[:3]:
            points = [line for line in ax.lines if line.get_marker() in ('o', 'x')]
            assert len(points) == 1
            point = points[0]
            assert point.get_marker() == ('x' if state == 'undefined' else 'o')
            if state == 'undefined':
                assert point.get_markeredgecolor() == figures.PALETTE['gray']
            else:
                assert point.get_markerfacecolor() == ('white' if state == 'uncertain' else point.get_markeredgecolor())
        assert axes[0].lines[-2].get_xdata()[0] == value
        assert axes[1].lines[-2].get_ydata()[0] == value
        for ax in axes[:2]:
            assert len(ax.collections) == (0 if state == 'undefined' else 1)
        assert ('CI 未定义' in axes[3].texts[0].get_text()) == (state == 'undefined')
        assert axes[2].images[0].get_array()[0, 0] == value
        pd.testing.assert_frame_equal(frame, before)
    finally:
        figures.plt.close(fig)


@pytest.mark.parametrize('stage,runs,seed,repetitions', [
    ('smoke', 8, 2026100304, 20),
    ('pilot', 500, 2026100301, 1000),
    ('formal', 5000, 2026100302, 1000),
])
def test_cli_stage_sampling_without_running_simulations(stage, runs, seed, repetitions, monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(run_all, 'ROOT', tmp_path)
    monkeypatch.setattr(run_all, 'source_hashes', lambda: {})
    monkeypatch.setattr(run_all.subprocess, 'check_output', lambda *args, **kwargs: 'test-head')
    monkeypatch.setattr(study, 'build_catalog', lambda spec, base: dict(cells=[]))
    monkeypatch.setattr(study, 'execute', lambda output, n, master, workers, models: calls.append((n, master)))
    monkeypatch.setattr(analyze, 'analyze', lambda raws, output, b, design, base: calls.append(b))
    monkeypatch.setattr(analyze, '_presentation', lambda *args: None)
    monkeypatch.setattr(figures, 'render', lambda *args: None)
    monkeypatch.setattr(figures, 'write_report', lambda *args: None)
    monkeypatch.setattr(sys, 'argv', ['run_all.py', '--' + stage])
    run_all.main()
    assert calls == [(runs, seed), repetitions]
    import json
    info = json.loads((tmp_path / '.run' / stage / 'run-info.json').read_text(encoding='utf-8'))
    assert info['status'] == 'complete' and info['master_seed'] == seed


def test_position_point_remains_defined_when_one_bootstrap_has_zero_SST(monkeypatch):
    design, base = study.build_catalog(), study.base_config()
    n = design['sampling']['smoke_runs']
    repetitions = design['sampling']['smoke_bootstrap']
    raw = {key: np.zeros((n, 30)) for key in VECTOR_METRICS}
    raw['base_deficit_hard'][:] = np.repeat([0., 1.], n // 2)[:, None]
    raw['base_deficit_grace'][:] = raw['base_deficit_hard']
    raw['ever_compromised_count'] = np.ones(n)
    raws = {r['cell_id']: raw for r in design['roles'] if r['family'] == 'position'}

    def indices(size, count, seed, domain):
        return np.array([np.arange(size)] * (count - 1) + [np.zeros(size, dtype=int)])

    monkeypatch.setattr(analyze, 'bootstrap_indices', indices)
    table, _ = analyze.position_analysis(raws, design, base, repetitions)
    assert table['status'].eq('defined').all() and (table['denominator'] > 0).all()
    assert np.isfinite(table['value']).all() and table['ci_status'].eq('undefined').all()
    assert table[['ci_low', 'ci_high']].isna().all().all()
    assert table['reason'].eq('bootstrap_zero_SST').all() and table['bootstrap_valid'].eq(repetitions - 1).all()


def test_family_reordering_preserves_cells_and_all_estimands(monkeypatch):
    original = study.protocol()
    reversed_spec = deepcopy(original)
    reversed_spec['families'].reverse()
    for family in reversed_spec['families']:
        family['axes'] = dict(reversed(list(family['axes'].items())))
        for axis in family['axes'].values():
            axis.reverse()
    reference = study.build_catalog()
    monkeypatch.setattr(study, 'protocol', lambda: reversed_spec)
    alternate = study.build_catalog()
    assert alternate['cells'] == reference['cells'] and alternate['roles'] == reference['roles']
    assert alternate == reference


def test_role_ids_preserve_metric_view_statistic_applicability():
    design = study.build_catalog()
    contrasts = {c['id']: c for c in design['contrasts']}
    primary = {e['id']: e for e in study.protocol()['primary_effects']}
    metrics = {analyze.LOSS, *(f['id'] for f in study.base_config()['functions'])}
    applicable = 0
    for contrast in contrasts.values():
        assert all(identity == study.object_hash(role) for identity, role in contrast['roles'].items())
    for estimand in design['estimands']:
        assert 'roles' not in estimand
        assert len(estimand['role_ids']) == len(set(estimand['role_ids']))
        for role in study._estimand_roles(estimand, contrasts):
            if role['tier'] == 'primary':
                assert estimand['metric'] in metrics
                assert estimand['view'] in {'primary', 'grace', 'equal_function', 'low_compromised_utility', 'high_compromised_utility'}
                assert estimand['statistic'] == primary[role['purpose']]['statistic']
                applicable += 1
    assert applicable == len(primary) * len(metrics) * 5


def test_only_consumed_bootstraps_are_computed_and_all_rows_remain(monkeypatch, tmp_path):
    design = study.build_catalog()
    n, repetitions = 4, 3
    raw = {key: np.zeros((n, 30)) for key in VECTOR_METRICS}
    raw.update({key: np.zeros(n) for key in SCALAR_METRICS})
    raw['run_index'] = np.arange(n)
    raws = {cell['id']: raw for cell in design['cells']}
    base = study.base_config()
    tail_calls, mean_calls = [], []
    tail, mean = analyze._bootstrap_tail, analyze._mean_contrast

    def record_tail(loss, matrix, indices):
        tail_calls.append(matrix.shape[1])
        return tail(loss, matrix, indices)

    def record_mean(vectors, coefficients, frequencies):
        mean_calls.append(1)
        return mean(vectors, coefficients, frequencies)

    monkeypatch.setattr(analyze, '_bootstrap_tail', record_tail)
    monkeypatch.setattr(analyze, '_mean_contrast', record_mean)
    tables = analyze.analyze(raws, tmp_path / 'all', repetitions, design, base)
    effects = tables['effects']
    assert len(effects) == 19260 and effects['estimand_id'].is_unique
    assert set(effects['estimand_id']) == {e['id'] for e in design['estimands']}
    assert effects['status'].eq('not_computed').sum() == 10455
    assert len(mean_calls) == (effects['status'].eq('defined') & effects['statistic'].eq('mean')).sum()
    _, bootstrap = analyze._statistic_plan(design)
    assert sorted(tail_calls) == sorted(len(metrics) for groups in bootstrap.values() for metrics in groups.values())
    assert effects.loc[effects['status'].eq('defined'), ['ci_low', 'ci_high']].notna().all().all()

    level_only = dict(design, estimands=[e for e in design['estimands'] if 'cell_id' in e])
    tail_calls.clear()
    mean_calls.clear()
    level_tables = analyze.analyze(raws, tmp_path / 'levels', repetitions, level_only, base)
    levels = level_tables['effects']
    assert not tail_calls and not mean_calls
    assert len(levels) == 10455 and levels['status'].eq('not_computed').all()
    pd.testing.assert_frame_equal(levels.reset_index(drop=True), effects[effects['estimand_type'].eq('level')].reset_index(drop=True))


def test_presentation_is_natural_unique_and_independent_of_outcomes(tmp_path):
    design = study.build_catalog()
    base, spec = study.base_config(), study.protocol()
    effects = pd.DataFrame([dict(estimand_id=e['id'], estimand_type='level' if 'cell_id' in e else 'direct',
        catalog_id=e.get('cell_id', e.get('contrast_id')), metric=e['metric'], view=e['view'], statistic=e['statistic'],
        value=1., ci_low=-1., ci_high=2., direction='uncertain', status='defined',
        tail_component=e['statistic'] == 'ES95' and e['metric'] != analyze.LOSS) for e in design['estimands']])
    tables = dict(effects=effects, position=pd.DataFrame(dict(view=design['position']['views'], value=[0., np.nan, np.nan],
                  status=['defined', 'undefined', 'undefined'], ci_status=['undefined'] * 3,
                  ci_low=[np.nan] * 3, ci_high=[np.nan] * 3, bootstrap_valid=[19, 0, 0], bootstrap_requested=[20] * 3,
                  reason=['bootstrap_zero_SST', 'zero_SST', 'zero_SST'])),
                  position_strata=pd.DataFrame(dict(view=['primary'] * 4, size=[2, 2, 3, 3],
                      count=[20, 20, 20, 20], initial_node=['A01', 'A02', 'A01', 'A03'], mean=[1., 2., 3., 4.])))
    frames = analyze._presentation(tables, design, base, spec)
    assert [len(frame) for frame in frames['dependency']] == [5, 5]
    assert frames['command_blocking'].attrs['unit'] == 'Agent-tick 差'
    assert frames['human']['label'].tolist() == [f'd={d},cap={cap}\nfull − autonomy' for d in (2, 5, 10) for cap in (1, 3, 'unlimited')]
    assert frames['command']['label'].tolist() == [f'd={d}\n{command} − distributed' for d in (2, 5, 10) for command in ('selective', 'centralized')]
    assert frames['isolation'][0]['label'].tolist() == [f'profile={profile},O={o}\nTrue − False' for profile in ('abrupt', 'progressive') for o in (0, 1, 2)]
    for key in ('dependency', 'isolation', 'information'):
        for frame in frames[key]:
            assert frame['label'].is_unique
    changed = effects.iloc[::-1].assign(value=-999., ci_low=-1000., ci_high=-998., direction='negative')
    alternate = analyze._presentation(dict(tables, effects=changed,
        position=tables['position'].iloc[::-1].assign(value=-999.),
        position_strata=tables['position_strata'].iloc[::-1].assign(mean=-999.)), design, base, spec)
    for key in ('dependency', 'isolation', 'information'):
        for left, right in zip(frames[key], alternate[key]):
            pd.testing.assert_frame_equal(left[['estimand_id', 'label']], right[['estimand_id', 'label']])
    for key in ('human', 'command', 'command_blocking', 'command_with_human'):
        pd.testing.assert_frame_equal(frames[key][['estimand_id', 'label']], alternate[key][['estimand_id', 'label']])
    for (left_id, left), (right_id, right) in zip(frames['isolation_functions'], alternate['isolation_functions']):
        assert left_id == right_id
        pd.testing.assert_frame_equal(left[['estimand_id', 'label']], right[['estimand_id', 'label']])
    for key in ('fixed_budget', 'fixed_budget_tail', 'oversight_capacity'):
        for (left_id, left), (right_id, right) in zip(frames[key], alternate[key]):
            assert left_id == right_id
            pd.testing.assert_frame_equal(left[['estimand_id', 'label']], right[['estimand_id', 'label']])
    assert frames['monitoring_levels']['condition'].tolist() == [1, 3, 5]
    assert frames['capacity_levels']['condition'].tolist() == [1, 2, 3, 4, 6, 10, 'unlimited']
    assert dict(frames['fixed_budget'])[analyze.LOSS]['label'].tolist() == ['\n3 − 1', '\n5 − 1', '\n5 − 3']
    for key, axis in (('triage_lines', 'deadline'), ('triage_functions', 'label')):
        for (left_id, left), (right_id, right) in zip(frames[key], alternate[key]):
            assert left_id == right_id
            pd.testing.assert_series_equal(left[axis], right[axis])
    assert frames['position']['view'].tolist() == alternate['position']['view'].tolist()
    columns = ['view', 'size', 'count', 'initial_node']
    pd.testing.assert_frame_equal(frames['position_example'][columns].reset_index(drop=True),
                                  alternate['position_example'][columns].reset_index(drop=True))
    for metric in ('information_blocking', 'review_blocking', 'denial_blocking', 'command_blocking', 'isolation_blocking', 'service_blocking'):
        assert analyze._metric_unit(metric) == 'Agent-tick 差'
    for metric in ('false_isolations', 'false_review_denials', 'wrong_actions'):
        assert analyze._metric_unit(metric) == '次数差'
    for metric in ('mean_information_coverage', 'mean_clean_information_fraction'):
        assert analyze._metric_unit(metric) == '覆盖比例差'
    assert analyze._metric_unit('F3') == '归一化服务缺口 × 抽象tick'
    assert analyze._metric_unit(analyze.LOSS) == '功能关键性 × 抽象tick'
    pd.testing.assert_frame_equal(frames['primary'][['estimand_id', 'label']], alternate['primary'][['estimand_id', 'label']])
    main = frames['primary'][frames['primary']['view'].eq('primary') & frames['primary']['metric'].eq(analyze.LOSS)]
    assert main['label'].tolist() == [
        'RQ1 / H1b：共同依赖均值差', 'RQ1 / H1b：共同依赖 ES95 差', 'RQ2 / H2a：观察阶段与隔离交互',
        'RQ2 / H2b：暴露节奏与隔离交互', 'RQ3 / H3a：审核时限交互', 'RQ3 / H3a：审核容量交互',
        'RQ3 / H3b：生命安全分诊与 FIFO', 'RQ3 / H3c：附加指挥复核时限交互', 'RQ3 / H3d：信息等待时限交互']
    figures.write_report(frames, tmp_path, 8, 20, 'smoke')
    report = (tmp_path / 'report.md').read_text(encoding='utf-8')
    assert report.index('主视图：') < report.index('评价敏感性：')
    assert 'RQ1 / H1a：位置增量 R²' in report and 'bootstrap_zero_SST' in report
    assert '| defined | undefined (19/20;' in report and '| undefined | undefined (0/20;' in report
    assert 'pointwise 模拟区间' in report and '现实政策效果的不确定性已被识别' in report
    assert '`not_computed` 表示未计算置信区间，而不是没有点估计或模拟失败' in report
    for stage in ('pilot', 'formal'):
        figures.write_report(frames, tmp_path, 8, 20, stage)
        report = (tmp_path / 'report.md').read_text(encoding='utf-8')
        assert report.startswith(f'# 合成情景 {stage.capitalize()} ')
        for term in ('累计检查', 'middle−early', '监督拥塞', 'worst_function_deficit', 'F1/F2', 'unlimited'):
            assert term in report
        for key in ('fixed_budget', 'fixed_budget_tail', 'oversight_capacity'):
            for _, rows in frames[key]:
                assert all(identity[:12] in report for identity in rows['estimand_id'])


def test_verification_quality_registers_only_quality_slices():
    for contrast in study.build_catalog()['contrasts']:
        assert not any(r['purpose'] in {'verification', 'critical_global'} and r['dimensions']['family'] == 'verification_quality' for r in contrast['roles'].values())


@pytest.mark.parametrize('case', ['boolean_sampling', 'unknown_sampling', 'unknown_view', 'bad_utility', 'duplicate_family', 'unknown_primary'])
def test_protocol_boundary_rejects_invalid_specification(case, monkeypatch):
    spec = deepcopy(study.protocol())
    if case == 'boolean_sampling': spec['sampling']['pilot_runs'] = True
    elif case == 'unknown_sampling': spec['sampling']['extra'] = 1
    elif case == 'unknown_view': spec['evaluation_views']['primary']['members'] = 'unknown'
    elif case == 'bad_utility': spec['evaluation_views']['primary']['compromised_utility'] = float('nan')
    elif case == 'duplicate_family': spec['families'].append(deepcopy(spec['families'][0]))
    else: spec['primary_effects'][0]['extra'] = 1
    monkeypatch.setattr(study.yaml, 'load', lambda *args, **kwargs: spec)
    with pytest.raises(ValueError):
        study.protocol()


def test_supplement_catalog_preserves_old_cells_and_matching_exogenous_conditions():
    spec, base = study.protocol(), study.base_config()
    design = study.build_catalog(spec, base)
    old_spec = deepcopy(spec)
    old_spec['families'] = [f for f in spec['families'] if f['id'] not in {'fixed_budget', 'oversight_capacity'}]
    old_cells = {c['id'] for c in study.build_catalog(old_spec, base)['cells']}
    cells = {c['id']: c for c in design['cells']}
    assert len(old_cells) == 248 and len(cells.keys() - old_cells) == 7
    assert old_cells <= cells.keys()
    budget = sorted((r for r in design['roles'] if r['family'] == 'fixed_budget'), key=lambda r: r['axes']['monitoring_offset'])
    assert [r['axes']['monitoring_offset'] for r in budget] == [1, 3, 5]
    parameters = []
    for role in budget:
        p = cells[role['cell_id']]['parameters'].copy()
        assert p.pop('monitoring_offset') == role['axes']['monitoring_offset']
        assert p['automatic_isolation'] and 'observation_level' not in p
        assert p['initial_nodes'] == [] and p['shock_type'] == 'data' and p['shock_profile'] == 'abrupt'
        assert (p['detection_probability'], p['false_alarm_probability']) == (.5, .005)
        parameters.append(p)
    assert parameters[0] == parameters[1] == parameters[2]
    capacity = [r for r in design['roles'] if r['family'] == 'oversight_capacity']
    assert {r['axes']['review_capacity'] for r in capacity} == {1, 2, 3, 4, 6, 10, 'unlimited'}
    consumer_cells, references, comparisons = set(), set(), set()
    for contrast in design['contrasts']:
        for role in contrast['roles'].values():
            if role['purpose'] not in {'fixed_budget', 'oversight_capacity'}:
                continue
            assert contrast['terms'] == study.normalize_terms(contrast['terms'], cells)
            consumer_cells.update(cell for cell, _ in contrast['terms'])
            target = next(cell for cell, coef in contrast['terms'] if coef == 1)
            reference = next(cell for cell, coef in contrast['terms'] if coef == -1)
            if role['purpose'] == 'fixed_budget':
                comparisons.add((cells[target]['parameters']['monitoring_offset'], cells[reference]['parameters']['monitoring_offset']))
            else:
                references.add(reference)
                model = study.configuration(cells[target], base)
                p = model.config['parameters']
                assert (p['initial_nodes'], p['shock_type'], p['command_structure']) == (['A04'], 'none', 'distributed')
                assert (p['review_scope'], p['review_priority'], p['review_service_time'], p['deadline_window']) == ('all', 'life_safety', 3, 5)
                model.config['parameters']['oversight'] = 'autonomy'
                assert compile_config(model.config).digest == reference
    assert comparisons == {(3, 1), (5, 1), (5, 3)} and len(references) == 1
    assert cells.keys() - old_cells <= consumer_cells


def test_supplement_metrics_paired_bootstrap_and_function_decomposition_without_simulation(monkeypatch, tmp_path):
    design, base = study.build_catalog(), study.base_config()
    contrasts = {c['id']: c for c in design['contrasts']}
    selected = {c['id'] for c in design['contrasts'] if any(
        r['purpose'] in {'fixed_budget', 'oversight_capacity', 'triage', 'dependency'} for r in c['roles'].values())}
    metrics = {analyze.LOSS, 'worst_function_deficit', *(f['id'] for f in base['functions'])}
    design['estimands'] = [e for e in design['estimands'] if e.get('contrast_id') in selected and e['view'] == 'primary' and e['metric'] in metrics]
    n, repetitions = 6, 13
    rng = np.random.default_rng(101)
    raws = {}
    independent = {}
    ids = [a['id'] for a in sorted(base['agents'], key=lambda a: a['id'])]
    criticality = np.array([f['criticality'] for f in base['functions']])
    for cell in design['cells']:
        raw = {key: rng.uniform(0, 5, (n, 30)) for key in VECTOR_METRICS}
        raw.update({key: np.zeros(n) for key in SCALAR_METRICS})
        raw['run_index'] = np.arange(n)
        raws[cell['id']] = raw
        deficits = raw['base_deficit_hard'] + .5 * raw['compromised_weight_hard']
        functions = np.column_stack([sum(deficits[:, ids.index(agent)] * w for agent, w in f['members'].items()) / sum(f['members'].values()) for f in base['functions']])
        independent[cell['id']] = dict(service_deficit=functions @ criticality, worst_function_deficit=functions.max(axis=1),
                                      **{f['id']: functions[:, j] for j, f in enumerate(base['functions'])})
    assert not np.isclose(independent[design['cells'][0]['id']]['worst_function_deficit'].mean(),
                          max(independent[design['cells'][0]['id']][f['id']].mean() for f in base['functions']))

    def forbidden(*args, **kwargs):
        pytest.fail('Evaluation and reporting must not simulate')

    monkeypatch.setattr(study, 'execute', forbidden)
    monkeypatch.setattr(study, 'simulate', forbidden)
    tables = analyze.analyze(raws, tmp_path, repetitions, design, base)
    indices = np.random.Generator(np.random.PCG64(np.random.SeedSequence([design['sampling']['seeds']['bootstrap'], 0]))).integers(0, n, size=(repetitions, n), dtype=np.int64)
    effects = tables['effects']
    for row in effects[effects['statistic'].eq('mean')].itertuples():
        paired = sum(coef * independent[cell][row.metric] for cell, coef in contrasts[row.catalog_id]['terms'])
        assert row.value == pytest.approx(paired.mean(), abs=1e-12)
        assert [row.ci_low, row.ci_high] == pytest.approx(np.quantile(paired[indices].mean(axis=1), [.025, .975]), abs=1e-12)
    for _, group in effects.groupby(['catalog_id', 'statistic']):
        components = group.set_index('metric')
        if all(f['id'] in components.index for f in base['functions']):
            assert components.loc[[f['id'] for f in base['functions']], 'value'].to_numpy() @ criticality == pytest.approx(components.loc[analyze.LOSS, 'value'], abs=1e-12)


@pytest.mark.parametrize('metric,invalid', [('completed_reviews', 31), ('review_queue_time', 10000),
    ('critical_review_queue_time', 10000), ('monitoring_requests', 29), ('true_detections', 31), ('deadline_misses', 31)])
def test_supplement_raw_diagnostics_reject_contract_violations(metric, invalid):
    base = study.base_config()
    base['parameters'].update(automatic_isolation=True, monitoring_offset=3)
    model = compile_config(base)
    row = simulate(model, 17)
    raw = {key: np.asarray([value], dtype=float) for key, value in row.items()}
    raw['run_index'] = np.array([0])
    study.validate_raw(raw, 1, model)
    raw[metric][0] = invalid
    with pytest.raises(ValueError):
        study.validate_raw(raw, 1, model)
