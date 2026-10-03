"""Run the protocol's Smoke, Pilot or Formal through one research pipeline."""
import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import subprocess
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


def source_hashes():
    paths = subprocess.check_output(['git', 'ls-files'], cwd=ROOT, text=True).splitlines()
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in paths}


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
    provenance = dict(stage=stage, status='running', started_utc=datetime.now(timezone.utc).isoformat(),
        git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        source_hashes=source_hashes(), design_hash=study.object_hash(design),
        python=sys.version, dependencies={name: version(name) for name in ('numpy', 'pandas', 'matplotlib', 'PyYAML')},
        sampling=sampling, runs_per_cell=runs, master_seed=master, bootstrap_repetitions=repetitions,
        configurations=len(models), workers=workers)
    info = output / 'run-info.json'
    info.write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    study.execute(output, runs, master, workers, models)
    raws = {cell_id: study.load_raw(output / 'raw' / (cell_id + '.npz')) for cell_id in models}
    tables = analyze.analyze(raws, output, repetitions, design, base)
    frames = analyze._presentation(tables, design, base, spec)
    figures.render(frames, output / 'figures', stage, base)
    figures.write_report(frames, output, runs, repetitions, stage)
    if source_hashes() != provenance['source_hashes']:
        raise ValueError('Sources changed during the run; retain outputs and rerun the affected stage')
    provenance.update(status='complete', completed_utc=datetime.now(timezone.utc).isoformat(),
        artifact_hashes={path.relative_to(output).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                         for path in sorted(output.rglob('*')) if path.is_file() and path != info})
    info.write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
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
