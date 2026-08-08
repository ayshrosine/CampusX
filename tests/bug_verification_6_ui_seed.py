#!/usr/bin/env python3
"""Iteration 6 wrapper around the existing focused UI seed/cleanup helpers."""
from pathlib import Path

import bug_verification_5_ui_seed as seed

seed.STATE_PATH = Path("/app/test_reports/bug_verification_6_ui_seed.json")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()
    if args.cleanup:
        seed.cleanup()
        client, db = seed.db_client()
        try:
            db.maintenance.update_one({"request_id": "mnt_seed_01"}, {"$set": {"photos": [], "status": "In progress", "description": "Spindle vibration during calibration"}})
        finally:
            client.close()
    else:
        seed.setup()