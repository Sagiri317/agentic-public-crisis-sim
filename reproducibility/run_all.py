"""Run the protocol's Smoke, Pilot or Formal through one research pipeline."""
import argparse
from importlib.metadata import version
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'experiments')]
import study
import analyze
import figures


def temporary_output(path):
    path = Path(path).resolve()
    if path.parent != (ROOT / '.run').resolve():
        raise ValueError('Outputs must be .run/<name> in gitignored .run')
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise ValueError('Refusing to overwrite outputs; use an empty directory')
    return path


def pipeline(stage, output, workers):
    output = temporary_output(output)
    study.validate_python()
    spec = study.protocol()
    base = study.base_config()
    design = study.build_catalog(spec, base)
    models = {cell['id']: study.configuration(cell, base) for cell in design['cells']}
    sampling = spec['sampling']
    runs, master = sampling[stage + '_runs'], sampling['seeds'][stage]
    repetitions = sampling['smoke_bootstrap'] if stage == 'smoke' else sampling['bootstrap_repetitions']
    output.mkdir(parents=True, exist_ok=True)
    run_info = dict(stage=stage, status='running', configurations=len(models),
        runs_per_cell=runs, master_seed=master, bootstrap_repetitions=repetitions,
        bootstrap_seed=sampling['seeds']['bootstrap'], python=sys.version.split()[0],
        dependencies={name: version(name) for name in ('numpy', 'pandas', 'matplotlib', 'PyYAML')},
        threads={name: os.environ.get(name) for name in
                 ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS', 'NUMEXPR_NUM_THREADS')})
    info = output / 'run-info.json'
    info.write_text(json.dumps(run_info, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    study.execute(output, runs, master, workers, models)
    raws = {cell_id: study.load_raw(output / 'raw' / (cell_id + '.npz')) for cell_id in models}
    tables = analyze.analyze(raws, output, repetitions, design, base)
    frames = analyze._presentation(tables, design, base, spec)
    figures.render(frames, output / 'figures', stage, base)
    figures.write_report(frames, output, runs, repetitions, stage)
    run_info['status'] = 'complete'
    info.write_text(json.dumps(run_info, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{stage.capitalize()} complete: {len(models)} configurations × {runs} runs, '
          f'{repetitions} bootstrap repetitions; {output}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument('--smoke', action='store_true')
    actions.add_argument('--pilot', action='store_true')
    actions.add_argument('--formal', action='store_true')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()
    if args.workers <= 0:
        parser.error('workers must be positive')
    stage = 'smoke' if args.smoke else 'pilot' if args.pilot else 'formal'
    pipeline(stage, args.output or ROOT / '.run' / stage, args.workers)


if __name__ == '__main__':
    main()
