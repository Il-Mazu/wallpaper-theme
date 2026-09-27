import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import wallpaper_theme as w


class ThemeTests(unittest.TestCase):
    def test_selection_contrast(self):
        for color in ['#ffff00', '#ffffff', '#57ade6', '#00ff00', '#ff0000', '#000000']:
            self.assertGreaterEqual(1.05 / (w.luminance(w.selection(color)) + 0.05), 4.5)

    def test_saturated_region_beats_black_background(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'preview.png'
            image = Image.new('RGB', (100,100), '#050505')
            image.paste('#0088dd', (0,0,40,100))
            image.save(path)
            red, green, blue = w.rgb(w.extract(path))
            self.assertGreater(blue, green)
            self.assertGreater(green, red)

    def test_grayscale_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'preview.png'
            Image.new('RGB', (10,10), '#888888').save(path)
            self.assertEqual(w.extract(path), '#8da9bd')

    def test_preview_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / 'project.json').write_text('{"preview":"../outside.png"}')
            with self.assertRaises(ValueError):
                w.resolve({'plugin':'com.github.catsout.wallpaperEngineKde', 'source':f'file:{folder}/scene.json+scene'})

    def test_palette_preserves_semantic_colors(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(w, 'DATA', Path(directory)):
            w.write_scheme('#57ade6')
            generated = w.parser(Path(directory) / 'color-schemes/WallpaperAdaptive.colors')
            base = w.parser('/usr/share/color-schemes/BreezeDark.colors')
            self.assertEqual(generated['Colors:View']['ForegroundNegative'], base['Colors:View']['ForegroundNegative'])
            self.assertNotEqual(generated['Colors:View']['BackgroundNormal'], generated['Colors:Window']['BackgroundNormal'])

    def test_invalid_override_rejected(self):
        for value in ['red', '#123', '; echo nope', '#zzzzzz']:
            with self.assertRaises(ValueError):
                w.rgb(value)


if __name__ == '__main__':
    unittest.main()
