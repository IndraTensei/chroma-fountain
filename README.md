# 🎨 chroma-fountain

> Generate beautiful color palettes from text descriptions, random seeds, or images — zero dependencies.

![Python](https://img.shields.io/badge/python-3.6%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-00b300?style=flat-square)
![Dependencies](https://img.shields.io/badge/dependencies-0-ff69b4?style=flat-square)

**chroma-fountain** is a CLI tool (and Python library) that creates gorgeous color palettes in seconds. Describe a mood, point it at an image, or pick a preset — and get beautifully formatted palettes ready for your next project.

No npm. No pip installs. No API keys. Just pure Python 3.

---

## ✨ Features

- **🎭 Text-to-Color** — Type `"sunset over the ocean"` and get a matching palette
- **🖼️ Image Extraction** — Pull dominant colors from PNG, JPEG, BMP, or GIF images
- **🎲 Random Generation** — Get surprised with beautiful random palettes
- **📋 23 Built-in Presets** — From "autumn-harvest" to "candy-pop"
- **🔗 Color Harmonies** — Generate complementary, triadic, analogous, split-complementary, tetradic, and monochromatic harmonies
- **📤 8 Output Formats** — Terminal, JSON, CSS, SCSS, SVG, CSV, HTML, ASE, PNG
- **🌐 90+ Semantic Keywords** — Understands emotions, nature, materials, and vibes
- **⚡ Zero Dependencies** — Uses only Python standard library
- **🔬 Color Science** — Proper HSL conversion, contrast ratios, and perceptual diversity
- **📦 Usable as a Library** — Import it in your own Python projects
- **📊 Palette Scoring** — Rate palettes on contrast, diversity & colorblind safety with letter grades
- **🔀 Palette Comparison** — Compare two palettes side-by-side with score diffs
- **💬 Interactive Mode** — REPL for iterative palette refinement with save/load/score/compare
- **🔗 Palette Blending** — Blend two text descriptions or palettes with adjustable ratio
- **📦 ASE Export** — Export palettes as Adobe Swatch Exchange files for Photoshop/Illustrator
- **🛡️ Accessibility Report** — WCAG contrast matrix, best pair, and colorblind-safety summary via `--a11y`
- **🎯 Best Contrast Pair** — Find the most readable bg/fg combo in a palette via `--best-contrast`
- **🔍 Search Saved Palettes** — Find saved palettes by name or tag via `--search-saved`
- **🎨 23 Built-in Presets** — From "autumn-harvest" to "candy-pop"

---

## 🚀 Installation

### As a CLI tool
```bash
curl -O https://raw.githubusercontent.com/IndraTensei/chroma-fountain/main/chroma_fountain.py
chmod +x chroma_fountain.py
./chroma_fountain.py "ocean sunset"
```

### As a Python library
```bash
pip install git+https://github.com/IndraTensei/chroma-fountain.git
```

### Clone the repo
```bash
git clone https://github.com/IndraTensei/chroma-fountain.git
cd chroma-fountain
python chroma_fountain.py "cozy cabin"
```

---

## 🖥️ CLI Usage

### Text-based generation
```bash
python chroma_fountain.py "sunset over the ocean"
python chroma_fountain.py "neon cyberpunk nights"
python chroma_fountain.py "autumn forest"
```

### Random palette
```bash
python chroma_fountain.py --random --count 8
```

### Extract from an image
```bash
python chroma_fountain.py --image photo.jpg --count 6
```

### Use a preset
```bash
python chroma_fountain.py --preset neon-nights
python chroma_fountain.py --preset ocean-breeze --count 7
```

### List all presets
```bash
python chroma_fountain.py --list-presets
```

### Color harmony from a base color
```bash
python chroma_fountain.py --harmony "#ff6b6b" --harmony-mode triadic
python chroma_fountain.py --harmony "3498db" --harmony-mode monochromatic
```

### Choose output format
```bash
python chroma_fountain.py "pastel dream" --format json
python chroma_fountain.py "forest" --format css
python chroma_fountain.py "neon" --format svg --output palette.svg
python chroma_fountain.py "cozy" --format html --output preview.html
python chroma_fountain.py "dark mode" --format scss
python chroma_fountain.py "warm sunset" --format csv
```

### Terminal output (default)
```
[██] [██] [██] [██] [██]
 #e85d4a  #f4a261  #2a9d8f  #264653  #e9c46a
```

### Score a palette
```bash
python chroma_fountain.py "sunset" --score
python chroma_fountain.py --preset neon-nights --score
```

### Compare two palettes
```bash
python chroma_fountain.py "sunset" --compare "ocean"
python chroma_fountain.py "forest" --compare "#ff0000,#00ff00,#0000ff"
```

### Interactive mode
```bash
python chroma_fountain.py --interactive
# Type text to generate, 'score' to rate, 'save <name>' to store,
# 'compare <text>' to diff, 'blend <a> <b>' to blend, 'colorblind' to toggle, 'quit' to exit
```

### Blend two palettes
```bash
python chroma_fountain.py --blend sunset ocean
python chroma_fountain.py --blend sunset ocean --blend-ratio 0.3
python chroma_fountain.py --blend sunset ocean --format css
```

### Export to Adobe Swatch Exchange
```bash
python chroma_fountain.py "sunset" --format ase --output palette.ase
python chroma_fountain.py --preset neon-nights --format ase --output neon.ase
```

### Accessibility report (WCAG contrast)
```bash
python chroma_fountain.py "sunset" --a11y
python chroma_fountain.py --preset neon-nights --a11y
```
Prints a contrast matrix between every pair of colors, the WCAG level for each pair (AAA / AA / AA Large / Fail), the single highest-contrast foreground/background pair, and a colorblind-safety summary.

### Best contrast pair only
```bash
python chroma_fountain.py "sunset" --best-contrast
python chroma_fountain.py --preset neon-nights --best-contrast
```
Prints just the most readable background/foreground pair found in the palette.

### Search saved palettes
```bash
python chroma_fountain.py --save brand --tags web,blue
python chroma_fountain.py --search-saved blue
python chroma_fountain.py --search-saved web
```
Searches saved palettes by name or tag (case-insensitive substring match).

---

## 📚 Python Library Usage

```python
from chroma_fountain import generate_from_text, generate_random, format_css

# Generate from text
colors = generate_from_text("tropical sunset", count=5)
print(colors)
# ['#e07a5f', '#f4a261', '#81b29a', '#3d405b', '#f2cc8f']

# Generate random
colors = generate_random(count=6)

# Format as CSS
css = format_css(colors, prefix="brand")
print(css)

# All available functions
from chroma_fountain import (
    generate_from_text,    # Text -> palette
    generate_from_seed,    # String seed -> deterministic palette
    generate_random,       # Random palette
    generate_from_image,   # Image file -> dominant colors
    generate_preset,       # Named preset -> palette
    generate_harmony,      # Color harmony from HEX
    hex_to_rgb, rgb_to_hex, rgb_to_hsl, hsl_to_rgb,  # Conversions
    score_palette,         # Score palette quality (v1.2.0)
    compare_palettes,       # Compare two palettes (v1.2.0)
    blend_palettes,         # Blend two palettes in HSL space (v1.3.0)
    blend_texts,            # Blend two text descriptions (v1.3.0)
    format_ase,             # Export as Adobe Swatch Exchange (v1.3.0)
    best_contrast_pair,     # Highest-contrast bg/fg pair (v1.4.0)
    format_a11y_report,     # WCAG accessibility report (v1.4.0)
    search_saved_palettes,  # Search saved palettes by name/tag (v1.4.0)
)
```

---

## 🎨 Text-to-Color Semantics

chroma-fountain understands **90+ keywords** across several categories:

| Category | Example Keywords |
|----------|-----------------|
| **Nature** | sunset, ocean, forest, lava, snow, coral, sand |
| **Emotions** | happy, calm, romantic, energetic, mysterious |
| **Vibes** | neon, pastel, retro, cyberpunk, gothic, cozy |
| **Materials** | gold, ruby, marble, leather, chrome, wood |
| **Seasons** | autumn, winter, spring, summer |
| **Colors** | crimson, teal, navy, mauve, olive, ivory |

When you type `"vintage sunset over calm ocean"`, the tool blends the semantic meanings of `vintage`, `sunset`, `calm`, and `ocean` to create a cohesive palette.

---

## 🔗 Color Harmonies

Generate mathematically sound color harmonies from any base color:

| Mode | Description |
|------|-------------|
| `complementary` | Base + opposite on the color wheel |
| `analogous` | Three adjacent colors |
| `triadic` | Three evenly spaced (120°) |
| `split-complementary` | Base + two adjacent to complement |
| `tetradic` | Four colors, rectangular on the wheel |
| `monochromatic` | Five shades of the same hue |

```bash
# Get a triadic harmony from a coral base
python chroma_fountain.py --harmony "#ff7f50" --harmony-mode triadic
```

---

## 📤 Output Formats

| Format | Description | Use Case |
|--------|-------------|----------|
| `terminal` | Colored blocks + HEX/RGB/HSL | Quick preview |
| `json` | Structured JSON | API consumption, scripting |
| `css` | CSS custom properties (`:root`) | Web projects |
| `scss` | SCSS variables | Sass projects |
| `svg` | Visual SVG image with swatches | Design mockups |
| `csv` | Comma-separated values | Spreadsheet import |
| `html` | Self-contained HTML preview | Sharing, presenting |
| `png` | PNG image with color swatches | Social media, documentation |
| `ase` | Adobe Swatch Exchange | Photoshop, Illustrator, InDesign |

---

## 🎯 Example Workflows

### Designing a website
```bash
# Generate and export CSS
python chroma_fountain.py "modern professional" --format css --output variables.css
```

### Presenting to a client
```bash
# Generate an HTML preview and open it
python chroma_fountain.py "warm autumn branding" --format html --output preview.html
open preview.html
```

### Building a data visualization
```bash
# Get JSON for programmatic use
python chroma_fountain.py "colorblind friendly" --format json > palette.json
```

### Brand identity exploration
```bash
# Generate SVG for design tools
python chroma_fountain.py "luxury gold minimalist" --format svg --output brand.svg
```

---

## 🛠️ Development

```bash
# Run tests
python -m pytest tests/

# Type checking
mypy chroma_fountain.py

# Lint
ruff check chroma_fountain.py
```

---

## 🤝 Contributing

Contributions are welcome! Here are some ways to help:

- Add more semantic keywords or improve existing ones
- Add more preset palettes
- Improve image color extraction algorithms
- Add new output formats
- Improve tests and documentation

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- Color name definitions inspired by traditional color theory
- HSL conversion algorithms based on CSS Color Level 4 specification
- Deterministic PRNG uses xorshift64 for fast, reproducible results
