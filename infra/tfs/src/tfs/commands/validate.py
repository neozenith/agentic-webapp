"""`tfs validate` — check every stacks/*/backends/*.config matches the declared
state-layout convention. The expected bucket + prefix are resolved layout-aware
(config.bucket_for / expected_prefix), so validate is correct for both the
multi-project (bucket per env, prefix per stack) and single-project (one bucket,
env in the prefix) layouts."""

import logging
import sys
from argparse import Namespace

from tfs.backends import find_backend_config, parse_backend_config
from tfs.config import VALID_ENVS, bucket_for, expected_prefix, layout_of, load_config, validate_config_shape
from tfs.roots import find_infra_root

log = logging.getLogger(__name__)


def cmd_validate(args: Namespace) -> None:
    infra_root = find_infra_root(override=args.infra_root)
    config_paths = find_backend_config(infra_root)
    if not config_paths:
        log.warning("No stacks/*/backends/*.config files found.")
    config = load_config(infra_root)
    validate_config_shape(config)
    layout = layout_of(config)

    results: dict[str, list[str]] = {}
    for path in config_paths:
        rel = path.relative_to(infra_root)
        results[str(rel)] = []
        env_config = path.stem  # dev / test / prod
        stack_name = path.parts[path.parts.index("stacks") + 1]
        parsed = parse_backend_config(path)

        if env_config not in VALID_ENVS:
            results[str(rel)].append(f"invalid environment '{env_config}' (must be one of {VALID_ENVS})")
            continue

        want_bucket = bucket_for(config, env_config)
        if parsed.get("bucket") != want_bucket:
            results[str(rel)].append(f"bucket = '{parsed.get('bucket')}', expected '{want_bucket}'")

        want_prefix = expected_prefix(stack_name, env_config, layout=layout)
        if parsed.get("prefix") != want_prefix:
            results[str(rel)].append(f"prefix = '{parsed.get('prefix')}', expected '{want_prefix}'")

        if not results[str(rel)]:
            log.info("✅ %s is valid", rel)
        else:
            log.error("❌ %s is invalid: %s", rel, results[str(rel)])

    total_errors = sum(len(v) for v in results.values())
    log.info("Errors: %d", total_errors)
    if total_errors > 0:
        sys.exit(1)
