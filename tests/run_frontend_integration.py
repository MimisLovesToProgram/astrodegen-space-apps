"""Run the Dart client against an isolated PocketBase and Python worker."""

import json
import os
import subprocess
import tempfile
import threading
from pathlib import Path

from test_pocketbase import PocketBaseTests
from assessment_fixtures import sample_policy
from astrocrates import report_processed


def main():
    binary = os.environ.get('POCKETBASE_TEST_BINARY')
    flutter = os.environ.get('FLUTTER_TEST_BINARY')
    if not binary or not flutter:
        raise SystemExit('Set POCKETBASE_TEST_BINARY and FLUTTER_TEST_BINARY to local executables.')
    PocketBaseTests.setUpClass()
    stop = threading.Event()
    errors = []
    thread = None
    try:
        case = PocketBaseTests(methodName='test_checkin_is_durable_owned_and_idempotent')
        case.setUp()
        _, _, _, password = case.crew_login()
        policy = sample_policy()
        policy.update(source='crew_checkin', purpose='team_defined', simulation_only=False)
        for domain in policy['domains'].values():
            domain['rules'][0].update(metric='mood', operator='lte', threshold=2)

        def worker():
            while not stop.is_set():
                try:
                    result = case.worker.process_pending()
                    if result['packet_ids']:
                        report_processed(case.worker, result, policy, run_assessment=True)
                except Exception as error:
                    errors.append(type(error).__name__)
                    return
                stop.wait(.05)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        # We pass ephemeral test credentials through a private file instead
        # of putting passwords in command arguments or committed fixtures.
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json') as settings:
            os.chmod(settings.name, 0o600)
            json.dump({'ASTROCRATES_INTEGRATION_URL': case.url,
                       'ASTROCRATES_INTEGRATION_USERNAME': 'crew_a',
                       'ASTROCRATES_INTEGRATION_PASSWORD': password}, settings)
            settings.flush()
            subprocess.run([flutter, 'test', 'test/crew_live_test.dart',
                            '--dart-define-from-file=' + settings.name],
                           cwd=Path(__file__).resolve().parents[1] / 'src/app_frontend', check=True)
        if errors:
            raise RuntimeError('Integration worker failed: ' + ', '.join(errors))
    finally:
        stop.set()
        if thread is not None:
            thread.join(timeout=10)
        PocketBaseTests.doClassCleanups()


if __name__ == '__main__':
    main()
