import unittest

from bot.discovery.adb_discovery import (
    BindingCandidate,
    build_bindings_template,
    filter_candidates,
    parse_adb_devices_output,
    parse_memuc_adb_shell_output,
    parse_memuc_listvms_output,
)


class AdbDiscoveryParserTests(unittest.TestCase):
    def test_parse_adb_devices_output(self) -> None:
        devices = parse_adb_devices_output(
            "\n".join(
                [
                    "List of devices attached",
                    "127.0.0.1:23533        device product:SM-S908B model:SM_S908B device:SM-S908B transport_id:234",
                ]
            )
        )

        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].serial, "127.0.0.1:23533")
        self.assertEqual(devices[0].model, "SM_S908B")
        self.assertEqual(devices[0].port, 23533)

    def test_parse_memuc_listvms_output(self) -> None:
        vms = parse_memuc_listvms_output(
            "\n".join(
                [
                    "202,11JP - 202H AI,0,0,0",
                    "203,11JP - 203H AI,591336,1,14536",
                ]
            )
        )

        self.assertEqual(len(vms), 2)
        self.assertFalse(vms[0].is_running)
        self.assertTrue(vms[1].is_running)
        self.assertEqual(vms[1].process_id, 14536)

    def test_parse_memuc_adb_shell_output(self) -> None:
        adb_serial, android_serial = parse_memuc_adb_shell_output(
            "already connected to 127.0.0.1:23533\n\n56175161\n"
        )

        self.assertEqual(adb_serial, "127.0.0.1:23533")
        self.assertEqual(android_serial, "56175161")

    def test_build_bindings_template_empty(self) -> None:
        template = build_bindings_template([])

        self.assertEqual(template, "# No fully-resolved bindings were found.")

    def test_filter_candidates_by_index_and_name(self) -> None:
        candidates = [
            BindingCandidate(
                vm_index=203,
                vm_name="11JP - 203H AI",
                process_id=14536,
                hwnd=591336,
                window_title="11JP - 203H AI",
                adb_serial="127.0.0.1:23533",
                adb_state="device",
                android_serial="56175161",
                model="SM_S908B",
                device="SM-S908B",
                product="SM-S908B",
            ),
            BindingCandidate(
                vm_index=204,
                vm_name="11JP - 204",
                process_id=0,
                hwnd=None,
                window_title=None,
                adb_serial=None,
                adb_state=None,
                android_serial=None,
                model=None,
                device=None,
                product=None,
            ),
        ]

        filtered = filter_candidates(candidates, vm_index=203, name_contains="AI")

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].adb_serial, "127.0.0.1:23533")


if __name__ == "__main__":
    unittest.main()
