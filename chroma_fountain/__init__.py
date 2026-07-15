"""chroma-fountain — Generate beautiful color palettes from text, images, or random seeds."""
import importlib.util
import os

# Load the root chroma_fountain.py module directly to avoid circular import
_module_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "chroma_fountain.py")
_spec = importlib.util.spec_from_file_location("chroma_fountain_root", _module_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# Re-export everything
generate_from_text = _mod.generate_from_text
generate_from_seed = _mod.generate_from_seed
generate_random = _mod.generate_random
generate_from_image = _mod.generate_from_image
generate_preset = _mod.generate_preset
generate_harmony = _mod.generate_harmony
format_terminal = _mod.format_terminal
format_json = _mod.format_json
format_css = _mod.format_css
format_scss = _mod.format_scss
format_svg = _mod.format_svg
format_csv = _mod.format_csv
format_html = _mod.format_html
format_png = _mod.format_png
format_ase = _mod.format_ase
hex_to_rgb = _mod.hex_to_rgb
rgb_to_hex = _mod.rgb_to_hex
rgb_to_hsl = _mod.rgb_to_hsl
hsl_to_rgb = _mod.hsl_to_rgb
simulate_colorblind = _mod.simulate_colorblind
make_colorblind_safe = _mod.make_colorblind_safe
blend_palettes = _mod.blend_palettes
blend_texts = _mod.blend_texts
save_palette = _mod.save_palette
load_palette = _mod.load_palette
list_saved_palettes = _mod.list_saved_palettes
score_palette = _mod.score_palette
format_score_report = _mod.format_score_report
format_a11y_report = _mod.format_a11y_report
best_contrast_pair = _mod.best_contrast_pair
compare_palettes = _mod.compare_palettes
interactive_mode = _mod.interactive_mode
PRESETS = _mod.PRESETS
SEMANTIC_COLORS = _mod.SEMANTIC_COLORS
__version__ = _mod.__version__

__all__ = [
    "generate_from_text",
    "generate_from_seed",
    "generate_random",
    "generate_from_image",
    "generate_preset",
    "generate_harmony",
    "format_terminal",
    "format_json",
    "format_css",
    "format_scss",
    "format_svg",
    "format_csv",
    "format_html",
    "format_png",
    "format_ase",
    "hex_to_rgb",
    "rgb_to_hex",
    "rgb_to_hsl",
    "hsl_to_rgb",
    "simulate_colorblind",
    "make_colorblind_safe",
    "blend_palettes",
    "blend_texts",
    "save_palette",
    "load_palette",
    "list_saved_palettes",
    "score_palette",
    "format_score_report",
    "format_a11y_report",
    "best_contrast_pair",
    "compare_palettes",
    "interactive_mode",
    "PRESETS",
    "SEMANTIC_COLORS",
    "__version__",
]
