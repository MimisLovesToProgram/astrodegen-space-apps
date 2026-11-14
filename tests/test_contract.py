"""The published handoff must match implemented validation behavior."""

import unittest

from ingest_validate.contract import CONTRACT_VERSION, history_handoff, observation_contract
from ingest_validate.validation import NUMERIC_RULES


class ContractTests(unittest.TestCase):
    def test_contract_matches_the_validator(self):
        contract = observation_contract()
        self.assertEqual(contract["contract_version"], CONTRACT_VERSION)
        for metric, rule in NUMERIC_RULES.items():
            self.assertEqual(contract["metrics"][metric]["unit"], rule[0])
            self.assertEqual(contract["metrics"][metric]["minimum"], rule[1])
            self.assertEqual(contract["metrics"][metric]["maximum"], rule[2])

    def test_history_envelope_preserves_observations(self):
        observations = [{"metric": "spo2", "value": 97}]
        result = history_handoff("a", observations, 250)
        self.assertEqual(result["observations"], observations)
        self.assertEqual(result["order"], "newest_first")
        self.assertFalse(result["may_be_truncated"])
