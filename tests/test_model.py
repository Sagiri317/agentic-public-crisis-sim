"""Hand-computable, adversarial and extreme-condition model contracts."""
from copy import deepcopy
import hashlib
import json
import sys

import numpy as np
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experiments'))
from agent_crisis_sim.config import compile_config, partition
from agent_crisis_sim.simulation import Run, simulate, PHASES, keyed_uniform
from study import base_config
from analyze import evaluate


def fixture(**parameters):
    c = base_config()
    chosen = ['A01', 'A02', 'A17', 'A28']
    c['agents'] = [a for a in c['agents'] if a['id'] in chosen]
    for a in c['agents']:
        a['release'] = 0
    c['functions'] = [dict(id='F3', name='test', criticality=1., members={'A01': 1., 'A02': 1., 'A17': 2., 'A28': 1.})]
    c['fixed']['life_safety_functions'] = ['F3']
    c['edges'] = [dict(source='A01', target='A17', role='required', verify=True)]
    c['resource_users'] = dict(model=chosen, data=chosen, tool=['A17'])
    c['parameters'].update(initial_nodes=[], horizon=10, information_error_rate=0.,
                            propagation_probability=0., supplemental_check_effectiveness=0.,
                            false_alarm_probability=0., information_policy='fast')
    c['parameters'].update(parameters)
    return c


def runtime(**parameters):
    return Run(compile_config(fixture(**parameters)), 17, 0, True)


def events(result, event, agent=None):
    return [e for e in result['events'] if e['event'] == event and (agent is None or e['agent'] == agent)]


def step_all(run):
    while run.t < run.p['horizon']:
        run.step()
    return run.result()


def test_base_model_structure_and_information_consumers():
    model = compile_config(base_config())
    assert len(model.agents) == 30 and len(model.function_weights) == 7
    assert len(model.config['edges']) == 79
    a29 = model.agents.index(next(a for a in model.agents if a['id'] == 'A29'))
    assert len(model.required[a29]) == 2 and model.outgoing[a29]
    assert set(model.config['resource_users']['tool']) == {a['id'] for i, a in enumerate(model.agents) if model.external[i]}


@pytest.mark.parametrize('field,value', [
    ('propagation_probability', float('nan')), ('review_sensitivity', float('inf')),
    ('review_specificity', -.1), ('execution_autonomy', 2), ('review_capacity', True),
    ('command_capacity', 'unlimited'), ('deadline_window', 0), ('recovery_delay', 0),
    ('shock_time', -1), ('partition_seed', True), ('observation_level', True),
    ('oversight', 'risk'), ('information_policy', 'unknown'), ('automatic_isolation', 1),
])
def test_invalid_fields_even_when_inactive(field, value):
    with pytest.raises(ValueError):
        compile_config(fixture(**{field: value}))


@pytest.mark.parametrize('field', ['unknown_parameter', 'function_mapping'])
def test_strict_parameter_schema_rejects_unknown_fields(field):
    c = fixture()
    c['parameters'][field] = 1
    with pytest.raises(ValueError, match='parameters fields'):
        compile_config(c)


@pytest.mark.parametrize('case', ['unknown_top', 'duplicate_agent', 'duplicate_edge', 'cycle', 'unknown_endpoint', 'empty_function', 'zero_weight', 'nonfinite_weight', 'unknown_member', 'unknown_resource', 'duplicate_resource', 'tool_internal', 'K', 'latency_zero', 'bad_release', 'bool_authority', 'unknown_agent_field', 'unknown_edge_field'])
def test_structure_adversaries(case):
    c = fixture()
    if case == 'unknown_top': c['extra'] = 1
    elif case == 'duplicate_agent': c['agents'].append(deepcopy(c['agents'][0]))
    elif case == 'duplicate_edge': c['edges'].append(deepcopy(c['edges'][0]))
    elif case == 'cycle': c['edges'].append(dict(source='A17', target='A01', role='required', verify=False))
    elif case == 'unknown_endpoint': c['edges'][0]['source'] = 'missing'
    elif case == 'empty_function': c['functions'][0]['members'] = {}
    elif case == 'zero_weight': c['functions'][0]['members']['A01'] = 0
    elif case == 'nonfinite_weight': c['functions'][0]['members']['A01'] = float('inf')
    elif case == 'unknown_member': c['functions'][0]['members']['unknown'] = 1
    elif case == 'unknown_resource': c['resource_users']['data'].append('unknown')
    elif case == 'duplicate_resource': c['resource_users']['data'].append('A01')
    elif case == 'tool_internal': c['resource_users']['tool'] = ['A28']
    elif case == 'K': c['parameters'].update(shock_type='tool', resource_groups=2)
    elif case == 'latency_zero': c['fixed']['message_latency'] = 0
    elif case == 'bad_release': c['agents'][0]['release'] = -1
    elif case == 'bool_authority': c['agents'][0]['authority'] = True
    elif case == 'unknown_agent_field': c['agents'][0]['human_review_class'] = 'high'
    else: c['edges'][0]['trust'] = .9
    with pytest.raises(ValueError):
        compile_config(c)


def test_phase_order_and_trace_does_not_change_metrics():
    c = fixture()
    traced = simulate(c, 17, 0, True)
    raw = simulate(c, 17, 0)
    assert all(traced[key] == value for key, value in raw.items())
    for tick in range(c['parameters']['horizon']):
        assert tuple(e['name'] for e in events(traced, 'phase') if e['time'] == tick) == PHASES
    assert min(e['time'] for e in events(traced, 'message_receive')) >= 1


def test_clean_timely_world_primary_exact_zero():
    c = base_config()
    c['parameters'].update(initial_nodes=[], shock_type='none', information_error_rate=0.)
    r = simulate(c, 9)
    loss, functions, _ = evaluate({k: np.asarray([v]) for k, v in r.items()}, c,
        {'members': 'configured', 'function_criticality': 'configured', 'timeliness': 'hard', 'compromised_utility': 'base'})
    assert loss[0] == 0 and np.array_equal(functions, np.zeros((1, 7)))


def test_zero_missing_and_zero_propagation_extremes():
    c = fixture(initial_nodes=['A01'], propagation_probability=0., information_error_rate=0.)
    r = simulate(c, 2, 0, True)
    assert r['ever_compromised_count'] == 1
    assert not [e for e in events(r, 'contaminate') if e['cause'] in {'missing', 'message'}]


def test_wrong_accepted_information_never_leaks_truth_into_policy():
    c = fixture(initial_nodes=['A01'], local_verification_probability=0.,
                information_policy='integrated', propagation_probability=0.)
    r = simulate(c, 2, 0, True)
    row = r['trajectory'][1]
    assert row['coverage'][2] == 1 and row['clean_coverage'][2] == 0
    assert events(r, 'propose', 'A17')[0]['time'] == 1
    assert not row['compromised'][2]


def test_rejected_new_message_invalidates_old_slot_and_stale_is_not_rechecked():
    run = runtime(verification_mode='global', verification_effectiveness=1.)
    run.t = 2
    run.accepted[0], run.clean[0], run.seen[0] = True, True, 0
    run.messages[2] = [(0, 1, False)]
    run.deliver()
    assert run.obs[2] == run.clean_coverage[2] == 0
    assert run.metrics['verification_load'] == 1
    run.t = 3
    run.messages[3] = [(0, 0, True), (0, 1, False)]
    run.deliver()
    assert run.metrics['verification_load'] == 1 and run.obs[2] == 0


@pytest.mark.parametrize('role', ['required', 'supplemental'])
def test_isolated_new_message_invalidates_old_clean_slot_without_load_or_replay(role):
    c = fixture(verification_mode='global', verification_effectiveness=1.)
    c['edges'][0]['role'] = role
    run = Run(compile_config(c), 17, 0, True)
    run.t = 1
    run.messages[1] = [(0, 0, True)]
    run.deliver()
    assert run.accepted[0] and run.clean[0] and run.metrics['verification_load'] == 1
    run.isolated_until[2], run.t = 4, 2
    run.messages[2] = [(0, 2, False)]
    run.deliver()
    assert run.seen[0] == 2 and not run.accepted[0] and not run.clean[0]
    assert run.metrics['verification_load'] == 1 and not run.messages
    run.t = 4
    run.release_holds()
    run.deliver()
    assert not run.accepted[0] and not run.clean[0]
    assert (run.obs[2] == run.clean_coverage[2] == 0) if role == 'required' else run.supplement[2] == 0
    run.t = 5
    run.messages[5] = [(0, 1, True), (0, 2, True)]
    run.deliver()
    assert not run.accepted[0] and run.seen[0] == 2 and run.metrics['verification_load'] == 1


def test_clean_and_contaminated_messages_share_verification_load():
    counts = []
    for initial in ([], ['A01']):
        r = simulate(fixture(initial_nodes=initial, verification_mode='global',
                             verification_effectiveness=1.), 2, 0, True)
        counts.append(r['verification_load'])
    assert counts == [1, 1]


def test_supplemental_positive_consumer_can_succeed_and_fail_without_erasing_harm():
    c = fixture(initial_nodes=['A17'], supplemental_check_effectiveness=1.)
    c['edges'][0]['role'] = 'supplemental'
    run = Run(compile_config(c), 17, 0, True)
    run.compromised[2], run.harm[2] = True, True
    run.messages[1] = [(0, 0, True)]
    run.t = 1
    run.deliver()
    assert not run.compromised[2] and run.harm[2]
    c['parameters']['supplemental_check_effectiveness'] = 0.
    other = Run(compile_config(c), 17, 0, True)
    other.compromised[2] = True
    other.messages[1], other.t = [(0, 0, True)], 1
    other.deliver()
    assert other.compromised[2]


def test_same_tick_message_order_is_invariant():
    c = fixture(propagation_probability=1., local_verification_probability=0.)
    c['edges'].append(dict(source='A02', target='A17', role='supplemental', verify=True))
    a, b = Run(compile_config(c), 9, 0, True), Run(compile_config(c), 9, 0, True)
    for run in (a, b):
        run.messages[1] = [(0, 0, False), (1, 0, True)]
        run.t = 1
    b.messages[1].reverse()
    a.deliver()
    b.deliver()
    assert a.compromised == b.compromised and a.accepted == b.accepted and a.events == b.events


def test_missing_error_precedes_review_and_is_drawn_once():
    run = runtime(information_error_rate=1., oversight='full', review_capacity='unlimited',
                  review_service_time=1, review_sensitivity=1., review_specificity=1.)
    result = step_all(run)
    missing = [e for e in events(result, 'contaminate', 'A17') if e['cause'] == 'missing']
    assert len(missing) == 1 and missing[0]['phase'] == 'propose'
    assert events(result, 'review_complete', 'A17')[0]['outcome'] == 'corrected'
    assert result['wrong_actions'] == 0


def test_perfect_review_reads_current_truth_and_service_has_no_hidden_tick():
    run = runtime(oversight='full', review_capacity='unlimited', review_service_time=2,
                  review_sensitivity=1., review_specificity=1., propagation_probability=1.,
                  local_verification_probability=0.)
    run.step()
    run.messages[2] = [(0, 1, False)]
    run.step()
    run.step()
    record = run.review_requests[2]
    assert record['started_at'] == 0 and record['completed_at'] == 2
    assert record['truth'] is True and record['outcome'] == 'corrected'
    assert not run.compromised[2] and run.resolved[2] == 2


def test_false_denial_hold_is_exact_once_and_unlimited_eliminates_queue_only():
    r = simulate(fixture(oversight='full', review_capacity='unlimited', review_service_time=1,
                         review_specificity=0., false_denial_hold=2), 7, 0, True)
    assert r['human_review_load'] == 4 and r['false_review_denials'] == 4
    assert r['review_blocking'] == 4 and r['denial_blocking'] == 8
    assert r['critical_review_queue_time'] == 0
    assert all(q['started_at'] == q['requested_at'] for q in r['review_records'])
    assert all(e['time'] == 3 for e in events(r, 'resolve'))


def test_review_miss_does_not_force_wrong_execution_or_resample():
    r = simulate(fixture(initial_nodes=['A17'], oversight='full', review_capacity='unlimited',
                         review_service_time=1, review_sensitivity=0., execution_autonomy=0.), 7, 0, True)
    assert events(r, 'review_complete', 'A17')[0]['outcome'] == 'missed'
    assert r['wrong_actions'] == 0 and len(events(r, 'defer', 'A17')) == 1
    assert r['unfinished_tasks'] == 1


def test_later_correction_releases_deferred_action():
    run = runtime(initial_nodes=['A17'], execution_autonomy=0.)
    run.step()
    assert run.resolved[2] == -1 and run.unsafe_attempted[2]
    run.change(2, False, 'fixture_correction')
    run.step()
    assert run.resolved[2] == 1


@pytest.mark.parametrize('scope,count', [('all', 4), ('external', 1), ('direct_control', 1)])
def test_review_scope_has_real_consumer_and_internal_messages_are_tentative(scope, count):
    r = simulate(fixture(initial_nodes=['A01'], oversight='full', review_scope=scope,
                         review_service_time=3, review_capacity='unlimited'), 7, 0, True)
    assert r['human_review_load'] == count
    assert events(r, 'send', 'A01')[0]['time'] == 0
    assert events(r, 'send', 'A01')[0]['clean'] is False
    assert not events(r, 'wrong_action', 'A28')


def test_no_external_permission_does_not_count_internal_error():
    r = simulate(fixture(initial_nodes=['A28', 'A01'], execution_autonomy=1.), 7)
    assert r['ever_compromised_count'] == 2 and r['wrong_actions'] == 0


def test_abrupt_progressive_share_latent_exposure_and_resource_not_release_bound():
    c = fixture(shock_type='model', shock_probability=1., shock_time=0, horizon=12)
    c['agents'][0]['release'] = 7
    a = simulate(c, 9, 0, True)
    c['parameters']['shock_profile'] = 'progressive'
    b = simulate(c, 9, 0, True)
    assert set(a['exposure']) == set(b['exposure']) == set(c['resource_users']['model'])
    assert [e['time'] for e in events(a, 'resource_consume', 'A01')] == [0]
    assert events(b, 'resource_consume', 'A01')[0]['time'] < 7


@pytest.mark.parametrize('kind,compromised,wrong', [('data', 0, 0), ('model', 4, 1), ('tool', 0, 1)])
def test_resource_injection_semantics(kind, compromised, wrong):
    r = simulate(fixture(shock_type=kind, shock_probability=1., shock_time=0,
                         local_verification_probability=1., execution_autonomy=1.,
                         oversight='full', review_capacity='unlimited', review_service_time=1,
                         review_sensitivity=0., review_specificity=1.), 3, 0, True)
    assert sum(e['cause'] in {'data', 'model'} for e in events(r, 'contaminate')) == compromised
    assert r['wrong_actions'] == wrong
    if kind == 'tool':
        assert all(not q['truth'] for q in r['review_records'])


def test_tool_exposure_after_completed_action_adds_no_action():
    r = simulate(fixture(shock_type='tool', shock_probability=1., shock_time=5), 4, 0, True)
    assert r['wrong_actions'] == 0 and len(events(r, 'resolve', 'A17')) == 1


def test_resource_consumption_deferred_only_by_isolation_once():
    run = runtime(shock_type='model', shock_probability=1., shock_time=0,
                  automatic_isolation=True, detection_probability=0.)
    run.isolated_until[0] = 2
    run.step()
    run.step()
    assert 0 not in run.exposure_consumed
    run.step()
    assert 0 in run.exposure_consumed and run.compromised[0]
    assert [e['time'] for e in run.events if e['event'] == 'resource_consume' and e['agent'] == 'A01'] == [2]


@pytest.mark.parametrize('level,first', [(2, 0), (1, 1), (0, 1)])
def test_monitor_opportunity_for_truth_and_false_alarm_is_identical(level, first):
    for initial, probability in ((['A17'], 'detection_probability'), ([], 'false_alarm_probability')):
        c = fixture(initial_nodes=initial, automatic_isolation=True, observation_level=level,
                    execution_autonomy=1., **{probability: 1.})
        r = simulate(c, 7, 0, True)
        assert events(r, 'isolate', 'A17')[0]['time'] == first
        if level == 0 and initial:
            assert events(r, 'wrong_action', 'A17')[0]['time'] == 0


def test_failed_rollback_preserves_harm_and_single_attempt_after_repeated_isolation():
    run = runtime(initial_nodes=['A17'], execution_autonomy=1., automatic_isolation=True,
                  observation_level=0, detection_probability=1., recovery_delay=1,
                  rollback_success=0.)
    r = step_all(run)
    assert len(events(r, 'rollback', 'A17')) == 1
    assert events(r, 'rollback', 'A17')[0]['success'] is False
    assert r['active_harms_at_horizon'] == 1 and len(events(r, 'wrong_action', 'A17')) == 1


def test_recovery_is_not_immunity_and_historical_message_cannot_be_retracted():
    run = runtime(initial_nodes=['A01'], automatic_isolation=True, observation_level=1,
                  detection_probability=1., recovery_delay=1, propagation_probability=1.,
                  local_verification_probability=0.)
    run.step()
    assert run.messages[1][0][2] is False
    run.step()
    assert run.compromised[2]
    run.step()
    assert not run.compromised[0]
    run.change(0, True, 'new_pollution')
    assert run.compromised[0]


def test_review_spends_time_through_isolation_and_A28_pauses_command():
    run = runtime(oversight='full', review_capacity='unlimited', review_service_time=2,
                  review_specificity=1., command_structure='centralized', command_service_time=1)
    run.step()
    run.isolated_until[2] = 4
    run.step()
    run.step()
    assert run.review_done[2] and run.review_requests[2]['completed_at'] == 2
    run.t = 4
    run.release_holds()
    run.dispatch()
    assert 2 in run.command_active
    run.command_active[2] = 0
    run.isolated_until[3] = 6
    run.finish_command()
    assert not run.command_done[2] and run.command_active[2] == 0
    run.t = 6
    run.release_holds()
    run.finish_command()
    assert run.command_done[2]


@pytest.mark.parametrize('effect,expected', [(0., True), (1., False)])
def test_command_has_real_cross_domain_correction_and_zero_effect_ablation(effect, expected):
    run = runtime(command_structure='centralized', command_intercept_effectiveness=effect)
    run.proposed = [0] * 4
    run.compromised[2] = True
    run.obs, run.clean_coverage, run.supplement = run.coverage()
    run.command_requests[2] = dict(completed_at=None)
    run.command_active[2] = 0
    run.finish_command()
    assert run.compromised[2] == expected


def test_A28_compromise_is_single_point_risk_and_target_snapshot_is_current():
    run = runtime(command_structure='centralized', command_error_probability=1.)
    run.proposed = [0] * 4
    run.compromised[3] = True
    run.command_requests[2] = dict(completed_at=None)
    run.command_active[2] = 0
    run.finish_command()
    assert run.compromised[2]
    assert not run.m.command_targets[3]


def test_least_slack_can_reverse_fifo_and_life_safety_does_not_read_outcome():
    run = runtime(oversight='full', review_priority='due_first', review_capacity=1)
    run.review_requests = {0: dict(requested_at=0), 2: dict(requested_at=1)}
    run.deadline[0], run.deadline[2] = 10, 2
    assert sorted([0, 2], key=run.review_key) == [2, 0]
    run.p['review_priority'] = 'fifo'
    assert sorted([0, 2], key=run.review_key) == [0, 2]
    run.p['review_priority'] = 'life_safety'
    before = sorted([0, 2], key=run.review_key)
    run.harm[0], run.compromised[2] = True, True
    assert sorted([0, 2], key=run.review_key) == before == [2, 0]


def test_information_policies_have_distinct_partial_arrival_times():
    times = []
    for policy in ('fast', 'balanced', 'integrated'):
        c = fixture(information_policy=policy)
        c['edges'].append(dict(source='A02', target='A17', role='required', verify=True))
        run = Run(compile_config(c), 7, 0, True)
        run.messages[1] = [(0, 0, True)]
        # A02 has not produced information until beyond the integrated wait cap.
        run.m.agents[1]['release'] = 8
        r = step_all(run)
        times.append(events(r, 'propose', 'A17')[0]['time'])
    assert times == [0, 1, 3]


def test_blocking_is_mutually_exclusive_and_no_completion_tick_is_charged():
    run = runtime(oversight='full', command_structure='centralized')
    run.proposed = [0] * 4
    run.review_requests[2] = dict(requested_at=0)
    run.command_requests[2] = dict(requested_at=0)
    run.isolated_until[2], run.denied_until[2] = 1, 2
    run.obs, run.clean_coverage, run.supplement = run.coverage()
    run.measure()
    assert run.metrics['isolation_blocking'] == 1 and run.metrics['denial_blocking'] == run.metrics['review_blocking'] == run.metrics['command_blocking'] == 0
    r = simulate(fixture(oversight='full', review_capacity='unlimited', review_service_time=1, review_specificity=1.), 2, 0, True)
    assert sum(r[key + '_blocking'] for key in ('information', 'review', 'denial', 'command', 'isolation')) == 4
    assert all(not any(row['blockers']) for row in r['trajectory'][1:])


def test_healthy_overdue_queue_is_not_zero_loss_and_grace_hand_calculation():
    c = fixture(oversight='full', review_capacity='unlimited', review_service_time=5,
                review_specificity=1., deadline_window=1, horizon=5)
    r = simulate(c, 9, 0, True)
    assert r['base_deficit_hard'] == [3.] * 4
    assert r['base_deficit_grace'] == [1.5] * 4
    assert r['unfinished_tasks'] == 4
    assert r['mean_information_coverage'] == 1


@pytest.mark.parametrize('entity', ['A17', ['资源', 'A17'], {'b': 2, 'a': '中文'}])
def test_common_random_field_exact_encoding_and_non_drift(entity):
    key = [9, 3, 'missing', entity, 0, 0]
    encoded = json.dumps(key, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    expected = (int(hashlib.sha256(encoded).hexdigest()[:13], 16) + .5) / 2**52
    assert keyed_uniform(*key[:5]) == expected
    before = keyed_uniform(9, 3, 'review_sensitivity', 'A17', 0)
    for t in range(12):
        keyed_uniform(9, 3, 'false_alarm', 'A01', t)
    assert keyed_uniform(9, 3, 'review_sensitivity', 'A17', 0) == before
    assert 0 < before < 1


@pytest.mark.parametrize('oversight', ['autonomy', 'full'])
def test_horizon_prefix_and_ordering_identity(oversight):
    c = fixture(oversight=oversight, initial_nodes=['A01'], propagation_probability=.7,
                automatic_isolation=True, observation_level=2, detection_probability=.3, horizon=5)
    a = simulate(c, 9, 3, True)
    c['parameters']['horizon'] = 12
    b = simulate(c, 9, 3, True)
    assert a['trajectory'] == b['trajectory'][:5]
    assert a['events'] == [e for e in b['events'] if e['time'] < 5]
    reversed_config = deepcopy(c)
    reversed_config['agents'].reverse()
    reversed_config['edges'].reverse()
    assert compile_config(c).digest == compile_config(reversed_config).digest
    assert b == simulate(reversed_config, 9, 3, True)


def test_numeric_identity_and_partition_determinism():
    c = fixture(propagation_probability=1)
    a = compile_config(c).digest
    c['parameters']['propagation_probability'] = 1.
    assert compile_config(c).digest == a
    assert partition(['b', 'a', 'c', 'd'], 'data', 2, 0) == [['a', 'c'], ['b', 'd']]
    assert partition(['b', 'a', 'c', 'd'], 'data', 2, 4101) == partition(['d', 'c', 'b', 'a'], 'data', 2, 4101)


def test_display_names_do_not_change_identity_or_trajectory():
    c = fixture(initial_nodes=['A01'], propagation_probability=.7)
    original = compile_config(c)
    for item in c['agents'] + c['functions']:
        item['name'] = '展示名称 ' + item['id']
    renamed = compile_config(c)
    assert renamed.digest == original.digest
    assert simulate(renamed, 9, 3, True) == simulate(original, 9, 3, True)
    c['agents'][0]['release'] += 1
    assert compile_config(c).digest != original.digest


@pytest.mark.parametrize('groups', [[[]], [['A17'], ['A17']], [['unknown']], [['A01']]])
def test_materialized_groups_are_validated_at_catalog_boundary(groups):
    with pytest.raises(ValueError):
        compile_config(fixture(shock_type='tool'), groups)


def test_no_required_input_coverage_is_undefined_and_supplemental_feedback_is_bounded():
    c = fixture(initial_nodes=['A01'], propagation_probability=1., local_verification_probability=0.)
    c['edges'] = [dict(source='A01', target='A17', role='supplemental', verify=False),
                  dict(source='A17', target='A01', role='supplemental', verify=False)]
    r = simulate(c, 8, 0, True)
    assert r['mean_information_coverage'] is None
    assert r['mean_clean_information_fraction'] is None
    assert len(events(r, 'send')) <= len(c['agents']) * c['parameters']['horizon']


def test_information_wait_cap_ends_at_deadline_but_does_not_skip_review():
    r = simulate(fixture(information_policy='integrated', deadline_window=1,
                         oversight='full', review_service_time=3, review_capacity='unlimited'), 8, 0, True)
    assert events(r, 'propose', 'A17')[0]['time'] == 1
    assert events(r, 'resolve', 'A17')[0]['time'] == 4


def test_coverage_counts_internal_and_unfinished_nodes_at_horizon():
    c = fixture(oversight='full', review_service_time=5, horizon=1)
    c['edges'][0]['target'] = 'A28'
    r = simulate(c, 8, 0, True)
    assert r['unfinished_tasks'] == 4 and r['mean_information_coverage'] == 0
    assert r['mean_clean_information_fraction'] == 0


def test_A28_new_isolation_precedes_command_completion_same_tick():
    run = runtime(command_structure='centralized', automatic_isolation=True,
                  observation_level=2, false_alarm_probability=1.)
    run.proposed = [0] * 4
    run.command_active[2] = 0
    run.command_requests[2] = dict(completed_at=None)
    run.step()
    assert run.isolated(3) and not run.command_done[2] and run.command_active[2] == 0
