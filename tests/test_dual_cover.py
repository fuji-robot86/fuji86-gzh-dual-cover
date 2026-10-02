import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]


class DualCoverTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="dual-cover-test-")
        self.addCleanup(self.scratch.cleanup)
        self.directory = Path(self.scratch.name)
        self.skill = self.directory / "skill"
        shutil.copytree(ROOT / "scripts", self.skill / "scripts")
        shutil.copytree(ROOT / "templates", self.skill / "templates")
        self.script = self.skill / "scripts" / "dual_cover.py"
        self.horizontal = self.directory / "horizontal.png"
        self.square = self.directory / "square.png"
        self.output = self.directory / "combined.png"
        self.state = self.directory / "state.json"
        Image.new("RGB", (1504, 640), "red").save(self.horizontal)
        Image.new("RGB", (640, 640), "blue").save(self.square)

    def cli(self, *arguments, success=True):
        process = subprocess.run(
            [sys.executable, str(self.script), "--state", str(self.state), *map(str, arguments)],
            capture_output=True, text=True,
        )
        if success:
            self.assertEqual(process.returncode, 0, process.stderr)
            return json.loads(process.stdout)
        self.assertNotEqual(process.returncode, 0)
        return process.stderr

    def compose(self, success=True):
        return self.cli("compose", "--horizontal", self.horizontal,
                        "--square", self.square, "--output", self.output, success=success)

    def remember(self, style="mono-sci-fi", success=True):
        return self.cli("remember", "--style", style, "--horizontal", self.horizontal,
                        "--square", self.square, "--output", self.output, success=success)

    def test_composition_has_exact_crops_and_png_format(self):
        result = self.compose()
        with Image.open(self.output) as combined, Image.open(self.horizontal) as left, Image.open(self.square) as right:
            self.assertEqual(combined.size, (2144, 640))
            self.assertEqual(combined.format, "PNG")
            self.assertIsNone(ImageChops.difference(combined.crop((0, 0, 1504, 640)), left).getbbox())
            self.assertIsNone(ImageChops.difference(combined.crop((1504, 0, 2144, 640)), right).getbbox())
        for key, size in (("horizontal", (1504, 640)), ("square", (640, 640))):
            with Image.open(result[key]["preview"]) as preview:
                self.assertEqual(preview.size, size)

    def test_wrong_dimensions_do_not_create_output(self):
        Image.new("RGB", (1503, 640)).save(self.horizontal)
        self.assertIn("expected", self.compose(success=False))
        self.assertFalse(self.output.exists())

    def test_existing_output_is_preserved(self):
        self.compose()
        original = self.output.read_bytes()
        self.assertIn("Output exists", self.compose(success=False))
        self.assertEqual(original, self.output.read_bytes())

    def test_normalize_preserves_aspect_ratio_and_centers_padding(self):
        source, normalized = self.directory / "wide.png", self.directory / "normalized.png"
        Image.new("RGB", (800, 400), "black").save(source)
        self.cli("normalize", "--input", source, "--output", normalized, "--kind", "square")
        with Image.open(normalized) as image:
            self.assertEqual(image.size, (640, 640))
            white = Image.new("RGB", image.size, "white")
            self.assertEqual(ImageChops.difference(image, white).getbbox(), (0, 160, 640, 480))

    def test_state_survives_a_new_process_and_unknown_style_does_not_replace_it(self):
        self.compose()
        self.remember()
        self.assertEqual(self.cli("styles")["last_used"]["style_id"], "mono-sci-fi")
        original = self.state.read_bytes()
        self.remember("missing", success=False)
        self.assertEqual(self.state.read_bytes(), original)

    def test_changed_combined_image_cannot_update_state(self):
        self.compose()
        self.remember()
        original = self.state.read_bytes()
        with Image.open(self.output) as image:
            image.putpixel((20, 20), (0, 0, 0))
            image.save(self.output)
        self.assertIn("does not match", self.remember(success=False))
        self.assertEqual(self.state.read_bytes(), original)

    def test_add_style_copies_reference_without_changing_last_style(self):
        self.compose()
        self.remember()
        original = self.state.read_bytes()
        rules = self.directory / "rules.txt"
        rules.write_text("纯色背景，字体统一黑色。", encoding="utf-8")
        self.cli("add-style", "--id", "flat", "--name", "平面", "--rules-file", rules,
                 "--reference", self.square)
        result = self.cli("styles")
        self.assertEqual({style["id"] for style in result["templates"]}, {"mono-sci-fi", "flat"})
        self.assertEqual(self.state.read_bytes(), original)
        copied = self.skill / "templates" / "flat" / "reference-1.png"
        self.assertEqual(copied.read_bytes(), self.square.read_bytes())
        self.assertIn("Template exists", self.cli("add-style", "--id", "flat", "--name", "重复",
                                                 "--rules-file", rules, success=False))

    def test_transparency_is_composited_onto_background(self):
        Image.new("RGBA", (640, 640), (0, 0, 0, 0)).save(self.square)
        self.compose()
        with Image.open(self.output) as combined:
            self.assertEqual(combined.getpixel((1504, 0)), (255, 255, 255))
        self.remember()


if __name__ == "__main__":
    unittest.main()
