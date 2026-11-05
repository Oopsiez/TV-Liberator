"""Offline tests: no TV and no network required."""
import unittest

from tvlib import lg, netguard, privacy, updates


class TestNetGuard(unittest.TestCase):
    def setUp(self):
        cfg = netguard.GuardConfig(
            profiles=["youtube", "jellyfin", "time-and-net"])
        self.g = netguard.DNSGuard(cfg)

    def test_allows_youtube(self):
        self.assertTrue(self.g._is_allowed("www.youtube.com"))
        self.assertTrue(self.g._is_allowed("youtubei.googleapis.com"))

    def test_blocks_vendor_telemetry(self):
        for d in ("samsungads.com", "lgsmartad.com", "nmetrics.samsung.com",
                  "ad.lgappstv.com"):
            self.assertFalse(self.g._is_allowed(d), d)

    def test_blocks_firmware_update_hosts(self):
        for d in ("samsungotn.net", "rdx2.lgtvsdp.com", "lgeapi.com"):
            self.assertFalse(self.g._is_allowed(d), d)

    def test_default_deny_unknown(self):
        self.assertFalse(self.g._is_allowed("some-random-tracker.example.com"))

    def test_denylist_beats_allow_profile(self):
        # a denylisted host must stay blocked even if a profile would allow it
        self.g.cfg.extra_allow = ["samsungads.com"]
        self.assertFalse(self.g._is_allowed("samsungads.com"))

    def test_subdomain_matching(self):
        self.assertTrue(self.g._is_allowed("foo.bar.youtube.com"))
        self.assertFalse(self.g._is_allowed("evil-youtube.com.attacker.net"))


class TestLGCapability(unittest.TestCase):
    def test_old_webos_rootable(self):
        self.assertEqual(lg.assess_rootability("6.0.0")["tier"], "rootable")

    def test_new_webos_not_rootable(self):
        # the user's 86QNED82AAA is webOS 24
        r = lg.assess_rootability("24.0.0")
        self.assertEqual(r["tier"], "dev-mode-only")

    def test_unknown_version(self):
        self.assertEqual(lg.assess_rootability("")["tier"], "unknown")


class TestPlans(unittest.TestCase):
    def test_samsung_privacy_includes_mic_and_acr(self):
        keys = {p["key"] for p in privacy.samsung_privacy_plan()}
        self.assertIn("voice_recognition", keys)
        self.assertIn("acr_viewing_info", keys)

    def test_lg_privacy_includes_liveplus(self):
        names = {p["name"] for p in privacy.lg_privacy_plan()}
        self.assertIn("live_plus", names)
        self.assertIn("voice_recognition", names)

    def test_update_plan_has_network_layer_for_both(self):
        for vendor in ("samsung", "lg"):
            layers = [x["layer"] for x in updates.plan(vendor)["layers"]]
            self.assertIn("network-guard", layers)
            self.assertIn("native-setting", layers)


if __name__ == "__main__":
    unittest.main()
