import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from tvlib import appstore, samsung

CONFIG = ('<widget xmlns:tizen="http://tizen.org/ns/widgets">'
          '<tizen:application id="AbC123.Jellyfin" package="AbC123" '
          'required_version="2.3"/></widget>')


def _wgt(d: Path) -> Path:
    p = d / "x.wgt"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("config.xml", CONFIG)
    return p


class CatalogTests(unittest.TestCase):
    def test_jellyfin_for_both_vendors(self):
        for v in ("samsung", "lg"):
            self.assertEqual([a["id"] for a in appstore.catalog(v)], ["jellyfin"])

    def test_unknown_app_rejected(self):
        with self.assertRaises(appstore.AppStoreError):
            appstore.resolve("netflix", "samsung")

    def test_bundled_copy_preferred(self):
        with tempfile.TemporaryDirectory() as d:
            pre = Path(d) / "samsung-jellyfin.wgt"
            pre.write_bytes(b"x")
            with mock.patch.object(appstore, "bundled_dir", return_value=Path(d)), \
                 mock.patch.object(appstore, "_download") as dl:
                self.assertEqual(appstore.resolve("jellyfin", "samsung"), pre)
                dl.assert_not_called()

    def test_lg_download_checks_sha256(self):
        man = {"ipkUrl": "a.ipk", "ipkHash": {"sha256": "0" * 64}}
        with tempfile.TemporaryDirectory() as d, \
             mock.patch.object(appstore, "bundled_dir", return_value=Path(d) / "none"), \
             mock.patch.object(appstore, "_lg_manifest", return_value=man), \
             mock.patch.object(appstore, "_download",
                               side_effect=lambda u, p: p.write_bytes(b"bad") or p):
            with self.assertRaises(appstore.AppStoreError):
                appstore.resolve("jellyfin", "lg", Path(d))


class SamsungInstallTests(unittest.TestCase):
    def test_reads_app_id(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(samsung.wgt_app_id(_wgt(Path(d))), "AbC123.Jellyfin")

    def _run(self, install_out):
        calls = []

        def fake(*args, timeout=0):
            calls.append(args)
            if args[0] == "capability":
                return "sdk_toolpath:/opt/usr/home/owner/share/tmp/sdk_tools\n"
            if args[:2] == ("shell", "0"):
                return install_out
            return ""
        with tempfile.TemporaryDirectory() as d, \
             mock.patch.object(samsung, "sdb_path", return_value="sdb"):
            s = samsung.Samsung("10.0.0.5")
            with mock.patch.object(s, "_dev", side_effect=fake):
                s.install(str(_wgt(Path(d))))
        return calls

    def test_push_then_vd_appinstall(self):
        calls = self._run("spend time for pkgcmd is [1200]ms\ncmd_ret:0")
        remote = "/opt/usr/home/owner/share/tmp/sdk_tools/x.wgt"
        self.assertEqual(calls[1][0], "push")
        self.assertEqual(calls[1][2], remote)
        self.assertEqual(calls[2], ("shell", "0", "vd_appinstall", "AbC123.Jellyfin", remote))

    def test_failure_in_output_raises(self):
        with self.assertRaises(samsung.SamsungError):
            self._run("app_id[AbC123.Jellyfin] install failed[118, -12] Invalid certificate chain\ncmd_ret:0")


if __name__ == "__main__":
    unittest.main()
