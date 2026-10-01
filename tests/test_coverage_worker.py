from service.data_coverage.worker import CoverageWorker


class RecoveryRepository:
    def __init__(self):
        self.orphan_recoveries = 0
        self.worker = None

    def recover_orphaned(self):
        self.orphan_recoveries += 1
        return 2

    def recover_stale(self, _seconds):
        return 0

    def claim_next(self, _worker_id):
        self.worker.stop()
        return None


def test_coverage_worker_recovers_orphans_before_claiming_new_work():
    repository = RecoveryRepository()
    worker = CoverageWorker(repository, worker_id="auditor-test", poll_interval=0)
    repository.worker = worker

    worker.run_forever()

    assert repository.orphan_recoveries == 1
    assert worker.worker_id == "auditor-test"
