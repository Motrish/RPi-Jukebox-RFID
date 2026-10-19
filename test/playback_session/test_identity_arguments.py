import unittest
from components.playback_session.execution_gate import ExecutionGate
from jukebox.contracts import ContractValidationError


class TestExecutionGate(unittest.TestCase):

    def test_invalid_boot_constructor(self):
        invalid_values = [None, True, [], {}, "", "bad id"]
        for value in invalid_values:
            with self.assertRaises(ContractValidationError):
                ExecutionGate(boot_id=value)

    def test_reserve_start_with_invalid_values(self):
        gate = ExecutionGate(boot_id="boot_one")
        before = gate.snapshot()
        invalid_values = [None, True, [], {}, "", "bad id"]
        for value in invalid_values:
            with self.assertRaises(ContractValidationError):
                gate.reserve_start(entry_id=value)
            self.assertEqual(gate.snapshot(), before)

    def test_reserve_start_with_valid_and_invalid_values(self):
        gate = ExecutionGate(boot_id="boot_one")
        gate.reserve_start("valid_entry")
        before = gate.snapshot()
        invalid_values = [None, True, [], {}, "", "bad id"]
        for value in invalid_values:
            with self.assertRaises(ContractValidationError):
                gate.reserve_start(entry_id=value)
            self.assertEqual(gate.snapshot(), before)


if __name__ == '__main__':
    unittest.main()
