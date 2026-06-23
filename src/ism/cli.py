from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from pydantic import ValidationError

from ism.config import load_config
from ism.data.generator import SyntheticGenerator
from ism.data.io import write_documents
from ism.evaluation.reporting import report_from_artifacts
from ism.experiments.ablation import merge_ablation, run_ablation_experiment
from ism.experiments.audit import write_budget_audit, write_condition_audit
from ism.experiments.budgets import (
    DeterministicRepresentationProducer,
    build_budget_matrix,
)
from ism.experiments.compression_audit import run_compression_audit
from ism.experiments.conditions import build_condition_matrix
from ism.inference.factory import build_text_generator
from ism.inference.mock import MockTextGenerator
from ism.inference.pipeline import run_pipeline
from ism.planning import build_execution_plan, estimate_server_requirements
from ism.representation.tokenizer import WhitespaceTokenCounter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ism")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser(
        "validate-config",
        help="validate and print a resolved experiment config",
    )
    validate.add_argument("--config", required=True, type=Path)

    dry_run = subparsers.add_parser(
        "dry-run",
        help="validate config and print the bounded execution plan",
    )
    dry_run.add_argument("--config", required=True, type=Path)

    generate = subparsers.add_parser(
        "generate-synthetic",
        help="generate a bounded synthetic dataset from an experiment config",
    )
    generate.add_argument("--config", required=True, type=Path)
    generate.add_argument("--output", required=True, type=Path)

    mock_run = subparsers.add_parser(
        "run-mock",
        help="run the local CPU inference pipeline with the mock adapter",
    )
    mock_run.add_argument("--config", required=True, type=Path)
    mock_run.add_argument("--output", required=True, type=Path)
    mock_run.add_argument("--batch-size", type=int, default=1)
    mock_run.add_argument("--resume", action="store_true")

    run = subparsers.add_parser(
        "run",
        help="run the inference pipeline with the backend selected in the config",
    )
    run.add_argument("--config", required=True, type=Path)
    run.add_argument("--output", required=True, type=Path)
    run.add_argument("--batch-size", type=int, default=1)
    run.add_argument("--resume", action="store_true")

    run_ablation = subparsers.add_parser(
        "run-ablation",
        help="run experiment 6.1 (Dictionary Ablation) across the configured conditions",
    )
    run_ablation.add_argument("--config", required=True, type=Path)
    run_ablation.add_argument("--output", required=True, type=Path)
    run_ablation.add_argument("--batch-size", type=int, default=1)
    run_ablation.add_argument("--resume", action="store_true")
    run_ablation.add_argument("--doc-offset", type=int, default=0)
    run_ablation.add_argument("--doc-count", type=int, default=None)

    merge_ablation_parser = subparsers.add_parser(
        "merge-ablation",
        help="merge ablation shard outputs into one paired evaluation",
    )
    merge_ablation_parser.add_argument("--config", required=True, type=Path)
    merge_ablation_parser.add_argument("--output", required=True, type=Path)
    merge_ablation_parser.add_argument("--shards", required=True, nargs="+", type=Path)

    compress_audit = subparsers.add_parser(
        "compress-audit",
        help="compress documents only and report ISM structure diagnostics",
    )
    compress_audit.add_argument("--config", required=True, type=Path)
    compress_audit.add_argument("--output", required=True, type=Path)

    audit = subparsers.add_parser(
        "audit-conditions",
        help="build and validate the configured condition matrix locally",
    )
    audit.add_argument("--config", required=True, type=Path)
    audit.add_argument("--output", required=True, type=Path)

    budget_audit = subparsers.add_parser(
        "audit-budgets",
        help="build and validate the configured method-budget matrix locally",
    )
    budget_audit.add_argument("--config", required=True, type=Path)
    budget_audit.add_argument("--output", required=True, type=Path)

    report = subparsers.add_parser(
        "report-run",
        help="render metrics from prediction and condition audit artifacts",
    )
    report.add_argument("--config", required=True, type=Path)
    report.add_argument("--predictions", required=True, type=Path)
    report.add_argument("--condition-audit", required=True, type=Path)
    report.add_argument("--output", required=True, type=Path)

    estimate = subparsers.add_parser(
        "estimate-server",
        help="estimate worst-case GPU time and storage before a server run",
    )
    estimate.add_argument("--config", required=True, type=Path)
    estimate.add_argument("--calls-per-second", required=True, type=float)
    estimate.add_argument("--bytes-per-call", required=True, type=int)
    estimate.add_argument("--approved-gpu-hours", required=True, type=float)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == "validate-config":
            sys.stdout.write(config.stable_json())
            return
        if args.command == "dry-run":
            payload = {
                "config_hash": config.config_hash(),
                "plan": build_execution_plan(config).to_dict(),
            }
            sys.stdout.write(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            )
            return
        if args.command == "generate-synthetic":
            documents = SyntheticGenerator(config.experiment.seed).generate(
                config.dataset.max_documents,
                split=config.experiment.split.value,
            )
            write_documents(args.output, documents)
            payload = {
                "documents": len(documents),
                "output": str(args.output.resolve()),
                "questions": sum(len(item.questions) for item in documents),
            }
            sys.stdout.write(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            )
            return
        if args.command == "run-mock":
            summary = run_pipeline(
                config,
                output_dir=args.output,
                generator=MockTextGenerator(),
                batch_size=args.batch_size,
                resume=args.resume,
            )
            sys.stdout.write(
                json.dumps(
                    summary.__dict__,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
            return
        if args.command == "run":
            summary = run_pipeline(
                config,
                output_dir=args.output,
                generator=build_text_generator(config),
                batch_size=args.batch_size,
                resume=args.resume,
            )
            sys.stdout.write(
                json.dumps(
                    summary.__dict__,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
            return
        if args.command == "run-ablation":
            ablation = run_ablation_experiment(
                config,
                output_dir=args.output,
                generator=build_text_generator(config),
                batch_size=args.batch_size,
                resume=args.resume,
                doc_offset=args.doc_offset,
                doc_count=args.doc_count,
            )
            sys.stdout.write(
                json.dumps(asdict(ablation), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            )
            return
        if args.command == "merge-ablation":
            merged = merge_ablation(
                tuple(args.shards),
                output_dir=args.output,
                run_id=config.experiment.name,
                seed=config.experiment.seed,
            )
            sys.stdout.write(
                json.dumps(asdict(merged), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            )
            return
        if args.command == "compress-audit":
            audit = run_compression_audit(
                config,
                output_dir=args.output,
                generator=build_text_generator(config),
            )
            sys.stdout.write(
                json.dumps(asdict(audit), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            )
            return
        if args.command == "audit-conditions":
            documents = SyntheticGenerator(config.experiment.seed).generate(
                config.dataset.max_documents,
                split=config.experiment.split.value,
            )
            matrix = build_condition_matrix(
                documents,
                conditions=tuple(config.conditions),
                budget=config.compression.budget,
                seed=config.experiment.seed,
                tokenizer=WhitespaceTokenCounter(),
            )
            write_condition_audit(args.output, matrix)
            payload = {
                "compressions": len(matrix.compressions),
                "inputs": len(matrix.inputs),
                "output": str(args.output.resolve()),
            }
            sys.stdout.write(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            )
            return
        if args.command == "audit-budgets":
            documents = SyntheticGenerator(config.experiment.seed).generate(
                config.dataset.max_documents,
                split=config.experiment.split.value,
            )
            tokenizer = WhitespaceTokenCounter()
            methods = tuple(
                dict.fromkeys(
                    "ism"
                    if condition
                    in {
                        "full_symbol_dict",
                        "symbol_only",
                        "corrupted_dict",
                        "random_symbol",
                        "unseen_swap_dict",
                        "unseen_swap_no_dict",
                    }
                    else condition
                    for condition in config.conditions
                    if condition != "full_context"
                )
            )
            artifacts = build_budget_matrix(
                documents,
                methods=methods,
                budgets=(config.compression.budget,),
                tokenizer=tokenizer,
                tokenizer_revision=config.model.tokenizer_revision,
                max_attempts=config.compression.max_regeneration_attempts,
                producer=DeterministicRepresentationProducer(
                    tokenizer,
                    seed=config.experiment.seed,
                ),
            )
            write_budget_audit(args.output, artifacts)
            payload = {
                "artifacts": len(artifacts),
                "invalid": sum(not item.valid for item in artifacts),
                "output": str(args.output.resolve()),
            }
            sys.stdout.write(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            )
            return
        if args.command == "report-run":
            metrics = report_from_artifacts(
                predictions_path=args.predictions,
                condition_audit_path=args.condition_audit,
                output_dir=args.output,
                run_id=config.experiment.name,
            )
            payload = {
                "conditions": len(metrics),
                "output": str(args.output.resolve()),
            }
            sys.stdout.write(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            )
            return
        if args.command == "estimate-server":
            estimate = estimate_server_requirements(
                build_execution_plan(config),
                calls_per_second=args.calls_per_second,
                bytes_per_call=args.bytes_per_call,
                approved_gpu_hours=args.approved_gpu_hours,
            )
            sys.stdout.write(
                json.dumps(
                    estimate.to_dict(),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
            return
        parser.error(f"unsupported command: {args.command}")
    except (OSError, ValueError, ValidationError) as error:
        parser.exit(2, f"error: {error}\n")
