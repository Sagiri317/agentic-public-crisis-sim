"""The model's eleven ordered phases and stateless keyed random field."""
import hashlib

from .config import Compiled, compile_config, stable_json

VECTOR_METRICS = ('base_deficit_hard', 'compromised_weight_hard',
                  'base_deficit_grace', 'compromised_weight_grace')
SCALAR_METRICS = (
    'function_failure_time', 'ever_compromised_count', 'wrong_actions',
    'verification_load', 'human_review_load', 'command_review_load',
    'information_blocking', 'review_blocking', 'denial_blocking',
    'command_blocking', 'isolation_blocking', 'false_isolations',
    'false_review_denials', 'mean_information_coverage',
    'mean_clean_information_fraction', 'critical_review_queue_time',
    'unfinished_tasks', 'active_harms_at_horizon',
)
PHASES = ('release_holds', 'deliver', 'propose', 'monitor', 'finish_review',
          'finish_command', 'dispatch', 'execute', 'send', 'measure', 'advance')


def keyed_uniform(master_seed, run_index, mechanism, entity, event_time, event_ordinal=0):
    encoded = stable_json([master_seed, run_index, mechanism, entity, event_time,
                           event_ordinal]).encode('utf-8')
    x = int.from_bytes(hashlib.sha256(encoded).digest()[:7], 'big') >> 4
    return (x + 0.5) / (2 ** 52)


class Run:
    """One bounded response window; methods also expose hand-computable fixtures."""
    def __init__(self, model, master_seed, run_index, trace=False):
        self.m = model
        self.p, self.f = model.parameters, model.config['fixed']
        self.seed, self.index, self.trace = master_seed, run_index, trace
        self.n, self.t = len(model.agents), 0
        self.ids = {a['id']: i for i, a in enumerate(model.agents)}
        self.compromised = [False] * self.n
        self.ever = [False] * self.n
        self.harm = [False] * self.n
        self.rollback_attempted = [False] * self.n
        self.tool = [False] * self.n
        self.unsafe_attempted = [False] * self.n
        self.proposed = [-1] * self.n
        self.resolved = [-1] * self.n
        self.isolated_until = [0] * self.n
        self.denied_until = [0] * self.n
        self.review_done = [not x for x in model.review_targets]
        self.command_done = [not x for x in model.command_targets]
        self.review_requests, self.command_requests = {}, {}
        self.review_queue, self.command_queue = [], []
        self.review_active, self.command_active = {}, {}
        self.dirty = [True] * self.n
        self.seen = [-1] * len(model.config['edges'])
        self.accepted = [False] * len(self.seen)
        self.clean = [False] * len(self.seen)
        self.messages = {}
        self.exposure_at, self.exposure_consumed = {}, set()
        kind = self.p['shock_type']
        for group in model.groups:
            if self.u('resource_group', [kind, group], 0) < self.p['shock_probability']:
                for name in group:
                    offset = int(self.f['progressive_steps'] * self.u('exposure', [kind, name], 0))
                    self.exposure_at[self.ids[name]] = self.p['shock_time'] + (offset if self.p['shock_profile'] == 'progressive' else 0)
        self.deadline = [a['release'] + self.p['deadline_window'] for a in model.agents]
        self.integrals = {key: [0.0] * self.n for key in VECTOR_METRICS}
        self.metrics = {key: 0 for key in SCALAR_METRICS}
        self.coverage_records = {}
        self.events, self.trajectory = [], []
        self.phase_name = None

    def u(self, mechanism, entity, time):
        return keyed_uniform(self.seed, self.index, mechanism, entity, time)

    def record(self, event, i=None, **fields):
        if self.trace:
            self.events.append(dict(time=self.t, phase=self.phase_name, event=event,
                                    agent=self.m.agents[i]['id'] if i is not None else None, **fields))

    def phase(self, name):
        self.phase_name = name
        self.record('phase', name=name)

    def isolated(self, i):
        return self.t < self.isolated_until[i]

    def change(self, i, compromised, cause):
        if compromised:
            self.ever[i] = True
        if self.compromised[i] != compromised:
            self.compromised[i] = compromised
            self.dirty[i] = True
            self.record('contaminate' if compromised else 'correct', i, cause=cause)

    def coverage(self):
        obs, clean, supplement = [], [], []
        for required, supplemental in zip(self.m.required, self.m.supplemental):
            obs.append(sum(self.accepted[e] for e in required) / len(required) if required else 1.0)
            clean.append(sum(self.accepted[e] and self.clean[e] for e in required) / len(required) if required else 1.0)
            supplement.append(sum(self.accepted[e] and self.clean[e] for e in supplemental) / len(supplemental) if supplemental else 0.0)
        return obs, clean, supplement

    def release_holds(self):
        self.phase('release_holds')
        for i in range(self.n):
            if self.isolated_until[i] and self.isolated_until[i] == self.t:
                self.change(i, False, 'recovery')
                self.tool[i] = False
                self.dirty[i] = True
                self.record('recover', i)
                if self.harm[i] and not self.rollback_attempted[i]:
                    self.rollback_attempted[i] = True
                    success = self.u('rollback', self.m.agents[i]['id'], 0) < self.p['rollback_success'] * self.m.agents[i]['reversibility']
                    if success:
                        self.harm[i] = False
                    self.record('rollback', i, success=success)
            if self.denied_until[i] and self.denied_until[i] == self.t:
                self.record('denial_release', i)

    def deliver(self):
        self.phase('deliver')
        if self.t == 0:
            for name in self.p['initial_nodes']:
                self.change(self.ids[name], True, 'initial')
        kind = self.p['shock_type']
        for i, at in self.exposure_at.items():
            if at <= self.t and i not in self.exposure_consumed and not self.isolated(i):
                self.exposure_consumed.add(i)
                self.record('resource_consume', i, kind=kind)
                if kind == 'tool':
                    self.tool[i] = True
                elif kind == 'model' or self.u('data_local', [kind, self.m.agents[i]['id']], 0) >= self.p['local_verification_probability']:
                    self.change(i, True, kind)
        contaminated, new_supplement = set(), set()
        edges = self.m.config['edges']
        for e, sent, truth in sorted(self.messages.pop(self.t, []), key=lambda msg: (msg[0], msg[1])):
            if sent <= self.seen[e]:
                continue
            self.seen[e] = sent
            edge = edges[e]
            j = self.ids[edge['target']]
            if self.isolated(j):
                self.accepted[e] = self.clean[e] = False
                self.record('message_drop', j, source=edge['source'], sent=sent)
                continue
            extra = self.p['verification_mode'] == 'global' or self.p['verification_mode'] == 'critical' and edge['verify']
            self.metrics['verification_load'] += int(extra)
            entity = [edge['source'], edge['target']]
            detected = not truth and (self.u('local', entity, sent) < self.p['local_verification_probability'] or extra and self.u('extra', entity, sent) < self.p['verification_effectiveness'])
            self.accepted[e], self.clean[e] = not detected, truth
            self.record('message_receive', j, source=edge['source'], sent=sent, accepted=not detected, clean=truth, checked=extra)
            if not detected and not truth and self.u('adopt', entity, sent) < self.p['propagation_probability'] * self.f['edge_transmission_weight']:
                contaminated.add(j)
            if not detected and truth and edge['role'] == 'supplemental':
                new_supplement.add(j)
        for i in sorted(contaminated):
            self.change(i, True, 'message')
        self.obs, self.clean_coverage, self.supplement = self.coverage()
        for i in sorted(new_supplement):
            if self.u('supplemental', self.m.agents[i]['id'], self.t) < self.p['supplemental_check_effectiveness'] * self.supplement[i]:
                self.change(i, False, 'supplemental')

    def propose(self):
        self.phase('propose')
        policy = self.f['information_policies'][self.p['information_policy']]
        for i, agent in enumerate(self.m.agents):
            if self.proposed[i] < 0 and not self.isolated(i) and self.t >= agent['release'] and (self.obs[i] >= policy['threshold'] or self.t >= min(agent['release'] + policy['max_wait'], self.deadline[i])):
                if not self.compromised[i] and self.u('missing', agent['id'], 0) < self.p['information_error_rate'] * (1 - self.obs[i]) * (1 - self.p['supplemental_check_effectiveness'] * self.supplement[i]):
                    self.change(i, True, 'missing')
                self.proposed[i], self.dirty[i] = self.t, True
                self.record('propose', i, coverage=self.obs[i])

    def monitor(self):
        self.phase('monitor')
        if not self.p['automatic_isolation']:
            return
        level = self.p['observation_level']
        for i, agent in enumerate(self.m.agents):
            opportunity = level == 2 or level == 1 and 0 <= self.proposed[i] < self.t or level == 0 and 0 <= self.resolved[i] < self.t
            if not opportunity or self.isolated(i):
                continue
            truth = self.compromised[i] or self.harm[i]
            alert = self.u('detect' if truth else 'false_alarm', agent['id'], self.t) < self.p['detection_probability' if truth else 'false_alarm_probability']
            if alert:
                self.isolated_until[i] = self.t + self.p['recovery_delay']
                self.metrics['false_isolations'] += int(not truth)
                self.record('isolate', i, true_anomaly=truth)

    def finish_review(self):
        self.phase('finish_review')
        for i in sorted([i for i, remaining in self.review_active.items() if remaining == 0]):
            del self.review_active[i]
            truth = self.compromised[i]
            name = self.m.agents[i]['id']
            if truth:
                detected = self.u('review_sensitivity', name, 0) < self.p['review_sensitivity']
                if detected:
                    self.change(i, False, 'review')
                outcome = 'corrected' if detected else 'missed'
            else:
                accepted = self.u('review_specificity', name, 0) < self.p['review_specificity']
                if not accepted:
                    self.denied_until[i] = self.t + self.p['false_denial_hold']
                    self.metrics['false_review_denials'] += 1
                outcome = 'approved' if accepted else 'false_denial'
            self.review_done[i] = True
            self.review_requests[i].update(completed_at=self.t, truth=truth, outcome=outcome)
            self.record('review_complete', i, truth=truth, outcome=outcome)

    def command_available(self):
        i = self.m.command_index
        return self.proposed[i] >= 0 and self.review_done[i] and not self.isolated(i) and self.t >= self.denied_until[i]

    def finish_command(self):
        self.phase('finish_command')
        if not self.command_available():
            return
        command = self.m.command_index
        truth = self.compromised[command]
        changes = []
        for i in sorted([i for i, remaining in self.command_active.items() if remaining == 0]):
            del self.command_active[i]
            name = self.m.agents[i]['id']
            outcome = 'approved'
            if truth and not self.compromised[i] and self.u('command_corrupt', name, 0) < self.p['command_error_probability']:
                changes.append((i, True))
                outcome = 'corrupted'
            elif not truth and self.compromised[i] and self.u('command_intercept', name, 0) < self.p['command_intercept_effectiveness'] * self.clean_coverage[command]:
                changes.append((i, False))
                outcome = 'corrected'
            self.command_done[i] = True
            self.command_requests[i].update(completed_at=self.t, outcome=outcome)
            self.record('command_complete', i, outcome=outcome, command_compromised=truth)
        for i, compromised in changes:
            self.change(i, compromised, 'command')

    def review_key(self, i):
        requested = self.review_requests[i]['requested_at']
        priority = self.p['review_priority']
        first = self.deadline[i] - self.p['review_service_time'] if priority == 'due_first' else -self.m.life_tier[i] if priority == 'life_safety' else requested
        return first, requested, self.m.agents[i]['id']

    def dispatch(self):
        self.phase('dispatch')
        for i in range(self.n):
            if self.proposed[i] < 0 or self.isolated(i):
                continue
            if not self.review_done[i] and i not in self.review_requests:
                self.review_requests[i] = dict(agent=self.m.agents[i]['id'], requested_at=self.t, started_at=None, completed_at=None)
                self.review_queue.append(i)
                self.metrics['human_review_load'] += 1
                self.record('review_request', i)
            if self.review_done[i] and self.t >= self.denied_until[i] and not self.command_done[i] and i not in self.command_requests:
                self.command_requests[i] = dict(agent=self.m.agents[i]['id'], requested_at=self.t, started_at=None, completed_at=None)
                self.command_queue.append(i)
                self.metrics['command_review_load'] += 1
                self.record('command_request', i)
        if self.p['oversight'] == 'full':
            capacity = self.n if self.p['review_capacity'] == 'unlimited' else self.p['review_capacity']
            self.review_queue.sort(key=self.review_key)
            while self.review_queue and len(self.review_active) < capacity:
                i = self.review_queue.pop(0)
                self.review_active[i] = self.p['review_service_time']
                self.review_requests[i]['started_at'] = self.t
                self.record('review_start', i)
        if self.command_available() and self.p['command_structure'] != 'distributed':
            self.command_queue.sort(key=lambda i: (self.command_requests[i]['requested_at'], self.m.agents[i]['id']))
            while self.command_queue and len(self.command_active) < self.p['command_capacity']:
                i = self.command_queue.pop(0)
                self.command_active[i] = self.p['command_service_time']
                self.command_requests[i]['started_at'] = self.t
                self.record('command_start', i)

    def execute(self):
        self.phase('execute')
        for i, agent in enumerate(self.m.agents):
            if self.resolved[i] >= 0 or self.proposed[i] < 0 or self.isolated(i) or self.t < self.denied_until[i] or not self.review_done[i] or not self.command_done[i]:
                continue
            if self.m.external[i] and self.compromised[i]:
                if self.unsafe_attempted[i]:
                    continue
                self.unsafe_attempted[i] = True
                if self.u('unsafe_execute', agent['id'], 0) >= self.p['execution_autonomy']:
                    self.record('defer', i)
                    continue
            self.resolved[i] = self.t
            wrong = self.m.external[i] and (self.compromised[i] or self.tool[i])
            if wrong:
                self.harm[i], self.ever[i] = True, True
                self.metrics['wrong_actions'] += 1
            if self.m.external[i]:
                self.tool[i] = False
            self.record('wrong_action' if wrong else 'resolve', i)

    def send(self):
        self.phase('send')
        for i in range(self.n):
            if self.proposed[i] < 0 or self.isolated(i) or not self.dirty[i]:
                continue
            truth = not self.compromised[i]
            for edge in self.m.outgoing[i]:
                self.messages.setdefault(self.t + self.f['message_latency'], []).append((edge, self.t, truth))
            self.dirty[i] = False
            self.record('send', i, clean=truth)

    def measure(self):
        self.phase('measure')
        utilities, blockers = [], []
        for i in range(self.n):
            visible = not self.isolated(i) and not self.harm[i]
            timely = self.resolved[i] >= 0 or self.t <= self.deadline[i]
            hard = float(timely)
            grace = 1.0 if timely else max(0.0, 1 - (self.t - self.deadline[i]) / self.f['deadline_grace'])
            for mode, h in (('hard', hard), ('grace', grace)):
                self.integrals['base_deficit_' + mode][i] += 1 - visible * h
                self.integrals['compromised_weight_' + mode][i] += visible * h * self.compromised[i]
            utilities.append(visible * hard * (self.f['primary_contaminated_utility'] if self.compromised[i] else 1.0))
            blocker = 'isolation' if self.isolated(i) else 'denial' if self.t < self.denied_until[i] else 'review' if i in self.review_requests and not self.review_done[i] else 'command' if i in self.command_requests and not self.command_done[i] else 'information' if self.t >= self.m.agents[i]['release'] and self.proposed[i] < 0 else None
            if blocker:
                self.metrics[blocker + '_blocking'] += 1
            blockers.append(blocker)
            if self.m.required[i] and i not in self.coverage_records and (self.resolved[i] >= 0 or self.t >= min(self.deadline[i], self.p['horizon'] - 1)):
                self.coverage_records[i] = self.obs[i], self.clean_coverage[i]
        self.metrics['critical_review_queue_time'] += sum(self.m.life_tier[i] for i in self.review_queue)
        scores = [sum(utilities[i] * w for i, w in weights) for weights in self.m.function_weights]
        self.metrics['function_failure_time'] += sum(c * (score < self.f['function_failure_threshold']) for score, c in zip(scores, self.m.function_criticality))
        if self.trace:
            self.trajectory.append(dict(time=self.t, compromised=self.compromised[:], harm=self.harm[:],
                isolated=[self.isolated(i) for i in range(self.n)], proposed=self.proposed[:],
                resolved=self.resolved[:], coverage=self.obs[:], clean_coverage=self.clean_coverage[:],
                utilities=utilities, function_scores=scores, blockers=blockers,
                review_queue=self.review_queue[:], review_active=dict(self.review_active),
                command_active=dict(self.command_active)))

    def advance(self):
        self.phase('advance')
        for i in self.review_active:
            if self.review_active[i] > 0:
                self.review_active[i] -= 1
        if self.command_available():
            for i in self.command_active:
                if self.command_active[i] > 0:
                    self.command_active[i] -= 1

    def step(self):
        self.release_holds()
        self.deliver()
        self.propose()
        self.monitor()
        self.finish_review()
        self.finish_command()
        self.dispatch()
        self.execute()
        self.send()
        self.measure()
        self.advance()
        self.t += 1

    def result(self):
        self.metrics['ever_compromised_count'] = sum(self.ever)
        self.metrics['unfinished_tasks'] = sum(t < 0 for t in self.resolved)
        self.metrics['active_harms_at_horizon'] = sum(self.harm)
        count = len(self.coverage_records)
        self.metrics['mean_information_coverage'] = sum(x[0] for x in self.coverage_records.values()) / count if count else None
        self.metrics['mean_clean_information_fraction'] = sum(x[1] for x in self.coverage_records.values()) / count if count else None
        result = dict(self.integrals, **self.metrics)
        if self.trace:
            result.update(events=self.events, trajectory=self.trajectory,
                          review_records=list(self.review_requests.values()),
                          command_records=list(self.command_requests.values()),
                          exposure={self.m.agents[i]['id']: at for i, at in self.exposure_at.items()})
        return result


def simulate(config, master_seed, run_index=0, trace=False):
    if type(master_seed) is not int or master_seed < 0 or type(run_index) is not int or run_index < 0:
        raise ValueError('Nonnegative integer master_seed and run_index required')
    model = config if isinstance(config, Compiled) else compile_config(config)
    run = Run(model, master_seed, run_index, trace)
    for _ in range(model.parameters['horizon']):
        run.step()
    return run.result()
