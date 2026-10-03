"""Render only protocol-selected rows; figures introduce no scientific comparison."""
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.ft2font import FT2Font
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, Rectangle

from analyze import _metric_unit, direction

TITLES = (
    '01_public_crisis_questions', '02_business_information_graph',
    '03_position_prediction', '04_dependency_partition',
    '05_observation_and_isolation', '06_review_and_command',
    '07_task_triage', '08_information_and_deadlines',
    '09_fixed_budget_monitoring', '10_oversight_capacity',
)


def chinese_font():
    required = set(map(ord, '公共危机智能体审核损失时间权重模拟−×Δ²Σ'))
    preferred = ('Microsoft YaHei', 'Noto Sans CJK SC', 'Noto Sans CJK', 'Source Han Sans SC', 'Source Han Sans')
    def rank(entry):
        return next((i for i, name in enumerate(preferred) if entry.name.startswith(name)), len(preferred)), entry.name
    for entry in sorted(font_manager.fontManager.ttflist, key=rank):
        if 'last resort' in entry.name.lower():
            continue
        if required <= set(FT2Font(entry.fname).get_charmap()):
            return entry.name
    raise RuntimeError('No Chinese font available')


# One visual vocabulary for all figures; colors never select observations.
PALETTE = dict(black='#000000', orange='#E69F00', sky='#56B4E9', green='#009E73',
               yellow='#F0E442', blue='#0072B2', vermillion='#D55E00', purple='#CC79A7',
               gray='#4D4D4D', mid='#9E9E9E', light='#D9D9D9')
PROFILES = (('abrupt', '集中暴露', 'blue', 'o', '-'),
            ('progressive', '逐步暴露', 'orange', 's', '--'))
COMMANDS = (('selective', '选择性复核', 'blue', 'o', '-'),
            ('centralized', '全面指挥复核', 'purple', 'D', '--'))
PRIORITIES = (('fifo', 'FIFO', 'gray', 'o', '-'),
              ('due_first', '到期优先', 'orange', 's', '--'),
              ('life_safety', '生命安全优先', 'blue', '^', '-'))
POLICIES = (('balanced − fast', '平衡 − 快速', 'orange', ':'),
            ('integrated − fast', '综合等待 − 快速', 'blue', '-'),
            ('integrated − balanced', '综合等待 − 平衡', 'purple', '--'))
DIVERGING = LinearSegmentedColormap.from_list('signed_effect', [PALETTE['blue'], '#FFFFFF', PALETTE['orange']])
FUNCTIONS = ('F1 态势感知', 'F2 道路交通', 'F3 疏散安置', 'F4 救援资源',
             'F5 医疗连续', 'F6 预警沟通', 'F7 生命线排涝')


def _figure(height, title, subtitle):
    fig = plt.figure(figsize=(7.3, height), facecolor='white')
    fig.text(.065, 1-.17/height, title, va='top', fontsize=10.5, weight='bold')
    fig.text(.065, 1-.43/height, subtitle, va='top', fontsize=7.3, color=PALETTE['gray'])
    return fig


def _panel(ax, letter, title):
    ax.set_title(title, loc='left', fontsize=8.8, pad=9)
    ax.text(-.10, 1.055, letter, transform=ax.transAxes, fontsize=10, weight='bold', va='bottom')
    ax.spines[['top', 'right']].set_visible(False)
    ax.tick_params(length=3, width=.65)
    ax.margins(x=.08, y=.12)


def _note(fig, text, *, ci=False):
    if ci:
        text += '\n区间图符号：实心为 CI 不含 0 或结构性零；空心为 CI 含 0；灰 × 为点有定义、CI 未定义。'
    fig.text(.065, .025, text, va='bottom', fontsize=7, color=PALETTE['gray'], linespacing=1.55)


def _handle(label, color, marker='o', linestyle='-'):
    return Line2D([], [], label=label, color=PALETTE[color], marker=marker,
                  markersize=4, linewidth=.9, linestyle=linestyle)


def _legend(fig, handles, y, columns):
    fig.legend(handles=handles, loc='upper center', bbox_to_anchor=(.53, y),
               ncol=columns, frameon=False, handlelength=2.2, columnspacing=1.6)


def _conditions(frame):
    """Unpack existing presentation labels, without choosing or recomputing rows."""
    prefixes, comparisons = zip(*(label.split('\n', 1) for label in frame['label']))
    dimensions = pd.DataFrame([dict(item.split('=', 1) for item in prefix.split(',') if item)
                               for prefix in prefixes], index=frame.index)
    return frame.join(dimensions).assign(comparison=comparisons)


def _ci_state(low, high, status):
    """Display state only; never replace missing bounds or change estimates."""
    if status == 'structural_zero':
        return 'structural_zero'
    if status != 'defined' or not np.isfinite([low, high]).all():
        return 'undefined'
    return 'uncertain' if low <= 0 <= high else 'defined'


def _point_style(state, color, marker):
    if state == 'undefined':
        return dict(marker='x', mec=PALETTE['gray'], mfc='none')
    return dict(marker=marker, mec=color, mfc='white' if state == 'uncertain' else color)


def _forest(ax, frame, labels, colors=None):
    for y, row in enumerate(frame.itertuples()):
        color = PALETTE[colors[y] if colors else 'blue']
        if not np.isfinite(row.value):
            ax.text(.03, y, '未定义', transform=ax.get_yaxis_transform(), fontsize=7.5)
            continue
        state = _ci_state(row.ci_low, row.ci_high, getattr(row, 'ci_status', row.status))
        if state != 'undefined':
            ax.hlines(y, row.ci_low, row.ci_high, color=color, lw=.95, zorder=4)
            ax.plot([row.ci_low, row.ci_high], [y, y], ls='None', marker='|',
                    ms=5.6, color=color, mew=.85, zorder=4)
        ax.plot(row.value, y, ls='None', ms=4.4, mew=.9, zorder=3,
                **_point_style(state, color, 'o'))
    ax.axvline(0, color=PALETTE['mid'], lw=.65, zorder=0)
    ax.set_yticks(range(len(labels)), labels)
    ax.set_ylim(len(labels)-.5, -.5)
    ax.spines['left'].set_visible(False)
    ax.tick_params(axis='y', length=0)
    ax.margins(x=.15)


def _line(ax, frame, x, color, marker, linestyle='-', offset=0):
    color = PALETTE[color]
    xx = np.asarray(x, dtype=float) + offset
    ax.plot(xx, frame['value'], color=color, lw=.9, ls=linestyle, zorder=2)
    for xi, row in zip(xx, frame.itertuples()):
        if not np.isfinite(row.value):
            ax.text(xi, .03, '未定义', transform=ax.get_xaxis_transform(), ha='center', fontsize=7.5)
            continue
        state = _ci_state(row.ci_low, row.ci_high, getattr(row, 'ci_status', row.status))
        if state != 'undefined':
            ax.vlines(xi, row.ci_low, row.ci_high, color=color, lw=.95, zorder=5)
            ax.plot([xi, xi], [row.ci_low, row.ci_high], ls='None', marker='_',
                    ms=5.6, color=color, mew=.8, zorder=5)
        ax.plot(xi, row.value, ms=4.2, mew=.85, zorder=4,
                **_point_style(state, color, marker))
    ax.axhline(0, color=PALETTE['mid'], lw=.65, zorder=0)


def _heatmap(ax, values, rows, columns, *, intervals=None, statuses=None, annotate=False):
    limit = np.nanmax(np.abs(values))
    # A zero-only matrix needs a nondegenerate color domain, not invented data.
    limit = limit if limit > 0 else 1.
    image = ax.imshow(values, cmap=DIVERGING, norm=TwoSlopeNorm(0, -limit, limit), aspect='auto')
    ax.set_xticks(range(len(columns)), columns)
    ax.set_yticks(range(len(rows)), rows)
    ax.tick_params(length=0)
    ax.spines[:].set_visible(False)
    for i in range(len(rows)):
        for j in range(len(columns)):
            if not np.isfinite(values[i, j]):
                ax.text(j, i, '未定义', ha='center', va='center', fontsize=7.2)
                continue
            if intervals is not None:
                low, high = intervals[i, j]
                state = _ci_state(low, high, statuses[i, j])
            if annotate:
                text = f'{values[i, j]:.1f}'
                if intervals is not None:
                    text += '\nCI 未定义' if state == 'undefined' else f'\n[{low:.1f}, {high:.1f}]'
                ax.text(j, i, text, ha='center', va='center', fontsize=7.2,
                        color='white' if values[i, j] < -.65*limit else PALETTE['black'])
            elif intervals is not None:
                ax.plot(j, i, ls='None', ms=3.6, mew=.7,
                        **_point_style(state, PALETTE['gray'], 'o'))
    return image


def _overview(frames, base, subtitle):
    fig = _figure(3.7, '局部 Agent 失效如何转化为公共功能风险', '研究框架 · 一个合成应急响应窗口 · 三个研究问题')
    ax = fig.add_axes([.035, .12, .93, .67])
    ax.set(xlim=(0, 1), ylim=(0, 1)); ax.axis('off')
    ax.text(.5, .93, '局部 Agent 失效  →  业务与技术依赖  →  公共功能风险',
            ha='center', va='center', fontsize=10)
    columns = [
        ('RQ1', '系统脆弱性', '初始位置 / 共同依赖', '公共功能损失分布'),
        ('RQ2', '监测与处置', '可见阶段 / 暴露节奏 / 隔离', '风险控制与治理负担'),
        ('RQ3', '决策与指挥', '审核 / 分诊 / 信息等待\n指挥复核', '时间与处理能力边界'),
    ]
    for x, (rq, title, factors, result) in zip((.015, .35, .685), columns):
        ax.add_patch(Rectangle((x, .28), .30, .48, facecolor='white', edgecolor=PALETTE['mid'], lw=.7))
        ax.text(x+.15, .70, rq, ha='center', color=PALETTE['blue'], weight='bold', fontsize=9)
        ax.text(x+.15, .59, title, ha='center', weight='bold', fontsize=9.5)
        ax.text(x+.15, .45, factors, ha='center', va='center', fontsize=8, linespacing=1.5)
        ax.text(x+.15, .32, result, ha='center', fontsize=8.2)
        for start, end in ((.86, .77), (.27, .17)):
            ax.add_patch(FancyArrowPatch((x+.15, start), (x+.15, end), arrowstyle='-|>', mutation_scale=8,
                                        color=PALETTE['gray'], lw=.75))
    ax.add_patch(Rectangle((.015, .035), .97, .13, facecolor='white', edgecolor=PALETTE['gray'], lw=.8))
    ax.text(.5, .10, '主结果：七项公共功能的关键性加权累计服务能力缺口 L', ha='center', va='center', fontsize=9)
    _note(fig, '4R：减少、准备、响应、恢复；TIL：时间、信息、领导力；TIE：及时、全面、有效。\n上述术语为分析框架，非已完整验证的因果定律；本模型不估计现实危机概率或政策效力。')
    return fig


def _architecture(frames, base, subtitle):
    fig = _figure(6.4, '正常信息与错误传播共用同一业务依赖网络',
                  f'{len(base["agents"])} 个 Agent · {len(base["edges"])} 条有向信息边 · 指挥复核作为附加过程')
    ax = fig.add_axes([.035, .245, .93, .625])
    ax.set(xlim=(-.04, 1.04), ylim=(-.24, 1.11)); ax.axis('off')
    ax.text(-.035, 1.08, 'a', fontsize=10, weight='bold')
    positions = {}
    for ids, x, ys in ((range(1, 7), .03, np.linspace(.92, .12, 6)),
                       (range(8, 12), .35, np.linspace(.87, .22, 4)),
                       (range(12, 17), .55, np.linspace(.92, .12, 5)),
                       (range(17, 25), .77, np.linspace(.98, .06, 8)),
                       (range(25, 28), .97, [.82, .50, .18])):
        positions.update({f'A{i:02}': (x, y) for i, y in zip(ids, ys)})
    positions.update(A07=(.19, .54), A28=(.34, -.13), A29=(.55, -.13), A30=(.15, -.13))
    for edge in base['edges']:
        source, target = edge['source'], edge['target']
        required = edge['role'] == 'required'
        rad = 0 if required else (.14 if positions[source][0] <= positions[target][0] else -.20)
        ax.add_patch(FancyArrowPatch(positions[source], positions[target],
            arrowstyle='-|>', mutation_scale=5.0, shrinkA=10, shrinkB=11,
            connectionstyle=f'arc3,rad={rad}', lw=.65 if required else .6,
            color=PALETTE['gray'] if required else PALETTE['sky'],
            alpha=.72 if required else .72, linestyle='-' if required else (0, (3, 2)), zorder=1))
    short = {'A05': '设施监测', 'A06': '公众报告', 'A08': '洪涝研判', 'A09': '道路研判',
             'A10': '人口暴露', 'A11': '医院容量', 'A22': '公用设施', 'A26': '媒体发布',
             'A28': '指挥支持', 'A29': '跨部门协调', 'A30': '现场反馈'}
    for agent in base['agents']:
        identity = agent['id']; x, y = positions[identity]
        color = PALETTE['blue'] if identity == base['fixed']['command_agent'] else PALETTE['black']
        ax.text(x, y, identity+'\n'+short.get(identity, agent['name']), ha='center', va='center',
                fontsize=7.1, color=color, linespacing=1.2,
                bbox=dict(facecolor='white', edgecolor='none', pad=.5), zorder=3)
    for x, label in ((.03, '感知'), (.29, '融合与研判'), (.55, '方案'), (.77, '执行'), (.97, '沟通')):
        ax.text(x, 1.08, label, ha='center', fontsize=8, weight='bold')
    # An exact adjacency inset disambiguates every edge at network crossings.
    matrix = fig.add_axes([.75, .065, .20, .155])
    ids = [a['id'] for a in base['agents']]
    for role, marker, color, filled in (('required', 's', 'gray', True), ('supplemental', 'o', 'blue', False)):
        edges = [e for e in base['edges'] if e['role'] == role]
        matrix.scatter([ids.index(e['target']) for e in edges], [ids.index(e['source']) for e in edges],
                       s=4, marker=marker, facecolors=PALETTE[color] if filled else 'none',
                       edgecolors=PALETTE[color], linewidths=.45)
    ticks = [0, 9, 19, 29]
    matrix.set(xticks=ticks, xticklabels=[ids[i] for i in ticks], yticks=ticks,
               yticklabels=[ids[i] for i in ticks], xlim=(-.8, 29.8), ylim=(29.8, -.8))
    matrix.set_xlabel('接收节点', fontsize=7); matrix.set_ylabel('发送节点', fontsize=7)
    matrix.tick_params(labelsize=6.4, length=2)
    matrix.spines[['top', 'right']].set_visible(False)
    matrix.set_title('全部信息边的精确邻接位置', fontsize=7.5, loc='left')
    matrix.text(-.18, 1.09, 'b', transform=matrix.transAxes, fontsize=10, weight='bold')
    legend = fig.add_axes([.065, .065, .60, .155]); legend.axis('off')
    legend.legend(handles=[_handle('必要输入：覆盖与等待', 'gray', '', '-'),
                           _handle('补充输入：检查与传播', 'sky', '', '--')],
                  loc='upper left', frameon=False, fontsize=7.6, handlelength=3)
    legend.text(.02, .45, '邻接小图：实方块为必要输入，空心圆为补充输入。\nA28：额外指挥检查、等待与单点风险；复核不是新增信息边。\n策略读取已接受覆盖；潜在真伪用于生成结果与事后计量。',
                va='top', fontsize=7.0, linespacing=1.5)
    _note(fig, '每条边均由基础配置读取；正常暂定信息与错误信息使用相同的发送与接收路径。')
    return fig


def _position(frames, base, subtitle):
    fig = _figure(4.8, '相同受损规模下，初始位置仍提供额外预测信息', subtitle)
    gs = fig.add_gridspec(2, 1, left=.24, right=.965, bottom=.20, top=.82, hspace=.78, height_ratios=[1, 1.5])
    ax = fig.add_subplot(gs[0]); _panel(ax, 'a', '交叉拟合增量 R²')
    _forest(ax, frames['position'], ['主映射', '成员等权', 'Agent重要性加权'], ['blue', 'gray', 'gray'])
    ax.set_xlabel('ΔR²（无量纲）')
    ax = fig.add_subplot(gs[1]); _panel(ax, 'b', '预先规定支持层：位置均值')
    supported = frames['position_example']
    if supported.empty:
        ax.text(.5, .5, '无满足预定支持量的同规模示例', ha='center', transform=ax.transAxes)
        note = '同规模示例仅用于说明，不替代全部位置的交叉拟合估计。'
    else:
        sizes = 14 + 18*np.sqrt(supported['count']/supported['count'].max())
        ax.scatter(np.arange(len(supported)), supported['mean'], s=sizes, color=PALETTE['blue'], linewidths=.5)
        ax.set_xticks(np.arange(len(supported)), supported['initial_node'], rotation=45, ha='right', fontsize=7)
        ax.set_ylim(bottom=0)
        note = (f'示例 K={supported["size"].iloc[0]}；全部合格位置按 Agent ID 排序；点面积轻度表示样本量 '
                f'n={supported["count"].min()}–{supported["count"].max()}。')
    ax.set_ylabel('平均服务缺口 L')
    _note(fig, note+'\n位置均值未计算 CI；ΔR² 为新抽样预测增量，不作现实因果解释。L 单位：功能关键性 × 抽象 tick。', ci=True)
    return fig


def _dependency(frames, base, subtitle):
    fig = _figure(3.5, '依赖分散降低尾部损失，但提高平均服务缺口', subtitle+' · data，p=0.20，K2 − K1')
    gs = fig.add_gridspec(1, 2, left=.16, right=.965, bottom=.29, top=.74, wspace=.57)
    for j, (frame, title, unit) in enumerate(zip(frames['dependency'], ('均值差', 'ES95 差'), ('Mean ΔL', 'ES95 ΔL'))):
        ax = fig.add_subplot(gs[j]); _panel(ax, chr(97+j), title+'：K2 − K1')
        labels = ['基准' if p == '0' else 'Partition '+p for p in _conditions(frame)['partition']]
        _forest(ax, frame, labels)
        ax.set_xlabel(unit+'（功能关键性 × tick）')
    _note(fig, '固定 data 情景及五个预先规定分组；额外 partition 的 K2 均对照基准 K1。\nES95 差是各分布尾部均值之差，不是差值分布的尾部；不外推到全部依赖结构。', ci=True)
    return fig


def _isolation(frames, base, subtitle):
    fig = _figure(5.75, '前移持续监测窗口增强隔离减损，也改变累计检查机会', subtitle+' · 隔离开启 − 关闭')
    gs = fig.add_gridspec(2, 2, left=.10, right=.945, bottom=.18, top=.79, wspace=.45, hspace=.70)
    titles = ('服务缺口效果', '业务阻塞', '误隔离次数')
    units = ('ΔL（功能关键性 × tick）', 'Δ Agent-tick', 'Δ 误隔离次数')
    for i, (frame, title, unit) in enumerate(zip(frames['isolation'], titles, units)):
        ax = fig.add_subplot(gs[i//2, i%2]); _panel(ax, chr(97+i), title)
        data = _conditions(frame)
        for p, (profile, _, color, marker, style) in enumerate(PROFILES):
            rows = data[data['profile'].eq(profile)]
            _line(ax, rows, rows['O'].astype(int), color, marker, style, (p-.5)*.055)
        ax.set_xticks([0, 1, 2], ['O0', 'O1', 'O2']); ax.set_ylabel(unit)
    ax = fig.add_subplot(gs[1, 1]); _panel(ax, 'd', '七项公共功能的隔离效果')
    values = np.column_stack([rows['value'] for _, rows in frames['isolation_functions']])
    intervals = np.stack([rows[['ci_low', 'ci_high']].to_numpy() for _, rows in frames['isolation_functions']], axis=1)
    statuses = np.column_stack([rows['status'] for _, rows in frames['isolation_functions']])
    im = _heatmap(ax, values, ['集中 O0', '集中 O1', '集中 O2', '逐步 O0', '逐步 O1', '逐步 O2'],
                  [f'F{i}' for i in range(1, 8)], intervals=intervals, statuses=statuses)
    cb = fig.colorbar(im, ax=ax, fraction=.05, pad=.035); cb.ax.tick_params(labelsize=7, length=2)
    cb.set_label('功能缺口差（tick）', fontsize=7)
    _legend(fig, [_handle(label, color, marker, style) for _, label, color, marker, style in PROFILES], .89, 2)
    _note(fig, 'O0：交付/行动后；O1：方案形成后；O2：内部遥测。这是持续监测政策效果，包含累计检测/误报机会变化。\n合成情景、抽象 tick；不解释为等预算的纯时点效应。F1–F7 为功能缺口；点横向微移仅为避让。', ci=True)
    return fig


def _review(frames, base, subtitle):
    fig = _figure(6.6, '审核的纠错收益与排队成本受容量、服务时间和时限约束', subtitle)
    gs = fig.add_gridspec(2, 2, left=.11, right=.96, bottom=.26, top=.81, wspace=.53, hspace=.78)
    ax = fig.add_subplot(gs[0, 0]); _panel(ax, 'a', '全面人工审核 − 无人工审核')
    data = _conditions(frames['human'])
    im = _heatmap(ax, data['value'].to_numpy().reshape(3, 3), ['d=2', 'd=5', 'd=10'], ['容量 1', '容量 3', '无限容量'],
                  intervals=data[['ci_low', 'ci_high']].to_numpy().reshape(3, 3, 2),
                  statuses=data['status'].to_numpy().reshape(3, 3), annotate=True)
    ax.set_xlabel('ΔL；格内为点估计与 95% CI', fontsize=7.5)
    cb = fig.colorbar(im, ax=ax, fraction=.04, pad=.035); cb.ax.tick_params(labelsize=7, length=2)
    for i, (key, title, unit) in enumerate((('command', '指挥复核总效果', 'ΔL（功能关键性 × tick）'),
                                           ('command_blocking', '指挥阻塞成本', 'Δ Agent-tick'))):
        ax = fig.add_subplot(gs[0, 1] if i == 0 else gs[1, 0]); _panel(ax, chr(98+i), title)
        data = _conditions(frames[key])
        for k, (command, _, color, marker, style) in enumerate(COMMANDS):
            rows = data[data['comparison'].eq(command+' − distributed')]
            _line(ax, rows, rows['d'].astype(int), color, marker, style, (k-.5)*.12)
        ax.set_xticks([2, 5, 10]); ax.set_xlabel('到期宽度 d'); ax.set_ylabel(unit)
    ax = fig.add_subplot(gs[1, 1]); _panel(ax, 'd', '叠加人工审核：预先规定敏感性')
    _forest(ax, frames['command_with_human'], ['选择性复核', '全面指挥复核'], ['blue', 'purple'])
    ax.set_xlabel('ΔL（相对分布式指挥）')
    _legend(fig, [_handle(label+' − 分布式', color, marker, style) for _, label, color, marker, style in COMMANDS], .89, 2)
    _note(fig, 'a：initial failure=A04；review_scope=all；review_priority=life_safety（非 FIFO）。\n'
          'review_service_time=3；command_structure=distributed；图 07 另比较三种审核优先级。\n'
          'b、c：无普通人工审核；d：叠加全面人工审核、d=5。热图蓝为负、橙为正；连线仅连接离散条件。\n'
          '指挥比较是额外复核 + 等待 + 有限容量 + A28 风险的组合效果；假定健康指挥零误拒绝，不评价制度优劣。', ci=True)
    return fig


def _triage(frames, base, subtitle):
    fig = _figure(8.8, '生命安全优先改善预定义加权总量，但伴随功能间取舍', subtitle)
    gs = fig.add_gridspec(3, 2, left=.14, right=.93, bottom=.145, top=.86,
                         hspace=.78, wspace=.62, height_ratios=[1, 2.1, 1.15])
    top_axes = []
    for i, capacity in enumerate((1, 3)):
        ax = fig.add_subplot(gs[0, i]); top_axes.append(ax)
        _panel(ax, chr(97+i), f'容量 {capacity}：总服务缺口水平')
        for j, (priority, _, color, marker, style) in enumerate(PRIORITIES):
            frame = next(frame for label, frame in frames['triage_lines'] if label == f'cap={capacity}, {priority}')
            ax.plot(frame['deadline']+(j-1)*.12, frame['service_deficit'], marker=marker,
                    color=PALETTE[color], lw=.9, ms=4, ls=style)
        ax.set_xticks([2, 5, 10]); ax.set_xlabel('到期宽度 d'); ax.set_ylabel('L（功能关键性 × tick）')
    common_upper = max(ax.get_ylim()[1] for ax in top_axes)
    for ax in top_axes: ax.set_ylim(0, common_upper)
    # The requested registered d=5/cap=1 effect is shown alongside all old levels.
    primary = frames['primary']
    effect = primary[primary['view'].eq('primary') & primary['label'].eq('RQ3 / H3b：生命安全分诊与 FIFO')]
    comparison = gs[1, :].subgridspec(2, 1, height_ratios=[1, 3.2], hspace=.95)
    for i, (rows, labels, color, unit) in enumerate((
            (effect[effect['metric'].eq('service_deficit')], ['总 L'], 'black', 'ΔL（功能关键性 × tick）'),
            (effect[effect['metric'].ne('service_deficit')], list(FUNCTIONS), 'blue', 'ΔL_f（归一化服务缺口 × tick）'))):
        ax = fig.add_subplot(comparison[i])
        _panel(ax, 'c' if i == 0 else '', '主比较：生命安全优先 − FIFO（d=5，cap=1）' if i == 0
               else 'F1–F7：归一化功能缺口分量（独立横轴）')
        _forest(ax, rows, labels, [color]*len(rows))
        ax.set_position([.23, ax.get_position().y0, .46, ax.get_position().height])
        ax.set_xlabel(unit)
        ax.text(1.05, 1.025, '点估计 [95% CI]', transform=ax.transAxes, fontsize=7.2)
        for y, row in enumerate(rows.itertuples()):
            ci = 'CI 未定义' if _ci_state(row.ci_low, row.ci_high, row.status) == 'undefined' else f'[{row.ci_low:.2f}, {row.ci_high:.2f}]'
            ax.text(1.05, y, f'{row.value:.2f} {ci}', transform=ax.get_yaxis_transform(),
                    va='center', fontsize=7.0, weight='bold' if i == 0 else 'normal')
    ax = fig.add_subplot(gs[2, 0]); _panel(ax, 'd', '全部条件的七项功能水平')
    values = np.column_stack([frame['value'] for _, frame in frames['triage_functions']])
    image = ax.imshow(values, cmap=LinearSegmentedColormap.from_list('function_level', ['white', PALETTE['blue']]),
                      vmin=0, aspect='auto')
    ax.set_xticks(range(7), [f'F{i}' for i in range(1, 8)])
    ax.set_yticks([1, 4, 7, 10, 13, 16], ['1 / 2', '1 / 5', '1 / 10', '3 / 2', '3 / 5', '3 / 10'])
    ax.set_ylabel('容量 / 到期宽度')
    for y in (2.5, 5.5, 8.5, 11.5, 14.5): ax.axhline(y, color='white', lw=.7)
    ax.tick_params(length=0); ax.spines[:].set_visible(False)
    cb = fig.colorbar(image, ax=ax, fraction=.045, pad=.035); cb.ax.tick_params(labelsize=7, length=2)
    cb.ax.set_title('tick', fontsize=7, pad=5)
    ax = fig.add_subplot(gs[2, 1]); _panel(ax, 'e', '加权排队诊断（非福利指标）')
    for label, frame in frames['triage_lines']:
        capacity = int(label.split(',')[0].split('=')[1]); priority = label.split(', ')[1]
        j, (_, _, color, marker, _) = next((j, p) for j, p in enumerate(PRIORITIES) if p[0] == priority)
        ax.plot(frame['deadline']+(j-1)*.12, frame['critical_review_queue_time'], color=PALETTE[color], marker=marker,
                ms=3.5, lw=.8, ls='-' if capacity == 1 else '--')
    ax.set_xticks([2, 5, 10]); ax.set_xlabel('到期宽度 d'); ax.set_ylabel('分层权重 × Agent-tick', fontsize=7.3)
    ax.set_ylim(bottom=0)
    _legend(fig, [_handle(label, color, marker, style) for _, label, color, marker, style in PRIORITIES], .925, 3)
    _note(fig, 'a、b、d、e 为水平诊断，未计算 CI。c：总 L 为功能关键性加权量（L = Σ c_f L_f），F1–F7 为归一化功能缺口分量。\n'
          'd 每组三行依次 FIFO、到期优先、生命安全优先；e 实线容量 1、虚线容量 3，仅累计未开始服务的排队。\n'
          '全部 18 个条件保留；点横向微移仅用于避让重叠；连线不表示连续时限下的插值推断。以下符号说明仅适用于 c。', ci=True)
    return fig


def _information(frames, base, subtitle):
    fig = _figure(6.7, '信息等待的直接效果存在，但期限交互未见明确方向', subtitle+' · 效果受人工审核配置影响')
    gs = fig.add_gridspec(2, 2, left=.11, right=.96, bottom=.25, top=.77, wspace=.40, hspace=.72)
    titles = ('服务缺口效果', '已接受信息覆盖', '真实正确的必要输入覆盖率', '业务阻塞')
    units = ('ΔL（功能关键性 × tick）', '覆盖比例差', '覆盖比例差', 'Δ Agent-tick')
    for i, (frame, title, unit) in enumerate(zip(frames['information'], titles, units)):
        ax = fig.add_subplot(gs[i//2, i%2]); _panel(ax, chr(97+i), title)
        data = _conditions(frame)
        for j, (comparison, _, color, style) in enumerate(POLICIES):
            for k, (oversight, marker) in enumerate((('autonomy', 'o'), ('full', 's'))):
                rows = data[data['comparison'].eq(comparison) & data['review'].eq(oversight)]
                _line(ax, rows, rows['d'].astype(int), color, marker, style, (2*j+k-2.5)*.07)
        ax.set_xticks([2, 5, 10]); ax.set_xlabel('到期宽度 d'); ax.set_ylabel(unit)
        if i == 0:
            zoom = ax.inset_axes([.54, .65, .43, .32])
            for j, (comparison, _, color, style) in enumerate(POLICIES):
                rows = data[data['comparison'].eq(comparison) & data['review'].eq('autonomy')]
                _line(zoom, rows, rows['d'].astype(int), color, 'o', style, (j-1)*.16)
            zoom.set_title('无人工审核（放大）', fontsize=6.8, pad=4)
            zoom.set_xticks([2, 5, 10]); zoom.tick_params(labelsize=6.2, length=2)
            zoom.spines[['top', 'right']].set_visible(False)
            zoom.margins(x=.10, y=.18)
    policies = [_handle(label, color, '', style) for _, label, color, style in POLICIES]
    handles = [policies[0], _handle('无人工审核', 'gray', 'o', 'None'),
               policies[1], _handle('全面人工审核', 'gray', 's', 'None'), policies[2]]
    _legend(fig, handles, .88, 3)
    _note(fig, 'H3d 检验无人工审核下「综合等待 − 快速」在 d=2 与 d=10 的期限交互；CI 含 0 不表示直接效果为 0。\n'
          'c 的分母为全部 required inputs，分子为被接受且真实正确的必要输入；它不是已接受消息中的正确率。\n'
          'C_clean 是模拟器生成结果与事后计量的潜在质量指标，不是策略可直接读取的 oracle。\n'
          '全面人工审核固定 capacity=3、scope=all、priority=life_safety、service_time=3；指挥为 distributed。\n'
          '颜色与线型对应政策；圆/方点对应审核；横向微移仅为避让。连线仅连接离散条件。', ci=True)
    return fig


def _monitoring_conclusion(frames):
    directions = dict(frames['fixed_budget'])['service_deficit']['direction']
    if directions.eq('positive').all():
        return '固定检查次数后，较晚监测增加平均功能缺口'
    if directions.eq('negative').all():
        return '固定检查次数后，较晚监测减少平均功能缺口'
    if directions.eq('uncertain').all():
        return '固定检查次数后，时点差异仍不确定'
    return '固定检查次数后，时点效果随比较而异'


def _capacity_conclusion(frames):
    directions = dict(frames['oversight_capacity'])['service_deficit']['direction']
    if directions.eq('positive').any() and directions.eq('negative').any():
        return '审核容量曲线中同时出现净损害与净收益'
    if directions.eq('positive').all():
        return '各档审核容量均增加净损失，增容未消除全部成本'
    if directions.eq('negative').all():
        return '各档审核容量均减少净损失，排队负担仍需披露'
    return '审核容量改变排队约束，净效果存在不确定性'


def _function_effects(ax, pairs, labels):
    rows = [(metric, frame) for metric, frame in pairs if metric in {f'F{i}' for i in range(1, 8)}]
    values = np.column_stack([frame['value'] for _, frame in rows])
    intervals = np.stack([frame[['ci_low', 'ci_high']].to_numpy() for _, frame in rows], axis=1)
    statuses = np.column_stack([frame['status'] for _, frame in rows])
    return _heatmap(ax, values, labels, [metric for metric, _ in rows], intervals=intervals, statuses=statuses)


def _fixed_budget(frames, base, subtitle):
    fig = _figure(5.6, _monitoring_conclusion(frames), subtitle+' · 单次主动检查 · data中心情景')
    gs = fig.add_gridspec(2, 1, left=.22, right=.90, bottom=.22, top=.81, hspace=.78)
    labels = ['middle − early', 'late − early', 'late − middle']
    ax = fig.add_subplot(gs[0]); _panel(ax, 'a', '检测质量相同，比较检查时点')
    _forest(ax, dict(frames['fixed_budget'])['service_deficit'], labels)
    ax.set_xlabel('均值 ΔL（功能关键性 × 抽象 tick）')
    ax = fig.add_subplot(gs[1]); _panel(ax, 'b', '七功能方向：正值表示功能缺口增加')
    im = _function_effects(ax, frames['fixed_budget'], labels)
    cb = fig.colorbar(im, ax=ax, fraction=.025, pad=.04)
    cb.set_label('ΔL_f（抽象 tick）', fontsize=7)
    counts = ', '.join(f'{name}: {row.monitoring_requests:g}' for name, row in
                       zip(('early', 'middle', 'late'), frames['monitoring_levels'].itertuples()))
    _note(fig, '合成情景；时点分别为 release+1、+3、+5；每节点至多一次，超出窗口不补查。\n'
          f'实际每 run 平均检查请求数：{counts}。O0/O1/O2 持续监测另见图5。\n'
          '功能分量使用归一化服务缺口；总 L 使用功能关键性权重。', ci=True)
    return fig


def _capacity(frames, base, subtitle):
    fig = _figure(7.8, _capacity_conclusion(frames), subtitle+' · human − autonomy · A04中心情景')
    gs = fig.add_gridspec(3, 2, left=.12, right=.94, bottom=.19, top=.85,
                         hspace=.72, wspace=.56, height_ratios=[1, 1.45, 1])
    levels = frames['capacity_levels']
    labels = levels['condition'].astype(str).tolist()
    xx = np.arange(len(labels))
    ax = fig.add_subplot(gs[0, :]); _panel(ax, 'a', '相对匹配自主参照的净功能缺口')
    _line(ax, dict(frames['oversight_capacity'])['service_deficit'], xx, 'blue', 'o')
    ax.set_xticks(xx, labels); ax.set_ylabel('均值 ΔL\n（功能关键性 × tick）')
    ax = fig.add_subplot(gs[1, :]); _panel(ax, 'b', 'F1–F7：保留容量配置中的功能取舍')
    im = _function_effects(ax, frames['oversight_capacity'], labels)
    ax.set_ylabel('审核容量')
    cb = fig.colorbar(im, ax=ax, fraction=.018, pad=.025)
    cb.set_label('ΔL_f（tick）', fontsize=7)
    for j, (metric, title, unit) in enumerate((('review_queue_time', '普通排队时间', 'Agent-tick'),
                                            ('completed_reviews', '窗口内完成的审核', '次数'))):
        ax = fig.add_subplot(gs[2, j]); _panel(ax, chr(99+j), title+'（水平）')
        ax.plot(xx, levels[metric], color=PALETTE['blue'], marker='o', ms=3.5, lw=.9)
        ax.set_xticks(xx, labels, rotation=35, ha='right'); ax.set_ylabel(unit); ax.set_ylim(bottom=0)
    _note(fig, '合成情景、抽象 tick；full/all/life_safety，deadline=5，service_time=3；其他条件与 autonomy 相同。\n'
          '各横轴按预定离散档位等距展示；连线不估计连续临界点。unlimited 仅取消容量排队，仍有服务时长。\n'
          'c、d 为均值水平、无 CI；监督拥塞是模型机制，不是现实经验定律。以下符号说明适用于 a、b。', ci=True)
    return fig


def render(frames, output, stage, base):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    # N is read from the supplied result rows, including table-only re-rendering.
    n = int(frames['human']['n_runs'].iloc[0])
    subtitle = f'{stage.capitalize()} · N={n}/config · 95% bootstrap CI'
    styles = {
        'font.family': [chinese_font()], 'font.size': 8,
        'axes.unicode_minus': True, 'axes.labelsize': 8, 'axes.titlesize': 8.8,
        'xtick.labelsize': 7.4, 'ytick.labelsize': 7.4, 'legend.fontsize': 7.4,
        'axes.linewidth': .65, 'axes.edgecolor': PALETTE['gray'], 'axes.grid': False,
        'lines.linewidth': .9, 'figure.facecolor': 'white', 'savefig.facecolor': 'white',
    }
    with plt.rc_context(styles):
        for name, renderer in zip(TITLES, (_overview, _architecture, _position, _dependency,
                                          _isolation, _review, _triage, _information, _fixed_budget, _capacity)):
            fig = renderer(frames, base, subtitle)
            if stage != 'formal' and renderer not in (_overview, _architecture):
                # Formal takeaways do not become claims about a different sample.
                fig.texts[0].set_text({
                    _position: '位置与同规模公共功能损失', _dependency: '共同依赖：均值与尾部的预先规定比较',
                    _isolation: '观察阶段与隔离：效果及治理负担', _review: '审核与指挥：处理能力和时限',
                    _triage: '任务分诊：总量与功能分解', _information: '信息政策：直接效果与期限交互',
                    _fixed_budget: '固定预算监测：三个时点的配对比较', _capacity: '审核容量：配对效果与监督拥塞诊断',
                }[renderer])
            fig.savefig(output / (name+'.png'), dpi=300)
            plt.close(fig)


def write_report(frames, output, runs_per_cell, repetitions, stage):
    output = Path(output)
    lines = [
        f'# 合成情景 {stage.capitalize()} 结果与数值诊断', '',
        f'每个去重配置运行 {runs_per_cell} 次；共 {frames["config_count"]} 个配置；{repetitions} 次诊断重抽样。',
        f'本报告记录 {stage.capitalize()} 的模拟结果与数值诊断，不作政策方向验收。',
        '理论与情景有效性依据设计文件；实现验证与极端条件由测试验证；尚无现实经验校准。',
        '30个Agent、79条边和七项功能是机制研究用的合成网络，不是郑州真实政府组织结构复刻；模拟频率不是现实发生概率。',
        '主量、七项功能分解和评价敏感性全部见 tables/effects.csv；诊断量不合成为福利分数。',
        '位置的全部已观察支持层见 tables/position_strata.csv；点和区间分别保留 defined / undefined。',
        '95% bootstrap CI 为固定合成模型与预先规定抽样规则下的 pointwise 模拟区间，不表示模型结构、参数或现实政策效果的不确定性已被识别。',
        'level 行中的 `not_computed` 表示未计算置信区间，而不是没有点估计或模拟失败。',
        '限制：一次响应任务、单一业务拓扑、简化补充检查、健康指挥零误拒绝、线性服务映射。',
        '主结果的效应、零结果、反向和不确定均保留；未依据结果调整参数、随机种子或切片。', '',
    ]
    lines.extend([_monitoring_conclusion(frames) + '；' + _capacity_conclusion(frames) + '。',
        '这两项补充仍分别属于RQ2与RQ3；其结果不升级为新增研究问题或替换原有主比较。', ''])

    def ci_text(row):
        return f'[{row.ci_low:.8g}, {row.ci_high:.8g}]' if np.isfinite([row.ci_low, row.ci_high]).all() else 'undefined'

    for main in (True, False):
        lines.extend(['## ' + ('主视图：注册主量及七项功能' if main else '评价敏感性：同一轨迹重算'), '',
            '| 主量 | 统计量 | 评分视图 | 指标 / 单位 | 数值 | 95% CI | direction | 点状态 | 区间状态 | 追溯 ID |',
            '|---|---|---|---|---:|---|---|---|---|---|'])
        for r in frames['position'][frames['position']['view'].eq('primary') == main].itertuples():
            value = f'{r.value:.8g}' if np.isfinite(r.value) else 'undefined'
            sign = direction(r.ci_low, r.ci_high) if r.ci_status == 'defined' else 'undefined'
            lines.append(f'| RQ1 / H1a：位置增量 R² | crossfit | {r.view} | 增量 R² / 无量纲 | {value} | {ci_text(r)} | {sign} | {r.status} | {r.ci_status} ({r.bootstrap_valid}/{r.bootstrap_requested}; {r.reason}) | position.csv |')
        for r in frames['primary'][frames['primary']['view'].eq('primary') == main].itertuples():
            metric = r.metric + ('（总 L 尾部贡献）' if r.tail_component else '')
            lines.append(f'| {r.label} | {r.statistic} | {r.view} | {metric} / {_metric_unit(r.metric)} | {r.value:.8g} | {ci_text(r)} | {r.direction} | {r.status} | {r.status} | {r.estimand_id[:12]} |')
        lines.append('')

    def effect_table(pairs):
        lines.extend(['| 比较 | 指标 / 单位 | 数值 | 95% CI | direction | 追溯 ID |',
                      '|---|---|---:|---|---|---|'])
        for metric, frame in pairs:
            for r in frame.itertuples():
                label = r.label.replace('\n', ' / ')
                title = metric + ('（总L尾部贡献）' if r.tail_component else '')
                lines.append(f'| {label} | {title} / {_metric_unit(metric)} | {r.value:.8g} | {ci_text(r)} | {r.direction} | {r.estimand_id[:12]} |')
        lines.append('')

    def level_table(frame, metrics):
        lines.extend(['| 条件 | ' + ' | '.join(metrics) + ' | cell ID |',
                      '|---|' + '---:|' * len(metrics) + '---|'])
        for _, row in frame.iterrows():
            values = ' | '.join(f'{row[metric]:.8g}' for metric in metrics)
            lines.append(f'| {row["condition"]} | {values} | {row["cell_id"][:12]} |')
        lines.append('')

    settings = frames['settings']
    lines.extend(['## RQ2补充：检测次数受控时的监测时点', '',
        '原O0/O1/O2比较的是前移持续监测窗口的整体政策效果，前移还改变累计检查及误报机会，不能单独识别等预算的纯时点作用。',
        f'本补充固定中心data同期冲击、自动隔离开启；检测概率={settings["detection_probability"]:g}、误报率={settings["false_alarm_probability"]:g}，三组相同。',
        'early、middle、late分别在节点release+1、+3、+5主动检查一次，不要求先形成方案或完成行动。超出horizon不补查、不移至窗口末。',
        '三组使用同一节点、同一run的潜在一次检测/误报随机数。状态随检查时点变化，因此共享随机数不意味着真检测数相同。',
        '预先规定middle−early、late−early、late−middle；均值ΔL为本补充的主要输出，ES95及功能尾部贡献为次级。单位均为抽象tick下的合成服务缺口。', '',
        '三组水平（condition为release后的tick数；计数为每run均值；level不计算CI）：', ''])
    level_table(frames['monitoring_levels'], ['service_deficit', 'worst_function_deficit', 'monitoring_requests',
        'true_detections', 'false_isolations', 'ever_compromised_count', 'wrong_actions'])
    lines.extend(['均值差：正值表示对应缺口或计数增加；七项功能缺口乘其主关键性权重后重建ΔL。', ''])
    effect_table(frames['fixed_budget'])
    lines.extend(['次级ES95：各分布尾部均值之差；功能项使用各cell总L同一尾部，不是各功能自己的ES95。', ''])
    effect_table(frames['fixed_budget_tail'])
    lines.extend(['![固定预算监测](figures/09_fixed_budget_monitoring.png)', '',
        '允许解释为本固定检测预算下的时点效应；不能等同于持续监测政策，更不是现实检测或隔离政策的因果估计。', '',
        '## RQ3补充：审核容量与监督拥塞', '',
        f'固定A04、无资源冲击、full/all/life_safety、deadline_window=5、review_service_time=3，审核灵敏度={settings["review_sensitivity"]:g}、特异度={settings["review_specificity"]:g}；其他条件取中心值，指挥为distributed。',
        '全部容量使用同一外生情景的autonomy参照和run-index配对；共享参照只保留一个物理配置。unlimited仅消除容量排队，仍需完整服务时长。',
        '“监督拥塞”指响应窗口内监督需求超过处理能力，审核可能减少错误行动，却通过排队和延期造成新的公共功能损失。这是模型提出的机制性概念，尚未经现实经验验证。', ''])
    capacity = dict(frames['oversight_capacity'])['service_deficit']
    caps = frames['capacity_levels']['condition'].astype(str).tolist()
    for sign, title in (('positive', '净损害（CI全正）'), ('negative', '净收益（CI全负）'), ('uncertain', '净效果不确定（CI含0）')):
        labels = [cap for cap, row in zip(caps, capacity.itertuples()) if row.direction == sign]
        lines.append(f'{title}的离散容量：' + ('、'.join(labels) if labels else '未出现') + '。')
    if not capacity['direction'].isin(['positive', 'negative', 'uncertain']).all():
        lines.append('另有未定义或结构性零结果，按表中状态保留，不补值。')
    monotone = np.all(np.diff(capacity['value']) <= 0)
    lines.extend(['该网格的ΔL点估计' + ('随容量非增' if monotone else '没有呈现随容量非增的单调关系') + '；这不是连续容量定律。',
        '下表相邻变化仅为点估计描述，不附加新的显著性检验；正的下降量表示增容后L降低。用于检查过载、过渡和边际收益减弱，不强行命名临界点。', '',
        '| 容量区间 | ΔL下降量（前档−后档） |', '|---|---:|'])
    for i in range(1, len(caps)):
        lines.append(f'| {caps[i-1]} → {caps[i]} | {capacity["value"].iloc[i-1] - capacity["value"].iloc[i]:.8g} |')
    lines.extend(['', '审核/排队水平：完成只计t<horizon的决定；普通队列为Agent-tick，加权队列为分层权重×Agent-tick。', ''])
    levels = pd.concat([frames['capacity_reference'], frames['capacity_levels']], ignore_index=True)
    level_table(levels, ['human_review_load', 'completed_reviews', 'review_queue_time', 'critical_review_queue_time',
                         'unfinished_tasks', 'deadline_misses', 'false_review_denials', 'wrong_actions'])
    lines.extend(['互斥阻塞分解水平（Agent-tick）：这些是记账归因，不是独立可加的政策因果贡献。', ''])
    level_table(levels, ['information_blocking', 'review_blocking', 'denial_blocking', 'command_blocking', 'isolation_blocking'])
    lines.extend(['全部human−autonomy差及七功能方向：', ''])
    effect_table(frames['oversight_capacity'])
    lines.extend(['![审核容量曲线](figures/10_oversight_capacity.png)', '',
        '如出现净损害与净收益，仅在已计算的离散容量间定位变化；CI含0的容量保留不确定，不插值推断现实编制或精确阈值。人工监督既非必然有益，也非必然有害。', '',
        '## 非补偿性风险与完整功能向量', '',
        '`worst_function_deficit`先在每run取max(F1,…,F7)，再求均值及配对差，单位为归一化服务缺口×抽象tick。它不乘功能关键性，也不等于max(E[F1],…,E[F7])。',
        '该次级结果来自与L相同的raw积分，未增加模拟或改变评分；不能替换主L。fixed-budget与capacity的该指标及功能方向已列于上表。',
        '以下保留所有规定的共同依赖/partition及分诊对比；表格单元格为点估计 [95% CI]。F1–F7为功能缺口差，最后一列为最大单项缺口差。',
        'life_safety的总L改善只表示预定价值权重下的改善；须同时看F1/F2等基础信息和非生命安全功能是否被挤压，不能称为普遍最优治理。', ''])
    for purpose, pairs in frames['function_vectors'].items():
        lines.extend(['### ' + ('共同依赖及partition' if purpose == 'dependency' else 'life_safety / due_first 相对FIFO'), '',
            '| 比较 | ' + ' | '.join(metric for metric, _ in pairs) + ' |',
            '|---|' + '---|' * len(pairs)])
        for i, label in enumerate(pairs[0][1]['label']):
            entries = [f'{frame.iloc[i]["value"]:.8g} {ci_text(frame.iloc[i])}' for _, frame in pairs]
            lines.append('| ' + label.replace('\n', ' / ') + ' | ' + ' | '.join(entries) + ' |')
        lines.append('')
    lines.extend(['本研究未验证4R/TIL等课程框架；位置ΔR²是合成场景中的预测增量，不是现实因果效应。',
        '复现信息和产物哈希见run-info.json；报告数值来自三张CSV，同一生成路径适用于Smoke、Pilot和Formal。', ''])
    (output / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
